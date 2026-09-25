//! `Transliterate` under every scheme, language, tone setting and unknown-character
//! policy.
//!
//! Properties: the stated invariants of `docs/formal-verification.md`, in the scope
//! `formal/lean/Transliterate` established for them (`tones = false`, no runtime
//! registrations, which this target never makes):
//!
//! - **I1** ASCII passthrough: ASCII input comes back unchanged, under every option
//!   (the Transliterate model found no exception without registrations, tones included).
//! - **I2** ASCII output under `on_unknown = Ignore` (and under `Replace` with an ASCII
//!   replacement), `tones = false`. `tones = true` is excluded by design: toned pinyin is
//!   non-ASCII.
//! - **I3** idempotence, stated for `errors = 'ignore'`; also checked under `Replace`
//!   with an ASCII replacement, where the same argument (I1 + I2) applies.
//! - **I7** output length: `|f(s)| <= 5 * |s|_bytes + |s|_chars` in bytes under `Ignore`,
//!   with `tones = false`, the scope `docs/formal-verification.md` states it in.
//! - `find_untranslatable` points at each character it reports: the input's character at
//!   the reported offset ([`disarm_fuzz::located`]), and when it reports nothing the three
//!   `on_unknown` policies agree ("exactly the set `run` would replace/ignore/preserve").
#![no_main]

use arbitrary::Arbitrary;
use disarm::api::{OnUnknown, Scheme, Transliterate};
use disarm::ErrorKind;
use disarm_fuzz::{located, text_and, Lang};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum SchemeOpt {
    Default,
    StrictIso9,
    Gost,
}

#[derive(Debug, Arbitrary)]
enum Unknown {
    Ignore,
    DefaultReplace,
    Preserve,
    Replace(String),
}

#[derive(Debug, Arbitrary)]
struct Opts {
    lang: Lang,
    scheme: SchemeOpt,
    tones: bool,
    unknown: Unknown,
}

fuzz_target!(|data: &[u8]| {
    let Some((s, o)) = text_and::<Opts>(data) else {
        return;
    };
    let scheme = match o.scheme {
        SchemeOpt::Default => Scheme::Default,
        SchemeOpt::StrictIso9 => Scheme::StrictIso9,
        SchemeOpt::Gost => Scheme::GostR7034,
    };
    let mut base = Transliterate::new().scheme(scheme).tones(o.tones);
    let lang = o.lang.code();
    if let Some(l) = &lang {
        base = base.lang(l.clone());
    }
    let (on_unknown, ascii_replacement) = match &o.unknown {
        Unknown::Ignore => (OnUnknown::Ignore, true),
        Unknown::DefaultReplace => (OnUnknown::default(), true),
        Unknown::Preserve => (OnUnknown::Preserve, false),
        Unknown::Replace(r) => (OnUnknown::Replace(r.clone()), r.is_ascii()),
    };
    let t = base.clone().on_unknown(on_unknown);
    // A raw `lang` the library does not know is refused, not silently replaced by the
    // default tables (the deprecated infallible `run` did that): that is the whole check
    // for such an input. Once a code is accepted, no later call with it can fail.
    let out = match t.try_run(&s) {
        Ok(out) => out,
        Err(e) => {
            assert!(lang.is_some(), "try_run failed with no lang: {e}");
            assert_eq!(e.kind(), ErrorKind::InvalidArgument, "{e}");
            return;
        }
    };

    // I1.
    if s.is_ascii() {
        assert_eq!(out, s, "I1: ASCII input changed");
    }

    // I2 and I3.
    if !o.tones && ascii_replacement {
        assert!(out.is_ascii(), "I2: non-ASCII output for {s:?}: {out:?}");
        assert_eq!(
            t.try_run(&out).expect("an accepted lang"),
            out,
            "I3: not idempotent on {s:?}"
        );
    }

    // I7, under `Ignore` and without tones, its documented scope: toned pinyin is a
    // display form whose vowels are two bytes, so U+337F under `tones = true` is
    // "zhu sh\u{ec} hu\u{ec} sh\u{e8}", 18 bytes for 3 (found by this target, and the
    // reason the scope is stated).
    let ignore = base
        .clone()
        .on_unknown(OnUnknown::Ignore)
        .try_run(&s)
        .expect("an accepted lang");
    assert!(
        o.tones || ignore.len() <= 5 * s.len() + s.chars().count(),
        "I7: {} output bytes for {} input bytes",
        ignore.len(),
        s.len()
    );

    // find_untranslatable.
    let missing = base.try_find_untranslatable(&s).expect("an accepted lang");
    for u in &missing {
        assert!(located(&s, u.offset, u.ch), "{u:?} is not in {s:?}");
    }
    if missing.is_empty() {
        let preserve = base
            .clone()
            .on_unknown(OnUnknown::Preserve)
            .try_run(&s)
            .expect("an accepted lang");
        let replace = base
            .on_unknown(OnUnknown::Replace("\u{1}".into()))
            .try_run(&s)
            .expect("an accepted lang");
        assert_eq!(
            ignore, preserve,
            "nothing untranslatable, yet Ignore != Preserve"
        );
        assert_eq!(
            ignore, replace,
            "nothing untranslatable, yet Ignore != Replace"
        );
    }
});
