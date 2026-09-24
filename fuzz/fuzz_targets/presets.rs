//! The presets, key builders and pipeline profiles.
//!
//! Properties:
//!
//! 1. **Idempotence**, for every builder under every digit policy, every named profile
//!    (with and without a digit policy), `strip_format`, `strip_obfuscation` and
//!    `ml_normalize`. The Presets model (`formal/lean/Presets`) proved the stable-image
//!    criterion and found four ways it failed; #1024 and #1029 fixed them, so every
//!    surface here is now documented, or built, as a fixed point.
//! 2. **`is_canonical(s, preset) == (preset(s) == s)`**, which is its definition (#730),
//!    for every preset name, alias and profile, `skeleton_key` included (#1029).
//! 3. `canonicalize` output carries no bidi control (`has_bidi_control`), and
//!    `strip_bidi` output carries none either.
//! 4. `digit_policy = Numeric` is byte-identical to the function without the argument.
//! 5. A listed `lang` (or `"auto"`) is accepted, and a refusal is `InvalidArgument`,
//!    never a panic.
#![no_main]

use arbitrary::Arbitrary;
use disarm::api::{self as d, DigitPolicy};
use disarm::ErrorKind;
use disarm_fuzz::{text_and, Lang, Policy};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
struct Opts {
    policy: Policy,
    lang: Lang,
    strict_iso9: bool,
    fold_case: bool,
    emoji_cldr: bool,
    profile: u8,
}

/// Names `is_canonical` accepts besides the profiles, each with its function.
const PRESETS: &[&str] = &[
    "canonicalize",
    "security_clean",
    "canonicalize_strict",
    "normalize_user_input",
    "strip_format",
    "display_clean",
    "strip_obfuscation",
    "search_key",
    "catalog_key",
    "sort_key",
    "ml_normalize",
    "skeleton_key",
];

fn preset(name: &str, s: &str) -> String {
    match name {
        "canonicalize" | "security_clean" => d::canonicalize(s).unwrap().into_owned(),
        "canonicalize_strict" | "normalize_user_input" => {
            d::canonicalize_strict(s).unwrap().into_owned()
        }
        "strip_format" | "display_clean" => d::strip_format(s).into_owned(),
        "strip_obfuscation" => d::strip_obfuscation(s).unwrap().into_owned(),
        "search_key" => d::search_key(s, None).unwrap().into_owned(),
        "catalog_key" => d::catalog_key(s, None, false).unwrap().into_owned(),
        "sort_key" => d::sort_key(s, None).unwrap().into_owned(),
        "ml_normalize" => d::ml_normalize(s, None, "cldr", true).unwrap().into_owned(),
        "skeleton_key" => d::skeleton_key(s, DigitPolicy::Numeric)
            .unwrap()
            .into_owned(),
        profile => d::get_pipeline(profile).unwrap().process(s).unwrap(),
    }
}

fn assert_idempotent(name: &str, s: &str, f: impl Fn(&str) -> String) {
    let once = f(s);
    let twice = f(&once);
    assert_eq!(once, twice, "{name} is not idempotent on {s:?}");
}

fuzz_target!(|data: &[u8]| {
    let Some((s, o)) = text_and::<Opts>(data) else {
        return;
    };
    let s = s.as_str();
    let policy = DigitPolicy::from(o.policy);

    // 1. Idempotence.
    assert_idempotent("canonicalize_with", s, |t| {
        d::canonicalize_with(t, policy).unwrap().into_owned()
    });
    assert_idempotent("canonicalize_strict_with", s, |t| {
        d::canonicalize_strict_with(t, policy).unwrap().into_owned()
    });
    assert_idempotent("strip_obfuscation_with", s, |t| {
        d::strip_obfuscation_with(t, policy).unwrap().into_owned()
    });
    assert_idempotent("catalog_key_with", s, |t| {
        d::catalog_key_with(t, None, o.strict_iso9, policy)
            .unwrap()
            .into_owned()
    });
    assert_idempotent("search_key_with", s, |t| {
        d::search_key_with(t, None, policy).unwrap().into_owned()
    });
    assert_idempotent("sort_key_with", s, |t| {
        d::sort_key_with(t, None, policy).unwrap().into_owned()
    });
    assert_idempotent("skeleton_key", s, |t| {
        d::skeleton_key(t, policy).unwrap().into_owned()
    });
    assert_idempotent("strip_format", s, |t| d::strip_format(t).into_owned());
    let emoji_style = if o.emoji_cldr { "cldr" } else { "none" };
    assert_idempotent("ml_normalize", s, |t| {
        d::ml_normalize(t, None, emoji_style, o.fold_case)
            .unwrap()
            .into_owned()
    });
    let profiles = d::list_profiles();
    let profile = &profiles[usize::from(o.profile) % profiles.len()];
    let pipe = d::get_pipeline(profile).unwrap();
    assert_idempotent(profile, s, |t| pipe.process(t).unwrap());
    // A policy on a profile with no confusable step is refused, not ignored.
    if let Ok(p) = pipe.with_digit_policy(policy) {
        assert_idempotent(&format!("{profile} under {policy}"), s, |t| {
            p.process(t).unwrap()
        });
    }

    // 2. `is_canonical` is `preset(s) == s`, for one preset and one profile per input.
    let name = PRESETS[usize::from(o.profile) % PRESETS.len()];
    for n in [name, profile.as_str()] {
        assert_eq!(
            d::is_canonical(s, n).unwrap(),
            preset(n, s) == s,
            "is_canonical({s:?}, {n:?}) disagrees with its definition"
        );
    }

    // 3. No bidi control survives.
    let canon = d::canonicalize(s).unwrap();
    assert!(
        !d::has_bidi_control(&canon),
        "canonicalize kept a bidi control: {s:?}"
    );
    assert!(
        !d::has_bidi_control(&d::strip_bidi(s)),
        "strip_bidi kept one: {s:?}"
    );

    // 4. `Numeric` is the default, byte for byte.
    assert_eq!(
        canon,
        d::canonicalize_with(s, DigitPolicy::Numeric).unwrap()
    );
    assert_eq!(
        d::search_key(s, None).unwrap(),
        d::search_key_with(s, None, DigitPolicy::Numeric).unwrap()
    );

    // 5. `lang` validation: a built-in code or "auto" works, anything else is refused.
    let lang = o.lang.code();
    let known = lang
        .as_deref()
        .is_none_or(|l| l == "auto" || d::list_langs().iter().any(|k| k == l));
    for r in [
        d::search_key(s, lang.as_deref()).map(|_| ()),
        d::sort_key(s, lang.as_deref()).map(|_| ()),
        d::catalog_key(s, lang.as_deref(), o.strict_iso9).map(|_| ()),
    ] {
        match r {
            // Not the converse: `is_valid_lang` also takes BCP-47 aliases (`nb`, `nn`,
            // `da`, …) that `list_langs` does not list.
            Ok(()) => {}
            Err(e) => {
                assert!(!known, "known lang {lang:?} refused: {e}");
                assert_eq!(e.kind(), ErrorKind::InvalidArgument);
            }
        }
    }
});
