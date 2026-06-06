#![no_main]
//! Fuzz `security_clean`: must never panic, and must be idempotent
//! (a stable fixed point under NFC) on any input.
use libfuzzer_sys::fuzz_target;
use unicode_normalization::UnicodeNormalization;

fuzz_target!(|data: &str| {
    if let Ok(once) = _translit::presets::_security_clean(data) {
        let twice = _translit::presets::_security_clean(&once).unwrap();
        let n1: String = once.nfc().collect();
        let n2: String = twice.nfc().collect();
        assert_eq!(n1, n2, "security_clean not idempotent on {data:?}");
    }
});
