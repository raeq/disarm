use super::runner::{apply_steps, check_growth};
use super::steps::{PresetCtx, Step};
use super::*;
use crate::confusables::DigitPolicy;

const POLICIES: [DigitPolicy; 2] = [DigitPolicy::Tr39, DigitPolicy::Preserve];

fn search(text: &str, policy: DigitPolicy) -> String {
    search_key_with(text, None, policy).unwrap().into_owned()
}

fn sort(text: &str, policy: DigitPolicy) -> String {
    sort_key_with(text, None, policy).unwrap().into_owned()
}

fn catalog(text: &str, policy: DigitPolicy) -> String {
    catalog_key_with(text, None, false, policy)
        .unwrap()
        .into_owned()
}

/// Finding 2. Under `tr39` or `preserve` the only fold `search_key` and `sort_key` have
/// is the pre-fold on the raw text, and `FoldCase` and `Transliterate` make sources
/// after it: U+A760 has no row and folds to U+A761, which does; U+01C1 transliterates
/// to `||`; under `tr39`, U+0100 folds to U+0101, whose row is U+00E3.
#[test]
fn the_policy_keys_are_fixed_points_on_the_lean_witnesses() {
    for policy in POLICIES {
        assert_eq!(search("\u{A760}", policy), "w", "{policy:?}");
        assert_eq!(search("\u{01C1}", policy), "ll", "{policy:?}");
        assert_eq!(sort("\u{A760}", policy), "w", "{policy:?}");
        assert_eq!(sort("\u{0100}", policy), "\u{E3}", "{policy:?}");
        for input in ["\u{A760}", "\u{01C1}", "\u{0100}", "|\"`", "x\u{A760}y"] {
            for (name, key) in [
                ("search_key", search as fn(&str, DigitPolicy) -> String),
                ("sort_key", sort),
                ("catalog_key", catalog),
            ] {
                let once = key(input, policy);
                assert_eq!(key(&once, policy), once, "{name}[{policy:?}]({input:?})");
            }
        }
    }
}

/// The same, over the Latin, Greek, Cyrillic and Latin Extended blocks, one scalar at
/// a time, for all three builders the policy reaches without a fold of their own or
/// with one (`catalog_key`, which never failed, is here so it cannot start).
#[test]
fn the_policy_keys_are_fixed_points_over_the_blocks_that_failed() {
    let scalars = (0x20u32..0x530)
        .chain(0x1E00..0x2000)
        .chain(0xA720..0xA800)
        .filter_map(char::from_u32);
    let mut failures = Vec::new();
    for ch in scalars {
        let text = ch.to_string();
        for policy in POLICIES {
            for (name, key) in [
                ("search_key", search as fn(&str, DigitPolicy) -> String),
                ("sort_key", sort),
                ("catalog_key", catalog),
            ] {
                let once = key(&text, policy);
                if key(&once, policy) != once {
                    failures.push(format!("{name}[{policy:?}] U+{:04X}", ch as u32));
                }
            }
        }
    }
    assert!(
        failures.is_empty(),
        "{} keys move on a second pass: {:?}",
        failures.len(),
        &failures[..failures.len().min(10)]
    );
}

/// The iteration is for the non-default policies only. Under the default the pre-fold
/// does nothing, the builders were already fixed points, and a stored key must not
/// move: `sort_key` has no fold, so U+A761 stays U+A761, and `search_key` leaves the
/// `||` its transliteration writes for U+01C1 as `||`.
#[test]
fn the_default_policy_is_not_iterated() {
    assert_eq!(sort("\u{A760}", DigitPolicy::Numeric), "\u{A761}");
    assert_eq!(
        sort_key("\u{A760}", None).unwrap(),
        sort("\u{A760}", DigitPolicy::Numeric)
    );
    assert_eq!(search("\u{01C1}", DigitPolicy::Numeric), "||");
    assert_eq!(search_key("\u{01C1}", None).unwrap(), "||");
}

/// Finding 4. A control (and, in `ml_normalize`, a zero-width character) between two
/// characters that compose was stripped after the last step that composes. Conjoining
/// jamo compose with no mark involved, so no mark strip hid it.
#[test]
fn a_stripped_character_between_two_jamo_does_not_keep_them_apart() {
    for glue in ["\u{0}", "\u{1}", "\u{200B}"] {
        let text = format!("\u{1100}{glue}\u{1161}");
        for policy in [
            DigitPolicy::Numeric,
            DigitPolicy::Tr39,
            DigitPolicy::Preserve,
        ] {
            let once = strip_obfuscation_with(&text, policy).unwrap();
            assert_eq!(once, "\u{AC00}", "strip_obfuscation[{policy:?}]({text:?})");
        }
        for fold in [true, false] {
            let once = ml_normalize(&text, None, "cldr", fold).unwrap();
            assert_eq!(once, "\u{AC00}", "ml_normalize(fold={fold})({text:?})");
        }
    }
}

/// The terminal NFC must not undo a step before it: a string that ends decomposed only
/// because of a mark the preset keeps (#749's negation overlay on a surviving base) is
/// still a fixed point.
#[test]
fn the_terminal_nfc_leaves_both_presets_fixed_points() {
    for text in [
        "=\u{338}",
        "=\u{0}\u{338}",
        "=\u{200B}\u{338}",
        "\u{A2}\u{338}",
        "e\u{0}\u{301}",
        "c\u{0}\u{327}",
        "\u{1100}\u{0}\u{1161}\u{0}\u{11A8}",
    ] {
        let once = strip_obfuscation(text).unwrap().into_owned();
        assert_eq!(strip_obfuscation(&once).unwrap(), once, "{text:?}");
        let once = ml_normalize(text, None, "cldr", true).unwrap().into_owned();
        assert_eq!(
            ml_normalize(&once, None, "cldr", true).unwrap(),
            once,
            "{text:?}"
        );
    }
}

fn ctx(input_len: usize) -> PresetCtx<'static> {
    PresetCtx {
        lang: None,
        strict_iso9: false,
        emoji_cldr: false,
        digit_policy: DigitPolicy::Numeric,
        input_len,
    }
}

/// Finding 6. The ceiling bounds growth over the preset's input, not the size of the
/// output: an input of any size that no step grows passes, and one byte of growth over
/// the allowance fails, whatever the absolute sizes.
#[test]
fn the_ceiling_is_on_growth() {
    let max = crate::limits::MAX_NORMALIZE_OUTPUT_BYTES;
    let at_the_limit = "a".repeat(max + 7);
    assert!(check_growth(&at_the_limit, &ctx(7)).is_ok());
    assert!(check_growth(&at_the_limit, &ctx(6)).is_err());
    // Shrinking and size alone never trip it.
    assert!(check_growth("", &ctx(max * 3)).is_ok());
    assert!(check_growth(&at_the_limit, &ctx(max * 3)).is_ok());
    match check_growth(&at_the_limit, &ctx(6)) {
        Err(crate::ErrorRepr::NormalizeOutputTooLarge {
            input,
            size,
            max: m,
        }) => {
            assert_eq!((input, size, m), (6, max + 7, max));
        }
        other => panic!("expected the output ceiling, got {other:?}"),
    }
}

/// NFKC is not the only step that grows the text. `ml_normalize` names U+1FAF0 in 40
/// bytes after NFKC has passed it, so 1.2 MB of it grew to 12 MB, past the ceiling,
/// with no error: the check sat on the `Nfkc` arm alone.
#[test]
fn a_step_after_nfkc_is_bounded_too() {
    let text = "\u{1FAF0}".repeat(300_000);
    match ml_normalize(&text, None, "cldr", true) {
        Err(crate::ErrorRepr::NormalizeOutputTooLarge { input, .. }) => {
            assert_eq!(input, text.len());
        }
        other => panic!(
            "expected the output ceiling, got {:?}",
            other.map(|s| s.len())
        ),
    }
    // Under the ceiling it still succeeds, and emoji="none" does not grow at all.
    assert!(ml_normalize(&"\u{1FAF0}".repeat(1_000), None, "cldr", true).is_ok());
    assert!(ml_normalize(&text, None, "none", true).is_ok());
}

/// The growth is measured from the preset's input on every pass, not from each pass's
/// input: a `FixedPoint` (and the policy iteration) sees text that has already grown,
/// and measuring from there would grant the allowance again on every pass.
#[test]
fn the_growth_base_is_the_preset_input_inside_a_fixed_point() {
    let max = crate::limits::MAX_NORMALIZE_OUTPUT_BYTES;
    let grown = "a".repeat(max + 2);
    let c = ctx(1);
    // One pass of a FixedPoint whose input has already grown past the allowance.
    assert!(apply_steps(&[Step::FoldCase], &grown, &c).is_err());
}
