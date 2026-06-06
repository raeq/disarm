#![no_main]
//! Fuzz `sanitize_user_input`: must never panic, and must be idempotent
//! (a stable fixed point under NFC) on any input.
use libfuzzer_sys::fuzz_target;
use unicode_normalization::UnicodeNormalization;

fuzz_target!(|data: &str| {
    if let Ok(once) = _translit::presets::_sanitize_user_input(data) {
        let twice = _translit::presets::_sanitize_user_input(&once).unwrap();
        let n1: String = once.nfc().collect();
        let n2: String = twice.nfc().collect();
        assert_eq!(n1, n2, "sanitize_user_input not idempotent on {data:?}");
    }
});
