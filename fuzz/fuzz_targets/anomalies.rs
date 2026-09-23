//! The anomaly detector and the smuggled-payload decoder.
//!
//! Properties:
//!
//! 1. `has_anomalies(s) == inspect_anomalies(s).anomalous == !findings.is_empty()`, and the
//!    report is internally consistent: `kinds` is the findings' kinds in first-appearance
//!    order, `reason` is the first finding's, and every span lies on char boundaries. A
//!    token finding's `token` is the input's text at its span (a `smuggled` finding's
//!    token is the decoded text instead, by design).
//! 2. **A line feed is a hard cut** (`hasAnomalies_append_lf`, proved in
//!    `formal/lean/Detection`): `has(u + "\n" + v) == has(u) || has(v)`.
//! 3. **Canonical equivalence** (#1025, `tests/exhaustive_anomalies.rs`): the NFC and NFD
//!    spellings of the input report the same set of kinds.
//! 4. Deleting a control or a tag character from the text is always reported
//!    (`formal/lean/Detection`, "Checked and not a bug"): if `strip_control_chars` or
//!    `strip_tags` changes the input, `has_anomalies` is true.
//! 5. `decode_smuggled`: spans on char boundaries, `units` is the span's length in
//!    characters, and `text`, when present, is exactly the decoded bytes. A carrier
//!    payload that decodes to text is reported by the detector.
//! 6. **Round trip** (`roundtrip_tag`, `roundtrip_vs`, `roundtrip_zw`): encoding bytes in
//!    one of the three carriers and setting the run between two ordinary characters
//!    anywhere in the text decodes to exactly those bytes and that span.
#![no_main]

use std::collections::HashSet;

use arbitrary::Arbitrary;
use disarm::api::{self as d, AnomalyKind, PayloadScheme};
use disarm_fuzz::{nfc, nfd, split_at_choice, text_and};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum Carrier {
    Tag,
    Variation,
    ZeroWidth,
}

#[derive(Debug, Arbitrary)]
struct Opts {
    with_lexicon: bool,
    split: u16,
    carrier: Carrier,
    payload: Vec<u8>,
}

fn lexicon(on: bool) -> HashSet<String> {
    if on {
        d::lexicon([
            "paypal", "google", "admin", "login", "free", "viagra", "support",
        ])
    } else {
        HashSet::new()
    }
}

fn kind_set(s: &str, lex: &HashSet<String>) -> Vec<AnomalyKind> {
    let mut kinds = d::inspect_anomalies(s, lex).kinds;
    kinds.sort_by_key(|k| format!("{k:?}"));
    kinds
}

/// Encode `bytes` in `carrier`, or `None` where the scheme cannot carry them as given.
fn encode(carrier: &Carrier, bytes: &[u8]) -> Option<String> {
    match carrier {
        // Printable ASCII only; one byte is a payload.
        Carrier::Tag => (!bytes.is_empty() && bytes.iter().all(|b| (0x20..=0x7E).contains(b)))
            .then(|| {
                bytes
                    .iter()
                    .map(|&b| char::from_u32(0xE0000 + u32::from(b)).unwrap())
                    .collect()
            }),
        // Two selectors or more (`MIN_VARIATION_RUN`). A leading VS15/VS16 after an
        // ordinary character is read as that character's presentation selector, which is
        // the documented exception, so the round trip is not claimed for it.
        Carrier::Variation => (bytes.len() >= 2 && !matches!(bytes[0], 0x0E | 0x0F)).then(|| {
            bytes
                .iter()
                .map(|&b| {
                    let cp = if b < 16 {
                        0xFE00 + u32::from(b)
                    } else {
                        0xE0100 + u32::from(b) - 16
                    };
                    char::from_u32(cp).unwrap()
                })
                .collect()
        }),
        // Whole bytes, MSB first: U+200B is 0, U+200C is 1.
        Carrier::ZeroWidth => (!bytes.is_empty()).then(|| {
            bytes
                .iter()
                .flat_map(|&b| (0..8).rev().map(move |i| (b >> i) & 1))
                .map(|bit| if bit == 0 { '\u{200B}' } else { '\u{200C}' })
                .collect()
        }),
    }
}

fn scheme_of(carrier: &Carrier) -> PayloadScheme {
    match carrier {
        Carrier::Tag => PayloadScheme::TagAscii,
        Carrier::Variation => PayloadScheme::VariationBytes,
        Carrier::ZeroWidth => PayloadScheme::ZeroWidthBinary,
    }
}

fuzz_target!(|data: &[u8]| {
    let Some((s, o)) = text_and::<Opts>(data) else {
        return;
    };
    let lex = lexicon(o.with_lexicon);

    // 1.
    let has = d::has_anomalies(&s, &lex);
    let report = d::inspect_anomalies(&s, &lex);
    assert_eq!(
        has, report.anomalous,
        "has_anomalies != report.anomalous on {s:?}"
    );
    assert_eq!(
        has,
        !report.findings.is_empty(),
        "anomalous without findings on {s:?}"
    );
    let mut kinds = Vec::new();
    for f in &report.findings {
        if !kinds.contains(&f.kind) {
            kinds.push(f.kind);
        }
        assert!(f.start <= f.end && f.end <= s.len());
        assert!(s.is_char_boundary(f.start) && s.is_char_boundary(f.end));
        if f.kind != AnomalyKind::Smuggled {
            assert_eq!(
                f.token,
                &s[f.start..f.end],
                "token is not the input at its span"
            );
        }
    }
    assert_eq!(kinds, report.kinds);
    assert_eq!(
        report.reason,
        report.findings.first().map(d::Finding::reason)
    );

    // 2. A line feed is a hard cut.
    let (u, v) = split_at_choice(&s, o.split);
    let joined = format!("{u}\n{v}");
    assert_eq!(
        d::has_anomalies(&joined, &lex),
        d::has_anomalies(u, &lex) || d::has_anomalies(v, &lex),
        "LF is not a cut: {u:?} / {v:?}"
    );

    // 3. Canonical equivalence.
    assert_eq!(
        kind_set(&nfc(&s), &lex),
        kind_set(&nfd(&s), &lex),
        "NFC and NFD spellings disagree on {s:?}"
    );

    // 4. A deletion by the control or tag strip is reported.
    for (name, stripped) in [
        ("strip_control_chars", d::strip_control_chars(&s)),
        ("strip_tags", d::strip_tags(&s)),
    ] {
        if stripped != s {
            assert!(has, "{name} changes {s:?} and the detector is silent");
        }
    }

    // 5. The decoder's own report.
    for p in d::decode_smuggled(&s) {
        assert!(p.start < p.end && p.end <= s.len());
        assert!(s.is_char_boundary(p.start) && s.is_char_boundary(p.end));
        assert_eq!(
            p.units,
            s[p.start..p.end].chars().count(),
            "units != span length"
        );
        if let Some(t) = &p.text {
            assert_eq!(
                t.as_bytes(),
                p.bytes.as_slice(),
                "text is not the decoded bytes"
            );
            if p.scheme != PayloadScheme::PercentEscape {
                assert!(
                    has,
                    "a carrier payload decodes to {t:?} and the detector is silent"
                );
            }
        }
    }

    // 6. Round trip through each carrier, between two ordinary characters.
    if let Some(enc) = encode(&o.carrier, &o.payload) {
        let start = u.len() + 1;
        let hidden = format!("{u}x{enc}x{v}");
        let found = d::decode_smuggled(&hidden);
        assert!(
            found.iter().any(|p| p.scheme == scheme_of(&o.carrier)
                && p.start == start
                && p.end == start + enc.len()
                && p.bytes == o.payload),
            "{:?} payload {:?} did not round-trip in {hidden:?}: {found:?}",
            o.carrier,
            o.payload
        );
    }
});
