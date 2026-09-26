//! The preset unit tests: the fast-path audits, the step-order gates that read the
//! step lists' source, and each preset's behaviour.

/// #646 §2: `Step::Confusables` can now express the digit policy, and the fold it
/// calls actually applies it.
///
/// Before this the step held only a target script and
/// `normalize_confusables_into` did a bare map lookup, so every preset was pinned to
/// `Numeric` while the public `normalize_confusables` could be told otherwise — two
/// call paths into one fold, one of which could not say the security-relevant thing.
#[test]
fn the_confusables_step_carries_and_applies_a_digit_policy() {
    use crate::confusables::DigitPolicy;
    let ctx = PresetCtx {
        lang: None,
        strict_iso9: false,
        emoji_cldr: false,
        digit_policy: crate::confusables::DigitPolicy::Numeric,
        input_len: 0,
    };
    // Devanagari zero: `Numeric` reads it as a number, `Tr39` as an identifier
    // skeleton, `Preserve` leaves it in its own script.
    let input = "\u{0966}";
    let mut out = String::new();
    for (policy, expected) in [
        (DigitPolicy::Numeric, "0"),
        (DigitPolicy::Tr39, "o"),
        (DigitPolicy::Preserve, "\u{0966}"),
    ] {
        let ctx = PresetCtx {
            lang: ctx.lang,
            strict_iso9: ctx.strict_iso9,
            emoji_cldr: ctx.emoji_cldr,
            digit_policy: policy,
            input_len: 0,
        };
        apply_into(Step::ConfusablesCtx("latin"), input, &ctx, &mut out)
            .expect("the latin target is valid");
        assert_eq!(out, expected, "{policy:?} on U+0966");
    }
}

/// Every shipped preset still passes `Numeric`, which is what they did implicitly.
///
/// The point of #646 §2 is to widen what is *expressible*, not to change what any
/// preset does. A preset silently gaining `Tr39` would turn a number into a letter
/// inside a key — the damage `docs/architecture/prototype-policy.md` §2 prices at
/// `SKU-100` and `SKU-1O0` sharing one key.
#[test]
fn no_shipped_preset_uses_a_non_default_digit_policy() {
    // Only the module body: the test module below names `DigitPolicy::Tr39` in its
    // own assertions, and a scan over the whole file matched itself.
    let src = concat!(
        include_str!("mod.rs"),
        include_str!("steps.rs"),
        include_str!("guard.rs"),
        include_str!("runner.rs"),
        include_str!("bidi.rs"),
        include_str!("text.rs"),
        include_str!("keys.rs"),
        include_str!("verify.rs"),
    );
    let body = &src[..src.find("\nmod tests {").unwrap_or(src.len())];
    // Search for the non-default variants directly rather than for a line holding
    // both `Step::Confusables` and a policy. A step formatted across two lines has
    // neither token on the same line, so the paired search would miss exactly the
    // case a reviewer would reformat into existence (#869 review).
    let offenders: Vec<&str> = body
        .lines()
        .filter(|l| l.contains("DigitPolicy::Tr39") || l.contains("DigitPolicy::Preserve"))
        .collect();
    assert!(
        offenders.is_empty(),
        "a preset names a digit policy other than Numeric, which changes key output: \
         {offenders:?}",
    );
    // The default is the variant every preset names; asserted on the enum rather
    // than through an `as_str` that nothing in the library needs yet.
    assert!(
        body.contains("DigitPolicy::Numeric"),
        "no preset names a digit policy"
    );
}

use super::*;
use std::borrow::Cow;

use super::bidi::is_bidi_or_format;
use super::guard::{acts_on_nonascii, is_demojizable, Actionable};
use super::runner::{run, without_fastpath};
use super::steps::{apply_into, PresetCtx, Step};
use super::text::without_fold_case;
use crate::{case_fold, confusables, whitespace};

/// Every preset as a `&str -> String` closure, for the #458 fast-path checks.
/// `ml_normalize` appears under both emoji styles so the conditional demojize
/// path is exercised on each side of the guard.
#[allow(clippy::type_complexity)]
fn all_presets() -> Vec<(&'static str, Box<dyn Fn(&str) -> String>)> {
    vec![
        (
            "canonicalize",
            Box::new(|s| canonicalize(s).unwrap().into_owned()),
        ),
        (
            "canonicalize_strict",
            Box::new(|s| canonicalize_strict(s).unwrap().into_owned()),
        ),
        (
            "strip_obfuscation",
            Box::new(|s| strip_obfuscation(s).unwrap().into_owned()),
        ),
        ("strip_format", Box::new(|s| strip_format(s).into_owned())),
        (
            "search_key",
            Box::new(|s| search_key(s, None).unwrap().into_owned()),
        ),
        (
            "sort_key",
            Box::new(|s| sort_key(s, None).unwrap().into_owned()),
        ),
        (
            "catalog_key",
            Box::new(|s| catalog_key(s, None, false).unwrap().into_owned()),
        ),
        (
            "ml_normalize_cldr",
            Box::new(|s| ml_normalize(s, None, "cldr", true).unwrap().into_owned()),
        ),
        (
            "ml_normalize_none",
            Box::new(|s| ml_normalize(s, None, "none", true).unwrap().into_owned()),
        ),
        // A key builder with its own guard mask, and it was missing here, so no
        // fast-path check had ever run on it.
        (
            "skeleton_key",
            Box::new(|s| skeleton_key(s, "numeric").unwrap().into_owned()),
        ),
    ]
}

/// #458 mask audit (criterion 5): exhaustive over all 128 ASCII bytes in six
/// positions (alone, embedded, doubled, leading, trailing, spaced). For every
/// preset the guarded output must equal the un-guarded full pipeline. This
/// fails if a `Step` acts on an ASCII class the guard's mask misses — it would
/// change the byte while the guard wrongly skipped the input — or if the
/// generated `ASCII_CONFUSABLE_LATIN` set ever drifts from the table.
#[test]
fn fast_path_mask_covers_every_ascii_byte() {
    for b in 0u8..128 {
        let c = b as char;
        let probes = [
            c.to_string(),
            format!("a{c}b"),
            format!("{c}{c}"),
            format!("{c}a"),
            format!("a{c}"),
            format!("a {c} b"),
        ];
        for probe in &probes {
            for (name, f) in all_presets() {
                let guarded = f(probe);
                let full = without_fastpath(|| f(probe));
                assert_eq!(
                    guarded, full,
                    "{name}: fast path differs from full pipeline on byte {b:#04x} probe {probe:?}"
                );
            }
        }
    }
}

/// The guard's ASCII rewrite set is Latin-only; a preset using a non-Latin
/// confusable target (whose map rewrites different ASCII bytes, e.g. Cyrillic
/// `A`/`B`/`a`/`b`) must be rejected rather than silently mis-classified.
#[test]
#[should_panic(expected = "only Latin confusable targets")]
fn fast_path_rejects_non_latin_confusable_target() {
    let _ = Actionable::for_steps(&[Step::ConfusablesCtx("cyrillic")]);
}

/// L-2: the confusables fold composes base+mark clusters at lookup (#475), so it acts
/// on a decomposed homoglyph. The mask must set `marks` on the `Confusables` step
/// alone — not rely on a preceding `Nfkc` to set it — else a `Confusables`-only preset
/// would let the guard skip a decomposed homoglyph the step would fold (a bypass).
#[test]
fn confusables_step_marks_clusters_actionable() {
    assert!(
        Actionable::for_steps(&[Step::ConfusablesCtx("latin")]).marks,
        "ConfusablesCtx step must set marks (decomposed-homoglyph bypass)"
    );
    assert!(
        Actionable::for_steps(&[Step::ConfusablesNfcFixedPointCtx("latin")]).marks,
        "ConfusablesNfcFixedPointCtx step must set marks"
    );
}

/// #471: NFKC composition of conjoining Hangul jamo is a *cross-character*
/// operation — `L + V` compose into one `LV` syllable, `LV + T` into `LVT` —
/// yet each jamo is NFKC-stable in isolation and is not a combining mark, so the
/// per-character actionability test under-approximates and the guard wrongly
/// fast-paths the sequence. The guarded output must equal the full pipeline, and
/// an NFKC-bearing preset must actually compose. Was a silent normalization-
/// evasion (decomposed Hangul canonicalized differently from precomposed).
#[test]
fn fast_path_composes_conjoining_jamo() {
    // (input, the NFKC-composed syllable a composing preset must reach)
    let cases = [
        ("\u{1100}\u{1161}", "\u{AC00}"),         // L+V         → 가
        ("\u{AC00}\u{11A8}", "\u{AC01}"),         // LV syllable + T → 각
        ("\u{1100}\u{1161}\u{11A8}", "\u{AC01}"), // L+V+T       → 각
    ];
    for (input, composed) in cases {
        for (name, f) in all_presets() {
            let guarded = f(input);
            let full = without_fastpath(|| f(input));
            assert_eq!(
                guarded, full,
                "{name}: fast path differs from full pipeline on jamo {input:?}"
            );
        }
        // strip_obfuscation (NFKC first) must compose the jamo, not pass them through.
        assert_eq!(
            strip_obfuscation(input).unwrap(),
            composed,
            "strip_obfuscation should NFKC-compose {input:?}"
        );
    }

    // A grid sample across the jamo block: every L×V pair must compose (the guard
    // must decline all of them), not just the three pinned above.
    for l in 0x1100u32..=0x1112 {
        for v in 0x1161u32..=0x1175 {
            let input: String = [l, v].iter().filter_map(|&c| char::from_u32(c)).collect();
            let guarded = strip_obfuscation(&input).unwrap();
            let full = without_fastpath(|| strip_obfuscation(&input).unwrap());
            assert_eq!(guarded, full, "fast path != full on L={l:#06X} V={v:#06X}");
        }
    }
}

/// F3 (the Lean model in `formal/lean/Confusables`): the one starter outside Hangul
/// that composes with the character before it. U+16D67 U+16D67 is the NFD of
/// U+16D68, each is NFKC-stable alone and neither is a mark, so the guard fast-pathed
/// the pair and every NFKC preset returned it unnormalized under the default policy,
/// while `tr39`, which bypasses the guard, composed it.
#[test]
fn fast_path_composes_kirat_rai() {
    let cases = [
        ("\u{16D67}\u{16D67}", "\u{16D68}"),
        ("\u{16D63}\u{16D67}", "\u{16D69}"),
        ("\u{16D63}\u{16D67}\u{16D67}", "\u{16D6A}"),
    ];
    for (input, composed) in cases {
        for (name, f) in all_presets() {
            let guarded = f(input);
            let full = without_fastpath(|| f(input));
            assert_eq!(guarded, full, "{name}: fast path != full on {input:?}");
        }
        for (name, out) in [
            ("canonicalize", canonicalize(input).unwrap()),
            ("canonicalize_strict", canonicalize_strict(input).unwrap()),
            ("strip_obfuscation", strip_obfuscation(input).unwrap()),
            ("skeleton_key", skeleton_key(input, "numeric").unwrap()),
        ] {
            assert_eq!(out, composed, "{name} left {input:?} decomposed");
        }
    }
}

fn sk(text: &str, policy: &str) -> String {
    skeleton_key(text, policy).unwrap().into_owned()
}

/// F1 (the Lean model in `formal/lean/Confusables`): `skeleton_key` was not a fixed
/// point, so two spellings of one identity could key apart. Three causes, one row
/// each at least: case folding emits a decomposed sequence (U+0390), the fold leaves a
/// base beside a mark it composes with (U+00A5 + grave, and the #522 pair
/// U+04AA + cedilla), and a control or invisible between a base and its mark was
/// removed only after the fold, too late for the two to compose.
#[test]
fn skeleton_key_is_a_fixed_point_on_the_lean_witnesses() {
    let cases = [
        ("\u{0390}", "\u{1E2F}"),
        ("\u{03B0}", "\u{01D8}"),
        ("\u{00A5}\u{0300}", "\u{00FD}"),
        ("\u{04AA}\u{0327}", "c"),
        ("\u{00E7}", "c"),
        ("a\u{1}\u{0300}", "\u{00E0}"),
        ("cafe\u{1}\u{0301}", "caf\u{00E9}"),
        ("caf\u{00E9}", "caf\u{00E9}"),
        // The prototype fold must see the composed letter whatever sat in between:
        // `I` + ZWSP + acute keyed as `l` + acute, while `I` + acute keyed as U+00ED.
        ("I\u{0301}", "\u{00ED}"),
        ("I\u{200B}\u{0301}", "\u{00ED}"),
        ("I\u{1}\u{0301}", "\u{00ED}"),
        ("I\u{FE00}\u{0301}", "\u{00ED}"),
        ("I\u{202E}\u{0301}", "\u{00ED}"),
    ];
    for policy in ["numeric", "tr39", "preserve"] {
        for (input, key) in cases {
            let once = sk(input, policy);
            assert_eq!(once, key, "{policy}: skeleton_key({input:?})");
            assert_eq!(
                sk(&once, policy),
                once,
                "{policy}: not a fixed point on {input:?}"
            );
        }
    }
}

/// The same property over the classes that failed, small enough for every run: each
/// base in the Latin, Greek and Cyrillic blocks and Latin and Greek Extended, alone
/// and before each of four composing marks, directly and with a control or a
/// zero-width space between. The whole of Unicode, and every composing mark, is
/// `exhaustive_skeleton_key_*` in `tests/exhaustive_confusables.rs` (tier 3).
///
/// Also the key is never itself confusable. Under `preserve` it can be, by design:
/// that policy keeps the digit rows `is_confusable` flags (#648).
#[test]
fn skeleton_key_is_a_fixed_point_over_the_failing_classes() {
    let bases = (0x20u32..0x250)
        .chain(0x370..0x530)
        .chain(0x1E00..0x2000)
        .filter_map(char::from_u32);
    let mut failures = Vec::new();
    for base in bases {
        let mut probes = vec![base.to_string()];
        for mark in ['\u{0300}', '\u{0301}', '\u{0308}', '\u{0327}'] {
            for between in ["", "\u{1}", "\u{200B}"] {
                probes.push(format!("{base}{between}{mark}"));
            }
        }
        for probe in probes {
            let once = sk(&probe, "numeric");
            if sk(&once, "numeric") != once
                || crate::confusables::is_confusable(&once, "latin").unwrap()
            {
                failures.push(probe);
            }
        }
    }
    assert!(
        failures.is_empty(),
        "{} probes key to a non-fixed point or a confusable key: {:?}",
        failures.len(),
        &failures[..failures.len().min(10)]
    );
}

/// FP-1: the `fold_case` actionability predicate gates on the fold *table*
/// (`case_folding.tsv`), not std `is_alphabetic`, so it can neither under-mark a
/// char the fold changes nor over-mark one it leaves alone — decoupling soundness
/// from std's Unicode version. The observable proof is the over-mark direction: a
/// CJK ideograph is `is_alphabetic` (the old gate marked it) but is not in the
/// fold table, so the table-gated predicate leaves it inert; a circled capital
/// the table *does* fold stays marked.
#[test]
fn fast_path_fold_case_predicate_uses_fold_table_not_is_alphabetic() {
    let fold_only = Actionable {
        controls: false,
        collapse_ws: false,
        fold_case: true,
        confusables: false,
        nfkc: false,
        marks: false,
        strip_accents: false,
        zalgo_cap: None,
        bidi: false,
        zero_width: false,
        invisible: false,
        transliterate: false,
        demojize: false,
        prototype: false,
    };
    // `日` (U+65E5): alphabetic but not foldable — the old `is_alphabetic` gate
    // over-marked it; the fold-table gate does not.
    assert!('日'.is_alphabetic());
    assert!(crate::tables::case_folding_data::lookup('日').is_none());
    assert!(
        !acts_on_nonascii('日', fold_only, None),
        "CJK is not folded, so the table-gated predicate must leave it inert"
    );
    // `Ⓐ` (U+24B6): in the fold table (→ `ⓐ`) — must stay marked.
    assert!(crate::tables::case_folding_data::lookup('\u{24B6}').is_some());
    assert!(
        acts_on_nonascii('\u{24B6}', fold_only, None),
        "a foldable char must be marked actionable"
    );
}

/// P-3 premise: every ASCII code point is `Latin` or `Common`, so
/// `transliterate_preserving_latin_into` keeps it verbatim and may skip the
/// per-char script binary search. Lock the assumption.
#[test]
fn ascii_is_always_kept_verbatim() {
    for b in 0u8..128 {
        let script = crate::scripts::block_script(b as char);
        assert!(
            matches!(script, "Latin" | "Common" | "Inherited"),
            "ASCII U+{b:02X} has script {script:?} — the P-3 ASCII fast path would mis-handle it"
        );
    }
}

/// Runs are grouped by the *block* script, not by `Script` (Finding 5 of the Lean
/// detection model). The katakana prolonged sound mark is Common to the UCD, and
/// splitting the run at it would keep it verbatim in a key instead of lengthening
/// the vowel before it: `U+30B3 U+30FC` is `ko-`, not `ko` + `U+30FC`. Bopomofo,
/// which nothing romanizes, stays verbatim as it did while it resolved to no script.
#[test]
fn a_common_mark_in_a_script_block_stays_in_its_run() {
    let mut out = String::new();
    super::keys::transliterate_preserving_latin_into(
        "\u{30B3}\u{30FC}\u{30D2}\u{30FC}",
        None,
        &mut out,
    );
    assert_eq!(out, "ko-hi-");
    super::keys::transliterate_preserving_latin_into("\u{3105}\u{3106}", None, &mut out);
    assert_eq!(out, "\u{3105}\u{3106}");
}

/// `is_demojizable` must still cover everything `demojize` rewrites (#990).
///
/// It is a conservative superset guarding a fast path: over-marking costs a skipped
/// optimisation, under-marking silently skips text a step would have changed. That
/// used to hold by construction, because `demojize`'s unknown-emoji branch *was*
/// `is_emoji_codepoint`. It now asks `unnamed_emoji_len_at`, and containment holds
/// only because the twelve `Emoji_Presentation` code points outside
/// `is_emoji_codepoint`'s ranges — `U+231A`, `U+23E9`, `U+25FD`, `U+2B1B` and their
/// neighbours — happen to be in the CLDR name table. That is a contingency, so it is asserted rather than assumed:
/// the exhaustive sweep below is `#[ignore]`d for pre-release, and this is cheap
/// enough to run every time.
#[test]
fn is_demojizable_covers_every_emoji_presentation_code_point() {
    for cp in 0u32..=0x10_FFFF {
        let Some(ch) = char::from_u32(cp) else {
            continue;
        };
        if ch.is_ascii() || !crate::tables::is_emoji_presentation(ch) {
            continue;
        }
        assert!(
            is_demojizable(ch),
            "U+{cp:04X} is Emoji_Presentation and `demojize` rewrites it, but \
             the fast path does not mark it actionable"
        );
    }
}

/// Option D exhaustive audit (tier 3): every BMP + key-astral code point, in
/// three positions, through every preset — the guarded output must equal the
/// un-guarded full pipeline. Catches any non-ASCII class the conservative
/// `acts_on_nonascii` predicate under-marks. ~0.6M comparisons; run pre-release.
#[test]
#[ignore = "tier 3: exhaustive over the BMP + astral emoji/tag ranges — run before release"]
fn fast_path_nonascii_exhaustive() {
    let presets = all_presets();
    let check = |cp: u32| {
        let Some(ch) = char::from_u32(cp) else { return };
        if ch.is_ascii() {
            return;
        }
        for probe in [format!("{ch}"), format!("a{ch}z"), format!("{ch} {ch}")] {
            for (name, f) in &presets {
                let guarded = f(&probe);
                let full = without_fastpath(|| f(&probe));
                assert_eq!(
                    guarded, full,
                    "{name}: fast path differs from full pipeline on U+{cp:04X} probe {probe:?}"
                );
            }
        }
    };
    for cp in 0x80..=0xFFFFu32 {
        check(cp);
    }
    // Astral ranges where actionable classes live: emoji, tags, math alphanum,
    // and supplementary noncharacters/PUA.
    for cp in (0x1D400..=0x1D7FF) // Mathematical Alphanumeric
        .chain(0x1F000..=0x1FAFF) // emoji
        .chain(0xE0000..=0xE007F) // Tags
        .chain(0xF0000..=0xF00FF)
    // PUA-A sample
    {
        check(cp);
    }
    // #471: the per-character probes above never place two *different*
    // conjoining jamo adjacent, so they cannot see cross-character NFKC
    // composition (`L+V` → one syllable). Sweep the conjoining-jamo grid in
    // `L+V` and `L+V+T` order — every pair must match the full pipeline.
    for l in 0x1100u32..=0x1112 {
        for v in 0x1161u32..=0x1175 {
            for t in std::iter::once(None).chain((0x11A8u32..=0x11C2).map(Some)) {
                let probe: String = [Some(l), Some(v), t]
                    .into_iter()
                    .flatten()
                    .filter_map(char::from_u32)
                    .collect();
                for (name, f) in &presets {
                    let guarded = f(&probe);
                    let full = without_fastpath(|| f(&probe));
                    assert_eq!(
                        guarded, full,
                        "{name}: fast path differs from full pipeline on jamo {probe:?}"
                    );
                }
            }
        }
    }
}

/// #464: benign ASCII that is clean except for whitespace (leading / trailing /
/// doubled spaces, or a fold-control) takes the `WhitespaceOnly` path — the
/// pipeline reduces to one `collapse_whitespace` pass. The output must equal both
/// `collapse_whitespace` *and* the un-guarded full pipeline, for every preset.
#[test]
fn whitespace_only_fast_path_matches_full_pipeline() {
    let probes = [
        "hello world ",         // trailing space
        " hello world",         // leading space
        "hello  world",         // doubled interior space
        "  hello   world  ",    // all three
        "hello\tworld",         // fold-control (TAB)
        "a\rb\nc",              // CR + LF fold-controls
        "the quick brown fox ", // longer, lowercase (no FoldCase trigger)
        // benign non-ASCII present but inert (Option D) + ASCII whitespace dirt:
        // still WhitespaceOnly for the non-transliterating presets.
        "café  date",
    ];
    for probe in probes {
        let collapsed = whitespace::collapse_whitespace(probe);
        for (name, f) in all_presets() {
            let guarded = f(probe);
            let full = without_fastpath(|| f(probe));
            assert_eq!(
                guarded, full,
                "{name}: WhitespaceOnly fast path differs from full pipeline on {probe:?}"
            );
            // For the pure whitespace-hygiene presets the result is exactly the
            // collapse (no transliteration/folding can apply to lowercase ASCII).
            if matches!(
                name,
                "canonicalize" | "canonicalize_strict" | "strip_format"
            ) {
                assert_eq!(
                    guarded, collapsed,
                    "{name}: WhitespaceOnly result should equal collapse_whitespace on {probe:?}"
                );
            }
        }
    }
}

/// #464: whitespace dirt combined with a *non*-whitespace actionable byte must
/// fall through to the full pipeline, not the WhitespaceOnly shortcut. If the
/// shortcut fired here it would skip case folding / confusable folding / control
/// stripping and silently corrupt the output.
#[test]
fn whitespace_plus_other_action_takes_full_pipeline() {
    for probe in [
        "Hello  World",    // doubled space + uppercase (FoldCase presets)
        "hello  \u{0007}", // doubled space + BEL control (StripControl presets)
        "café  CAFÉ ",     // whitespace + accented uppercase
    ] {
        for (name, f) in all_presets() {
            let guarded = f(probe);
            let full = without_fastpath(|| f(probe));
            assert_eq!(
                guarded, full,
                "{name}: guarded != full on mixed whitespace+action input {probe:?}"
            );
        }
    }
}

/// #614: inside a comparison preset the TR39 fold wins over the emoji name.
#[test]
fn strip_obfuscation_folds_the_rows_tr39_also_claims() {
    // CVE-2017-5383. The euro sign is not an emoji; it reaches the emoji table
    // from CLDR annotationsDerived, which names non-emoji characters.
    assert_eq!(
        strip_obfuscation("\u{20AC}xample.com").unwrap(),
        "example.com"
    );
    // Every glyph the CVE names now collapses onto its ASCII form.
    for spoof in [
        "ex\u{2010}ample.com",
        "ex\u{2011}ample.com",
        "ex\u{2212}ample.com",
    ] {
        assert_eq!(
            strip_obfuscation(spoof).unwrap(),
            strip_obfuscation("ex-ample.com").unwrap(),
            "{spoof:?}"
        );
    }
}

/// The skip is scoped: standalone `demojize` still names them.
#[test]
fn standalone_demojize_still_names_the_claimed_rows() {
    let mut out = String::new();
    crate::emoji::demojize_rust_into(
        "I \u{2764} \u{20AC}5",
        false,
        crate::emoji::NamePolicy::NAME_EVERYTHING,
        &mut out,
    );
    assert_eq!(out, "I red heart euro 5");
}

/// The TR39 folds that #614's separator logic was protecting still happen (#910).
///
/// That review found `\u{20AC}` fusing onto the emoji name before it: the euro is not
/// alphanumeric, but TR39 folds it to `e`, so emitting it bare after "woman's hat"
/// produced "woman's hate" — a word in neither the input nor any emoji name.
///
/// There is no name to fuse onto now, so the separator question is gone. The folds
/// themselves are what mattered underneath it, and they are asserted here so removing
/// the naming step did not quietly take them along.
#[test]
fn the_tr39_folds_behind_the_separator_rule_still_happen() {
    for (input, expected) in [
        ("\u{1F452}\u{20AC}", "\u{1F452}e"),
        ("\u{1F452}\u{2211}", "\u{1F452}s"),
        ("\u{1F452}\u{2200}", "\u{1F452}a"),
        ("\u{1F452}\u{2010}", "\u{1F452}-"),
    ] {
        assert_eq!(strip_obfuscation(input).unwrap(), expected, "{input:?}");
    }
}

/// Idempotence, which the naming step used to complicate (#910).
///
/// The confusable pass ran after `demojize` precisely so the `\u{2019}` inside
/// "woman's hat" was folded; otherwise a second call folded it and the preset was not
/// a fixed point. With no names emitted there is no punctuation to chase, and this
/// asserts the property directly rather than through the arrangement that protected it.
#[test]
fn strip_obfuscation_is_a_fixed_point_on_an_emoji() {
    let once = strip_obfuscation("\u{1F452}").unwrap();
    assert_eq!(once, "\u{1F452}");
    assert_eq!(strip_obfuscation(&once).unwrap(), once);
}

/// #615: a mark whose own script differs from its base's is the CVE-2017-7833
/// shape, and only `canonicalize_strict` removes it.
#[test]
fn canonicalize_strict_drops_a_cross_script_mark() {
    // U+0651 ARABIC SHADDA on a Latin base.
    assert_eq!(
        canonicalize_strict("exa\u{651}mple.com").unwrap(),
        canonicalize_strict("example.com").unwrap()
    );
    // U+0E31 THAI MAI HAN AKAT — ccc == 0, so a combining-class test would miss it.
    assert_eq!(
        canonicalize_strict("exa\u{E31}mple.com").unwrap(),
        canonicalize_strict("example.com").unwrap()
    );
}

/// An `Inherited` mark attaches to anything, so ordinary diacritics survive.
#[test]
fn canonicalize_strict_keeps_ordinary_diacritics() {
    for text in ["caf\u{e9}", "na\u{ef}ve", "Vi\u{1ec7}t Nam"] {
        assert_eq!(canonicalize_strict(text).unwrap(), text, "{text:?}");
    }
}

/// #638: stripping the mark can expose a COMPOSITION the fold already finished
/// with, so the two steps have to iterate together.
///
/// `U+0489` has ccc 0, which makes it a *starter*: it blocks `C` + `U+0327` from
/// composing, so the fold's fixed point correctly finds nothing to do. Removing it
/// leaves the two adjacent, the terminal NFC composes them into `Ç`, and `Ç` folds
/// to `C` — one pass too late. The preset returned `Ç` and then `C`, which is a
/// comparison key that depends on how many times you applied it.
#[test]
fn canonicalize_strict_folds_what_the_mark_strip_exposes() {
    for (input, expected) in [("C\u{489}\u{327}", "C"), ("c\u{489}\u{327}", "c")] {
        let once = canonicalize_strict(input).unwrap();
        assert_eq!(once, expected, "{input:?}");
        assert_eq!(
            canonicalize_strict(&once).unwrap(),
            once,
            "{input:?} is not a fixed point"
        );
    }
}

/// The blocking starter is not a curiosity: 474 code points reach that shape in
/// the `C` + X + cedilla probe alone. Sampled here rather than swept, because the
/// exhaustive form belongs in the proptest that found it.
#[test]
fn the_blocking_starters_are_a_class_not_one_character() {
    // U+0488 COMBINING CYRILLIC HUNDRED THOUSANDS SIGN, and a Thaana vowel sign —
    // both ccc 0, both script-specific, both removed by the #615 rule.
    for blocker in ['\u{488}', '\u{489}', '\u{7A6}', '\u{7AF}'] {
        let input = format!("C{blocker}\u{327}");
        let once = canonicalize_strict(&input).unwrap();
        assert_eq!(
            canonicalize_strict(&once).unwrap(),
            once,
            "U+{:04X} leaves a non-fixed point",
            blocker as u32
        );
    }
}

/// `canonicalize` deliberately does NOT get the rule — it is destructive for
/// scholarly transliteration, so it stays behind the stricter contract.
#[test]
fn canonicalize_does_not_get_the_cross_script_rule() {
    let eclipsed = "exa\u{651}mple.com";
    assert_ne!(
        canonicalize(eclipsed).unwrap(),
        canonicalize("example.com").unwrap()
    );
}

#[test]
fn preset_golden_fixtures() {
    // Frozen pre-refactor outputs — lock byte-identity for the #430 byte-stable
    // aliases (canonicalize, strip_format, canonicalize_strict) and the hot-path
    // keys. Regenerate ONLY with explicit sign-off: changing one is an API break
    // for the byte-stable aliases. Generated by running the pre-refactor impl.
    //
    // #788 moved two of these, with sign-off, and the input is why: `o` followed by
    // THREE combining acutes is 3 marks, and `is_zalgo` fires only ABOVE 3 — so this
    // string is ordinary text by the library's own predicate, and `canonicalize` was
    // removing a mark from it anyway. The fixture had frozen that. `strip_format`
    // does not run the zalgo step and is unchanged, which is the control.
    //
    // #835 moved the same entry again, for the opposite reason: three acutes is not
    // too MANY marks, it is the same mark three times, which renders as one and which
    // no keyboard produces. So the row now folds to a single acute. `strip_format` is
    // still the control and still unchanged.
    let alias_in = "Ηеllо\u{202E}\u{200B}Wo\u{0301}\u{0301}\u{0301}rld\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}";
    assert_eq!(
        canonicalize(alias_in).unwrap(),
        "HelloW\u{f3}rld\u{1f3f4}\u{e0067}\u{e0062}\u{e0073}\u{e0063}\u{e0074}\u{e007f}"
    );
    assert_eq!(
        strip_format(alias_in),
        "\u{397}\u{435}ll\u{43e}Wo\u{301}\u{301}\u{301}rld\u{1f3f4}\u{e0067}\u{e0062}\u{e0073}\u{e0063}\u{e0074}\u{e007f}"
    );
    assert_eq!(
        canonicalize_strict(alias_in).unwrap(),
        "HelloW\u{f3}rld\u{1f3f4}\u{e0067}\u{e0062}\u{e0073}\u{e0063}\u{e0074}\u{e007f}"
    );
    assert_eq!(search_key("CAFÉ\u{200B} ИМЯ", None).unwrap(), "cafe imya");
    assert_eq!(
        catalog_key("Война и МИР\u{00AD}", None, false).unwrap(),
        "voyna i mir"
    );
    assert_eq!(sort_key("Über ИМЯ", None).unwrap(), "\u{fc}ber imya");
    assert_eq!(
        ml_normalize("Café \u{1F600} ИМЯ", Some("ru"), "cldr", true).unwrap(),
        "cafe grinning face imya"
    );
    assert_eq!(
        strip_obfuscation("Ηеllо\u{202E}Wоrld \u{1F600}").unwrap(),
        "HelloWorld \u{1F600}"
    );
}

#[test]
fn run_executes_steps_in_order_with_pingpong() {
    let steps = &[Step::StripBidi, Step::FoldCase, Step::CollapseWs];
    let ctx = PresetCtx {
        lang: None,
        strict_iso9: false,
        emoji_cldr: false,
        digit_policy: crate::confusables::DigitPolicy::Numeric,
        input_len: 0,
    };
    let got = run(steps, "  HE\u{202E}LLO  ", &ctx).unwrap();
    let want = whitespace::collapse_whitespace(&case_fold::fold_case_impl(&strip_bidi(
        "  HE\u{202E}LLO  ",
    )));
    assert_eq!(got, want);
}

#[test]
fn run_empty_steps_is_identity() {
    let ctx = PresetCtx {
        lang: None,
        strict_iso9: false,
        emoji_cldr: false,
        digit_policy: crate::confusables::DigitPolicy::Numeric,
        input_len: 0,
    };
    assert_eq!(run(&[], "café \u{202E}x", &ctx).unwrap(), "café \u{202E}x");
}

#[test]
fn run_skips_noop_steps_without_corrupting_buffers() {
    // NfcIfNonAscii is a no-op on ASCII; gated Transliterate is a no-op with lang=None.
    // A no-op in the MIDDLE of the chain must not leak stale scratch into the next step.
    let ctx = PresetCtx {
        lang: None,
        strict_iso9: false,
        emoji_cldr: false,
        digit_policy: crate::confusables::DigitPolicy::Numeric,
        input_len: 0,
    };
    let steps = &[
        Step::FoldCase,
        Step::NfcIfNonAscii,
        Step::Transliterate {
            mode: crate::ErrorMode::Preserve,
            only_if_lang: true,
        },
        Step::CollapseWs,
    ];
    assert_eq!(
        run(steps, "  HELLO   WORLD  ", &ctx).unwrap(),
        "hello world"
    );
}

// #431: canonicalize / canonicalize_strict no longer neutralize path
// separators — '/' and '\' pass through (defend traversal at the sink).
#[test]
fn test_presets_do_not_mangle_path_separators() {
    assert_eq!(
        canonicalize("https://example.com/path").unwrap(),
        "https://example.com/path"
    );
    assert_eq!(canonicalize("../etc/passwd").unwrap(), "../etc/passwd");
    assert_eq!(canonicalize_strict("a/b\\c").unwrap(), "a/b\\c");
}

// ── strip_bidi: exhaustive UAX #9 coverage ────────────────
// Every character in is_bidi_or_format gets its own assertion so
// that a future omission is caught immediately.

#[test]
fn test_strip_bidi_soft_hyphen() {
    assert_eq!(strip_bidi("pass\u{00AD}word"), "password");
}

#[test]
fn test_strip_bidi_arabic_letter_mark() {
    // U+061C — added in Unicode 6.3; lives in the Arabic block,
    // far from the other bidi controls, which is why it was missed.
    assert_eq!(strip_bidi("hello\u{061C}world"), "helloworld");
}

#[test]
fn test_strip_bidi_marks() {
    assert_eq!(strip_bidi("a\u{200E}b"), "ab"); // LRM
    assert_eq!(strip_bidi("a\u{200F}b"), "ab"); // RLM
}

#[test]
fn test_strip_bidi_embeddings_overrides() {
    assert_eq!(strip_bidi("a\u{202A}b"), "ab"); // LRE
    assert_eq!(strip_bidi("a\u{202B}b"), "ab"); // RLE
    assert_eq!(strip_bidi("a\u{202C}b"), "ab"); // PDF
    assert_eq!(strip_bidi("a\u{202D}b"), "ab"); // LRO
    assert_eq!(strip_bidi("a\u{202E}b"), "ab"); // RLO
}

#[test]
fn test_strip_bidi_isolates() {
    assert_eq!(strip_bidi("a\u{2066}b"), "ab"); // LRI
    assert_eq!(strip_bidi("a\u{2067}b"), "ab"); // RLI
    assert_eq!(strip_bidi("a\u{2068}b"), "ab"); // FSI
    assert_eq!(strip_bidi("a\u{2069}b"), "ab"); // PDI
}

#[test]
fn test_strip_bidi_all_at_once() {
    // Every UAX #9 bidi char + soft hyphen in a single string.
    // If a new char is added to is_bidi_or_format, add it here too.
    let all_bidi = "\u{00AD}\u{061C}\u{200E}\u{200F}\
                    \u{202A}\u{202B}\u{202C}\u{202D}\u{202E}\
                    \u{2066}\u{2067}\u{2068}\u{2069}";
    assert_eq!(strip_bidi(&format!("x{all_bidi}y")), "xy");
    // Verify we have exactly 13 characters in the list
    assert_eq!(all_bidi.chars().count(), 13);
}

#[test]
fn test_strip_bidi_preserves_normal() {
    assert_eq!(strip_bidi("hello world"), "hello world");
    assert_eq!(strip_bidi("café"), "café");
    // Arabic text itself is preserved — only formatting chars are stripped
    assert_eq!(strip_bidi("مرحبا"), "مرحبا");
}

#[test]
fn strip_bidi_has_no_ascii_targets() {
    // Premise for the strip_bidi_into ASCII fast path (review D-3): no ASCII
    // code point is a bidi/format character, so ASCII passes through whole.
    for cp in 0u8..=0x7F {
        assert!(
            !is_bidi_or_format(cp as char),
            "ASCII U+{cp:02X} must not be a bidi/format target"
        );
    }
}

#[test]
fn test_canonicalize_homoglyph() {
    // Cyrillic р and а in "раypal"
    let result = canonicalize("\u{0440}\u{0430}ypal").unwrap();
    assert_eq!(result, "paypal");
}

#[test]
fn test_canonicalize_bidi() {
    let result = canonicalize("admin\u{202E}user").unwrap();
    assert_eq!(result, "adminuser");
}

#[test]
fn test_canonicalize_arabic_letter_mark() {
    let result = canonicalize("admin\u{061C}user").unwrap();
    assert_eq!(result, "adminuser");
}

#[test]
fn test_canonicalize_invisible_math_operators() {
    // Invisible math operators are stripped by collapse_whitespace (step 3),
    // so canonicalize should remove them too.
    let result = canonicalize("pass\u{2061}word").unwrap();
    assert_eq!(result, "password");
}

#[test]
fn test_canonicalize_soft_hyphen() {
    let result = canonicalize("pass\u{00AD}word").unwrap();
    assert_eq!(result, "password");
}

#[test]
fn test_canonicalize_zwsp() {
    let result = canonicalize("admin\u{200B}user").unwrap();
    assert_eq!(result, "adminuser");
}

#[test]
fn test_canonicalize_idempotent_on_invisible_separated_mark() {
    // #416: stripping the zero-width leaves `a` adjacent to U+0301 (combining
    // acute) — a decomposed sequence the leading NFKC passed over. The
    // terminal NFC recomposes it on the FIRST pass, so f(f(x)) == f(x).
    for sep in ['\u{200B}', '\u{200C}', '\u{200D}', '\u{FEFF}'] {
        let input = format!("a{sep}\u{0301}b");
        let once = canonicalize(&input).unwrap();
        assert_eq!(once, "\u{00E1}b", "sep {sep:?} should compose to á+b");
        assert_eq!(
            once,
            canonicalize(&once).unwrap(),
            "sep {sep:?} not idempotent"
        );
    }
}

#[test]
fn test_presets_idempotent_on_duplicate_combining_marks() {
    // #434: a duplicate combining mark used to break the confusables sandwich.
    // `c`+◌̧+◌̧: NFC composes one cedilla → `ç`, the fold drops it → `c`, and the
    // recomposing NFC reattaches the spare → `ç`, which the next pass folds to
    // `c` — non-idempotent. The fixed-point loop folds all the way to `c`.
    let input = "c\u{0327}\u{0327}"; // c + two COMBINING CEDILLA
    for preset in [
        canonicalize(input).unwrap(),
        canonicalize_strict(input).unwrap(),
    ] {
        assert_eq!(preset, "c", "should fold to a bare c in one call");
    }
    assert_eq!(canonicalize("c").unwrap(), canonicalize(input).unwrap());
    assert_eq!(
        canonicalize_strict("c").unwrap(),
        canonicalize_strict(input).unwrap()
    );
}

/// #843's zalgo cap was placed before the zero-width strip, so an invisible could
/// split a mark run, survive the count, and then be deleted — merging the runs for
/// the next pass, which truncated further. Found by `sort_key_idempotent` on a
/// later PR's CI, minimal input below.
#[test]
fn sort_key_zalgo_cap_runs_after_the_zero_width_strip() {
    // Four DISTINCT marks, all combining class 230, split by a zero-width. Distinct
    // deliberately: #835 made the cap drop a repeat of the same mark whatever the cap
    // allows, so the original four-identical-acutes input now collapses to one mark
    // for that reason and stops exercising the ordering this test is about.
    let input = "\u{300}\u{301}\u{302}\u{200b}\u{303}";
    let once = sort_key(input, None).unwrap();
    let twice = sort_key(&once, None).unwrap();
    assert_eq!(once, twice, "sort_key must be idempotent on {input:?}");
    // The four are one run once the ZWSP is gone, so the cap applies to all four on
    // the first pass rather than to two runs of three and one.
    let marks = once
        .chars()
        .filter(|c| unicode_normalization::char::canonical_combining_class(*c) == 230)
        .count();
    assert_eq!(marks, crate::zalgo::DEFAULT_MAX_MARKS);
}

/// #874 review: the repeat step must do **no work** when there is no repeat.
///
/// It first normalized to NFC on that path, and every pipeline that uses it runs the
/// zalgo cap immediately after — which does its own NFD→NFC pass. So the common case,
/// text with no repeated mark at all, paid for two full normalizations to arrive at
/// the same bytes. `apply_into` already has a no-op signal; the step now uses it.
///
/// Asserted on the return value rather than on the output, because the output was
/// correct either way. That is what made it invisible to every other test here.
#[test]
fn the_repeat_step_is_a_no_op_when_nothing_repeats() {
    let ctx = PresetCtx {
        lang: None,
        strict_iso9: false,
        emoji_cldr: false,
        digit_policy: crate::confusables::DigitPolicy::Numeric,
        input_len: 0,
    };
    let mut out = String::new();
    for input in [
        "hello",
        "caf\u{e9}",
        "cafe\u{301}",
        "Vi\u{1ec7}t",
        // Two DIFFERENT marks on one base: acute then grave. The rule is about the
        // repeat, not about stacking.
        "\u{e1}\u{300}",
    ] {
        out.clear();
        let wrote = apply_into(Step::DropRepeatedMarks, input, &ctx, &mut out).unwrap();
        assert!(
            !wrote,
            "{input:?} has no repeated mark but the step claimed a rewrite"
        );
        assert!(
            out.is_empty(),
            "{input:?}: a no-op must not touch the scratch buffer"
        );
    }
    // And it still reports a rewrite when there IS one, or the no-op path would be
    // hiding the whole feature.
    for (input, expected) in [
        ("a\u{301}\u{301}", "\u{e1}"),
        // Precomposed plus the same mark again. It is only a repeat in NFD, which is
        // why the check decomposes rather than scanning the input as written — and
        // it is exactly #835's case: this renders as `\u{e1}` and nothing else.
        ("\u{e1}\u{301}", "\u{e1}"),
    ] {
        out.clear();
        let wrote = apply_into(Step::DropRepeatedMarks, input, &ctx, &mut out).unwrap();
        assert!(wrote, "{input:?} repeats a mark in NFD");
        assert_eq!(out, expected, "{input:?}");
    }
}

/// The ordering constraint itself, for every pipeline that caps marks.
///
/// `canonicalize` has carried this rule as a prose comment since #121 — a stripped
/// invisible between two marks must not be able to split a run and hide the count —
/// and nothing checked it. #843 then violated it in `sort_key`. The `STEPS` arrays
/// are function-local consts, so this reads the source: it is the only way to see
/// every pipeline at once, and a new builder is covered the day it is written.
#[test]
fn every_zalgo_cap_runs_after_its_invisible_strip() {
    let src = concat!(include_str!("text.rs"), include_str!("keys.rs"));
    let mut checked = 0;
    for (name, body) in step_arrays(src) {
        // Every step whose result depends on how marks are grouped into runs, not
        // just the cap. #835's `DropRepeatedMarks` has the identical hazard for the
        // identical reason — a zero-width between two acutes hides the repeat from
        // it exactly as it hides the count from the cap — and a gate that names only
        // `Step::Zalgo(` would have gone on passing while a new step reintroduced
        // the bug it exists to catch.
        for step in ["Step::Zalgo(", "Step::DropRepeatedMarks"] {
            let Some(z) = body.find(step) else {
                continue;
            };
            // `Step::Zalgo(0)` removes every mark whatever the run structure, so a
            // split run cannot change its output and the ordering does not bind.
            // `strip_obfuscation` relies on this;
            // `zalgo_zero_is_order_independent` below checks the exemption is real
            // rather than assumed.
            if body[z..].starts_with("Step::Zalgo(0)") {
                continue;
            }
            let before = &body[..z];
            // EVERY step that can delete a character from between two marks, not just
            // the one this gate was first written for. #850 checked `StripZeroWidth`
            // alone, which is why it did not see #862: `ConfusablesMarkFixedPoint`
            // carries the #615 cross-script mark strip, and that removes *marks* —
            // so a cross-script mark split two runs, survived the count, was deleted,
            // and the runs merged for the next pass.
            //
            // Naming them rather than accepting "any strip" is deliberate: an
            // over-broad gate is what let #850's own bug through. Add to this list when
            // a step gains the ability to remove a character, and the ordering is
            // enforced for every pipeline at once.
            for remover in MARK_RUN_SPLITTERS {
                assert!(
                    before.contains(remover),
                    "{name}: {step} runs before {remover}, which can delete a \
                 character from between two mark runs — the runs then merge on the \
                 next pass and the mark rule sees a different grouping (#121, #850, \
                 #862, #835)",
                );
            }
            checked += 1;
        }
    }
    assert!(
        checked >= 6,
        "expected the cap AND the repeat rule in each of canonicalize, \
         canonicalize_strict and sort_key; found {checked} — has the parser drifted?",
    );
}

/// The exemption the ordering gate grants `Step::Zalgo(0)`: with a cap of zero, an
/// invisible splitting a mark run cannot change the result, because every mark goes
/// either way. Checked rather than assumed.
#[test]
fn zalgo_zero_is_order_independent() {
    let split = "a\u{301}\u{301}\u{301}\u{200b}\u{301}b";
    let joined = "a\u{301}\u{301}\u{301}\u{301}b";
    let once = strip_obfuscation(split).unwrap();
    assert_eq!(once, strip_obfuscation(joined).unwrap());
    assert_eq!(once, strip_obfuscation(&once).unwrap());
    assert!(
        !once.contains('\u{301}'),
        "cap 0 must leave no marks: {once:?}"
    );
}

/// A confusable fold can *create* a repeated mark, after the pass that drops them.
///
/// `no_pipeline_truncates_further_on_a_second_pass` uses `'a'` as its base, so its
/// fold is a no-op and it can only ever exercise repeats present in the *input*. This
/// class needs a base whose fold target carries a mark of its own: `U+1EF3` (y with
/// grave) folds to `U+00FD` (y with acute), whose NFD is `y` + acute — so a following
/// combining acute becomes a duplicate the fold manufactured, one step after the pass
/// that removes duplicates already ran.
///
/// `canonicalize` was not idempotent on 16 such pairs, and every idempotence sweep in
/// this repository walked single code points. This needs a base *and* a mark, so none
/// of them could see it.
#[test]
fn a_fold_that_creates_a_repeated_mark_is_still_a_fixed_point() {
    for (base, mark) in [
        ('\u{1ef3}', '\u{301}'), // y with grave  -> y with acute
        ('\u{1ef7}', '\u{301}'), // y with hook   -> y with acute
        ('\u{010b}', '\u{301}'), // c with dot    -> c with acute
        ('\u{0101}', '\u{303}'), // a with macron -> a with tilde
        ('\u{01e7}', '\u{306}'), // g with caron  -> g with breve
    ] {
        let input: String = [base, mark].into_iter().collect();
        let once = canonicalize(&input).unwrap().into_owned();
        let twice = canonicalize(&once).unwrap().into_owned();
        assert_eq!(
            once, twice,
            "canonicalize is not a fixed point on {input:?}: the fold created a \
             repeated mark after the pass that removes them (#835)",
        );
        // The other two builders are already clean — #862 put their cap after the
        // fold, so their single `DropRepeatedMarks` is downstream of it — and they
        // are asserted here so a future reordering cannot quietly break them.
        let strict = canonicalize_strict(&input).unwrap().into_owned();
        assert_eq!(
            strict,
            canonicalize_strict(&strict).unwrap().into_owned(),
            "canonicalize_strict is not a fixed point on {input:?}",
        );
        let sorted = sort_key(&input, None).unwrap().into_owned();
        assert_eq!(
            sorted,
            sort_key(&sorted, None).unwrap().into_owned(),
            "sort_key is not a fixed point on {input:?}",
        );
    }
}

/// A confusable fold can MOVE a mark, after the cap that counted it: `ģ` (a cedilla,
/// below) folds to `ġ` (a dot, above). `ǧ` + U+0327 + three marks above: the cedilla
/// composed into `ģ`, the cap kept the three marks above, and the fold made a fourth,
/// which the next call cut. Found by the `presets` fuzz target.
///
/// The sweep crosses every Latin fold whose source or target carries a mark with three
/// marks from above and below, which is the shape a moved mark needs.
#[test]
fn a_fold_that_moves_a_mark_is_still_a_fixed_point() {
    use unicode_normalization::UnicodeNormalization;
    let found = "\u{1E7}\u{327}\u{367}\u{327}\u{327}\u{327}\u{303}";
    let once = canonicalize(found).unwrap().into_owned();
    assert_eq!(once, "\u{121}\u{30C}\u{367}");
    assert_eq!(canonicalize(&once).unwrap(), once);

    let marked = |s: &str| s.nfd().any(unicode_normalization::char::is_combining_mark);
    let map = crate::tables::resolve_confusable_map("latin").unwrap();
    let bases: Vec<char> = map
        .entries()
        .filter(|&(&key, &value)| marked(&key.to_string()) || marked(value))
        .map(|(&key, _)| key)
        .collect();
    assert!(bases.len() > 20, "{} bases", bases.len());
    let marks = [
        '\u{300}', '\u{301}', '\u{303}', '\u{304}', '\u{307}', '\u{308}', '\u{30C}', '\u{367}',
        '\u{323}', '\u{327}', '\u{328}',
    ];
    let builders: [(&str, fn(&str) -> String); 3] = [
        ("canonicalize", |t| canonicalize(t).unwrap().into_owned()),
        ("canonicalize_strict", |t| {
            canonicalize_strict(t).unwrap().into_owned()
        }),
        ("sort_key", |t| sort_key(t, None).unwrap().into_owned()),
    ];
    let mut failures = Vec::new();
    for &base in &bases {
        for &a in &marks {
            for &b in &marks {
                for &c in &marks {
                    let input: String = [base, a, b, c].into_iter().collect();
                    for (name, f) in builders {
                        let once = f(&input);
                        if f(&once) != once {
                            failures.push(format!("{name} {input:?}"));
                        }
                    }
                }
            }
        }
    }
    assert!(
        failures.is_empty(),
        "{} not fixed points: {:?}",
        failures.len(),
        &failures[..failures.len().min(10)]
    );
}

/// Every step that can delete a character sitting between two combining marks.
///
/// A mark cap counts *runs*, so anything that removes a character between two of
/// them changes the count — and if the removal happens after the count, the runs
/// merge and the next pass truncates further. That is #121, and it has now been
/// found three times: `canonicalize` (#121), `sort_key` (#850) and
/// `canonicalize_strict` (#862). Each time the fix was to move the cap.
///
/// `ConfusablesMarkFixedPoint` is deliberately NOT here, and that is the limit of
/// what a source-order gate can do: it carries the #615 cross-script mark strip, but
/// only in strict mode, and the step list does not say which mode a pipeline runs in
/// — `canonicalize` keeps `U+0489` where `canonicalize_strict` removes it. Reading
/// the list alone would fail `canonicalize` for a bug it does not have.
///
/// That case is covered by `no_pipeline_truncates_further_on_a_second_pass` below,
/// which asks the pipelines rather than the source and so sees every remover
/// whatever its mode.
const MARK_RUN_SPLITTERS: &[&str] = &[
    "Step::StripZeroWidth",
    "Step::StripInvisible",
    // #863 review. #121's rule names control stripping explicitly, and a C0 control
    // between two marks splits a run for the count exactly as a zero-width does.
    // Left out of the first draft because the zero-width case was the one in hand,
    // which is how a gate ends up narrower than the rule it enforces.
    "Step::StripControl",
];

/// Every mark-capping pipeline is idempotent on a run split by a removable
/// character — whichever step does the removing (#862).
///
/// The source-order gate above reads the step list, which cannot see a step that
/// removes marks only in one mode. This asks the functions instead: it is weaker
/// about *why* a pipeline fails and stronger about *whether* it does, and the two
/// together are what #121 needs.
///
/// The inputs are runs of ordinary marks split by something a pipeline may delete —
/// a zero-width, a CGJ, and a cross-script mark, which is the one #850 missed.
#[test]
fn no_pipeline_truncates_further_on_a_second_pass() {
    let splitters = [
        ('\u{200b}', "ZERO WIDTH SPACE"),
        ('\u{034f}', "COMBINING GRAPHEME JOINER"),
        (
            '\u{0489}',
            "COMBINING CYRILLIC MILLIONS SIGN — cross-script on a Latin base",
        ),
        ('\u{200d}', "ZERO WIDTH JOINER"),
        (
            '\u{0001}',
            "START OF HEADING — a C0 control, which #121 names too",
        ),
    ];
    for (splitter, what) in splitters {
        for run in 1..=4 {
            let input: String = std::iter::once('a')
                .chain(std::iter::repeat_n('\u{0308}', run))
                .chain(std::iter::once(splitter))
                .chain(std::iter::once('\u{0308}'))
                .collect();
            for (name, once) in [
                (
                    "canonicalize",
                    canonicalize(&input).map(std::borrow::Cow::into_owned),
                ),
                (
                    "canonicalize_strict",
                    canonicalize_strict(&input).map(std::borrow::Cow::into_owned),
                ),
                (
                    "sort_key",
                    sort_key(&input, None).map(std::borrow::Cow::into_owned),
                ),
                (
                    "search_key",
                    search_key(&input, None).map(std::borrow::Cow::into_owned),
                ),
            ] {
                let once = once.expect("pipeline should not error on this input");
                let twice = match name {
                    "canonicalize" => canonicalize(&once).unwrap().into_owned(),
                    "canonicalize_strict" => canonicalize_strict(&once).unwrap().into_owned(),
                    "sort_key" => sort_key(&once, None).unwrap().into_owned(),
                    _ => search_key(&once, None).unwrap().into_owned(),
                };
                assert_eq!(
                    once, twice,
                    "{name} is not idempotent on {run} marks split by {what}: \
                     {input:?} -> {once:?} -> {twice:?}",
                );
            }
        }
    }
}

/// The next step list in `src`, and whether it is the macro form (#695).
fn next_list(src: &str) -> Option<(usize, bool)> {
    let macro_at = src.find("\n    static_steps! {");
    let plain_at = src
        .match_indices("\n    const STEPS: &[Step")
        .map(|(i, _)| i)
        .find(|&i| {
            src[i..]
                .lines()
                .nth(1)
                .is_some_and(|l| l.trim_end().ends_with('['))
        });
    match (macro_at, plain_at) {
        (Some(m), Some(p)) => Some(if m < p { (m, true) } else { (p, false) }),
        (Some(m), None) => Some((m, true)),
        (None, Some(p)) => Some((p, false)),
        (None, None) => None,
    }
}

/// Split the source into `(enclosing fn name, const STEPS body)` pairs.
///
/// The name is only used to make a failure legible, but a wrong one is worse than
/// none: it sends the reader to a function that is fine. So the scan is anchored to a
/// *definition line* — one starting at column 0 with `fn ` or `pub…fn ` — rather than
/// to the first `fn ` found anywhere backwards, which matches prose in the comments
/// these pipelines are thick with (#850 review).
fn step_arrays(src: &str) -> Vec<(&str, &str)> {
    let mut out = Vec::new();
    let mut rest = src;
    // Two forms since #695. Most presets use `static_steps! { … [ … ] }`, which also
    // emits their compile-time mask and unrolled applier. `ml_normalize` keeps a plain
    // `const STEPS: &[Step; 11]` because it selects between two lists at runtime — and
    // it links every table through its own `Transliterate` and `Demojize` steps
    // anyway, so converting it would buy nothing. Both are scanned: a gate that
    // silently stopped covering a pipeline is what the floor assertion below catches.
    while let Some((i, is_macro)) = next_list(rest) {
        let i = if is_macro {
            if let Some(n) = rest[i..].find("\n        [\n") {
                i + n
            } else {
                rest = &rest[i + 20..];
                continue;
            }
        } else {
            // Only an array *literal*. `const STEPS_NO_FOLD: [Step; 10] =
            // without_fold_case(STEPS);` is one line with no `];` terminator, so
            // treating it as a pipeline made the scan swallow the next function's
            // array and drop `catalog_key` entirely — a gate silently covering one
            // pipeline fewer than it reports.
            let decl_end = rest[i + 1..].find('\n').map_or(rest.len(), |n| i + 1 + n);
            if !rest[i..decl_end].trim_end().ends_with('[') {
                rest = &rest[decl_end..];
                continue;
            }
            i
        };
        let name = rest[..i]
            .lines()
            .rev()
            .find_map(|line| {
                let sig = line.strip_prefix("pub(crate) fn ").or_else(|| {
                    line.strip_prefix("pub fn ")
                        .or_else(|| line.strip_prefix("fn "))
                })?;
                let name = &sig[..sig.find(['<', '(']).unwrap_or(sig.len())];
                // `canonicalize_with` owns `canonicalize`'s list (#896); the gate
                // reports by the builder's name.
                Some(name.strip_suffix("_with").unwrap_or(name))
            })
            .unwrap_or("<unknown fn>");
        let body = &rest[i..];
        let end = if is_macro {
            body.find("\n        ]\n").unwrap_or(body.len())
        } else {
            body.find("\n    ];").unwrap_or(body.len())
        };
        out.push((name, &body[..end]));
        rest = &body[end..];
    }
    out
}

// ── digit_policy reaches the six key builders (#896), and preserve holds (#949) ──

#[test]
fn a_policy_reaches_every_builder_and_the_default_is_the_plain_call() {
    use crate::confusables::DigitPolicy::{Numeric, Tr39};
    // U+0A66 GURMUKHI ZERO for "o": a digit under the default, the letter under tr39.
    assert_eq!(canonicalize_with("g\u{0A66}ogle", Tr39).unwrap(), "google");
    assert_eq!(canonicalize("g\u{0A66}ogle").unwrap(), "g0ogle");
    assert_eq!(
        catalog_key_with("g\u{0A66}ogle", None, false, Tr39).unwrap(),
        "google"
    );
    for text in [
        "g\u{0A66}ogle",
        "amount-\u{0661}",
        "Caf\u{00E9} R\u{00E9}sum\u{00E9}",
        "SKU-1O0",
        "",
    ] {
        assert_eq!(
            canonicalize_with(text, Numeric).unwrap(),
            canonicalize(text).unwrap()
        );
        assert_eq!(
            canonicalize_strict_with(text, Numeric).unwrap(),
            canonicalize_strict(text).unwrap()
        );
        assert_eq!(
            strip_obfuscation_with(text, Numeric).unwrap(),
            strip_obfuscation(text).unwrap()
        );
        assert_eq!(
            search_key_with(text, None, Numeric).unwrap(),
            search_key(text, None).unwrap()
        );
        assert_eq!(
            sort_key_with(text, None, Numeric).unwrap(),
            sort_key(text, None).unwrap()
        );
        assert_eq!(
            catalog_key_with(text, None, false, Numeric).unwrap(),
            catalog_key(text, None, false).unwrap()
        );
    }
}

#[test]
fn preserve_holds_where_a_builder_owns_a_fold_and_transliteration_still_romanizes() {
    use crate::confusables::DigitPolicy::Preserve;
    let x = "amount-\u{0661}"; // ARABIC-INDIC DIGIT ONE
                               // #949: the pre-pass kept the numeral and the preset's own fold then folded it.
    assert_eq!(canonicalize_with(x, Preserve).unwrap(), x);
    assert_eq!(canonicalize_strict_with(x, Preserve).unwrap(), x);
    assert_eq!(strip_obfuscation_with(x, Preserve).unwrap(), x);
    // Both halves: a key that maps every script to Latin romanizes the digit — by
    // transliteration, not by the fold — and `preserve` cannot and should not stop it.
    assert_eq!(search_key_with(x, None, Preserve).unwrap(), "amount-1");
    assert_eq!(sort_key_with(x, None, Preserve).unwrap(), "amount-1");
    assert_eq!(
        catalog_key_with(x, None, false, Preserve).unwrap(),
        "amount-1"
    );
}

#[test]
fn the_pre_fold_is_the_public_fold_and_the_guard_does_not_skip_it() {
    use crate::confusables::DigitPolicy::Tr39;
    // `ā` → `ã` is a tr39-only row. Decomposed, the single-pass fold missed it; the
    // fixed-point form composes first, as the pre-pass did. And on `sort_key`, whose
    // other steps leave `āb` alone, the inert guard used to hand the input back without
    // running the pre-fold at all — the two deltas a 290k-probe sweep found.
    for text in ["\u{0101}b", "a\u{0304}b"] {
        let pre = confusables::normalize_confusables(text, "latin", "tr39").unwrap();
        let via_public = sort_key(&pre, None).unwrap().into_owned();
        assert_eq!(
            sort_key_with(text, None, Tr39).unwrap(),
            via_public,
            "{text:?}"
        );
        assert_eq!(via_public, "\u{00E3}b");
    }
    // The fast path still borrows on the default.
    assert!(matches!(sort_key("plain", None).unwrap(), Cow::Borrowed(_)));
}

#[test]
fn the_pre_fold_step_is_a_no_op_under_the_default() {
    let ctx = PresetCtx {
        lang: None,
        strict_iso9: false,
        emoji_cldr: false,
        digit_policy: crate::confusables::DigitPolicy::Numeric,
        input_len: 0,
    };
    let mut out = String::new();
    assert!(!apply_into(
        Step::PolicyPreFold("latin"),
        "g\u{0A66}ogle",
        &ctx,
        &mut out
    )
    .unwrap());
    let ctx = PresetCtx {
        digit_policy: crate::confusables::DigitPolicy::Tr39,
        ..ctx
    };
    assert!(apply_into(
        Step::PolicyPreFold("latin"),
        "g\u{0A66}ogle",
        &ctx,
        &mut out
    )
    .unwrap());
    assert_eq!(out, "google");
}

// ── the pre-fold and the guard (#951) ────────────────────────────

#[test]
fn the_pre_fold_contributes_nothing_to_the_guard_mask() {
    // Inert under the default and bypassed otherwise, so `search_key` / `sort_key`
    // must not start paying the guard's confusable-source scan on every call.
    let mask = Actionable::for_steps(&[Step::PolicyPreFold("latin")]);
    assert!(!mask.confusables && !mask.marks);
}

#[test]
fn a_builder_without_a_fold_keeps_its_fast_path() {
    // `|` is an ASCII confusable source; every other step of `sort_key` leaves it
    // alone, so the default still hands the input back borrowed.
    assert!(matches!(
        sort_key("plain|text", None).unwrap(),
        Cow::Borrowed(_)
    ));
}

/// `step_arrays` names the right function, since the ordering gate's failure message
/// is only useful if it does.
#[test]
fn step_arrays_names_the_enclosing_function() {
    let names: Vec<&str> = step_arrays(concat!(include_str!("text.rs"), include_str!("keys.rs")))
        .into_iter()
        .map(|(name, _)| name)
        .collect();
    for expected in [
        "canonicalize",
        "canonicalize_strict",
        "sort_key",
        "search_key",
        "catalog_key",
        "strip_obfuscation",
        "strip_format",
        "ml_normalize",
    ] {
        assert!(
            names.contains(&expected),
            "{expected} missing from {names:?}"
        );
    }
    assert!(
        !names.contains(&"<unknown fn>"),
        "a STEPS array was not attributed to a function: {names:?}",
    );
}

#[test]
fn test_sort_key_idempotent_on_invisible_separated_mark() {
    // #416 / #411: sort_key now preserves the accent, so the same decomposed
    // sequence must be recomposed by the terminal NFC to stay a fixed point.
    for sep in ['\u{200B}', '\u{200C}', '\u{200D}', '\u{FEFF}'] {
        let input = format!("a{sep}\u{0301}b");
        let once = sort_key(&input, None).unwrap();
        assert_eq!(once, "\u{00E1}b");
        assert_eq!(
            once,
            sort_key(&once, None).unwrap(),
            "sep {sep:?} not idempotent"
        );
    }
}

#[test]
fn test_key_presets_idempotent_on_case_pair_transliteration() {
    // #419: a Georgian Mtavruli capital `Ჱ` (U+1CB1) is absent from the
    // transliteration table but folds to Mkhedruli `ჱ` (U+10F1), which IS in
    // the table (→ "he"). Folding case before transliterate makes the key
    // presets reach the fully-transliterated form on the first pass.
    let input = "\u{1CB1}"; // Ჱ
    for once in [
        sort_key(input, None).unwrap(),
        search_key(input, None).unwrap(),
        catalog_key(input, None, false).unwrap(),
    ] {
        assert_eq!(once, "he", "first pass should fully transliterate");
    }
    assert_eq!(
        sort_key(input, None).unwrap(),
        sort_key("he", None).unwrap()
    );
    assert_eq!(
        search_key(input, None).unwrap(),
        search_key("he", None).unwrap()
    );
    assert_eq!(
        catalog_key(input, None, false).unwrap(),
        catalog_key("he", None, false).unwrap()
    );
}

#[test]
fn test_ml_normalize_basic() {
    let result = ml_normalize("Café Résumé", None, "cldr", true).unwrap();
    assert_eq!(result, "cafe resume");
}

// ── #559: the fold_case switch ───────────────────────────────────────────

/// The default is unchanged. Every existing caller keeps the folding behaviour.
#[test]
fn ml_normalize_folds_case_by_default() {
    assert_eq!(
        ml_normalize("José Martínez", None, "cldr", true).unwrap(),
        "jose martinez"
    );
}

/// `fold_case=false` keeps capitals. Note it does NOT keep diacritics —
/// `strip_accents` is a separate step and still runs (that distinction is the
/// subject of #564).
#[test]
fn ml_normalize_without_fold_case_keeps_capitals_not_accents() {
    assert_eq!(
        ml_normalize("José Martínez", None, "cldr", false).unwrap(),
        "Jose Martinez"
    );
}

/// The flag must change exactly one thing. Every other stage — NFKC, demojize,
/// transliterate, strip-accents, control/zero-width stripping, whitespace
/// folding — has to behave identically, so the only difference between the two
/// outputs is case. Comparing the unfolded output's own case fold against the
/// folded output proves that directly, on input that exercises each stage.
#[test]
fn ml_normalize_fold_case_changes_only_case() {
    for input in [
        "José Martínez",
        "MÜNCHEN Straße",
        "Hi \u{1F600} THERE",
        "\u{FB01}LTER",       // ligature ﬁ via NFKC
        "A\u{200B}B\tC   D",  // zero-width + control + whitespace
        "Ｆｕｌｌｗｉｄｔｈ", // NFKC width fold
        "café \u{2247} X",    // #498 exposed-base demojize
        "",
    ] {
        let folded = ml_normalize(input, None, "cldr", true).unwrap();
        let unfolded = ml_normalize(input, None, "cldr", false).unwrap();
        assert_eq!(
            crate::api::fold_case(&unfolded),
            folded,
            "fold_case changed something other than case for {input:?}: \
             folded={folded:?} unfolded={unfolded:?}"
        );
    }
}

/// Transliteration still runs with the flag off — `lang` is orthogonal to case.
#[test]
fn ml_normalize_without_fold_case_still_transliterates() {
    assert_eq!(
        ml_normalize("MÜNCHEN Straße", Some("de"), "cldr", false).unwrap(),
        "MUeNCHEN Strasse"
    );
}

/// Both modes must stay idempotent — dropping a step must not break the fixed
/// point the preset promises.
#[test]
fn ml_normalize_idempotent_without_fold_case() {
    for input in ["José Martínez", "MÜNCHEN", "Hi \u{1F600}", "a\u{200B}b  c"] {
        let once = ml_normalize(input, None, "cldr", false).unwrap();
        let twice = ml_normalize(&once, None, "cldr", false).unwrap();
        assert_eq!(once, twice, "not idempotent for {input:?}");
    }
}

/// Argument validation is not skipped on the no-fold path.
#[test]
fn ml_normalize_validates_arguments_in_both_modes() {
    for fold in [true, false] {
        assert!(ml_normalize("x", None, "bogus", fold).is_err());
        assert!(ml_normalize("x", Some("zzz"), "cldr", fold).is_err());
    }
}

/// The derived no-fold list must be the folded list minus exactly the fold step.
/// `without_fold_case` const-asserts the count; this pins the *content*, so a
/// reordering that happened to keep the length would still be caught.
#[test]
fn no_fold_step_list_is_the_folded_list_minus_fold_case() {
    const FULL: &[Step; 11] = &[
        Step::ResolveDeletions,
        Step::Nfkc,
        Step::Demojize {
            only_if_cldr: true,
            policy: crate::emoji::NamePolicy {
                skip_tr39_claimed: false,
                skip_non_emoji: true,
            },
        },
        Step::Transliterate {
            mode: crate::ErrorMode::Ignore,
            only_if_lang: true,
        },
        Step::StripAccents,
        Step::Demojize {
            only_if_cldr: true,
            policy: crate::emoji::NamePolicy {
                skip_tr39_claimed: false,
                skip_non_emoji: true,
            },
        },
        Step::FoldCase,
        Step::StripControl,
        Step::StripZeroWidth,
        Step::CollapseWs,
        Step::NfcIfNonAscii,
    ];
    let derived = without_fold_case(FULL);
    let expected: Vec<_> = FULL
        .iter()
        .filter(|s| !matches!(s, Step::FoldCase))
        .map(std::mem::discriminant)
        .collect();
    let got: Vec<_> = derived.iter().map(std::mem::discriminant).collect();
    assert_eq!(got, expected);
}

#[test]
fn test_ml_normalize_ligature() {
    let result = ml_normalize("\u{FB01}lter", None, "cldr", true).unwrap();
    assert_eq!(result, "filter");
}

/// Negated relations are preserved, and naming the bare base is idempotent (#749).
///
/// This class was enumerated by an exhaustive scan over every Unicode scalar where
/// NFKD strips a combining mark to expose a single base that demojize names. It used
/// to assert that each *negated* relation resolved to its **positive** name — `∦` to
/// "parallel", `⊄` to "subset of", `≰` to "less-than or equal" — because the overlay
/// was stripped before the base was named. Seventeen rows, each naming a symbol as
/// its own opposite, which for the tokenizer this preset serves is the corruption
/// #749 describes rather than a normalization.
///
/// Two fixes retired that mechanism from both ends. #749 keeps `U+0338` on a symbol,
/// so the base is never exposed. #757 stops naming a row that carries no emoji
/// property, and every base here is `Sm`, so the name would not fire even if it were
/// exposed. What is left to assert is that both forms survive, that both are fixed
/// points, and that they stay distinct — the negated relation must never share the
/// positive one's output, which is the property the original 17 rows violated.
#[test]
fn test_ml_normalize_negated_relations_are_preserved() {
    // (negated input, bare base) — the complete scanned class. The third column is
    // the CLDR name the positive base carried when this test asserted the inversion;
    // it is retained as a comment so the row is still greppable from #498.
    for (input, base) in [
        ("\u{2204}", "\u{2203}"), // ∄ → ∃  (there exists)
        ("\u{220C}", "\u{220B}"), // ∌ → ∋  (contains as member)
        ("\u{2224}", "\u{2223}"), // ∤ → ∣  (divides)
        ("\u{2226}", "\u{2225}"), // ∦ → ∥  (parallel)
        ("\u{2241}", "\u{223C}"), // ≁ → ∼  (tilde operator)
        ("\u{2244}", "\u{2243}"), // ≄ → ≃  (asymptotically equal)
        ("\u{2247}", "\u{2245}"), // ≇ → ≅  (approximately equal)
        ("\u{2249}", "\u{2248}"), // ≉ → ≈  (almost equal)
        ("\u{2262}", "\u{2261}"), // ≢ → ≡  (identical to)
        ("\u{2270}", "\u{2264}"), // ≰ → ≤  (less-than or equal)
        ("\u{2271}", "\u{2265}"), // ≱ → ≥  (greater-than or equal)
        ("\u{2275}", "\u{2273}"), // ≵ → ≳  (greater-than equivalent)
        ("\u{2280}", "\u{227A}"), // ⊀ → ≺  (precedes)
        ("\u{2284}", "\u{2282}"), // ⊄ → ⊂  (subset of)
        ("\u{2285}", "\u{2283}"), // ⊅ → ⊃  (superset)
        ("\u{2288}", "\u{2286}"), // ⊈ → ⊆  (subset equal)
        ("\u{2289}", "\u{2287}"), // ⊉ → ⊇  (superset equal)
    ] {
        // The negation survives, and survives a second pass.
        let once = ml_normalize(input, None, "cldr", true).unwrap();
        assert_eq!(
            once, input,
            "ml_normalize({input:?}) must not resolve a negated relation to anything"
        );
        assert_eq!(
            once,
            ml_normalize(&once, None, "cldr", true).unwrap(),
            "ml_normalize not idempotent on {input:?}"
        );
        // So does the positive base: it is `Sm`, so #757 leaves it alone too.
        let base_out = ml_normalize(base, None, "cldr", true).unwrap();
        assert_eq!(
            base_out, base,
            "ml_normalize({base:?}) should pass a non-emoji math symbol through"
        );
        assert_ne!(
            once, base_out,
            "the negated form must not share the positive form's output"
        );
    }
}

#[test]
fn test_catalog_key_dedup() {
    let a = catalog_key("Café", None, false).unwrap();
    let b = catalog_key("café", None, false).unwrap();
    let c = catalog_key("CAFÉ", None, false).unwrap();
    assert_eq!(a, b);
    assert_eq!(b, c);
}

#[test]
fn test_catalog_key_iso9() {
    let result = catalog_key("\u{0419}\u{043E}\u{0433}\u{0430}", None, true).unwrap();
    // Transliterate first with ISO 9: Й→J, о→o, г→g, а→a → "joga"
    assert_eq!(result, "joga");
}

/// #467: `catalog_key` must be a fixed point in one call. Its single
/// `Confusables` pass left two ways for a foldable form to survive to a second
/// call:
///   (A) `StripAccents` (which runs *after* `Confusables`) drops the U+0338
///       overlay of a negated relation, exposing a confusable base the fold
///       already passed: `∤`→`∣`→`l`.
///   (B) the confusables map itself chains — a value that is again confusable:
///       `ᴔ`→`ǝo`→`eo`, `➗`→`÷`→`/`.
/// Each must reach its fixed point on the first call (`f(x) == f(f(x))`) and
/// equal the stable target. These are the complete BMP trigger set.
#[test]
fn test_catalog_key_idempotent_on_confusable_cascades() {
    for (input, want) in [
        // (A) negated relations: NFD = base + U+0338, base is a confusable.
        //
        // These asserted the *inverted* targets until #749 — `∄` folded through `∃`
        // to `e`, so the key for "there does not exist" was the key for "there
        // exists". The cascade was real and so was the idempotence it demonstrated;
        // the destination was the defect. `U+0338` is now kept, so the fold stops
        // where the negation is and each still reaches its fixed point in one call,
        // which is what #467/#498 closed and what this test is for.
        ("\u{2204}", "\u{2204}"), // ∄ THERE DOES NOT EXIST — negation preserved
        ("\u{2224}", "\u{2224}"), // ∤ DOES NOT DIVIDE
        ("\u{2226}", "\u{2226}"), // ∦ NOT PARALLEL TO
        ("\u{2241}", "\u{2241}"), // ≁ NOT TILDE
        // (B) chained confusables (single codepoint, no combining mark).
        ("\u{1D14}", "eo"), // ᴔ TURNED OE → ǝo → eo
        ("\u{256A}", "!"),  // ╪ BOX DRAWINGS … → ǂ → !
        ("\u{2797}", "/"),  // ➗ HEAVY DIVISION SIGN → ÷ → /
    ] {
        let once = catalog_key(input, None, false).unwrap();
        assert_eq!(
            once, want,
            "catalog_key({input:?}) should fold fully in one call"
        );
        assert_eq!(
            once,
            catalog_key(&once, None, false).unwrap(),
            "catalog_key not idempotent on {input:?}"
        );
    }
}

#[test]
fn test_search_key_accent_insensitive() {
    let a = search_key("Café", None).unwrap();
    let b = search_key("cafe", None).unwrap();
    let c = search_key("CAFÉ", None).unwrap();
    assert_eq!(a, "cafe");
    assert_eq!(a, b);
    assert_eq!(b, c);
}

#[test]
fn test_search_key_cyrillic() {
    assert_eq!(search_key("Москва", None).unwrap(), "moskva");
}

#[test]
fn test_search_key_greek() {
    assert_eq!(search_key("ΩMEGA", None).unwrap(), "omega");
}

#[test]
fn test_sort_key_preserves_accents() {
    // sort_key PRESERVES base accented Latin characters for collation; only
    // case is folded (Über → über). This is the documented distinction from
    // search_key, which folds the accent away (über vs uber).
    assert_eq!(sort_key("Über", None).unwrap(), "über");
    assert_eq!(sort_key("naïve", None).unwrap(), "naïve");
    assert_eq!(sort_key("Köln", None).unwrap(), "köln");
    // ß is a case-fold expansion, not an accent: it still becomes "ss".
    assert_eq!(sort_key("Straße", None).unwrap(), "strasse");
}

#[test]
fn test_sort_key_folds_uppercase_emitted_by_transliteration() {
    // Review (D-1 generator): a non-Latin source can transliterate to an
    // uppercase-bearing proper noun — Old Persian `𐏈` (U+103C8) → "Auramazda"
    // — which the pre-transliterate fold can't reach. The post-transliterate
    // fold makes the key lowercase and a true fixed point.
    let once = sort_key("\u{103C8}", None).unwrap();
    assert_eq!(once, "auramazda");
    assert_eq!(sort_key(&once, None).unwrap(), once);
}

#[test]
fn test_sort_key_cyrillic() {
    // Non-Latin scripts are still folded to a consistent Latin form.
    assert_eq!(sort_key("Война и мир", None).unwrap(), "voyna i mir");
}

#[test]
fn test_sort_key_vs_search_key() {
    // Non-Latin folds to the same Latin form in both keys.
    assert_eq!(
        sort_key("Москва", None).unwrap(),
        search_key("Москва", None).unwrap()
    );
    // But accented Latin diverges: sort_key keeps the accent for ordering,
    // search_key folds it away for exact-match lookup.
    assert_eq!(search_key("Über", None).unwrap(), "uber");
    assert_ne!(
        sort_key("Über", None).unwrap(),
        search_key("Über", None).unwrap()
    );
}

#[test]
fn test_sort_key_lang_does_not_expand_latin_accents() {
    // A language profile only transliterates non-Latin runs; an accented
    // Latin letter is never expanded by `lang` in a sort key (de: ü→ue is a
    // search/fold convention, not a collation one).
    assert_eq!(sort_key("Über", Some("de")).unwrap(), "über");
    assert_eq!(search_key("Über", Some("de")).unwrap(), "ueber");
}

#[test]
fn test_sort_key_mixed_script_preserves_latin_folds_other() {
    // Greek folds to Latin; the Latin accent survives intact.
    assert_eq!(sort_key("Ω café", None).unwrap(), "o café");
}

#[test]
fn test_key_functions_strip_bidi_and_soft_hyphen() {
    // #93: a value stored with an invisible bidi/format char must produce
    // the SAME key as its clean equivalent, or dedup/lookup silently misses.
    for (stored, clean) in [
        ("pass\u{00AD}word", "password"), // soft hyphen
        ("user\u{202E}txt", "usertxt"),   // RLO override
        ("a\u{200E}b", "ab"),             // LRM
        ("x\u{061C}y", "xy"),             // Arabic Letter Mark
    ] {
        assert_eq!(
            search_key(stored, None).unwrap(),
            search_key(clean, None).unwrap(),
            "search_key must collide for {stored:?} vs {clean:?}"
        );
        assert_eq!(
            catalog_key(stored, None, false).unwrap(),
            catalog_key(clean, None, false).unwrap(),
            "catalog_key must collide for {stored:?} vs {clean:?}"
        );
        assert_eq!(
            sort_key(stored, None).unwrap(),
            sort_key(clean, None).unwrap(),
            "sort_key must collide for {stored:?} vs {clean:?}"
        );
    }
}

#[test]
fn test_strip_format_basic() {
    assert_eq!(strip_format("hello   world"), "hello world");
    assert_eq!(strip_format("hello\x00world"), "helloworld");
    assert_eq!(strip_format("hello\u{200B}world"), "helloworld");
}

#[test]
fn test_strip_format_strips_bidi() {
    // RLO can visually reorder rendered text to hide malicious content
    assert_eq!(strip_format("admin\u{202E}user"), "adminuser");
    // Soft hyphen can split security keywords invisibly
    assert_eq!(strip_format("pass\u{00AD}word"), "password");
    // Arabic Letter Mark
    assert_eq!(strip_format("hello\u{061C}world"), "helloworld");
}

#[test]
fn test_strip_format_idempotent_on_vs_after_blank_render() {
    // Review D-2: a presentation VS kept after a base that a *later* strip
    // removes (Braille blank, Hangul filler, control, zero-width) used to be
    // orphaned on the second pass. Now the VS is dropped with its base, so
    // one pass already reaches the fixed point.
    for input in [
        "\u{2800}\u{FE0F}x", // Braille blank (blank-render) + VS16
        "\u{115F}\u{FE0F}x", // Hangul Choseong filler + VS16
        "\u{0000}\u{FE0F}x", // NUL (control) + VS16
        "\u{200B}\u{FE0F}x", // ZWSP (zero-width) + VS16
    ] {
        let once = strip_format(input);
        assert_eq!(once, "x", "input {input:?} should reduce to \"x\"");
        assert_eq!(strip_format(&once), once, "not idempotent on {input:?}");
    }
}

// ── canonicalize_strict ──────────────────────────────────

#[test]
fn test_canonicalize_strict_clean_text() {
    assert_eq!(
        canonicalize_strict("Hello, world!").unwrap(),
        "Hello, world!"
    );
}

#[test]
fn test_canonicalize_strict_preserves_script() {
    // Original script is preserved (no transliteration)
    let result = canonicalize_strict("Москва").unwrap();
    // Confusables maps some Cyrillic to Latin, but that's intentional
    // for homoglyph protection — the key point is no transliteration step
    assert!(!result.is_empty());
}

#[test]
fn test_canonicalize_strict_strips_zalgo() {
    let mut zalgo = String::from("hello");
    for _ in 0..20 {
        zalgo.push('\u{0300}');
    }
    zalgo.push_str(" world");
    let result = canonicalize_strict(&zalgo).unwrap();
    // Zalgo marks stripped down to max 2 per base
    assert!(result.len() < zalgo.len());
    assert!(result.contains("world"));
}

#[test]
fn test_canonicalize_strict_strips_bidi() {
    assert_eq!(
        canonicalize_strict("admin\u{202E}user").unwrap(),
        "adminuser"
    );
}

#[test]
fn test_canonicalize_strict_strips_zero_width() {
    assert_eq!(canonicalize_strict("pass\u{200B}word").unwrap(), "password");
}

#[test]
fn test_canonicalize_strict_preserves_accents() {
    // Legitimate diacritics are preserved — no transliteration or accent stripping
    assert_eq!(canonicalize_strict("café").unwrap(), "café");
    assert_eq!(canonicalize_strict("résumé").unwrap(), "résumé");
}

#[test]
fn test_canonicalize_strict_homoglyph() {
    // Cyrillic а in "pаypal" → Latin a
    let result = canonicalize_strict("p\u{0430}ypal").unwrap();
    assert_eq!(result, "paypal");
}

/// Property-based security invariants for the defense pipelines.
///
/// Asserts the THREAT_MODEL.md guarantees across the full Unicode input
/// space: no panic on any input, idempotence (a stable fixed point), and
/// that bidi/format controls never survive a pipeline whose definition
/// includes a bidi-stripping step.
mod proptest_properties {
    use super::*;
    use proptest::prelude::*;

    /// Characters the defense pipelines specifically target — bidi/format
    /// controls, zero-width/invisible chars, zalgo combining marks,
    /// confusables, and an emoji. Mixed into the generator so the "no bidi
    /// survives" properties actually exercise these (a plain `\PC*` strategy
    /// would never produce category-C controls, making them vacuous).
    const SPECIAL: &[char] = &[
        // bidi / format controls
        '\u{200E}',
        '\u{200F}',
        '\u{202A}',
        '\u{202B}',
        '\u{202C}',
        '\u{202D}',
        '\u{202E}',
        '\u{061C}',
        '\u{2066}',
        '\u{2067}',
        '\u{2068}',
        '\u{2069}',
        '\u{00AD}',
        // zero-width / invisible
        '\u{200B}',
        '\u{200C}',
        '\u{200D}',
        '\u{2060}',
        '\u{FEFF}',
        // zalgo combining marks
        '\u{0301}',
        '\u{0300}',
        '\u{0489}',
        // marks that compose a Latin confusable base into a *precomposed*
        // confusable table key (cedilla → ç, diaeresis → ï): the trigger
        // class for the post-fold-NFC idempotency path (review D-1/#434).
        '\u{0327}',
        '\u{0308}',
        // confusables (Cyrillic а р с е о) + a fullwidth char + an emoji
        '\u{0430}',
        '\u{0440}',
        '\u{0441}',
        '\u{0435}',
        '\u{043E}',
        '\u{FF41}',
        '\u{1F452}',
    ];

    /// Adversarial input: arbitrary scalar values heavily salted with the
    /// attack characters above.
    fn adversarial() -> impl Strategy<Value = String> {
        let special = proptest::sample::select(SPECIAL.to_vec());
        proptest::collection::vec(
            prop_oneof![4 => any::<char>(), 3 => special, 2 => prop::char::range('a', 'z')],
            0..40,
        )
        .prop_map(|cs| cs.into_iter().collect())
    }

    /// #458 fast-path generator: dense in the bytes that exercise every ASCII
    /// actionable class and its boundaries — uppercase (FoldCase), whitespace
    /// incl. fold-controls and boundary/run spaces (CollapseWs), C0/DEL
    /// controls (StripControl), the ASCII confusable sources `" ` |`
    /// (Confusables) — mixed with the non-ASCII classes and benign ASCII.
    /// Unioned with `adversarial()` to span both the edges and the broad space.
    fn fastpath_gen() -> impl Strategy<Value = String> {
        let edge = prop::sample::select(vec![
            'a',
            'b',
            'Z',
            'A',
            '0',
            '9',
            '.',
            '-',
            '_',
            ' ',
            '\t',
            '\n',
            '\r',
            '\u{0B}',
            '\u{0C}',
            '\u{1C}',
            '\u{00}',
            '\u{07}',
            '\u{1B}',
            '\u{7F}',
            '"',
            '`',
            '|',
            // non-ASCII: actionable classes + benign foreign text (Option D
            // skip path) — accented/inert Latin, CJK, Hangul, Cyrillic, Arabic,
            // Greek, C1 control, NBSP, combining mark, zero-width, bidi, emoji.
            'é',
            'ñ',
            'ø',
            'þ',
            'Ω',
            'Σ',
            '日',
            '本',
            '한',
            '글',
            'м',
            'и',
            'р',
            'ا',
            '\u{0080}',
            '\u{00A0}',
            '\u{0301}',
            '\u{200B}',
            '\u{202E}',
            '\u{1F600}',
            '\u{1F3F4}',
            '\u{2800}',
        ]);
        prop_oneof![
            proptest::collection::vec(edge, 0..24)
                .prop_map(|cs| cs.into_iter().collect::<String>())
                .boxed(),
            adversarial().boxed(),
            jamo_seq().boxed(),
        ]
    }

    /// #467 generator: dense in the `catalog_key` confusable-cascade class — a
    /// confusable that survives the single `Confusables` pass and only folds on
    /// a second call. Seeds the precomposed triggers (both mechanisms found in
    /// the BMP) and the raw ingredients to synthesize fresh ones: the combining
    /// long solidus overlay `U+0338` (which `strip_accents` drops to re-expose a
    /// base) and the confusable bases the negated relations decompose to. Mixed
    /// with `adversarial()` so the property still spans the broad space.
    fn confusable_cascade() -> impl Strategy<Value = String> {
        const TRIGGERS: &[char] = &[
            // (A) precomposed negated relations: NFD = base + U+0338.
            '\u{2204}', '\u{2224}', '\u{2226}', '\u{2241}',
            // (B) chained confusables (a confusable whose fold is again confusable).
            '\u{1D14}', '\u{256A}', '\u{2797}',
            // raw ingredients: the overlay + the bases, to synthesize new forms
            // (`base` + `U+0338`) the precomposed set doesn't enumerate.
            '\u{0338}', '\u{2203}', '\u{2223}', '\u{2225}', '\u{223C}',
        ];
        let trig = proptest::sample::select(TRIGGERS.to_vec());
        prop_oneof![
            proptest::collection::vec(trig, 0..12)
                .prop_map(|cs| cs.into_iter().collect::<String>())
                .boxed(),
            adversarial().boxed(),
        ]
    }

    /// #471: a leading jamo `L` with an optional vowel `V` and trailing `T` — so
    /// it emits a lone `L`, `L+V`, and `L+V+T`. NFKC composes an `L+V(+T)` run into
    /// one syllable, but each jamo is NFKC-stable alone and is not a combining mark
    /// — exactly the cross-character case the per-character guard missed (the lone
    /// `L` is genuinely inert and pins that the over-marking stays equivalent).
    /// `fastpath_gen` never emitted these, so `fast_path_equivalence` passed while
    /// the guard was unsound; this closes that generator gap.
    fn jamo_seq() -> impl Strategy<Value = String> {
        let lead = (0x1100u32..=0x1112).prop_map(|c| char::from_u32(c).unwrap());
        let vowel = prop::option::of((0x1161u32..=0x1175).prop_map(|c| char::from_u32(c).unwrap()));
        let trail = prop::option::of((0x11A8u32..=0x11C2).prop_map(|c| char::from_u32(c).unwrap()));
        (lead, vowel, trail).prop_map(|(l, v, t)| {
            let mut s = String::new();
            s.push(l);
            if let Some(v) = v {
                s.push(v);
            }
            if let Some(t) = t {
                s.push(t);
            }
            s
        })
    }

    /// Tier-3 exhaustive gate for preset idempotency (#416/#467/#498/#523 class).
    ///
    /// The key presets are fixed points: `canonicalize(canonicalize(x)) ==
    /// canonicalize(x)`, and likewise for `sort_key`/`search_key`/`catalog_key`/
    /// `ml_normalize`. The `adversarial()` proptests sample `any::<char>()`; this
    /// enumerates the two domains where non-idempotency actually lives. (1) Every
    /// single code point — the #498 class (a base exposed by NFKD/strip that only
    /// resolves on a second pass). (2) Every BMP base × every combining diacritical
    /// (U+0300–036F) — the #523 class (a fold/transliterate output that composes with
    /// a following mark, or a composition that exposes a new fold); BMP covers every
    /// composable Latin/Greek/Cyrillic base, and the astral planes are covered by (1).
    /// `#[ignore]` (Tier 3): ~1.1M scalars across 5 presets plus ~7.1M BMP base×mark
    /// pairs across 2 presets, each checked twice — on the order of 40M preset calls,
    /// a few seconds in release.
    #[test]
    #[ignore = "exhaustive: preset idempotency over code points + base×mark; Tier 3"]
    fn exhaustive_preset_idempotency() {
        // Generic (monomorphized) so the tens-of-millions of calls in the inner loops
        // pay no vtable dispatch — Tier-3 runtime stays predictable.
        fn idem<F: Fn(&str) -> String>(label: &str, f: F, s: &str) {
            let once = f(s);
            assert_eq!(once, f(&once), "{label} not idempotent on {s:?}");
        }
        let cat = |s: &str| catalog_key(s, None, false).unwrap().into_owned();
        let ml = |s: &str| ml_normalize(s, None, "cldr", true).unwrap().into_owned();

        // (1) every single code point, across the key presets.
        for cp in 0u32..=0x0010_FFFF {
            let Some(c) = char::from_u32(cp) else {
                continue;
            };
            let s = c.to_string();
            idem(
                "canonicalize",
                |x| canonicalize(x).unwrap().into_owned(),
                &s,
            );
            idem("sort_key", |x| sort_key(x, None).unwrap().into_owned(), &s);
            idem(
                "search_key",
                |x| search_key(x, None).unwrap().into_owned(),
                &s,
            );
            idem("catalog_key", cat, &s);
            idem("ml_normalize", ml, &s);
        }

        // (2) every BMP base × every combining diacritical — the compose/fold class.
        let marks: Vec<char> = (0x0300u32..=0x036F).filter_map(char::from_u32).collect();
        for base in (0u32..=0xFFFF).filter_map(char::from_u32) {
            for &m in &marks {
                let s: String = [base, m].iter().collect();
                idem("catalog_key", cat, &s);
                idem("ml_normalize", ml, &s);
            }
        }
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(1000))]

        /// #458 criterion 1: every preset's guarded output equals its
        /// un-guarded full pipeline. The guard is sound iff it never skips an
        /// input the pipeline would change.
        #[test]
        fn fast_path_equivalence(s in fastpath_gen()) {
            for (name, f) in all_presets() {
                let guarded = f(&s);
                let full = without_fastpath(|| f(&s));
                prop_assert_eq!(&guarded, &full, "{} fast-path != full on {:?}", name, s);
            }
        }

        #[test]
        fn canonicalize_idempotent(s in adversarial()) {
            // #416: assert *raw* equality, not equality-modulo-NFC. The
            // earlier `nfc(once) == nfc(twice)` form normalized away the very
            // difference the terminal-NFC fix removes, so it could not catch
            // the base+invisible+mark idempotency violation.
            let once = canonicalize(&s).unwrap();
            let twice = canonicalize(&once).unwrap();
            prop_assert_eq!(&once, &twice);
        }

        // #419: the transliterating key presets fold case BEFORE transliterate,
        // so a case pair whose folded form is in the table (but whose original
        // is not) is stable across passes. `adversarial()` draws `any::<char>()`,
        // so it exercises cross-script case pairs like Georgian Mtavruli.
        #[test]
        fn sort_key_idempotent(s in adversarial()) {
            let once = sort_key(&s, None).unwrap();
            let twice = sort_key(&once, None).unwrap();
            prop_assert_eq!(&once, &twice);
        }

        #[test]
        fn search_key_idempotent(s in adversarial()) {
            let once = search_key(&s, None).unwrap();
            let twice = search_key(&once, None).unwrap();
            prop_assert_eq!(&once, &twice);
        }

        #[test]
        fn catalog_key_idempotent(s in adversarial()) {
            let once = catalog_key(&s, None, false).unwrap();
            let twice = catalog_key(&once, None, false).unwrap();
            prop_assert_eq!(&once, &twice);
        }

        // #467: the same raw-idempotency property, but over a generator dense in
        // the confusable-cascade class (a confusable surviving the single
        // Confusables pass — exposed by strip_accents or chained through the
        // map). `catalog_key_idempotent` above draws this only rarely from
        // `any::<char>()`; this reliably exercises it.
        #[test]
        fn catalog_key_idempotent_on_cascades(s in confusable_cascade()) {
            let once = catalog_key(&s, None, false).unwrap();
            let twice = catalog_key(&once, None, false).unwrap();
            prop_assert_eq!(&once, &twice);
        }

        // ml_normalize is a fixed point under BOTH emoji styles. With "none"
        // there is no demojize at all. With "cldr" the demojize naming step runs
        // twice — once before transliterate (so emoji survive the Ignore-mode
        // transliterate) and once after strip-accents (#498), so both a base
        // exposed by strip-accents' NFD (`≇`→`≅`→"approximately equal") and any
        // typographic punctuation inside a CLDR name (the U+2019 in "woman's
        // hat") are resolved within the first call. Pin idempotency across both
        // styles and the lang-present and lang-absent paths.
        #[test]
        fn ml_normalize_idempotent_both_styles(
            s in adversarial(),
            lang in prop::option::of(prop::sample::select(vec!["de", "ru", "ja"])),
            style in prop::sample::select(vec!["cldr", "none"]),
        ) {
            let once = ml_normalize(&s, lang, style, true).unwrap();
            let twice = ml_normalize(&once, lang, style, true).unwrap();
            prop_assert_eq!(&once, &twice);
        }

        // Structural post-conditions that hold for ALL four conditional paths
        // (lang present/absent × emoji_style cldr/none), complementing the
        // idempotency property above. Verifies the case-fold and
        // whitespace-collapse stages actually took effect regardless of which
        // conditional stages ran.
        #[test]
        fn ml_normalize_postconditions_all_modes(
            s in adversarial(),
            lang in prop::option::of(prop::sample::select(vec!["de", "ru", "ja"])),
            style in prop::sample::select(vec!["cldr", "none"]),
        ) {
            let out = ml_normalize(&s, lang, style, true).unwrap();
            // fold_case ran (after demojize/transliterate) and nothing after it
            // re-introduces case, so the output is a fixed point of fold_case.
            // (Asserting "no uppercase" would be wrong: fold_case's table does
            // not cover every cased script — e.g. Cherokee U+13A0 — so an
            // uppercase char it cannot fold legitimately survives.)
            prop_assert!(
                case_fold::fold_case_impl(&out) == out,
                "fold_case not a fixed point of ml_normalize output: {out:?}"
            );
            // collapse_whitespace ran last: trimmed, and no run of ASCII spaces.
            prop_assert_eq!(out.trim(), &out, "not trimmed: {:?}", out);
            prop_assert!(!out.contains("  "), "double space in {out:?}");
        }

        #[test]
        fn strip_obfuscation_idempotent(s in adversarial()) {
            // Assert *raw* equality, matching the four peer presets. NFKC up front,
            // the all-marks zalgo strip, confusable fold (run after demojize so
            // typographic punctuation in CLDR names folds too), accent strip and
            // whitespace collapse leave a stable fixed point — `strip_accents`'
            // terminal NFC means no decomposed tail survives — so the weaker
            // nfc-modulo form (which could mask a real non-idempotency) is not needed.
            let once = strip_obfuscation(&s).unwrap();
            let twice = strip_obfuscation(&once).unwrap();
            prop_assert_eq!(&once, &twice);
        }

        #[test]
        fn canonicalize_strict_idempotent(s in adversarial()) {
            // #434: raw equality (not nfc-modulo). The confusables fixed-point
            // loop + terminal NFC make this a true fixed point, so the weaker
            // `nfc(once) == nfc(twice)` form is no longer needed.
            let once = canonicalize_strict(&s).unwrap();
            let twice = canonicalize_strict(&once).unwrap();
            prop_assert_eq!(&once, &twice);
        }

        #[test]
        fn strip_format_idempotent(s in adversarial()) {
            // Review D-2: a presentation VS kept after a base that a later
            // strip removes (blank-render, control, zero-width) was orphaned
            // on the second pass. `is_presentation_base` now rejects those
            // bases, so the preset is a true fixed point.
            let once = strip_format(&s);
            prop_assert_eq!(&once, &strip_format(&once));
        }

        #[test]
        fn strip_bidi_idempotent(s in adversarial()) {
            let once = strip_bidi(&s);
            prop_assert_eq!(&once, &strip_bidi(&once));
        }

        // No bidi/format control survives a pipeline that strips bidi.
        #[test]
        fn no_bidi_after_strip_bidi(s in adversarial()) {
            prop_assert!(!strip_bidi(&s).chars().any(is_bidi_or_format));
        }

        #[test]
        fn no_bidi_after_canonicalize(s in adversarial()) {
            prop_assert!(!canonicalize(&s).unwrap().chars().any(is_bidi_or_format));
        }

        #[test]
        fn no_bidi_after_strip_obfuscation(s in adversarial()) {
            prop_assert!(!strip_obfuscation(&s).unwrap().chars().any(is_bidi_or_format));
        }

        #[test]
        fn no_bidi_after_canonicalize_strict(s in adversarial()) {
            prop_assert!(!canonicalize_strict(&s).unwrap().chars().any(is_bidi_or_format));
        }
    }
}
