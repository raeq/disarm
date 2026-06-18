#![no_main]
//! Fuzz `canonicalize_strict`: must never panic, and must be idempotent
//! (a stable fixed point under NFC) on any input.
use libfuzzer_sys::fuzz_target;
use unicode_normalization::UnicodeNormalization;

fuzz_target!(|data: &str| {
    if let Ok(once) = _disarm::presets::canonicalize_strict(data) {
        let twice = _disarm::presets::canonicalize_strict(&once).unwrap();
        let n1: String = once.nfc().collect();
        let n2: String = twice.nfc().collect();
        assert_eq!(n1, n2, "canonicalize_strict not idempotent on {data:?}");
    }
});
