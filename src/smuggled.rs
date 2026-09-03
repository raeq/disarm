//! Layer 1 (pure-Rust core): decode what a smuggled run *spells* (#701).
//!
//! disarm strips the three ASCII-smuggling carriers and, since #700, reports that
//! invisible characters are present. Neither answer tells the caller that the run reads
//! `tracked-by:acct-99213`.
//!
//! Presence and decode are different strengths of evidence. An invisible character can
//! arrive by accident — a copy-paste artefact, a BOM, an editor quirk. A run that decodes
//! to readable text cannot: random damage does not spell words. A successful decode is
//! the one signal in this area that needs no threshold and no policy to interpret.
//!
//! Pure arithmetic on code point values. No table, which matters under #695: this adds
//! nothing to the data section that dominates a wasm build.
//!
//! The three schemes, and the printable-only rule, follow `juriku/untrace`'s
//! `internal/decode`.

/// Which carrier a [`Payload`] was hidden in.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PayloadScheme {
    /// `U+E0020`–`U+E007E`: subtract `0xE0000`, one byte per character.
    TagAscii,
    /// `U+FE00`–`U+FE0F` and `U+E0100`–`U+E01EF`: an index 0–255, one byte per character.
    VariationBytes,
    /// `U+200B` = 0, `U+200C` = 1, MSB first. `U+200D`, `U+2060` and `U+FEFF` separate.
    ZeroWidthBinary,
    /// `%XX` triples, two hex digits each, one byte per triple (#727).
    ///
    /// The fourth scheme on this type rather than a `percent_decode` of its own, for the
    /// reason #727 gives: a decode-for-inspection primitive returns what the escapes
    /// *spelled*, and a substituting decoder hands back a string some callers will
    /// re-emit — repeated decoding is its own vulnerability class. Decoded exactly once:
    /// `%25%32%45` spells `%2E`, and that `text` is the evidence of double-encoding, not
    /// a prompt to decode again.
    ///
    /// **Not fed to the detector.** Unlike the three carriers above, a percent run that
    /// spells readable text is ordinary in any URL. `decode_smuggled` reports it;
    /// `inspect_anomalies` does not.
    PercentEscape,
}

impl PayloadScheme {
    /// The wire name of the scheme, as the bindings and `Finding.detail` report it.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::TagAscii => "tag_ascii",
            Self::VariationBytes => "variation_bytes",
            Self::ZeroWidthBinary => "zero_width_binary",
            Self::PercentEscape => "percent_escape",
        }
    }
}

/// One decoded run.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Payload {
    /// Which carrier the run was hidden in.
    pub scheme: PayloadScheme,
    /// Byte offset of the first carrier character, into the string that was passed in.
    pub start: usize,
    /// Byte offset one past the last carrier character.
    pub end: usize,
    /// Characters the run consumed — **not** bytes decoded, which differ per scheme, and
    /// not strictly carriers either.
    ///
    /// The zero-width scheme counts its `ZWJ`/`WJ`/`BOM` separators, which carry no bit,
    /// and the tag scheme counts a trailing `CANCEL TAG`. `units` is therefore the span's
    /// length in characters: `end - start` measures the same run in bytes.
    pub units: usize,
    /// The decoded bytes, whether or not they form printable text.
    pub bytes: Vec<u8>,
    /// The decoded string, and **only** when the bytes are valid UTF-8 and wholly
    /// printable.
    ///
    /// Left `None` otherwise, deliberately. A run of arbitrary selectors is reported as a
    /// payload of *n* bytes with no decoded string rather than as a bogus one: reporting
    /// a garbage decode would undo the reason a decode is trustworthy in the first place.
    pub text: Option<String>,
}

/// A variation-selector run shorter than this is not reported.
///
/// One selector is the overwhelmingly common legitimate use — `VS16` asking for emoji
/// presentation — and one byte cannot spell anything. Without the floor every
/// `☂\u{FE0F}` in ordinary text is a "payload".
const MIN_VARIATION_RUN: usize = 2;

/// A percent run shorter than this is not reported.
///
/// One `%20` is a URL-escaped space and one byte cannot spell anything; without the floor
/// every escaped path segment is a "payload". Two is the same floor as
/// [`MIN_VARIATION_RUN`], for the same reason.
const MIN_PERCENT_RUN: usize = 2;

/// Decode every smuggled run in `text`, in order of appearance.
///
/// A well-formed emoji subdivision flag is not a payload: `U+1F3F4` + tag letters +
/// `U+E007F` spelling one of the three RGI values is the Scotland flag, not a channel.
/// The allowlist is the stripper's own, borrowed rather than
/// restated — #700 is about exactly that kind of drift.
pub fn decode_smuggled(text: &str) -> Vec<Payload> {
    let chars: Vec<(usize, char)> = text.char_indices().collect();
    let just_chars: Vec<char> = chars.iter().map(|&(_, c)| c).collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        let (offset, ch) = chars[i];
        // A valid subdivision flag is skipped whole, so its tag letters never reach the
        // tag-ascii scan below.
        if let Some(len) = crate::invisibles::subdivision_flag_len(&just_chars[i..]) {
            i += len;
            continue;
        }
        if let Some(p) = scan_tag_ascii(&chars, i, offset) {
            i += p.units;
            out.push(p);
            continue;
        }
        if let Some(p) = scan_variation(&chars, i, offset) {
            i += p.units;
            out.push(p);
            continue;
        }
        if let Some(p) = scan_percent(&chars, i, offset) {
            i += p.units;
            out.push(p);
            continue;
        }
        if let Some((p, consumed)) = scan_zero_width(&chars, i, offset) {
            i += consumed;
            if let Some(p) = p {
                out.push(p);
            }
            continue;
        }
        let _ = ch;
        i += 1;
    }
    out
}

fn finish(
    scheme: PayloadScheme,
    start: usize,
    end: usize,
    units: usize,
    bytes: Vec<u8>,
) -> Payload {
    let text = printable(&bytes);
    Payload {
        scheme,
        start,
        end,
        units,
        bytes,
        text,
    }
}

/// `Some` only for bytes that are valid UTF-8 **and** wholly printable.
///
/// This is what makes a decode evidence rather than a guess, so "printable" has to mean
/// *a reader would see it*, not merely "not a C0 control". Rejecting controls alone was
/// not enough (caught in review on #940): a payload of `U+202E` + `U+200B` is valid UTF-8
/// with no control character in it, and was reported as recovered text that renders as
/// nothing at all — exactly the bogus decode the `None` case exists to avoid.
///
/// The invisible classes are disarm's own predicates rather than a second list, for the
/// reason #700 gives: two copies of a rule are two rules.
fn printable(bytes: &[u8]) -> Option<String> {
    if bytes.is_empty() {
        return None;
    }
    let s = std::str::from_utf8(bytes).ok()?;
    s.chars().all(is_visible).then(|| s.to_owned())
}

/// Whether `c` puts something on the screen.
///
/// The Private Use Area is deliberately **not** excluded: a PUA code point renders as
/// whatever an icon font says, which is a rendering question rather than an invisibility
/// one, and #413 already carves `strip_format` out for exactly that case.
fn is_visible(c: char) -> bool {
    !(c.is_control()
        || crate::invisibles::is_zero_width(c)
        || crate::invisibles::is_variation_selector(c)
        || crate::invisibles::is_default_ignorable_format(c)
        || crate::invisibles::is_tag(c)
        || crate::invisibles::is_noncharacter(c)
        || crate::invisibles::is_invisible_filler(c)
        || crate::scripts::is_bidi_control(c))
}

/// `U+E007F CANCEL TAG` — the terminator, which carries no byte of its own.
const CANCEL_TAG: char = '\u{E007F}';

fn is_tag_byte(ch: char) -> bool {
    matches!(ch, '\u{E0020}'..='\u{E007E}')
}

fn scan_tag_ascii(chars: &[(usize, char)], i: usize, offset: usize) -> Option<Payload> {
    if !is_tag_byte(chars[i].1) {
        return None;
    }
    let mut bytes = Vec::new();
    let mut j = i;
    while j < chars.len() && is_tag_byte(chars[j].1) {
        // Every value in the range is ASCII by construction, so the cast cannot truncate.
        bytes.push((chars[j].1 as u32 - 0xE0000) as u8);
        j += 1;
    }
    // A trailing CANCEL TAG terminates the channel as well as a flag, so it belongs to the
    // run — and the code has to agree with that, or one Tags run is reported as two
    // adjacent spans with the terminator between them (caught in review on #940). It
    // carries no byte, so only the span and `units` grow.
    if chars.get(j).is_some_and(|&(_, c)| c == CANCEL_TAG) {
        j += 1;
    }
    let end = chars
        .get(j)
        .map_or_else(|| offset + tail_len(chars, i, j), |&(o, _)| o);
    Some(finish(PayloadScheme::TagAscii, offset, end, j - i, bytes))
}

/// Byte length of `chars[i..j]`, for the case where the run reaches the end of the string.
fn tail_len(chars: &[(usize, char)], i: usize, j: usize) -> usize {
    chars[i..j].iter().map(|&(_, c)| c.len_utf8()).sum()
}

fn variation_byte(ch: char) -> Option<u8> {
    let cp = ch as u32;
    match cp {
        0xFE00..=0xFE0F => u8::try_from(cp - 0xFE00).ok(),
        0xE0100..=0xE01EF => u8::try_from(cp - 0xE0100 + 16).ok(),
        _ => None,
    }
}

fn scan_variation(chars: &[(usize, char)], i: usize, offset: usize) -> Option<Payload> {
    variation_byte(chars[i].1)?;
    let mut bytes = Vec::new();
    let mut j = i;
    while j < chars.len() {
        match variation_byte(chars[j].1) {
            Some(b) => bytes.push(b),
            None => break,
        }
        j += 1;
    }
    if j - i < MIN_VARIATION_RUN {
        return None;
    }
    let end = chars
        .get(j)
        .map_or_else(|| offset + tail_len(chars, i, j), |&(o, _)| o);
    Some(finish(
        PayloadScheme::VariationBytes,
        offset,
        end,
        j - i,
        bytes,
    ))
}

/// The byte a `%XX` triple at `chars[i]` encodes, if it is well formed.
///
/// `%` followed by fewer than two hex digits is malformed and is not part of any run
/// (#727 item 2): it is left where it is, and a run in progress ends before it.
fn percent_byte(chars: &[(usize, char)], i: usize) -> Option<u8> {
    if chars.get(i)?.1 != '%' {
        return None;
    }
    let hi = chars.get(i + 1)?.1.to_digit(16)?;
    let lo = chars.get(i + 2)?.1.to_digit(16)?;
    u8::try_from(hi * 16 + lo).ok()
}

fn scan_percent(chars: &[(usize, char)], i: usize, offset: usize) -> Option<Payload> {
    percent_byte(chars, i)?;
    let mut bytes = Vec::new();
    let mut j = i;
    while let Some(b) = percent_byte(chars, j) {
        bytes.push(b);
        j += 3;
    }
    if bytes.len() < MIN_PERCENT_RUN {
        return None;
    }
    let end = chars
        .get(j)
        .map_or_else(|| offset + tail_len(chars, i, j), |&(o, _)| o);
    // `printable` gives item 2's first answer for free: `%FF` is not valid UTF-8, so the
    // run is reported as bytes with no `text`, never as a bogus string.
    Some(finish(
        PayloadScheme::PercentEscape,
        offset,
        end,
        j - i,
        bytes,
    ))
}

fn is_zw_separator(ch: char) -> bool {
    matches!(ch, '\u{200D}' | '\u{2060}' | '\u{FEFF}')
}

/// Returns the payload (if the run yielded at least one whole byte) and how many
/// characters to advance past — the run is consumed either way, so a bit-short run is not
/// rescanned character by character.
fn scan_zero_width(
    chars: &[(usize, char)],
    i: usize,
    offset: usize,
) -> Option<(Option<Payload>, usize)> {
    if !matches!(chars[i].1, '\u{200B}' | '\u{200C}') {
        return None;
    }
    let mut bits: Vec<u8> = Vec::new();
    let mut j = i;
    while j < chars.len() {
        match chars[j].1 {
            '\u{200B}' => bits.push(0),
            '\u{200C}' => bits.push(1),
            c if is_zw_separator(c) => {}
            _ => break,
        }
        j += 1;
    }
    let units = j - i;
    // Only whole bytes are decoded. A trailing partial byte is dropped rather than
    // zero-padded: padding invents bits the carrier did not contain.
    let bytes: Vec<u8> = bits
        .as_chunks::<8>()
        .0
        .iter()
        .map(|c| c.iter().fold(0u8, |acc, &b| (acc << 1) | b))
        .collect();
    if bytes.is_empty() {
        return Some((None, units));
    }
    let end = chars
        .get(j)
        .map_or_else(|| offset + tail_len(chars, i, j), |&(o, _)| o);
    Some((
        Some(finish(
            PayloadScheme::ZeroWidthBinary,
            offset,
            end,
            units,
            bytes,
        )),
        units,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Encode `s` as tag characters, the way the channel is actually used.
    fn tags(s: &str) -> String {
        s.chars()
            .map(|c| char::from_u32(c as u32 + 0xE0000).unwrap())
            .collect()
    }

    /// Encode `s` as MSB-first zero-width binary.
    fn zw(s: &str) -> String {
        s.bytes()
            .flat_map(|b| {
                (0..8).map(move |i| {
                    if (b >> (7 - i)) & 1 == 1 {
                        '\u{200C}'
                    } else {
                        '\u{200B}'
                    }
                })
            })
            .collect()
    }

    #[test]
    fn a_tag_run_decodes_to_what_it_spells() {
        let found = decode_smuggled(&format!("hello{}", tags("tracked-by:acct-99213")));
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].scheme, PayloadScheme::TagAscii);
        assert_eq!(found[0].text.as_deref(), Some("tracked-by:acct-99213"));
        assert_eq!(found[0].start, 5, "byte offset of the first carrier");
        assert_eq!(found[0].units, 21);
    }

    #[test]
    fn a_zero_width_run_decodes_to_what_it_spells() {
        let found = decode_smuggled(&format!("hi{}", zw("hi")));
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].scheme, PayloadScheme::ZeroWidthBinary);
        assert_eq!(found[0].text.as_deref(), Some("hi"));
        assert_eq!(found[0].units, 16, "two bytes, eight carriers each");
    }

    #[test]
    fn a_variation_run_decodes_to_what_it_spells() {
        // 'h' = 0x68 = 104 -> U+E0100 + (104 - 16); 'i' = 0x69 = 105.
        let carriers: String = "hi"
            .bytes()
            .map(|b| char::from_u32(0xE0100 + u32::from(b) - 16).unwrap())
            .collect();
        let found = decode_smuggled(&carriers);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].scheme, PayloadScheme::VariationBytes);
        assert_eq!(found[0].text.as_deref(), Some("hi"));
    }

    /// The rule that makes a decode trustworthy: no bogus text, ever.
    #[test]
    fn undecodable_bytes_are_reported_without_a_string() {
        // Two selectors whose bytes are not printable UTF-8.
        let found = decode_smuggled("\u{FE00}\u{FE01}");
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].bytes, vec![0, 1]);
        assert_eq!(found[0].text, None, "a garbage decode must not be reported");
    }

    /// A valid subdivision flag is an emoji, not a channel (#700's allowlist, reused).
    #[test]
    fn a_subdivision_flag_is_not_a_payload() {
        for flag in ["gbeng", "gbsct", "gbwls"] {
            let s = format!("\u{1F3F4}{}\u{E007F}", tags(flag));
            assert!(
                decode_smuggled(&s).is_empty(),
                "{flag} reported as a payload"
            );
        }
    }

    /// ...but the same base with any other tail is the channel wearing a flag.
    #[test]
    fn a_flag_base_with_another_tail_is_still_decoded() {
        let s = format!("\u{1F3F4}{}\u{E007F}", tags("ushi"));
        let found = decode_smuggled(&s);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].text.as_deref(), Some("ushi"));
    }

    /// One variation selector is emoji presentation, not a payload.
    #[test]
    fn a_lone_variation_selector_is_not_a_payload() {
        assert!(decode_smuggled("\u{2602}\u{FE0F}").is_empty());
        assert!(decode_smuggled("text\u{FE0E}").is_empty());
    }

    /// A run too short to fill a byte yields no payload, and is not rescanned.
    #[test]
    fn a_bit_short_zero_width_run_yields_nothing() {
        assert!(decode_smuggled("a\u{200B}\u{200C}\u{200B}b").is_empty());
    }

    /// Partial trailing bits are dropped, never zero-padded into a byte that was not sent.
    #[test]
    fn trailing_bits_are_dropped_not_padded() {
        let found = decode_smuggled(&format!("{}\u{200C}\u{200C}", zw("A")));
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].bytes, b"A".to_vec());
        assert_eq!(found[0].units, 10, "the stray bits are still consumed");
    }

    /// "Wholly printable" has to mean a reader sees it, not merely "no C0 control".
    ///
    /// Caught in review on #940: `U+202E` + `U+200B` is valid UTF-8 with no control
    /// character in it, and was reported as recovered text that renders as nothing.
    #[test]
    fn an_invisible_payload_is_not_recovered_text() {
        for payload in [
            "\u{202E}\u{200B}", // bidi override + zero width
            "\u{200B}\u{200C}", // zero width only
            "\u{FE00}",         // a variation selector
            "\u{3164}",         // HANGUL FILLER — Lo, and renders as nothing
            "\u{FFFE}",         // a noncharacter
        ] {
            let carriers: String = payload
                .as_bytes()
                .iter()
                .flat_map(|b| {
                    (0..8).map(move |i| {
                        if (b >> (7 - i)) & 1 == 1 {
                            '\u{200C}'
                        } else {
                            '\u{200B}'
                        }
                    })
                })
                .collect();
            let found = decode_smuggled(&carriers);
            assert_eq!(found.len(), 1, "{payload:?}");
            assert_eq!(
                found[0].text, None,
                "{payload:?} was reported as readable text"
            );
        }
        // ...and ordinary words still are.
        assert_eq!(
            decode_smuggled(&zw("hi there"))
                .first()
                .and_then(|p| p.text.as_deref()),
            Some("hi there")
        );
    }

    /// One Tags run is one span, terminator included.
    ///
    /// Caught in review on #940: the scan stopped before `CANCEL TAG`, so a terminated run
    /// was reported as two adjacent spans with the terminator between them.
    #[test]
    fn a_terminated_tag_run_is_one_span() {
        let s = format!("x{}{CANCEL_TAG}y", tags("hi"));
        let found = decode_smuggled(&s);
        assert_eq!(found.len(), 1, "{found:?}");
        assert_eq!(found[0].text.as_deref(), Some("hi"));
        assert_eq!(found[0].units, 3, "two letters and the terminator");
        assert_eq!(found[0].bytes.len(), 2, "the terminator carries no byte");
        // The span covers the terminator, so nothing is left between two runs.
        assert_eq!(&s[found[0].end..], "y");
    }

    fn pct(s: &str) -> String {
        use std::fmt::Write as _;
        s.bytes().fold(String::new(), |mut out, b| {
            let _ = write!(out, "%{b:02X}");
            out
        })
    }

    #[test]
    fn a_percent_run_decodes_to_what_it_spells() {
        let found = decode_smuggled(&format!("q={}", pct("tracked-by:acct-99213")));
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].scheme, PayloadScheme::PercentEscape);
        assert_eq!(found[0].text.as_deref(), Some("tracked-by:acct-99213"));
        assert_eq!(found[0].units, 21 * 3, "three characters per byte");
        assert_eq!(found[0].start, 2);
    }

    /// #727 item 2, all three answers.
    #[test]
    fn the_error_contract() {
        // `%FF` is not UTF-8: bytes, no text — the existing printable rule.
        let found = decode_smuggled("%FF%FE");
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].bytes, vec![0xFF, 0xFE]);
        assert_eq!(found[0].text, None);
        // `%` with fewer than two hex digits is malformed and ends the run before it.
        let found = decode_smuggled("%48%69%4");
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].text.as_deref(), Some("Hi"));
        assert_eq!(found[0].units, 6, "the malformed `%4` is not consumed");
        assert!(decode_smuggled("%4x%zz").is_empty());
        // Double encoding decodes ONCE; the result is the evidence, not a prompt.
        let found = decode_smuggled("%25%32%45");
        assert_eq!(found[0].text.as_deref(), Some("%2E"));
    }

    /// A lone `%20` is an escaped space, not a payload.
    #[test]
    fn a_single_escape_is_not_a_payload() {
        assert!(decode_smuggled("a%20b").is_empty());
        assert!(decode_smuggled("/path%2Fseg").is_empty());
    }

    #[test]
    fn hex_digits_are_case_insensitive_and_offsets_are_bytes() {
        let s = "caf\u{e9}=%68%69";
        let found = decode_smuggled(s);
        assert_eq!(found[0].text.as_deref(), Some("hi"));
        assert_eq!(&s[found[0].start..found[0].end], "%68%69");
        // `0x6a` and `0x6B` are both lowercase letters; the hex digits' case is not the
        // letters' case, which the first draft of this line got wrong.
        assert_eq!(decode_smuggled("%6a%6B")[0].text.as_deref(), Some("jk"));
    }

    #[test]
    fn ordinary_text_decodes_to_nothing() {
        for s in [
            "hello world",
            "",
            "café",
            "\u{1F600}",
            "Москва",
            "100%",
            "50% off",
        ] {
            assert!(decode_smuggled(s).is_empty(), "{s:?}");
        }
    }

    #[test]
    fn several_runs_are_reported_in_order() {
        let s = format!("a{}b{}c", tags("one"), zw("hi"));
        let found = decode_smuggled(&s);
        assert_eq!(found.len(), 2);
        assert_eq!(found[0].text.as_deref(), Some("one"));
        assert_eq!(found[1].text.as_deref(), Some("hi"));
        assert!(found[0].start < found[1].start);
    }

    /// The span must index the input, so a caller can slice it.
    #[test]
    fn the_span_indexes_the_input() {
        let s = format!("hello{}world", tags("hi"));
        let found = decode_smuggled(&s);
        assert_eq!(found.len(), 1);
        let (start, end) = (found[0].start, found[0].end);
        assert_eq!(&s[..start], "hello");
        assert_eq!(&s[end..], "world");
        assert_eq!(s[start..end].chars().count(), 2);
    }
}
