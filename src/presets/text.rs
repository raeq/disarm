//! The text presets: `canonicalize`, `canonicalize_strict`, `strip_obfuscation`,
//! `strip_format` and `ml_normalize`, each a step list that returns normalized text.

use std::borrow::Cow;

use super::guard::Actionable;
use super::runner::{check_growth, run, run_static};
use super::steps::{apply_into, static_steps, PresetCtx, Step};
use super::{COMPARISON_STRIP, RENDERING_STRIP};

// ---------------------------------------------------------------------------
// Precompiled pipeline functions
// ---------------------------------------------------------------------------

/// Security-focused text canonicalization.
///
/// Pipeline: resolve deletions → [policy pre-fold] → NFKC → strip bidi/format → strip
/// invisibles → strip_control → strip_zero_width → collapse_whitespace → drop repeated
/// marks → cap marks at 3 (zalgo) → NFC → fixed point(confusables → NFC) → drop repeated
/// marks
///
/// Collapses fullwidth bypasses, neutralizes homoglyph spoofing, strips
/// zero-width injections and control chars, removes dangerous bidi overrides and
/// soft hyphens, and caps combining-mark stacking (#429) while preserving
/// legitimate diacritics.
///
/// `strip_bidi` runs *before* `collapse_whitespace` so that removing
/// invisible characters (e.g. soft hyphen U+00AD) can expose leading,
/// trailing, or consecutive whitespace that `collapse_whitespace` then
/// normalizes. Confusable folding is sandwiched between two NFC passes (#416) —
/// TR39 skeletoning is not normalization-stable — so the pipeline is idempotent
/// (`f(f(x)) == f(x)`).
/// `canonicalize` under the default policy. See [`canonicalize_with`].
pub(crate) fn canonicalize(text: &str) -> Result<Cow<'_, str>, crate::ErrorRepr> {
    canonicalize_with(text, crate::confusables::DigitPolicy::Numeric)
}

/// `canonicalize`, folding under `digit_policy` (#896): a pre-fold on the raw text under
/// any policy but the default, and the preset's own fold under the same policy.
pub(crate) fn canonicalize_with(
    text: &str,
    digit_policy: crate::confusables::DigitPolicy,
) -> Result<Cow<'_, str>, crate::ErrorRepr> {
    static_steps! {
        const STEPS;
        fn apply;
        [
            // FIRST, before `Nfkc` (#937). The renderer saw the code points as
            // written; NFKC would split `\u{FB01}` and change what the preceding
            // cell is, so the erase has to happen before anything else runs.
            Step::ResolveDeletions,
            // The #885 pre-pass, as a step: a no-op under the default (#896).
            Step::PolicyPreFold("latin"),
            // 1. NFKC normalization (collapses fullwidth, ligatures, superscripts)
            Step::Nfkc,
            // 2. Strip bidi overrides, isolates, marks, and soft hyphens
            Step::StripBidi,
            // 2b. Strip the #413 smuggling / non-interchange classes: Unicode Tags
            //     (keeping valid emoji flag sequences), variation selectors, CGJ,
            //     noncharacters, and the Private Use Area. Runs before the NFC below so a
            //     CGJ stripped from between a base and a mark gets recomposed.
            Step::StripInvisible(COMPARISON_STRIP),
            // 3. Strip non-whitespace controls + zero-width, then fold whitespace (#433:
            //    these were one fused `collapse_whitespace(_, true, true)` call; the split
            //    makes the steps explicit and lets the line controls fold to a space
            //    rather than be deleted, so e.g. `a\rb` → `a b`, not `ab`).
            Step::StripControl,
            Step::StripZeroWidth,
            Step::CollapseWs,
            // 3b. Cap combining marks at 3 per base (#429; 3 since #788, the figure
            //     `is_zalgo` flags above), matching canonicalize_strict.
            //     Removes zalgo stacking so a stacked token matches its base in a denylist
            //     comparison, while keeping legitimate diacritics (`café`, `Việt`). Runs
            //     AFTER the control / zero-width strip above so a stripped invisible
            //     between two marks cannot split a mark run and hide the count (the #121
            //     lesson); a later strip would merge the runs and break idempotency.
            // 3a. Drop a mark that repeats on one base (UTS #39 5.4, #835). BEFORE the
            //     cap, not after, so the cap counts distinct marks: `a` + five acutes +
            //     five graves capped first keeps three acutes and loses the grave
            //     entirely, while deduping first keeps one of each — the marks a reader
            //     can actually tell apart. Shares the cap's ordering requirement and so
            //     its position: after the zero-width strip, because an invisible between
            //     two identical marks would otherwise hide the repeat (#121, #850).
            Step::DropRepeatedMarks,
            Step::Zalgo(crate::zalgo::DEFAULT_MAX_MARKS),
            // 4. NFC (#416): the strips above can leave a base character next to a
            //    combining mark that was non-adjacent before (e.g. separated by a
            //    now-removed zero-width), which the leading NFKC passed over. Compose it
            //    here so the confusable fold below sees the *composed* form consistently.
            Step::Nfc,
            // 5. Confusables → Latin (neutralizes cross-script homoglyphs), iterated to a
            //    fixed point between NFC passes (#416/#434). TR39 skeletoning is not
            //    normalization-stable: it drops the diacritic on a *composed* accented
            //    letter (`ç`→`c`, `ø`→`o`) but never on the *decomposed* form, and it can
            //    *emit* a decomposed skeleton (`Ý`→`Y`+◌́). The leading NFC feeds it a
            //    composed form and the trailing NFC recomposes its output — but a
            //    *duplicate* combining mark breaks a single sandwich: NFC composes only
            //    one mark onto the base, the fold drops it, and the recomposing NFC
            //    reattaches the *spare* mark, re-creating a foldable composed char the
            //    next call would consume (`c`+◌̧+◌̧ → `ç` then `c`). Looping until stable
            //    makes the preset a true fixed point (`f(f(x)) == f(x)`).
            Step::ConfusablesNfcFixedPointCtx("latin"),
            // AGAIN, after the fold. The fold does not merely reveal a repeated mark, it
            // can MANUFACTURE one: `U+1EF3` (y with grave) folds to `U+00FD` (y with
            // acute), whose NFD is `y` + acute — so `U+1EF3` followed by a combining
            // acute becomes a base carrying the same mark twice, created by a step that
            // ran after the one which removes them. `canonicalize` stopped being
            // idempotent on 16 (base, mark) pairs.
            //
            // The pass above is NOT moved down to cover this. It runs before the cap on
            // purpose (#835): the cap must count marks a reader can distinguish, or
            // `a` + five acutes + five graves keeps three acutes and loses the grave
            // entirely. Both positions are needed, which is the same shape as
            // `CONFUSABLES_POST` (#852) and `FOLD_CASE_POST` (#751) — a step whose own
            // output re-opens the case an earlier step closed.
            //
            // `canonicalize_strict` and `sort_key` need no second pass and have none:
            // #862 already put their cap after the fold, so their single
            // `DropRepeatedMarks` is downstream of it. Measured, not assumed — both are
            // clean over every (base, mark) pair.
            Step::DropRepeatedMarks,
        ]
    }
    // #431: no path-separator neutralization. Mapping a synthesised '/' (e.g. a
    // confusable-unmasked U+2044) to '_' is sink-specific output-sanitizer
    // behaviour, which THREAT_MODEL.md says disarm does not do — and it silently
    // corrupted legitimate URLs/paths. Path-traversal defence belongs at the sink,
    // run on this canonicalized output (see THREAT_MODEL.md "Pipeline placement").
    run_static(
        MASK,
        text,
        &PresetCtx {
            lang: None,
            strict_iso9: false,
            emoji_cldr: false,
            digit_policy,
            input_len: text.len(),
        },
        apply,
    )
}

/// ML/NLP text normalization pipeline.
///
/// Pipeline: resolve deletions → NFKC → emoji→text → [transliterate] → strip_accents →
/// emoji→text → [fold_case] → strip_control → strip_zero_width → collapse_whitespace → NFC
///
/// Produces clean, accent-free, lowercased text suitable for tokenizers,
/// embeddings, and feature extraction. Emoji are expanded to their CLDR
/// short-name descriptions before transliteration.
///
/// "Emoji" means the Unicode property, not the CLDR table (#757). The annotation data
/// also names 326 code points that carry neither `Emoji` nor `Extended_Pictographic` —
/// the curly quotes, the dashes, the currency signs, the math operators — and naming
/// those inserts words into ordinary prose: `film’s` came back as
/// `film right apostrophe s`. They pass through unchanged. `demojize` called directly
/// still names them.
///
/// # Parameters
/// - `emoji_style`: `"cldr"` — expand emoji to CLDR short names (default);
///   `"none"` — leave emoji characters as-is; any other value raises `DisarmError`.
pub(crate) fn ml_normalize<'a>(
    text: &'a str,
    lang: Option<&str>,
    emoji_style: &str,
    fold_case: bool,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
    // `const` declared before the prologue to satisfy
    // clippy::items_after_statements; it has no runtime effect.
    const STEPS: &[Step; 11] = &[
        // FIRST, before `Nfkc` (#937). A sanitizer that turns `fool` into `fovJol`
        // has not recovered the input for a model — it has produced a third string
        // the model has never seen, which is what the attack wanted.
        Step::ResolveDeletions,
        // 1. NFKC normalization
        Step::Nfkc,
        // 2. Emoji → text (CLDR short names) when emoji_style == "cldr".
        //    #757: only for rows that are actually emoji. CLDR annotates 326 code
        //    points that carry no emoji property — the apostrophes, the dashes, the
        //    currency signs — and naming them inserted spurious tokens into ordinary
        //    body text: `film’s` came back as `film right apostrophe s`.
        Step::Demojize {
            only_if_cldr: true,
            policy: crate::emoji::NamePolicy {
                skip_tr39_claimed: false,
                skip_non_emoji: true,
            },
        },
        // 3. Transliterate if lang is set (e.g. "de" for ü→ue, "ja" for kana).
        //    Use Ignore mode: ML pipelines need clean ASCII-ish output, so
        //    characters with no mapping (e.g. katakana ー) should be dropped
        //    rather than preserved verbatim.
        Step::Transliterate {
            mode: crate::ErrorMode::Ignore,
            only_if_lang: true,
        },
        // 4. Strip accents (NFD decompose → remove combining marks → NFC)
        Step::StripAccents,
        // 4b. Re-run demojize after strip-accents (#498). A negated-relation symbol
        //     (e.g. `≇` U+2247, whose canonical NFD is `≅` U+2245 + U+0338 overlay)
        //     is NOT in the CLDR name table itself, so the step-2 demojize leaves it;
        //     the strip-accents step above (NFD decompose → drop combining marks →
        //     NFC) then drops the overlay and *exposes* the bare base
        //     (`≅`), which IS named. Without this second pass that freshly-exposed
        //     base is only named on the following call — non-idempotent. The
        //     exposed bases name to plain ASCII ("approximately equal"), so a
        //     single extra pass reaches the fixed point; no iteration is needed.
        Step::Demojize {
            only_if_cldr: true,
            policy: crate::emoji::NamePolicy {
                skip_tr39_claimed: false,
                skip_non_emoji: true,
            },
        },
        // 5. Unicode case folding (ß→ss, ﬁ→fi, etc.)
        Step::FoldCase,
        // 6. Strip non-whitespace controls + zero-width, then fold whitespace (#433).
        Step::StripControl,
        Step::StripZeroWidth,
        Step::CollapseWs,
        // 7. Terminal NFC, as `sort_key` has (#416). The two strips above run after the
        //    last step that composes, so a character they remove from between two that
        //    compose leaves the pair apart until the next call: conjoining jamo L + ZWSP +
        //    V came back as L V, and the key of that is the syllable. A jamo pair composes
        //    with no mark involved, which is why `StripAccents` never hid it. Finding 4
        //    of the Lean model in `formal/lean/Presets`.
        Step::NfcIfNonAscii,
    ];
    // #559: the `fold_case=false` variant, DERIVED from `STEPS` rather than written
    // out a second time — the two lists cannot drift, and `without_fold_case` const-
    // asserts that exactly one `FoldCase` was removed, so reordering or dropping the
    // step above fails the build instead of silently changing what the flag does.
    const STEPS_NO_FOLD: [Step; 10] = without_fold_case(STEPS);

    crate::transliterate::validate_lang(lang)?;
    // Validate emoji_style — only two modes are supported.
    if !matches!(emoji_style, "cldr" | "none") {
        return Err(crate::ErrorRepr::InvalidEmojiStyle {
            got: emoji_style.to_owned(),
        });
    }
    let steps: &[Step] = if fold_case { STEPS } else { &STEPS_NO_FOLD };
    run(
        steps,
        text,
        &PresetCtx {
            lang,
            strict_iso9: false,
            emoji_cldr: emoji_style == "cldr",
            digit_policy: crate::confusables::DigitPolicy::Numeric,
            input_len: text.len(),
        },
    )
}

/// Drop the single [`Step::FoldCase`] from `ml_normalize`'s step list, in `const` context.
///
/// Backs `ml_normalize`'s `fold_case=false` mode (#559). Deriving the shorter list from
/// the longer one — instead of maintaining two literals — means an edit to the pipeline
/// automatically reaches both, and the assertion below turns "someone removed or
/// duplicated `FoldCase`" into a build failure rather than a behaviour change nobody
/// notices. `Step::Nfkc` is only the array's initial filler; every slot is overwritten.
pub(super) const fn without_fold_case(steps: &[Step; 11]) -> [Step; 10] {
    let mut out = [Step::Nfkc; 10];
    let mut read = 0;
    let mut write = 0;
    while read < steps.len() {
        if !matches!(steps[read], Step::FoldCase) {
            // Check before the write, not after the loop: with zero `FoldCase` steps
            // the 11th write would hit `out[10]` and abort const-eval with a generic
            // out-of-bounds panic, hiding the reason. Assert here so the message the
            // maintainer sees names the actual invariant.
            assert!(
                write < 10,
                "ml_normalize's step list must contain exactly one Step::FoldCase"
            );
            out[write] = steps[read];
            write += 1;
        }
        read += 1;
    }
    assert!(
        write == 10,
        "ml_normalize's step list must contain exactly one Step::FoldCase"
    );
    out
}

/// Display-safe text cleaning pipeline.
///
/// Pipeline: strip bidi/format → strip invisibles → strip_control → strip_zero_width → collapse_whitespace
///
/// Lightweight cleanup for user-submitted content destined for rendering.
/// Strips bidirectional overrides (which can visually reorder text to hide
/// malicious content), control characters, and zero-width injections, then
/// collapses runs of whitespace to single spaces.
pub(crate) fn strip_format(text: &str) -> Cow<'_, str> {
    static_steps! {
        const STEPS;
        fn apply;
        [
            // 1. Strip bidi overrides, isolates, marks, and soft hyphens
            Step::StripBidi,
            // 1b. Strip the #413 smuggling / non-interchange classes, with the rendering
            //     policy: keep well-formed emoji flags, keep VS15/VS16 after a base, and
            //     PRESERVE the Private Use Area (icon fonts) rather than deleting it. CGJ
            //     and noncharacters are still stripped. No NFC pass: strip_format does no
            //     NFKC, so any base+mark left decomposed stays decomposed (idempotent).
            Step::StripInvisible(RENDERING_STRIP),
            // 2. Strip non-whitespace controls + zero-width, then fold whitespace (#433).
            Step::StripControl,
            Step::StripZeroWidth,
            Step::CollapseWs,
        ]
    }
    run_static(
        MASK,
        text,
        &PresetCtx {
            lang: None,
            strict_iso9: false,
            emoji_cldr: false,
            digit_policy: crate::confusables::DigitPolicy::Numeric,
            input_len: text.len(),
        },
        apply,
    )
    .expect("strip_format steps are infallible")
}

/// Normalize user-submitted input — Unicode hygiene, **not** an output sanitizer.
///
/// Neutralizes Unicode-level abuse (zalgo, homoglyphs, bidi, zero-width, control)
/// while preserving the original script. It performs no HTML/JS/SQL escaping and
/// is not an XSS or injection defense — encode at the output sink (see
/// `THREAT_MODEL.md`).
///
/// Pipeline: resolve deletions → [policy pre-fold] → NFKC → strip_bidi →
///           strip_zero_width → strip_control → strip invisible classes (#413) →
///           fixed point(fixed point(confusables → NFC) → strip cross-script marks) →
///           drop repeated marks → strip_zalgo → collapse_whitespace → NFC (terminal
///           NFC recomposes any base+mark left adjacent by a stripped invisible,
///           keeping the preset idempotent — #416/#413)
///
/// Accepts multilingual input in its original script while neutralizing
/// Unicode-level abuse:
/// - **NFKC**: collapses fullwidth bypasses, ligatures, superscripts
/// - **strip_bidi / zero-width / control**: removes invisibles *first* so they
///   cannot split a run of combining marks (keeps the zalgo cap idempotent)
/// - **strip_zalgo**: caps combining marks at `DEFAULT_MAX_MARKS` (3) per base
///   character — the same figure `is_zalgo` flags above, so this preset never strips
///   from text the library calls ordinary (#788) — preventing
///   stacked diacritical abuse while preserving legitimate diacritics (é, ñ, ệ)
/// - **confusables**: neutralizes cross-script homoglyph attacks, iterated with the
///   cross-script mark strip (#615, #638); the cap runs after both (#862)
/// - **collapse_whitespace**: final whitespace-run normalization
///
/// Unlike `canonicalize`, this pipeline strips zalgo text.  Unlike
/// `catalog_key`/`search_key`, it does *not* transliterate — the original
/// script is preserved.
/// `canonicalize_strict` under the default policy. See [`canonicalize_strict_with`].
pub(crate) fn canonicalize_strict(text: &str) -> Result<Cow<'_, str>, crate::ErrorRepr> {
    canonicalize_strict_with(text, crate::confusables::DigitPolicy::Numeric)
}

/// `canonicalize_strict`, folding under `digit_policy` (#896).
pub(crate) fn canonicalize_strict_with(
    text: &str,
    digit_policy: crate::confusables::DigitPolicy,
) -> Result<Cow<'_, str>, crate::ErrorRepr> {
    static_steps! {
        const STEPS;
        fn apply;
        [
            // FIRST, before `Nfkc` (#937). The renderer saw the code points as
            // written; NFKC would split `\u{FB01}` and change what the preceding
            // cell is, so the erase has to happen before anything else runs.
            Step::ResolveDeletions,
            // The #885 pre-pass, as a step: a no-op under the default (#896).
            Step::PolicyPreFold("latin"),
            // 1. NFKC normalization
            Step::Nfkc,
            // 2. Strip invisibles FIRST (bidi/format + zero-width + non-whitespace
            //    control) so they cannot split a run of combining marks; otherwise
            //    removing them later would merge two short runs into one long run that a
            //    second pass would cap differently (zalgo-capping would not be
            //    idempotent) — e.g. "\u{301}\u{301}\0\u{301}" must not become a longer
            //    contiguous run once the NUL is stripped. (#433) strip_control_chars now
            //    *preserves* the whitespace controls — CR/VT/FF/NEL/FS–US — which the
            //    final fold turns into a space; folding a separator, unlike deleting it,
            //    leaves a stable boundary and so keeps the cap idempotent.
            Step::StripBidi,
            Step::StripZeroWidth,
            Step::StripControl,
            // 2b. Strip the #413 smuggling / non-interchange classes (Tags with the flag
            //     carve-out, variation selectors, CGJ, noncharacters, PUA).
            Step::StripInvisible(COMPARISON_STRIP),
            // 4. Confusables → Latin (neutralizes cross-script homoglyphs), iterated with
            //    NFC to a fixed point (#434): a duplicate combining mark can survive one
            //    fold and recompose via NFC, re-creating a foldable composed char the next
            //    pass would consume (`c`+◌̧+◌̧ → `ç` then `c`). Looping makes the preset a
            //    true fixed point — see `canonicalize` for the full rationale.
            // 4 + 4b. The confusable fold and the #615 cross-script mark strip, iterated
            //     TOGETHER to a fixed point (#638). Each is a fixed point on its own and
            //     the pair was not, because they expose work for each other in both
            //     directions:
            //
            //     — the fold rewrites the BASE, so a mark that matched its base beforehand
            //       can stop matching afterwards. `а` (Cyrillic) + U+0489 (Cyrillic mark)
            //       agrees before the fold and not after it, which is why #615 put the
            //       strip second: deciding against the FINAL base script is the only
            //       stable point.
            //     — and the strip removes marks, which can expose a COMPOSITION the fold
            //       has already finished with. `U+0489` has ccc 0, so it is a starter and
            //       blocks `C`+`U+0327` from composing; remove it and the terminal NFC
            //       makes `Ç`, which folds to `C` — one pass too late. 474 code points
            //       reach that shape and `canonicalize_strict_idempotent` found one.
            //
            //     Neither ordering is a fixed point alone, so the pair loops. It converges
            //     for the same reason the inner fold does: every pass either folds a
            //     character or deletes a mark, and neither is undone.
            //
            //     4b's rule itself (drop a mark whose own script differs from its base's,
            //     #615, CVE-2017-7833): the zalgo cap above is a COUNT, and by count one
            //     Arabic shadda is indistinguishable from one acute accent, so no
            //     threshold removes the spoof and keeps `café`.
            Step::ConfusablesMarkFixedPointCtx("latin"),
            // 4c. Cap combining marks (#862). Runs AFTER the fold above, not before it,
            //     because `ConfusablesMarkFixedPoint` carries the #615 cross-script mark
            //     strip — and that strip DELETES marks. A cross-script mark sitting between
            //     two runs of ordinary ones splits them for the count, is then removed, and
            //     the runs merge for the next pass, which truncates further:
            //
            //         canonicalize_strict("a" + U+0308*3 + U+0489 + U+0308)  ->  4 marks
            //         canonicalize_strict(that)                              ->  3
            //
            //     This is the #121 lesson one step wider than #850 applied it. #850 moved
            //     `sort_key`'s cap after the zero-width strip; the cross-script mark strip
            //     is a third character-removing step, and the one that removes marks
            //     specifically. Every removing step has to precede the count.
            // 3a. Drop a mark that repeats on one base (UTS #39 5.4, #835). BEFORE the
            //     cap, not after, so the cap counts distinct marks: `a` + five acutes +
            //     five graves capped first keeps three acutes and loses the grave
            //     entirely, while deduping first keeps one of each — the marks a reader
            //     can actually tell apart. Shares the cap's ordering requirement and so
            //     its position: after the zero-width strip, because an invisible between
            //     two identical marks would otherwise hide the repeat (#121, #850).
            Step::DropRepeatedMarks,
            Step::Zalgo(crate::zalgo::DEFAULT_MAX_MARKS),
            // 5. Fold whitespace (#433: fold-only — control/zero-width were already
            //    stripped explicitly above, before the zalgo cap, per #121). The line
            //    controls now fold to a space instead of being deleted, so `a\rb` → `a b`.
            Step::CollapseWs,
            // 5b. Terminal NFC (#416/#413): stripping a CGJ (or other invisible) from
            //     between a base and a combining mark leaves them adjacent but decomposed;
            //     recompose so the pipeline stays a fixed point.
            Step::Nfc,
        ]
    }
    // #431: no path-separator neutralization — see canonicalize. Mapping '/' to
    // '_' is sink-specific output sanitization (out of scope per THREAT_MODEL.md)
    // and corrupted legitimate input; defend traversal at the sink instead.
    run_static(
        MASK,
        text,
        &PresetCtx {
            lang: None,
            strict_iso9: false,
            emoji_cldr: false,
            digit_policy,
            input_len: text.len(),
        },
        apply,
    )
}

/// Maximum-strength text deobfuscation pipeline.
///
/// Pipeline: resolve deletions → [policy pre-fold] → NFKC → strip_zalgo(max_marks=0)
///          → strip_bidi → strip_zero_width → strip invisibles → confusables
///          → strip_accents → strip_control → collapse_whitespace → NFC
///
/// No `demojize` since #910: a comparison surface must not write attacker-chosen words
/// into the value being compared, so an emoji is left where it stands.
///
/// Strips ALL combining marks, resolves homoglyph spoofing via TR39
/// confusable mapping (visual similarity), removes accents, and collapses
/// whitespace. **Preserves case** — case is not
/// deception (proper nouns, acronyms, sentence boundaries are meaningful).
/// Chain with `fold_case()` if lowercasing is also needed.
///
/// NFKC handles ligature decomposition (ﬁ→fi, ﬀ→ff) without case folding.
///
/// **Does NOT transliterate.** Confusable normalization maps by visual
/// similarity (Cyrillic р→p, с→c, В→B), not phonetic value (р→r, с→s, В→V).
/// Users who also need transliteration should chain explicitly:
/// `strip_obfuscation(text) → transliterate(result)`.
///
/// Use cases: content moderation, anti-phishing, spam detection, hate speech
/// detection, social media NLP preprocessing.
/// `strip_obfuscation` under the default policy. See [`strip_obfuscation_with`].
pub(crate) fn strip_obfuscation(text: &str) -> Result<Cow<'_, str>, crate::ErrorRepr> {
    strip_obfuscation_with(text, crate::confusables::DigitPolicy::Numeric)
}

/// `strip_obfuscation`, folding under `digit_policy` (#896).
pub(crate) fn strip_obfuscation_with(
    text: &str,
    digit_policy: crate::confusables::DigitPolicy,
) -> Result<Cow<'_, str>, crate::ErrorRepr> {
    static_steps! {
        const STEPS;
        fn apply;
        [
            // FIRST, before `Nfkc` (#937). The renderer saw the code points as
            // written; NFKC would split `\u{FB01}` and change what the preceding
            // cell is, so the erase has to happen before anything else runs.
            Step::ResolveDeletions,
            // The #885 pre-pass, as a step: a no-op under the default (#896).
            Step::PolicyPreFold("latin"),
            // 1. NFKC normalization (collapses fullwidth, ligatures, superscripts)
            Step::Nfkc,
            // 2. Strip ALL combining marks (max_marks=0) — removes zalgo AND accents early
            Step::Zalgo(0),
            // 3. Strip bidi overrides, isolates, marks, and soft hyphens
            Step::StripBidi,
            // 4. Strip zero-width chars (ZWS, ZWNJ, ZWJ, WJ, BOM)
            Step::StripZeroWidth,
            // 5. NO demojize (#910).
            //
            //    This preset named 1,177 emoji into English words, which is the same
            //    defect the `llm_guardrail` profile had: a surface used for comparison
            //    against untrusted text inserted attacker-chosen words into the value
            //    being compared. `\u{1F600}` reached `grinning face`, and the reachable
            //    vocabulary over `Emoji_Presentation` was 1,272 distinct words.
            //
            //    #614 and #757 narrowed WHAT it named — the TR39-claimed rows, then the
            //    non-emoji rows — twice. Neither could reach the case where the naming is
            //    correct and the profile should not be doing it at all.
            //
            //    Nothing else was riding on the step here. Unlike the composed pipeline
            //    in #914, TAG stripping is `StripInvisible`'s job below and always was.
            //
            //    Naming stays reachable: `demojize()` and `TextPipeline(demojize=True)`.
            // 5b. Strip the #413 smuggling / non-interchange classes: stray Tags,
            //     variation selectors, noncharacters and PUA. CGJ is already gone via the
            //     zalgo(0) combining-mark strip above.
            Step::StripInvisible(COMPARISON_STRIP),
            // 6. Confusables → Latin (TR39 visual mapping: Cyrillic р→p, с→c, В→B).
            //    The note that used to sit here — that this must follow demojize so the
            //    `\u{2019}` in "woman\u{2019}s hat" is folded, or a second pass would fold
            //    it and break idempotence — no longer applies: there are no emoji names to
            //    carry typographic punctuation into the string.
            Step::ConfusablesCtx("latin"),
            // 7. Strip accents (NFD decompose + strip combining marks)
            Step::StripAccents,
            // 8. Strip non-whitespace controls, then fold whitespace (#433: split out of
            //    the former fused collapse; zero-width was already stripped above). Case
            //    is NOT folded.
            Step::StripControl,
            Step::CollapseWs,
            // 9. Terminal NFC (#416), as `sort_key` has. The control strip above runs
            //    after the last step that composes, so a control between two characters
            //    that compose left them apart until the next call: conjoining jamo L +
            //    NUL + V came back as L V, whose key is the syllable. The mark strips
            //    cannot hide it, because a jamo pair composes with no mark involved.
            //    Finding 4 of the Lean model in `formal/lean/Presets`.
            Step::NfcIfNonAscii,
        ]
    }
    run_static(
        MASK,
        text,
        &PresetCtx {
            lang: None,
            strict_iso9: false,
            emoji_cldr: false,
            digit_policy,
            input_len: text.len(),
        },
        apply,
    )
}
