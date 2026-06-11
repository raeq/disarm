#![no_main]
//! Fuzz `normalize_confusables`: must never panic, and the output must
//! contain no character the bundled table still maps (a fixed point).
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &str| {
    for target in ["latin", "cyrillic"] {
        if let Ok(once) = _disarm::confusables::_normalize_confusables(data, target) {
            let twice = _disarm::confusables::_normalize_confusables(&once, target).unwrap();
            assert_eq!(
                once, twice,
                "normalize_confusables({target}) not idempotent on {data:?}"
            );
        }
    }
});
