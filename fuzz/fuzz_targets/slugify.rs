//! `slugify` over fuzzed text and configuration.
//!
//! Properties (the `SlugConfig` docs, and the S-properties of `formal/lean/Sanitizers`
//! as #1028 left them):
//!
//! - **S1** on the ASCII path (`allow_unicode = false`, no `safe_chars`): every character
//!   is an ASCII alphanumeric or a character of the separator, and with `lowercase` there
//!   is no upper case (**S5**).
//! - **S2** for a separator with no alphanumeric in it, of any length: the slug starts
//!   and ends with a word character, so there is no leading, trailing or partial
//!   separator (#1028 strips a truncated half), and no separator follows another.
//! - **S3** at most `max_length` bytes when `max_length > 0`, on either path.
//! - **S6** with no truncation and `save_order = false`, no word of the slug is a
//!   stopword, compared case-insensitively (#1028).
//! - `allow_unicode`: no leading or trailing ZWJ/ZWNJ (#711, #1028), none of the 130
//!   circled and squared Latin symbols `Alphabetic` used to let through in any word
//!   (#1028; the separator is the caller's, inserted as given, and may carry one), and the
//!   NFC and NFD spellings of the input give one slug (#477, and #1028's
//!   compose-after-lowercase), numeric entities included.
//! - **Idempotence** without stopwords or truncation, on both paths. Not in general:
//!   truncation can cut a word down to a stopword, as python-slugify's does, and the
//!   Sanitizers model records that as intended. With an empty separator under
//!   `allow_unicode` too, where the words are composed again after they are joined.
//!
//! The shape checks and idempotence assume a separator of ASCII punctuation. A separator
//! is the caller's string, and one made of combining marks joins the word before it on
//! the next pass, which is the caller's doing rather than a property the docs claim.
//! Idempotence also assumes, while entities are decoded, a separator with no `&`: one
//! ending in `&#` before a word of digits spells an entity the next pass decodes.
#![no_main]

use arbitrary::Arbitrary;
use disarm::api::{try_slugify, SlugConfig};
use disarm::ErrorKind;
use disarm_fuzz::{nfc, nfd, text_and, Lang};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum Sep {
    Dash,
    Underscore,
    Dot,
    Empty,
    DoubleDash,
    DashUnderscore,
    Raw(String),
}

#[derive(Debug, Arbitrary)]
struct Opts {
    sep: Sep,
    upper: bool,
    max_length: u8,
    word_boundary: bool,
    save_order: bool,
    stopwords: Vec<String>,
    allow_unicode: bool,
    lang: Lang,
    no_entities: bool,
    safe_chars: String,
}

const JOINERS: [char; 2] = ['\u{200C}', '\u{200D}'];

fn is_enclosed_latin(c: char) -> bool {
    matches!(c as u32, 0x24B6..=0x24E9 | 0x1F130..=0x1F189)
}

fuzz_target!(|data: &[u8]| {
    let Some((s, o)) = text_and::<Opts>(data) else {
        return;
    };
    let sep = match &o.sep {
        Sep::Dash => "-".to_owned(),
        Sep::Underscore => "_".to_owned(),
        Sep::Dot => ".".to_owned(),
        Sep::Empty => String::new(),
        Sep::DoubleDash => "--".to_owned(),
        Sep::DashUnderscore => "-_".to_owned(),
        Sep::Raw(r) => r.clone(),
    };
    let max_length = usize::from(o.max_length % 64);
    let stopwords: Vec<String> = o.stopwords.iter().take(4).cloned().collect();
    let mut config = SlugConfig::new()
        .with_separator(sep.clone())
        .with_lowercase(!o.upper)
        .with_max_length(max_length)
        .with_word_boundary(o.word_boundary)
        .with_save_order(o.save_order)
        .with_stopwords(stopwords.iter())
        .with_allow_unicode(o.allow_unicode)
        .with_entities(!o.no_entities)
        .with_decimal(!o.no_entities)
        .with_hexadecimal(!o.no_entities)
        .with_safe_chars(o.safe_chars.clone());
    if let Some(l) = o.lang.code() {
        config = config.with_lang(l);
    }
    // A raw `lang` the library does not know is refused (the deprecated infallible
    // `slugify` fell back to the default tables): that is the whole check for such an
    // input. Once `config` is accepted, no later call with it can fail.
    let out = match try_slugify(&s, &config) {
        Ok(out) => out,
        Err(e) => {
            assert!(
                config.lang.is_some(),
                "try_slugify failed with no lang: {e}"
            );
            assert_eq!(e.kind(), ErrorKind::InvalidArgument, "{e}");
            return;
        }
    };

    // S3.
    if max_length > 0 {
        assert!(
            out.len() <= max_length,
            "S3: {} > {max_length}: {out:?}",
            out.len()
        );
    }
    if !o.safe_chars.is_empty() {
        return;
    }
    // ASCII punctuation only (see the module docs).
    let plain_sep = sep.chars().all(|c| c.is_ascii_punctuation());

    if o.allow_unicode {
        assert!(
            !out.starts_with(JOINERS) && !out.ends_with(JOINERS),
            "a joiner at the edge of {out:?}"
        );
        // In the words, not the separators: the separator is inserted as given, and one
        // that carries U+24B6 puts it in the slug by the caller's hand, not the input's.
        let words: Vec<&str> = if sep.is_empty() {
            vec![out.as_str()]
        } else {
            out.split(sep.as_str()).collect()
        };
        assert!(
            !words.iter().any(|w| w.chars().any(is_enclosed_latin)),
            "an enclosed Latin symbol kept in {out:?} (separator {sep:?})"
        );
        // The documented property is form invariance (#477), not NFC: the path composes
        // with `compose_str`, which also forms composition exclusions, so
        // `"\u{F51}\u{FB7}"` gives U+0F52, which is not NFC but is what `"\u{F52}"` gives.
        assert_eq!(
            try_slugify(&nfc(&s), &config).expect("an accepted config"),
            try_slugify(&nfd(&s), &config).expect("an accepted config"),
            "NFC and NFD spellings of {s:?} slugify differently"
        );
    } else {
        // S1, S5.
        for c in out.chars() {
            assert!(
                c.is_ascii_alphanumeric() || sep.contains(c),
                "S1: {c:?} in {out:?} from {s:?}"
            );
            if !o.upper && !sep.contains(c) {
                assert!(!c.is_ascii_uppercase(), "S5: upper case in {out:?}");
            }
        }
        // S2.
        if plain_sep && !sep.is_empty() && !out.is_empty() {
            let word_char = |c: Option<char>| c.is_some_and(|c| c.is_ascii_alphanumeric());
            assert!(
                word_char(out.chars().next()) && word_char(out.chars().next_back()),
                "S2: {out:?} starts or ends in a separator ({sep:?})"
            );
            assert!(
                !out.contains(&sep.repeat(2)),
                "S2: doubled separator in {out:?}"
            );
        }
        // S6.
        if max_length == 0 && !o.save_order && plain_sep && !sep.is_empty() {
            for w in out.split(sep.as_str()).filter(|w| !w.is_empty()) {
                assert!(
                    !stopwords
                        .iter()
                        .any(|sw| sw.to_lowercase() == w.to_lowercase()),
                    "S6: stopword {w:?} in {out:?} (stopwords {stopwords:?})"
                );
            }
        }
    }

    // Idempotence without stopwords or truncation.
    let spells_entity = !o.no_entities && sep.contains('&');
    if stopwords.is_empty() && max_length == 0 && plain_sep && !spells_entity {
        assert_eq!(
            try_slugify(&out, &config).expect("an accepted config"),
            out,
            "slugify is not idempotent on {s:?}"
        );
    }

    // A valid slug is unchanged, under the default configuration.
    let default = SlugConfig::new();
    let slug = try_slugify(&s, &default).expect("an accepted config");
    assert_eq!(
        try_slugify(&slug, &default).expect("an accepted config"),
        slug,
        "a slug is not its own slug: {s:?}"
    );
});
