//! Tier-3 exhaustive checks on the Layer-2 confusables surface (#586).
//!
//! `#[ignore]` per the project's test tiers: these sweep the whole BMP crossed with
//! combining marks, which is too slow for the per-PR gate. Run them before a release:
//!
//! ```text
//! cargo test --no-default-features --test exhaustive_confusables -- --ignored
//! ```
//!
//! The first two properties below are what #586 was actually about. `normalize_confusables`
//! ran a single pass, so a base character whose fold *exposed* a composition (or whose
//! composition exposed a fold) came back half-done: not a fixed point, and still
//! flagged by `is_confusable`. The spot-check cases live in `api_pure_rust.rs`; these
//! sweeps are what prove no other codepoint in the BMP does the same thing.

use disarm::api::{self, DigitPolicy, TargetScript};

/// Marks that participate in canonical composition with a Latin or Cyrillic base, so a
/// fold can expose a composition and vice versa. U+0327 is the one from #586.
const MARKS: &[char] = ['\u{0300}', '\u{0301}', '\u{0308}', '\u{0327}'].as_slice();

/// The whole BMP, surrogates excluded. ASCII is deliberately **in**: the Latin table
/// maps ASCII sources (`|`→`l`, `"`→`\'\'`, `` ` ``→`\'`), so an ASCII base is not
/// identity even for the Latin target, and an ASCII base carrying a composing mark is
/// exactly the shape this file exists to check.
fn bmp_bases() -> impl Iterator<Item = char> {
    (0x0000_u32..=0xFFFF)
        .filter(|cp| !(0xD800..=0xDFFF).contains(cp))
        .filter_map(char::from_u32)
}

/// `f(f(x)) == f(x)` for every BMP base carrying a composing mark.
#[test]
#[ignore = "exhaustive: slow, run with --ignored"]
fn exhaustive_marked_base_idempotence() {
    let mut failures = Vec::new();
    for target in [TargetScript::Latin, TargetScript::Cyrillic] {
        for policy in [DigitPolicy::Numeric, DigitPolicy::Tr39] {
            for base in bmp_bases() {
                for &mark in MARKS {
                    let input = format!("{base}{mark}");
                    let once = api::normalize_confusables_with(&input, target, policy);
                    let twice = api::normalize_confusables_with(&once, target, policy);
                    if once != twice {
                        failures.push(format!(
                            "U+{:04X}+U+{:04X} {target:?}/{policy:?}: once={once:?}, twice={twice:?}",
                            base as u32, mark as u32
                        ));
                    }
                }
            }
        }
    }
    assert!(
        failures.is_empty(),
        "Idempotence violated for {} marked bases:\n{}",
        failures.len(),
        failures[..failures.len().min(20)].join("\n")
    );
}

/// The output of the fold must never itself be confusable with the target script.
///
/// This is the property that makes the result usable as a comparison skeleton, and the
/// one a single pass cannot provide: the loop can only exit once nothing folds, which is
/// the same condition `is_confusable` tests.
///
/// Swept under both digit policies, because `Tr39` reads a different table. Its overrides carry
/// upstream's raw targets, which are not all ASCII (`\u{A770}`) and not all letters
/// (`.`, `rn`) — see #587. None of them is itself a confusable source, so completeness
/// holds on that path too, and this pins that rather than assuming it.
#[test]
#[ignore = "exhaustive: slow, run with --ignored"]
fn exhaustive_folded_output_is_never_confusable() {
    let mut failures = Vec::new();
    for target in [TargetScript::Latin, TargetScript::Cyrillic] {
        for policy in [DigitPolicy::Numeric, DigitPolicy::Tr39] {
            for base in bmp_bases() {
                for &mark in MARKS {
                    let input = format!("{base}{mark}");
                    let folded = api::normalize_confusables_with(&input, target, policy);
                    if api::is_confusable(&folded, target) {
                        failures.push(format!(
                            "U+{:04X}+U+{:04X} {target:?}/{policy:?}: folded to {folded:?}, still confusable",
                            base as u32, mark as u32
                        ));
                    }
                }
            }
        }
    }
    assert!(
        failures.is_empty(),
        "Fold left confusable output for {} marked bases:\n{}",
        failures.len(),
        failures[..failures.len().min(20)].join("\n")
    );
}

/// Every scalar value, not only the BMP: `skeleton_key` reaches astral text too.
fn all_scalars() -> impl Iterator<Item = char> {
    (0u32..=0x10_FFFF).filter_map(char::from_u32)
}

/// The combining marks that take part in a canonical composition: every mark after the
/// first position in the NFD of a primary composite. Derived rather than listed, so it
/// follows the Unicode version the crate normalizes with.
fn composing_marks() -> Vec<char> {
    use unicode_normalization::char::is_combining_mark;
    use unicode_normalization::UnicodeNormalization;
    let mut marks = std::collections::BTreeSet::new();
    for c in all_scalars() {
        let nfd: Vec<char> = std::iter::once(c).nfd().collect();
        if nfd.len() >= 2 && nfd.iter().copied().nfc().eq(std::iter::once(c)) {
            marks.extend(nfd[1..].iter().copied().filter(|&m| is_combining_mark(m)));
        }
    }
    marks.into_iter().collect()
}

fn skeleton(text: &str, policy: DigitPolicy) -> String {
    api::skeleton_key(text, policy)
        .expect("a typed policy is always valid")
        .into_owned()
}

/// `skeleton_key` is a fixed point, and its key is not confusable, on every scalar value
/// alone. A key that is not a fixed point is not a key: before the Lean model of the fold
/// (`formal/lean/Confusables`, F1) eight code points failed here, U+0390 first, because
/// full case folding emits a decomposed sequence and nothing recomposed it.
///
/// Confusability is asserted under `numeric` and `tr39` only: `preserve` keeps the digit
/// rows by design (#648), and `is_confusable` takes no policy, so it flags them.
#[test]
#[ignore = "exhaustive: slow, run with --ignored"]
fn exhaustive_skeleton_key_scalars() {
    let mut failures = Vec::new();
    for policy in [
        DigitPolicy::Numeric,
        DigitPolicy::Tr39,
        DigitPolicy::Preserve,
    ] {
        for c in all_scalars() {
            let input = c.to_string();
            let once = skeleton(&input, policy);
            let twice = skeleton(&once, policy);
            let flagged =
                policy != DigitPolicy::Preserve && api::is_confusable(&once, TargetScript::Latin);
            if once != twice || flagged {
                failures.push(format!(
                    "U+{:04X} {policy:?}: once={once:?}, twice={twice:?}, confusable={flagged}",
                    c as u32
                ));
            }
        }
    }
    assert!(
        failures.is_empty(),
        "skeleton_key failed on {} scalars:\n{}",
        failures.len(),
        failures[..failures.len().min(20)].join("\n")
    );
}

/// The same over every BMP base carrying a composing mark, directly and with a control
/// between the two. Before F1's fix 9,526 of the direct pairs and 40,229 of the
/// separated ones (over the 85 marks Unicode 14 knows) keyed to a string that keyed
/// again to something else: the fold left `Y` beside a grave accent, or the control
/// was removed only after the last fold.
#[test]
#[ignore = "exhaustive: slow, run with --ignored"]
fn exhaustive_skeleton_key_marked_bases() {
    let marks = composing_marks();
    let mut failures = Vec::new();
    for policy in [DigitPolicy::Numeric, DigitPolicy::Tr39] {
        for base in bmp_bases() {
            for &mark in &marks {
                for between in ["", "\u{1}"] {
                    let input = format!("{base}{between}{mark}");
                    let once = skeleton(&input, policy);
                    let twice = skeleton(&once, policy);
                    let flagged = api::is_confusable(&once, TargetScript::Latin);
                    if once != twice || flagged {
                        failures.push(format!(
                            "{input:?} {policy:?}: once={once:?}, twice={twice:?}, confusable={flagged}"
                        ));
                    }
                }
            }
        }
    }
    assert!(
        failures.is_empty(),
        "skeleton_key failed on {} marked bases:\n{}",
        failures.len(),
        failures[..failures.len().min(20)].join("\n")
    );
}
