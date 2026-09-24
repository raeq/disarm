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
//! - **I7** output length: `|f(s)| <= 5 * |s|_bytes + |s|_chars` under `Ignore`, with
//!   `tones = false`: the docs state it unscoped, and it does not hold with tones.
//! - `find_untranslatable` points at each character it reports, in the weak sense of
//!   [`disarm_fuzz::located`] (the documented sense does not hold, see there), and when it
//!   reports nothing the three `on_unknown` policies agree, on input NFKC leaves alone
//!   (the documented "exactly the set" does not hold for compatibility characters).
#![no_main]

use arbitrary::Arbitrary;
use disarm::api::{normalize, NormalizationForm, OnUnknown, Scheme, Transliterate};
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
    let out = t.run(&s);

    // I1.
    if s.is_ascii() {
        assert_eq!(out, s, "I1: ASCII input changed");
    }

    // I2 and I3.
    if !o.tones && ascii_replacement {
        assert!(out.is_ascii(), "I2: non-ASCII output for {s:?}: {out:?}");
        assert_eq!(t.run(&out), out, "I3: not idempotent on {s:?}");
    }

    // I7, under `Ignore` and without tones. `docs/formal-verification.md` states I7
    // unscoped, but toned pinyin is multi-byte: U+337F under `tones = true` is
    // "zhu sh\u{ec} hu\u{ec} sh\u{e8}", 18 bytes for 3 (found by this target).
    let ignore = base.clone().on_unknown(OnUnknown::Ignore).run(&s);
    assert!(
        o.tones || ignore.len() <= 5 * s.len() + s.chars().count(),
        "I7: {} output bytes for {} input bytes",
        ignore.len(),
        s.len()
    );

    // find_untranslatable.
    let missing = base.find_untranslatable(&s);
    for u in &missing {
        assert!(located(&s, u.offset, u.ch), "{u:?} is not in {s:?}");
    }
    // Weakened to input NFKC leaves alone. `find_untranslatable` is documented as
    // "exactly the set run would replace/ignore/preserve", and a compatibility character
    // breaks that: U+1F240 is NFKC "\u{3014}\u{672C}\u{3015}", its ideograph transliterates
    // and its brackets do not, so `run` gives "[?]ben[?]" while `find_untranslatable`
    // reports nothing (found by this target).
    let compat_free = normalize(&s, NormalizationForm::Nfkc) == s;
    if missing.is_empty() && compat_free {
        let preserve = base.clone().on_unknown(OnUnknown::Preserve).run(&s);
        let replace = base.on_unknown(OnUnknown::Replace("\u{1}".into())).run(&s);
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
