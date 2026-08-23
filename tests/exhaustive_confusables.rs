//! Tier-3 exhaustive checks on the Layer-2 confusables surface (#586).
//!
//! `#[ignore]` per the project's test tiers: these sweep the whole BMP crossed with
//! combining marks, which is too slow for the per-PR gate. Run them before a release:
//!
//! ```text
//! cargo test --no-default-features --test exhaustive_confusables -- --ignored
//! ```
//!
//! The two properties below are what #586 was actually about. `normalize_confusables`
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
