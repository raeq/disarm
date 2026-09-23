//! The anomaly detector gives canonically equivalent text one verdict.
//!
//! Finding 3 of the Lean model in `formal/lean/Detection`: `has_anomalies` read four of its
//! tests off the code points as spelled, so `\u{e9}t\u{e9}` + `U+2067` was clean in NFC
//! and `bidi` in NFD, and 2,328,179 (scalar, context) pairs split the verdict. The model
//! proves the fix invariant on its alphabet. This file checks the same property on the
//! library, over every Unicode scalar alone and in the seven contexts of the model's
//! `scripts/sweep_nf.py`.
//!
//! Compared on `kinds`, not only the boolean, so a change that kept the verdict but moved
//! which kind fired would still be caught.
//!
//! **The domain.** The property is one verdict for canonically equivalent spellings that
//! contain no scalar NFC replaces with a different single scalar: the canonical singletons
//! (`\u{212A}` KELVIN SIGN, `\u{37E}` GREEK QUESTION MARK, the CJK compatibility
//! ideographs) and the duplicate encodings (`\u{1FEE}`, `\u{1F71}`). Those are different
//! characters, not a composition of the letters they stand for, so the detector reports
//! them as spelled: `\u{212A}ey` is not `Key`. Neither NFC nor NFD can contain one, so
//! comparing the two forms, as this file does, stays inside the domain for every input;
//! [`assert_one_verdict`] checks that rather than assuming it.
//!
//! Two tiers. The whole range is `#[ignore]`d, because it is 17.8 million calls and takes
//! minutes in a debug build; run it before a release (`tier3.yml` does):
//!
//! ```text
//! cargo test --no-default-features --release --test exhaustive_anomalies -- --ignored
//! ```
//!
//! The per-PR tier walks the scalars where the two forms can differ in the scalar itself,
//! the blocks the detector has rules for, and a stride through everything else.

use std::collections::HashSet;

use disarm::api;
use unicode_normalization::char::canonical_combining_class;
use unicode_normalization::UnicodeNormalization;

/// `(prefix, suffix)` around each scalar: alone, then the model's seven. The four with a
/// precomposed letter are the ones where NFC and NFD differ for **every** scalar, which is
/// why the release tier walks the whole range rather than only the scalars that decompose.
const CONTEXTS: &[(&str, &str)] = &[
    ("", ""),
    ("pay", "pal"),
    ("a", ""),
    ("\u{e9}", "\u{e9}"),
    ("", "\u{2066}"),
    ("\u{e9}t\u{e9}", "\u{2067}x"),
    ("\u{e9}", "\u{200d}\u{e9}"),
    ("\u{e0}\u{e9}", "\u{200f}1"),
];

/// Whether NFC replaces `c` on its own with one different scalar: outside the domain.
fn nfc_replaces(c: char) -> bool {
    let mut nfc = c.nfc();
    nfc.next().is_some_and(|f| f != c) && nfc.next().is_none()
}

/// Every split verdict among `scalars`, in every context.
fn splits(scalars: &[char], lexicon: &HashSet<String>) -> Vec<String> {
    let mut out = Vec::new();
    for &c in scalars {
        for (pre, post) in CONTEXTS {
            let s = format!("{pre}{c}{post}");
            let nfc: String = s.nfc().collect();
            let nfd: String = s.nfd().collect();
            assert!(
                !nfc.chars().chain(nfd.chars()).any(nfc_replaces),
                "a normal form of {s:?} left the domain"
            );
            let a = api::inspect_anomalies(&nfc, lexicon).kinds;
            let b = api::inspect_anomalies(&nfd, lexicon).kinds;
            if a != b {
                out.push(format!("{nfc:?} {a:?} | {nfd:?} {b:?}"));
            }
        }
    }
    out
}

/// [`splits`] spread over every core, asserting there are none.
fn assert_one_verdict(scalars: &[char]) {
    let lexicon = HashSet::new();
    let workers = std::thread::available_parallelism().map_or(4, std::num::NonZero::get);
    let chunk = scalars.len().div_ceil(workers).max(1);
    let failures: Vec<String> = std::thread::scope(|scope| {
        let handles: Vec<_> = scalars
            .chunks(chunk)
            .map(|part| {
                let lexicon = &lexicon;
                scope.spawn(move || splits(part, lexicon))
            })
            .collect();
        handles
            .into_iter()
            .flat_map(|h| h.join().expect("sweep worker panicked"))
            .collect()
    });
    assert!(
        failures.is_empty(),
        "{} split verdicts, first {}:\n{}",
        failures.len(),
        failures.len().min(20),
        failures[..failures.len().min(20)].join("\n")
    );
}

fn every_scalar() -> impl Iterator<Item = char> {
    (0..=0x10_FFFF_u32).filter_map(char::from_u32)
}

/// The release tier: every Unicode scalar, alone and in all seven contexts.
#[test]
#[ignore = "exhaustive: 17.8M detector calls, run with --release -- --ignored"]
fn every_scalar_gets_one_verdict_in_nfc_and_nfd() {
    assert_one_verdict(&every_scalar().collect::<Vec<_>>());
}

/// The per-PR tier, a few seconds in a debug build:
///
/// - every scalar that normalization itself moves: one with a canonical decomposition or
///   a nonzero combining class, which is where a composed and a decomposed spelling of
///   the scalar can meet a rule differently;
/// - the blocks the detector has character rules for: Latin through Arabic and NKo
///   (`U+0000`-`U+07FF`), General Punctuation with its bidi and format controls, the
///   variation selectors, and the Specials with the annotation characters and two
///   noncharacters;
/// - one scalar in 251 from everything else, so every plane is visited.
#[test]
fn normalization_active_and_rule_bearing_scalars_get_one_verdict() {
    let scalars: Vec<char> = every_scalar()
        .filter(|&c| {
            let cp = c as u32;
            c.nfd().ne(std::iter::once(c))
                || canonical_combining_class(c) != 0
                || cp < 0x0800
                || (0x2000..=0x206F).contains(&cp)
                || (0xFE00..=0xFE0F).contains(&cp)
                || (0xFFF0..=0xFFFF).contains(&cp)
                || cp.is_multiple_of(251)
        })
        .collect();
    assert!(scalars.len() > 7_000, "{} scalars", scalars.len());
    assert_one_verdict(&scalars);
}

/// The same property with a lexicon: the leet decode reads the composed word, so a
/// lexicon written in NFC matches either spelling.
#[test]
fn a_lexicon_word_gets_one_verdict_in_nfc_and_nfd() {
    let lexicon = api::lexicon(["caf\u{e9}", "na\u{ef}ve", "fran\u{e7}ais"]);
    for s in ["c4f\u{e9}", "n4\u{ef}v3", "fr4n\u{e7}4is"] {
        let nfc: String = s.nfc().collect();
        let nfd: String = s.nfd().collect();
        let a = api::inspect_anomalies(&nfc, &lexicon).kinds;
        assert_eq!(a, api::inspect_anomalies(&nfd, &lexicon).kinds, "{s:?}");
        assert_eq!(a, vec![api::AnomalyKind::Leet], "{s:?}");
    }
}
