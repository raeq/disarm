//! Layer 1: multi-codepoint confusable **sources** — contraction (#562).
//!
//! The confusable tables map one codepoint to one-or-more (`0271` → `rn`), so *expansion*
//! has always worked. *Contraction* — recognising that `rn` may stand in for `m` — could
//! not be expressed at all: the source column of both TSVs is a single hex codepoint in
//! every data row, so this was a schema change before it was a data change.
//!
//! # Why this is not a table merge
//!
//! Adding contraction means the mapping is no longer one-to-one, and unconditional
//! contraction is strictly worse than none: `rn` → `m` is right for `arnazon` and wrong
//! for `earnings`, `turnip` and `born`. So the rules live here, off by default, reachable
//! only from the hostname path — where the threat model justifies the false positives and
//! there is no running prose to corrupt. A general-text contraction mode, if it ever
//! lands, needs its own disambiguation story and its own issue.
//!
//! # Leftmost-longest
//!
//! With multi-codepoint sources the transform stops being a per-character PHF lookup and
//! becomes a search over an automaton. `MatchKind::LeftmostLongest` is the semantics that
//! matches how a reader disambiguates: scan left to right, and at each position prefer the
//! longest rule that fits. `vvv` therefore contracts to `wv`, never `vw`.
//!
//! # Idempotence
//!
//! Guaranteed structurally rather than by iteration: `build.rs` asserts that no rule's
//! *output* occurs inside any rule's *input*, so one pass can never expose a fresh match.
//! That check is what lets this run once instead of looping to a fixed point, and it fails
//! the build if a future data edit introduces a chain.

use std::sync::LazyLock;

use aho_corasick::{AhoCorasick, MatchKind};

/// The automaton, built once from the generated rule set.
///
/// `LazyLock` rather than a build-time artifact because `aho_corasick` has no const
/// constructor; the set is three rules, so construction is trivial and happens on first
/// use of the opt-in path — a caller who never asks for contraction never pays for it.
static AUTOMATON: LazyLock<AhoCorasick> = LazyLock::new(|| {
    let patterns: Vec<&str> = crate::tables::contraction_rules()
        .iter()
        .map(|(source, _)| *source)
        .collect();
    AhoCorasick::builder()
        .match_kind(MatchKind::LeftmostLongest)
        .build(&patterns)
        .expect("the contraction rule set is validated at build time")
});

/// Apply the contraction rules to `text`, leftmost-longest.
///
/// Borrows when nothing matches, which is the overwhelming common case — a hostname with
/// no digraph pays one automaton scan and no allocation.
pub(crate) fn contract(text: &str) -> std::borrow::Cow<'_, str> {
    let rules = crate::tables::contraction_rules();
    let mut matches = AUTOMATON.find_iter(text).peekable();
    if matches.peek().is_none() {
        return std::borrow::Cow::Borrowed(text);
    }

    let mut out = String::with_capacity(text.len());
    let mut last = 0;
    for m in matches {
        out.push_str(&text[last..m.start()]);
        // `pattern()` indexes the same slice the automaton was built from.
        out.push_str(rules[m.pattern().as_usize()].1);
        last = m.end();
    }
    out.push_str(&text[last..]);
    std::borrow::Cow::Owned(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn borrows_when_nothing_matches() {
        assert!(matches!(contract("example"), std::borrow::Cow::Borrowed(_)));
    }

    #[test]
    fn contracts_each_rule() {
        assert_eq!(contract("arnazon"), "amazon");
        assert_eq!(contract("vvikipedia"), "wikipedia");
        assert_eq!(contract("clropbox"), "dropbox");
    }

    /// Leftmost-longest, not leftmost-first: `vvv` has `vv` at 0 and at 1, and the left
    /// one wins.
    #[test]
    fn leftmost_longest_on_overlaps() {
        assert_eq!(contract("vvv"), "wv");
        assert_eq!(contract("vvvv"), "ww");
    }

    #[test]
    fn adjacent_distinct_rules_both_fire() {
        assert_eq!(contract("rnvv"), "mw");
    }

    /// The structural idempotence guarantee, exercised rather than assumed.
    #[test]
    fn is_idempotent() {
        for input in ["arnazon", "vvvv", "rnrn", "clcl", "example", "", "rn", "v"] {
            let once = contract(input).into_owned();
            assert_eq!(contract(&once), once, "not idempotent for {input:?}");
        }
    }

    /// No rule output may occur inside a rule input — build.rs asserts it, and this
    /// re-asserts it from the consumer side so the reason is visible in the test suite.
    #[test]
    fn no_rule_chains_into_another() {
        let rules = crate::tables::contraction_rules();
        for (_, target) in rules {
            for (source, _) in rules {
                assert!(
                    !source.contains(target),
                    "output {target:?} occurs inside source {source:?}"
                );
            }
        }
    }

    #[test]
    fn prose_words_that_must_not_be_touched_by_the_general_fold() {
        // These DO contract — which is exactly why the rules are opt-in and scoped to
        // hostnames. Pinned so the cost of the feature stays visible in the test suite.
        assert_eq!(contract("earnings"), "eamings");
        assert_eq!(contract("turnip"), "tumip");
        assert_eq!(contract("born"), "bom");
    }
}
