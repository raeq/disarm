//! The confusable fold and its detectors, for every target script and digit policy.
//!
//! Properties (the `normalize_confusables` docstring, and `formal/lean/Confusables`):
//!
//! 1. The fold is idempotent, for every target and every policy (`fixedFold_idem`).
//! 2. It is complete: `is_confusable` is false on its output under `Numeric` and `Tr39`.
//!    Not under `Preserve`, which keeps the digit rows by design (the docstring says so).
//! 3. `is_confusable(s) == !find_confusables(s).is_empty()` (`isConfusable_eq_find`).
//! 4. A detection implies the fold changes the string (`detect_changes`).
//! 5. Every `(ch, offset)` `find_confusables` and `find_unmapped_confusables` report points
//!    at `ch`: `ch` is the input's character at `offset` ([`disarm_fuzz::located`]).
#![no_main]

use arbitrary::Arbitrary;
use disarm::api::{self as d, DigitPolicy, TargetScript};
use disarm_fuzz::{located, text_and, Policy};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
struct Opts {
    target: u8,
    policy: Policy,
}

fuzz_target!(|data: &[u8]| {
    let Some((s, o)) = text_and::<Opts>(data) else {
        return;
    };
    let target = TargetScript::ALL[usize::from(o.target) % TargetScript::ALL.len()];
    let policy = DigitPolicy::from(o.policy);

    // 1.
    let folded = d::normalize_confusables_with(&s, target, policy);
    let again = d::normalize_confusables_with(&folded, target, policy);
    assert_eq!(
        folded, again,
        "fold not idempotent ({target}, {policy}) on {s:?}"
    );

    // 2.
    if policy != DigitPolicy::Preserve {
        assert!(
            !d::is_confusable(&folded, target),
            "fold incomplete ({target}, {policy}): {s:?} -> {folded:?}"
        );
    }

    // 3.
    let found = d::find_confusables(&s, target);
    let detected = d::is_confusable(&s, target);
    assert_eq!(
        detected,
        !found.is_empty(),
        "is_confusable != find_confusables on {s:?}"
    );

    // 4.
    if detected {
        assert_ne!(
            d::normalize_confusables(&s, target),
            s,
            "detected but the fold left {s:?} unchanged"
        );
    }

    // 5.
    for m in &found {
        assert!(located(&s, m.offset, m.ch), "{m:?} is not in {s:?}");
    }
    for u in d::find_unmapped_confusables(&s, target) {
        assert!(located(&s, u.offset, u.ch), "{u:?} is not in {s:?}");
    }
    let _ = d::find_confusables_with(&s, target, &["Latin", "Cyrillic", "Greek"]);
});
