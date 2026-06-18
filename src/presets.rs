use std::borrow::Cow;

use unicode_normalization::UnicodeNormalization;

use crate::{case_fold, confusables, emoji, invisibles, transliterate, whitespace, zalgo};

/// #413 strip policy for the comparison/storage presets (`canonicalize`,
/// `canonicalize_strict`, `strip_obfuscation`): strip every variation selector
/// and the Private Use Area.
const COMPARISON_STRIP: invisibles::StripPolicy = invisibles::StripPolicy {
    strip_pua: true,
    keep_presentation_vs: false,
};

/// #413 strip policy for the rendering preset (`strip_format`): preserve the
/// Private Use Area (icon fonts) and keep the VS15/VS16 presentation selectors
/// after a base character.
const RENDERING_STRIP: invisibles::StripPolicy = invisibles::StripPolicy {
    strip_pua: false,
    keep_presentation_vs: true,
};

/// Safety bound on the confusables fixed-point loop (#434). A single
/// `NFC → confusables → NFC` sandwich is not always a fixed point: a duplicate
/// combining mark leaves a *spare* mark that the terminal NFC reattaches,
/// re-creating a foldable composed character the next pass would consume (so the
/// preset is non-idempotent). The loop converges in a couple of iterations —
/// each folding pass removes at least one mark — and this bound is only a
/// guard against an unexpected non-converging input.
const CONFUSABLE_FIXED_POINT_ITERS: usize = 8;

// disarm does not cap input size in the pipeline presets — bounding untrusted
// input is the caller's responsibility (every stage is linear time/memory;
// see #80). The only retained size guard is the register_replacements output
// amplification bound (`MAX_REPLACEMENT_OUTPUT_BYTES` in src/limits.rs, #256),
// enforced in `tables::apply_replacements`.

// ---------------------------------------------------------------------------
// Shared ping-pong runner for the preset step lists (#453)
// ---------------------------------------------------------------------------

/// Runtime parameters for steps whose behaviour depends on call-site args.
/// Compile-time params (zalgo cap, strip policy, confusable target) ride in the
/// `Step` enum payload so step arrays stay `const`.
struct PresetCtx<'a> {
    lang: Option<&'a str>,
    strict_iso9: bool,
    emoji_cldr: bool,
}

/// One preset stage. A preset is a `const &[Step]`; ordering, subsetting, and
/// repeats are expressed by the array. Mirrors `pipeline.rs` apply_step_into,
/// extended with the four non-uniform preset stages.
#[derive(Clone, Copy)]
enum Step {
    Nfkc,
    Nfc,
    NfcIfNonAscii,
    StripBidi,
    StripInvisible(invisibles::StripPolicy),
    StripControl,
    StripZeroWidth,
    CollapseWs,
    Zalgo(usize),
    FoldCase,
    StripAccents,
    Transliterate {
        mode: crate::ErrorMode,
        only_if_lang: bool,
    },
    TranslitPreservingLatin,
    Confusables(&'static str),
    ConfusablesNfcFixedPoint(&'static str),
    Demojize {
        only_if_cldr: bool,
    },
}

/// Apply one step, writing into the reused scratch `out`. Returns `true` when `out`
/// holds the result (caller swaps it in) or `false` for a no-op (input unchanged,
/// `out` left as a spare). Every writing leaf clears `out` itself.
fn apply_into(
    step: Step,
    input: &str,
    ctx: &PresetCtx,
    out: &mut String,
) -> Result<bool, crate::ErrorRepr> {
    match step {
        Step::Nfkc => {
            crate::normalize::normalize_into(input, "NFKC", out)?;
            Ok(true)
        }
        Step::Nfc => {
            crate::normalize::normalize_into(input, "NFC", out)?;
            Ok(true)
        }
        Step::NfcIfNonAscii => {
            if input.is_ascii() {
                Ok(false)
            } else {
                crate::normalize::normalize_into(input, "NFC", out)?;
                Ok(true)
            }
        }
        Step::StripBidi => {
            strip_bidi_into(input, out);
            Ok(true)
        }
        Step::StripInvisible(policy) => {
            invisibles::strip_invisible_classes_into(input, policy, out);
            Ok(true)
        }
        Step::StripControl => {
            whitespace::strip_control_chars_into(input, out);
            Ok(true)
        }
        Step::StripZeroWidth => {
            whitespace::strip_zero_width_chars_into(input, out);
            Ok(true)
        }
        Step::CollapseWs => {
            whitespace::collapse_whitespace_into(input, out);
            Ok(true)
        }
        Step::Zalgo(cap) => {
            zalgo::strip_zalgo_into(input, cap, out);
            Ok(true)
        }
        Step::FoldCase => {
            case_fold::fold_case_into(input, out);
            Ok(true)
        }
        Step::StripAccents => {
            transliterate::strip_accents_into(input, out);
            Ok(true)
        }
        Step::Transliterate { mode, only_if_lang } => {
            if only_if_lang && ctx.lang.is_none() {
                return Ok(false);
            }
            match transliterate::transliterate_impl(
                input,
                ctx.lang,
                mode,
                "",
                ctx.strict_iso9,
                false,
                false,
            ) {
                Cow::Borrowed(_) => Ok(false),
                Cow::Owned(s) => {
                    *out = s;
                    Ok(true)
                }
            }
        }
        Step::TranslitPreservingLatin => {
            *out = transliterate_preserving_latin(input, ctx.lang);
            Ok(true)
        }
        Step::Confusables(target) => {
            confusables::normalize_confusables_into(input, target, out)?;
            Ok(true)
        }
        Step::ConfusablesNfcFixedPoint(target) => {
            let mut buf = input.to_owned();
            for _ in 0..CONFUSABLE_FIXED_POINT_ITERS {
                let next =
                    nfc_normalize(&confusables::normalize_confusables(&buf, target)?).into_owned();
                if next == buf {
                    break;
                }
                buf = next;
            }
            if buf == input {
                Ok(false)
            } else {
                *out = buf;
                Ok(true)
            }
        }
        Step::Demojize { only_if_cldr } => {
            if only_if_cldr && !ctx.emoji_cldr {
                return Ok(false);
            }
            emoji::demojize_rust_into(input, false, out);
            Ok(true)
        }
    }
}

/// Execute a preset step list with a two-buffer ping-pong (the engine pattern from
/// `pipeline.rs`): O(1) live buffers regardless of step count, no per-stage alloc.
fn run(steps: &[Step], text: &str, ctx: &PresetCtx) -> Result<String, crate::ErrorRepr> {
    let mut cur = text.to_owned();
    let mut scratch = String::new();
    for &step in steps {
        if apply_into(step, &cur, ctx, &mut scratch)? {
            std::mem::swap(&mut cur, &mut scratch);
        }
    }
    Ok(cur)
}

/// NFC-normalize `text`, skipping the pass for all-ASCII input (ASCII is already
/// in NFC normal form).
///
/// Used by the presets to keep them fixed points (#416). Stripping a zero-width /
/// invisible separator can leave a base character adjacent to a combining mark
/// that was not adjacent before — a *decomposed* sequence the leading NFKC passed
/// over; an NFC recomposes it. `canonicalize` additionally **sandwiches** its
/// confusable fold between two NFC passes, because TR39 skeletoning is not
/// normalization-stable (it treats composed vs decomposed accented letters
/// differently, and can emit a decomposed skeleton). NFC, not NFKC, is correct:
/// the leading NFKC already removed every compatibility form, and the later steps
/// only delete or skeleton code points, so only canonical base+mark adjacencies
/// can appear — exactly what NFC composes.
#[inline]
fn nfc_normalize(text: &str) -> Cow<'_, str> {
    if text.is_ascii() {
        Cow::Borrowed(text)
    } else {
        Cow::Owned(text.nfc().collect())
    }
}

/// Strip dangerous bidirectional override and formatting characters
/// that `collapse_whitespace` does not handle.
///
/// Character list follows UAX #9 (Unicode Bidirectional Algorithm) §3.3.2
/// "Explicit Directional Formatting Characters" plus the soft hyphen
/// (frequently abused to split security keywords invisibly).
///
/// Covers: soft hyphen (U+00AD), Arabic Letter Mark (U+061C),
/// bidi marks (U+200E–U+200F), bidi embeddings/overrides (U+202A–U+202E),
/// bidi isolates (U+2066–U+2069), deprecated format controls (U+206A–U+206F),
/// and interlinear annotation marks (U+FFF9–U+FFFB).
pub(crate) fn strip_bidi(text: &str) -> String {
    let mut out = String::new();
    strip_bidi_into(text, &mut out);
    out
}

/// In-place form of [`strip_bidi`] (#236 item 7).
pub(crate) fn strip_bidi_into(text: &str, out: &mut String) {
    out.clear();
    // Every bidi/format target is >= U+00AD, so pure-ASCII input passes through
    // unchanged — skip the per-char filter entirely (review D-3). Guarded by
    // `strip_bidi_has_no_ascii_targets`.
    if text.is_ascii() {
        out.push_str(text);
        return;
    }
    out.reserve(text.len()); // filter's size_hint lower bound is 0
    out.extend(text.chars().filter(|&ch| !is_bidi_or_format(ch)));
}

#[inline]
fn is_bidi_or_format(ch: char) -> bool {
    // ── Soft hyphen ─────────────────────────────────────
    // Not a bidi char per se, but invisible and used to split keywords.
    if ch == '\u{00AD}' {
        return true;
    }

    // ── Deprecated format controls + interlinear annotation (#67.2) ──
    // U+206A–U+206F (deprecated: symmetric/digit shaping, inhibit join) and
    // U+FFF9–U+FFFB (interlinear annotation anchor/separator/terminator) are
    // invisible/format characters; strip them here too so strip_bidi /
    // strip_format don't leave them behind (they were previously only handled
    // as transliteration-table entries).
    if matches!(ch, '\u{206A}'..='\u{206F}' | '\u{FFF9}'..='\u{FFFB}') {
        return true;
    }

    // ── UAX #9 §3.3.2 bidi formatting characters ───────
    // Grouped by Unicode version for auditability.
    matches!(
        ch,
        // Unicode 1.0 – marks
        '\u{200E}'             // LRM  Left-to-Right Mark
        | '\u{200F}'           // RLM  Right-to-Left Mark
        // Unicode 1.0 – explicit embeddings / overrides
        | '\u{202A}'           // LRE  Left-to-Right Embedding
        | '\u{202B}'           // RLE  Right-to-Left Embedding
        | '\u{202C}'           // PDF  Pop Directional Formatting
        | '\u{202D}'           // LRO  Left-to-Right Override
        | '\u{202E}'           // RLO  Right-to-Left Override
        // Unicode 6.3 – isolates + Arabic Letter Mark
        | '\u{061C}'           // ALM  Arabic Letter Mark
        | '\u{2066}'           // LRI  Left-to-Right Isolate
        | '\u{2067}'           // RLI  Right-to-Left Isolate
        | '\u{2068}'           // FSI  First Strong Isolate
        | '\u{2069}' // PDI  Pop Directional Isolate
    )
}

// ---------------------------------------------------------------------------
// Precompiled pipeline functions
// ---------------------------------------------------------------------------

/// Security-focused text canonicalization.
///
/// Pipeline: NFKC → strip bidi/format → strip invisibles → strip_control →
/// strip_zero_width → collapse_whitespace → cap marks (zalgo) → NFC →
/// confusables → NFC
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
pub(crate) fn canonicalize(text: &str) -> Result<String, crate::ErrorRepr> {
    const STEPS: &[Step] = &[
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
        // 3b. Cap combining marks at 2 per base (#429), matching canonicalize_strict.
        //     Removes zalgo stacking so a stacked token matches its base in a denylist
        //     comparison, while keeping legitimate diacritics (`café`, `Việt`). Runs
        //     AFTER the control / zero-width strip above so a stripped invisible
        //     between two marks cannot split a mark run and hide the count (the #121
        //     lesson); a later strip would merge the runs and break idempotency.
        Step::Zalgo(2),
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
        Step::ConfusablesNfcFixedPoint("latin"),
    ];
    // #431: no path-separator neutralization. Mapping a synthesised '/' (e.g. a
    // confusable-unmasked U+2044) to '_' is sink-specific output-sanitizer
    // behaviour, which THREAT_MODEL.md says disarm does not do — and it silently
    // corrupted legitimate URLs/paths. Path-traversal defence belongs at the sink,
    // run on this canonicalized output (see THREAT_MODEL.md "Pipeline placement").
    run(
        STEPS,
        text,
        &PresetCtx {
            lang: None,
            strict_iso9: false,
            emoji_cldr: false,
        },
    )
}

/// ML/NLP text normalization pipeline.
///
/// Pipeline: NFKC → emoji→text → strip_accents → fold_case → collapse_whitespace
///
/// Produces clean, accent-free, lowercased text suitable for tokenizers,
/// embeddings, and feature extraction. Emoji are expanded to their CLDR
/// short-name descriptions before transliteration.
///
/// # Parameters
/// - `emoji_style`: `"cldr"` — expand emoji to CLDR short names (default);
///   `"none"` — leave emoji characters as-is; any other value raises `DisarmError`.
pub(crate) fn ml_normalize(
    text: &str,
    lang: Option<&str>,
    emoji_style: &str,
) -> Result<String, crate::ErrorRepr> {
    // `const` declared before the prologue to satisfy
    // clippy::items_after_statements; it has no runtime effect.
    const STEPS: &[Step] = &[
        // 1. NFKC normalization
        Step::Nfkc,
        // 2. Emoji → text (CLDR short names) when emoji_style == "cldr".
        Step::Demojize { only_if_cldr: true },
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
        // 5. Unicode case folding (ß→ss, ﬁ→fi, etc.)
        Step::FoldCase,
        // 6. Strip non-whitespace controls + zero-width, then fold whitespace (#433).
        Step::StripControl,
        Step::StripZeroWidth,
        Step::CollapseWs,
    ];
    crate::transliterate::validate_lang(lang)?;
    // Validate emoji_style — only two modes are supported.
    if !matches!(emoji_style, "cldr" | "none") {
        return Err(crate::ErrorRepr::InvalidEmojiStyle {
            got: emoji_style.to_owned(),
        });
    }
    run(
        STEPS,
        text,
        &PresetCtx {
            lang,
            strict_iso9: false,
            emoji_cldr: emoji_style == "cldr",
        },
    )
}

/// Library catalog key generation pipeline.
///
/// Pipeline: NFKC → strip_bidi → fold_case → transliterate → confusables → strip_accents → fold_case → collapse_whitespace
///
/// Transliteration runs before confusable normalization so that non-Latin
/// scripts receive correct phonetic romanization (e.g. Cyrillic г→g, not
/// the visual confusable г→r).
///
/// `strip_bidi` runs early (#93) so bidi overrides (U+202E) and soft hyphens
/// (U+00AD) cannot survive into the key — otherwise two visually-identical
/// titles produce different keys and dedup/lookup silently misses.
///
/// Produces a canonical deduplication key for bibliographic titles.
/// Optional ISO 9:1995 transliteration for Cyrillic catalog records.
pub(crate) fn catalog_key(
    text: &str,
    lang: Option<&str>,
    strict_iso9: bool,
) -> Result<String, crate::ErrorRepr> {
    // `const` declared before the validate prologue to satisfy
    // clippy::items_after_statements; it has no runtime effect.
    const STEPS: &[Step] = &[
        // 1. NFKC normalization
        Step::Nfkc,
        // 2. Strip bidi overrides + soft hyphen + format marks (#93)
        Step::StripBidi,
        // 3. Unicode case folding FIRST (#419): a cased letter whose folded form is in
        //    the transliteration table but whose original is not (e.g. Georgian
        //    Mtavruli `Ჱ` → Mkhedruli `ჱ` → `he`) would otherwise transliterate only
        //    on the second pass — non-idempotent. Fold before transliterate so both
        //    passes see the same form.
        Step::FoldCase,
        // 4. Transliterate (always — catalog keys should be pure ASCII where possible;
        //    runs before confusables so that non-Latin scripts are romanized first,
        //    avoiding broken confusable mappings like Cyrillic к → literal \u{0138})
        Step::Transliterate {
            mode: crate::ErrorMode::Preserve,
            only_if_lang: false,
        },
        // 5. Confusables → Latin (normalize any remaining cross-script homoglyphs)
        Step::Confusables("latin"),
        // 6. Strip accents
        Step::StripAccents,
        // 6b. Case-fold AGAIN (#419): full transliteration can *emit* uppercase ASCII
        //     (`£` → `GBP`, `№` → `No`), unreachable by the pre-transliterate fold.
        Step::FoldCase,
        // 7. Strip non-whitespace controls + zero-width, then fold whitespace (#433).
        Step::StripControl,
        Step::StripZeroWidth,
        Step::CollapseWs,
    ];
    crate::transliterate::validate_lang(lang)?;
    run(
        STEPS,
        text,
        &PresetCtx {
            lang,
            strict_iso9,
            emoji_cldr: false,
        },
    )
}

/// Search index key generation pipeline.
///
/// Pipeline: NFKC → strip_bidi → fold_case → transliterate → strip_accents → fold_case → collapse_whitespace
///
/// Produces a case-insensitive, accent-insensitive, script-insensitive lookup
/// key.  Like `catalog_key` but without confusable normalization — lighter and
/// faster for search indexes where homoglyph attacks are not a concern.
///
/// `strip_bidi` runs early (#93) so an invisible char (bidi override, soft
/// hyphen) embedded in a stored value still produces the same key as the clean
/// query — otherwise lookups silently miss.
pub(crate) fn search_key(text: &str, lang: Option<&str>) -> Result<String, crate::ErrorRepr> {
    // `const` declared before the validate prologue to satisfy
    // clippy::items_after_statements; it has no runtime effect.
    const STEPS: &[Step] = &[
        // 1. NFKC normalization
        Step::Nfkc,
        // 2. Strip bidi overrides + soft hyphen + format marks (#93)
        Step::StripBidi,
        // 3. Unicode case folding FIRST (#419): a cased letter whose folded form is in
        //    the transliteration table but whose original is not (e.g. Georgian
        //    Mtavruli `Ჱ` → Mkhedruli `ჱ` → `he`) would otherwise transliterate only
        //    on the second pass — non-idempotent. Fold before transliterate so both
        //    passes see the same form.
        Step::FoldCase,
        // 4. Transliterate (always — search keys should be pure ASCII where possible)
        Step::Transliterate {
            mode: crate::ErrorMode::Preserve,
            only_if_lang: false,
        },
        // 5. Strip accents
        Step::StripAccents,
        // 6. Case-fold AGAIN (#419): full transliteration can *emit* uppercase ASCII
        //    (`£` → `GBP`, `№` → `No`), which the pre-transliterate fold above could not
        //    reach. Folding the output too makes the key a fixed point.
        Step::FoldCase,
        // 7. Strip non-whitespace controls + zero-width, then fold whitespace (#433).
        Step::StripControl,
        Step::StripZeroWidth,
        Step::CollapseWs,
    ];
    crate::transliterate::validate_lang(lang)?;
    run(
        STEPS,
        text,
        &PresetCtx {
            lang,
            strict_iso9: false,
            emoji_cldr: false,
        },
    )
}

/// Transliterate only non-Latin scripts, preserving Latin (including accented
/// Latin), Common (digits/punctuation/whitespace) and Inherited (combining
/// marks) characters verbatim.
///
/// This is the one step that distinguishes [`sort_key`] from [`search_key`]:
/// `search_key` ASCII-folds every accented letter (`ü` → `u`) for exact-match
/// lookup, whereas a collation key must keep the accent so ordering can tie-break
/// on it. We still fold *non-Latin* scripts to a consistent Latin form so that,
/// e.g., Cyrillic and Latin titles interfile ("Война" → "voyna").
///
/// disarm's transliteration tables are per-codepoint, so splitting the input
/// into maximal non-Latin runs at Latin/Common boundaries and transliterating
/// each run independently yields the same output as transliterating the whole
/// string would — minus the Latin characters we deliberately keep.
fn transliterate_preserving_latin(text: &str, lang: Option<&str>) -> String {
    let mut out = String::with_capacity(text.len());
    let mut run = String::new(); // pending consecutive non-Latin characters
    let flush = |run: &mut String, out: &mut String| {
        if !run.is_empty() {
            out.push_str(&transliterate::transliterate_impl(
                run,
                lang,
                crate::ErrorMode::Preserve,
                "",
                false,
                false,
                false,
            ));
            run.clear();
        }
    };
    for ch in text.chars() {
        // Latin (incl. Latin-1 Supplement / Extended accented letters), Common,
        // and Inherited (combining diacritics) are kept as-is; everything else
        // is buffered into the current run and transliterated at the next break.
        if matches!(
            crate::scripts::detect_char_script(ch),
            "Latin" | "Common" | "Inherited"
        ) {
            flush(&mut run, &mut out);
            out.push(ch);
        } else {
            run.push(ch);
        }
    }
    flush(&mut run, &mut out);
    out
}

/// Sort key generation pipeline.
///
/// Pipeline: NFKC → strip_bidi → fold_case → transliterate-non-Latin →
/// collapse_whitespace
///
/// Like [`search_key`] but **preserves base accented characters** so the accent
/// survives for ordering: "Über" folds to `über` (not `uber`), staying distinct
/// from an unaccented "Uber" instead of colliding with it. Non-Latin scripts are
/// still folded to a consistent Latin form so "Война и мир" files under
/// "voyna i mir". This is the collation counterpart to `search_key`, which folds
/// accents away for exact-match lookup — the two keys are deliberately *not*
/// interchangeable for accented Latin input.
///
/// Note: the result is a normalized string, not a UCA collation-weight key, so
/// plain codepoint comparison will *not* interfile `über` with ASCII `u…` words
/// (precomposed `ü` = U+00FC sorts after all of ASCII). Feed the key to a
/// locale-aware collator when linguistically-correct order matters; the value
/// here is that the accent is *preserved* for that collator rather than folded.
///
/// `strip_bidi` runs early (#93) so invisible bidi/format chars cannot perturb
/// the ordering of otherwise-identical strings.
pub(crate) fn sort_key(text: &str, lang: Option<&str>) -> Result<String, crate::ErrorRepr> {
    // `const` declared before the validate prologue to satisfy
    // clippy::items_after_statements; it has no runtime effect.
    const STEPS: &[Step] = &[
        // 1. NFKC normalization (canonical-composes accents: `é` stays one codepoint)
        Step::Nfkc,
        // 2. Strip bidi overrides + soft hyphen + format marks (#93)
        Step::StripBidi,
        // 3. Unicode case folding FIRST (#419). A cased letter whose *folded* form is
        //    in the transliteration table but whose original form is not — e.g. a
        //    Georgian Mtavruli capital `Ჱ` (U+1CB1), absent from the table, folds to
        //    Mkhedruli `ჱ` (U+10F1), which transliterates to `he` — would otherwise
        //    transliterate only on the *second* pass, breaking idempotency. Folding
        //    before transliterate makes both passes see the same form. (`Über` →
        //    `über`; `ß` → `ss`; Latin accents survive.)
        Step::FoldCase,
        // 4. Transliterate non-Latin scripts only — Latin accents are preserved so
        //    the collation key can order on them (this is the sort_key/search_key
        //    distinction; search_key strips accents here instead).
        Step::TranslitPreservingLatin,
        // 4b. Fold case AGAIN. Transliteration can *emit* uppercase from a non-Latin
        //     source the pre-transliterate fold could not reach — e.g. Old Persian
        //     `𐏈` (U+103C8) romanizes to the proper noun `Auramazda`. Without this
        //     second fold the key is `Auramazda` on pass 1 and `auramazda` on pass 2,
        //     violating `f(f(x)) == f(x)`. `fold_case` only lowercases (it never
        //     strips accents), so accent preservation — the sort_key invariant
        //     (`Über` → `über`) — is unaffected.
        Step::FoldCase,
        // 5. Strip non-whitespace controls + zero-width, then fold whitespace (#433).
        Step::StripControl,
        Step::StripZeroWidth,
        Step::CollapseWs,
        // 6. Terminal NFC (#416): because sort_key now *preserves* Latin accents
        //    (#411) instead of folding them away, a combining mark separated from its
        //    base by a now-stripped zero-width would otherwise survive in decomposed
        //    form and only compose on the next pass — breaking idempotency. Recompose
        //    so `f(f(x)) == f(x)`.
        Step::NfcIfNonAscii,
    ];
    crate::transliterate::validate_lang(lang)?;
    run(
        STEPS,
        text,
        &PresetCtx {
            lang,
            strict_iso9: false,
            emoji_cldr: false,
        },
    )
}

/// Display-safe text cleaning pipeline.
///
/// Pipeline: strip bidi/format → strip invisibles → strip_control → strip_zero_width → collapse_whitespace
///
/// Lightweight cleanup for user-submitted content destined for rendering.
/// Strips bidirectional overrides (which can visually reorder text to hide
/// malicious content), control characters, and zero-width injections, then
/// collapses runs of whitespace to single spaces.
pub(crate) fn strip_format(text: &str) -> String {
    const STEPS: &[Step] = &[
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
    ];
    run(
        STEPS,
        text,
        &PresetCtx {
            lang: None,
            strict_iso9: false,
            emoji_cldr: false,
        },
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
/// Pipeline: NFKC → strip_bidi → strip_zero_width → strip_control → strip
///           invisible classes (#413) → strip_zalgo → confusables →
///           collapse_whitespace → NFC (terminal NFC recomposes any base+mark
///           left adjacent by a stripped invisible, keeping the preset
///           idempotent — #416/#413)
///
/// Accepts multilingual input in its original script while neutralizing
/// Unicode-level abuse:
/// - **NFKC**: collapses fullwidth bypasses, ligatures, superscripts
/// - **strip_bidi / zero-width / control**: removes invisibles *first* so they
///   cannot split a run of combining marks (keeps the zalgo cap idempotent)
/// - **strip_zalgo**: caps combining marks at 2 per base character, preventing
///   stacked diacritical abuse while preserving legitimate diacritics (é, ñ, ệ)
/// - **confusables**: neutralizes cross-script homoglyph attacks
/// - **collapse_whitespace**: final whitespace-run normalization
///
/// Unlike `canonicalize`, this pipeline strips zalgo text.  Unlike
/// `catalog_key`/`search_key`, it does *not* transliterate — the original
/// script is preserved.
pub(crate) fn canonicalize_strict(text: &str) -> Result<String, crate::ErrorRepr> {
    const STEPS: &[Step] = &[
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
        // 3. Cap combining marks at 2 per base character (zalgo)
        Step::Zalgo(2),
        // 4. Confusables → Latin (neutralizes cross-script homoglyphs), iterated with
        //    NFC to a fixed point (#434): a duplicate combining mark can survive one
        //    fold and recompose via NFC, re-creating a foldable composed char the next
        //    pass would consume (`c`+◌̧+◌̧ → `ç` then `c`). Looping makes the preset a
        //    true fixed point — see `canonicalize` for the full rationale.
        Step::ConfusablesNfcFixedPoint("latin"),
        // 5. Fold whitespace (#433: fold-only — control/zero-width were already
        //    stripped explicitly above, before the zalgo cap, per #121). The line
        //    controls now fold to a space instead of being deleted, so `a\rb` → `a b`.
        Step::CollapseWs,
        // 5b. Terminal NFC (#416/#413): stripping a CGJ (or other invisible) from
        //     between a base and a combining mark leaves them adjacent but decomposed;
        //     recompose so the pipeline stays a fixed point.
        Step::Nfc,
    ];
    // #431: no path-separator neutralization — see canonicalize. Mapping '/' to
    // '_' is sink-specific output sanitization (out of scope per THREAT_MODEL.md)
    // and corrupted legitimate input; defend traversal at the sink instead.
    run(
        STEPS,
        text,
        &PresetCtx {
            lang: None,
            strict_iso9: false,
            emoji_cldr: false,
        },
    )
}

/// Maximum-strength text deobfuscation pipeline.
///
/// Pipeline: NFKC → strip_zalgo(max_marks=0) → strip_bidi → strip_zero_width
///          → demojize → normalize_confusables → strip_accents
///          → collapse_whitespace
///
/// `normalize_confusables` runs *after* `demojize` so typographic punctuation in
/// emoji names (e.g. the `’` in "woman’s hat") is folded too; otherwise the
/// output would not be idempotent.
///
/// Strips ALL combining marks, resolves homoglyph spoofing via TR39
/// confusable mapping (visual similarity), expands emoji to text, removes
/// accents, and collapses whitespace. **Preserves case** — case is not
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
pub(crate) fn strip_obfuscation(text: &str) -> Result<String, crate::ErrorRepr> {
    const STEPS: &[Step] = &[
        // 1. NFKC normalization (collapses fullwidth, ligatures, superscripts)
        Step::Nfkc,
        // 2. Strip ALL combining marks (max_marks=0) — removes zalgo AND accents early
        Step::Zalgo(0),
        // 3. Strip bidi overrides, isolates, marks, and soft hyphens
        Step::StripBidi,
        // 4. Strip zero-width chars (ZWS, ZWNJ, ZWJ, WJ, BOM)
        Step::StripZeroWidth,
        // 5. Demojize — expand emoji to text names with spacing
        Step::Demojize {
            only_if_cldr: false,
        },
        // 5b. Strip the #413 smuggling / non-interchange classes. Runs AFTER demojize
        //     so the emoji pass sees flags/presentation selectors intact; whatever
        //     demojize leaves (stray Tags, variation selectors, noncharacters, PUA) is
        //     removed here. CGJ is already gone via the zalgo(0) combining-mark strip.
        Step::StripInvisible(COMPARISON_STRIP),
        // 6. Confusables → Latin (TR39 visual mapping: Cyrillic р→p, с→c, В→B).
        //    Runs AFTER demojize so that typographic punctuation in emoji names
        //    (e.g. the ’ in "woman’s hat") is folded too; otherwise a second pass
        //    would fold it and strip_obfuscation would not be idempotent.
        Step::Confusables("latin"),
        // 7. Strip accents (NFD decompose + strip combining marks)
        Step::StripAccents,
        // 8. Strip non-whitespace controls, then fold whitespace (#433: split out of
        //    the former fused collapse; zero-width was already stripped above). Case
        //    is NOT folded.
        Step::StripControl,
        Step::CollapseWs,
    ];
    run(
        STEPS,
        text,
        &PresetCtx {
            lang: None,
            strict_iso9: false,
            emoji_cldr: false,
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preset_golden_fixtures() {
        // Frozen pre-refactor outputs — lock byte-identity for the #430 byte-stable
        // aliases (canonicalize, strip_format, canonicalize_strict) and the hot-path
        // keys. Regenerate ONLY with explicit sign-off: changing one is an API break
        // for the byte-stable aliases. Generated by running the pre-refactor impl.
        let alias_in = "Ηеllо\u{202E}\u{200B}Wo\u{0301}\u{0301}\u{0301}rld\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}";
        assert_eq!(
            canonicalize(alias_in).unwrap(),
            "HelloW\u{f3}\u{301}rld\u{1f3f4}\u{e0067}\u{e0062}\u{e0073}\u{e0063}\u{e0074}\u{e007f}"
        );
        assert_eq!(
            strip_format(alias_in),
            "\u{397}\u{435}ll\u{43e}Wo\u{301}\u{301}\u{301}rld\u{1f3f4}\u{e0067}\u{e0062}\u{e0073}\u{e0063}\u{e0074}\u{e007f}"
        );
        assert_eq!(
            canonicalize_strict(alias_in).unwrap(),
            "HelloW\u{f3}\u{301}rld\u{1f3f4}\u{e0067}\u{e0062}\u{e0073}\u{e0063}\u{e0074}\u{e007f}"
        );
        assert_eq!(search_key("CAFÉ\u{200B} ИМЯ", None).unwrap(), "cafe imya");
        assert_eq!(
            catalog_key("Война и МИР\u{00AD}", None, false).unwrap(),
            "voyna i mir"
        );
        assert_eq!(sort_key("Über ИМЯ", None).unwrap(), "\u{fc}ber imya");
        assert_eq!(
            ml_normalize("Café \u{1F600} ИМЯ", Some("ru"), "cldr").unwrap(),
            "cafe grinning face imya"
        );
        assert_eq!(
            strip_obfuscation("Ηеllо\u{202E}Wоrld \u{1F600}").unwrap(),
            "HelloWorld grinning face"
        );
    }

    #[test]
    fn run_executes_steps_in_order_with_pingpong() {
        let steps = &[Step::StripBidi, Step::FoldCase, Step::CollapseWs];
        let ctx = PresetCtx {
            lang: None,
            strict_iso9: false,
            emoji_cldr: false,
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
        let result = ml_normalize("Café Résumé", None, "cldr").unwrap();
        assert_eq!(result, "cafe resume");
    }

    #[test]
    fn test_ml_normalize_ligature() {
        let result = ml_normalize("\u{FB01}lter", None, "cldr").unwrap();
        assert_eq!(result, "filter");
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

        /// Compare under NFC: NFKC can reorder combining marks of equal
        /// canonical combining class, which is canonically equivalent.
        fn nfc(s: &str) -> String {
            s.nfc().collect()
        }

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            #[test]
            fn canonicalize_idempotent(s in adversarial()) {
                // #416: assert *raw* equality, not equality-modulo-NFC. The
                // earlier `nfc(once) == nfc(twice)` form normalized away the very
                // difference the terminal-NFC fix removes, so it could not catch
                // the base+invisible+mark idempotency violation.
                let once = canonicalize(&s).unwrap();
                let twice = canonicalize(&once).unwrap();
                prop_assert_eq!(once, twice);
            }

            // #419: the transliterating key presets fold case BEFORE transliterate,
            // so a case pair whose folded form is in the table (but whose original
            // is not) is stable across passes. `adversarial()` draws `any::<char>()`,
            // so it exercises cross-script case pairs like Georgian Mtavruli.
            #[test]
            fn sort_key_idempotent(s in adversarial()) {
                let once = sort_key(&s, None).unwrap();
                let twice = sort_key(&once, None).unwrap();
                prop_assert_eq!(once, twice);
            }

            #[test]
            fn search_key_idempotent(s in adversarial()) {
                let once = search_key(&s, None).unwrap();
                let twice = search_key(&once, None).unwrap();
                prop_assert_eq!(once, twice);
            }

            #[test]
            fn catalog_key_idempotent(s in adversarial()) {
                let once = catalog_key(&s, None, false).unwrap();
                let twice = catalog_key(&once, None, false).unwrap();
                prop_assert_eq!(once, twice);
            }

            #[test]
            fn strip_obfuscation_idempotent(s in adversarial()) {
                let once = strip_obfuscation(&s).unwrap();
                let twice = strip_obfuscation(&once).unwrap();
                prop_assert_eq!(nfc(&once), nfc(&twice));
            }

            #[test]
            fn canonicalize_strict_idempotent(s in adversarial()) {
                // #434: raw equality (not nfc-modulo). The confusables fixed-point
                // loop + terminal NFC make this a true fixed point, so the weaker
                // `nfc(once) == nfc(twice)` form is no longer needed.
                let once = canonicalize_strict(&s).unwrap();
                let twice = canonicalize_strict(&once).unwrap();
                prop_assert_eq!(once, twice);
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
}
