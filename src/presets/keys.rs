//! The key builders: `catalog_key`, `search_key`, `sort_key` and `skeleton_key`, each
//! a step list that returns a comparison key rather than text for display.

use std::borrow::Cow;

use super::guard::Actionable;
use super::runner::{check_growth, run_static, run_static_policy_fixed};
use super::steps::{apply_into, static_steps, PresetCtx, Step};
use super::COMPARISON_STRIP;
use crate::transliterate;

/// Library catalog key generation pipeline.
///
/// Pipeline: resolve deletions → [policy pre-fold] → NFKC → strip_bidi → strip
/// invisibles → fold_case → fixed point(transliterate → confusables → strip_accents) →
/// fold_case → strip_control → strip_zero_width → collapse_whitespace → NFC
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
/// `catalog_key` under the default policy. See [`catalog_key_with`].
pub(crate) fn catalog_key<'a>(
    text: &'a str,
    lang: Option<&str>,
    strict_iso9: bool,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
    catalog_key_with(
        text,
        lang,
        strict_iso9,
        crate::confusables::DigitPolicy::Numeric,
    )
}

/// `catalog_key`, folding under `digit_policy` (#896). The pre-fold runs on the raw
/// text, before transliteration consumes the non-Latin digit the policy exists to read.
pub(crate) fn catalog_key_with<'a>(
    text: &'a str,
    lang: Option<&str>,
    strict_iso9: bool,
    digit_policy: crate::confusables::DigitPolicy,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
    // `const` declared before the validate prologue to satisfy
    // clippy::items_after_statements; it has no runtime effect.
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
            // 2. Strip bidi overrides + soft hyphen + format marks (#93)
            Step::StripBidi,
            // 2b. Strip the #413 smuggling / non-interchange classes: Unicode Tags,
            //     variation selectors, CGJ, noncharacters and the Private Use Area — the
            //     same policy `canonicalize` uses, for the same reason (#805).
            //
            //     A key builder exists so two spellings of one identity compare equal, and
            //     every class here is a way to vary the key invisibly. Measured before the
            //     fix, all three builders were evaded by a noncharacter, by a Tag character
            //     and by a plane-15 PUA code point; `sort_key` additionally by a variation
            //     selector and by CGJ. BMP PUA was already handled, which is what made the
            //     gap look narrower than it was.
            Step::StripInvisible(COMPARISON_STRIP),
            // 3. Unicode case folding FIRST (#419): a cased letter whose folded form is in
            //    the transliteration table but whose original is not (e.g. Georgian
            //    Mtavruli `Ჱ` → Mkhedruli `ჱ` → `he`) would otherwise transliterate only
            //    on the second pass — non-idempotent. Fold before transliterate so both
            //    passes see the same form.
            Step::FoldCase,
            // 4/5/6. Romanization core, iterated to a fixed point (#467). A single pass
            //    of transliterate → confusables → strip-accents is not idempotent: each
            //    step can feed an EARLIER one on a re-run —
            //      • strip-accents drops the U+0338 overlay of a negated relation and
            //        exposes a confusable the fold already passed (`∤`→`∣`→`l`);
            //      • confusables emits a letter transliterate romanizes (`ᴔ`→`ǝo`, then
            //        `ǝ`→`e`);
            //      • the maps chain.
            //    Looping the whole core folds them all the way down in one call. Order
            //    within each pass is preserved (transliterate first, so non-Latin scripts
            //    are romanized before confusables — avoiding broken mappings like Cyrillic
            //    к → literal \u{0138}; confusables before strip-accents, so a confusable
            //    that *emits* an accent is still stripped). Transliterate uses Preserve
            //    mode (always on) so catalog keys are pure ASCII where possible.
            Step::FixedPoint(&[
                Step::Transliterate {
                    mode: crate::ErrorMode::Preserve,
                    only_if_lang: false,
                },
                Step::ConfusablesCtx("latin"),
                Step::StripAccents,
            ]),
            // 6b. Case-fold AGAIN (#419): full transliteration can *emit* uppercase ASCII
            //     (`£` → `GBP`, `№` → `No`), unreachable by the pre-transliterate fold.
            Step::FoldCase,
            // 7. Strip non-whitespace controls + zero-width, then fold whitespace (#433).
            Step::StripControl,
            Step::StripZeroWidth,
            Step::CollapseWs,
            // 8. Terminal NFC, as `sort_key` (#416) and `ml_normalize` have (#1040). The
            //    strips above run after the last step that composes, so a control between
            //    two characters that compose left them apart until the next call. Kirat
            //    Rai U+16D67 U+0016 U+16D67 keyed as the two vowel signs, and the key of
            //    that was U+16D68: the pair composes with no mark involved, and nothing
            //    romanizes Kirat Rai, so neither the accent strip nor transliteration hid
            //    it, as they hide conjoining jamo.
            Step::NfcIfNonAscii,
        ]
    }
    crate::transliterate::validate_lang(lang)?;
    run_static(
        MASK,
        text,
        &PresetCtx {
            lang,
            strict_iso9,
            emoji_cldr: false,
            digit_policy,
            input_len: text.len(),
        },
        apply,
    )
}

/// Search index key generation pipeline.
///
/// Pipeline: resolve deletions → [policy pre-fold] → NFKC → strip_bidi → strip
/// invisibles → fold_case → transliterate → strip_accents → fold_case → strip_control →
/// strip_zero_width → collapse_whitespace → NFC
///
/// Produces a case-insensitive, accent-insensitive, script-insensitive lookup
/// key.  Like `catalog_key` but without confusable normalization — lighter and
/// faster for search indexes where homoglyph attacks are not a concern. Under a
/// non-default digit policy the pre-fold is the whole confusable table, and the list
/// runs to a fixed point ([`search_key_with`]).
///
/// `strip_bidi` runs early (#93) so an invisible char (bidi override, soft
/// hyphen) embedded in a stored value still produces the same key as the clean
/// query — otherwise lookups silently miss.
/// `search_key` under the default policy. See [`search_key_with`].
pub(crate) fn search_key<'a>(
    text: &'a str,
    lang: Option<&str>,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
    search_key_with(text, lang, crate::confusables::DigitPolicy::Numeric)
}

/// `search_key`, folding under `digit_policy` (#896). This builder has no fold of its
/// own; the pre-fold on the raw text is the whole reach, as it was for the pre-pass.
///
/// Under a policy other than the default that fold is the whole confusable table, not
/// only the digit rows, and the builder is iterated to a fixed point
/// ([`run_static_policy_fixed`]); the default runs once, as it always has.
pub(crate) fn search_key_with<'a>(
    text: &'a str,
    lang: Option<&str>,
    digit_policy: crate::confusables::DigitPolicy,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
    // `const` declared before the validate prologue to satisfy
    // clippy::items_after_statements; it has no runtime effect.
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
            // 2. Strip bidi overrides + soft hyphen + format marks (#93)
            Step::StripBidi,
            // 2b. Strip the #413 smuggling / non-interchange classes: Unicode Tags,
            //     variation selectors, CGJ, noncharacters and the Private Use Area — the
            //     same policy `canonicalize` uses, for the same reason (#805).
            //
            //     A key builder exists so two spellings of one identity compare equal, and
            //     every class here is a way to vary the key invisibly. Measured before the
            //     fix, all three builders were evaded by a noncharacter, by a Tag character
            //     and by a plane-15 PUA code point; `sort_key` additionally by a variation
            //     selector and by CGJ. BMP PUA was already handled, which is what made the
            //     gap look narrower than it was.
            Step::StripInvisible(COMPARISON_STRIP),
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
            // 8. Terminal NFC, for the reason `catalog_key` gives (#1040).
            Step::NfcIfNonAscii,
        ]
    }
    crate::transliterate::validate_lang(lang)?;
    run_static_policy_fixed(
        MASK,
        text,
        &PresetCtx {
            lang,
            strict_iso9: false,
            emoji_cldr: false,
            digit_policy,
            input_len: text.len(),
        },
        apply,
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
pub(super) fn transliterate_preserving_latin_into(
    text: &str,
    lang: Option<&str>,
    out: &mut String,
) {
    // Ping-pong form: write into the runner's reused scratch buffer rather than
    // returning a fresh `String` (PR #454 review). Clears `out` first, per the
    // `*_into` leaf convention.
    out.clear();
    out.reserve(text.len());
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
        // P-3: every ASCII code point is Latin or Common (asserted by
        // `ascii_is_always_kept_verbatim`), so skip the per-char script binary
        // search on the hot ASCII path and keep it verbatim directly.
        //
        // The *block* script, not `detect_char_script`: a run is "the text one script's
        // transliteration owns", and the katakana prolonged sound mark is Common to the
        // UCD but has to stay in the katakana run it lengthens. Bopomofo is kept verbatim
        // as it was while it resolved to no script: nothing romanizes it.
        if ch.is_ascii()
            || matches!(
                crate::scripts::block_script(ch),
                "Latin" | "Common" | "Inherited" | "Bopomofo"
            )
        {
            flush(&mut run, out);
            out.push(ch);
        } else {
            run.push(ch);
        }
    }
    flush(&mut run, out);
}

/// Sort key generation pipeline.
///
/// Pipeline: resolve deletions → [policy pre-fold] → NFKC → strip_bidi → strip invisibles
/// → fold_case → transliterate-non-Latin → fold_case → strip_control → strip_zero_width →
/// collapse_whitespace → drop repeated marks → cap marks at 3 → NFC (if non-ASCII)
///
/// The second `fold_case` lowercases any uppercase a transliteration *emits* (e.g.
/// Old Persian `𐏈` → `Auramazda`), and the terminal NFC recomposes a base+mark left
/// adjacent by a stripped invisible — both required for `f(f(x)) == f(x)` (#419/#416).
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
/// `sort_key` under the default policy. See [`sort_key_with`].
pub(crate) fn sort_key<'a>(
    text: &'a str,
    lang: Option<&str>,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
    sort_key_with(text, lang, crate::confusables::DigitPolicy::Numeric)
}

/// `sort_key`, folding under `digit_policy` (#896). No fold of its own; the pre-fold on
/// the raw text is the whole reach, as it was for the pre-pass. Iterated to a fixed point
/// under a policy other than the default, like [`search_key_with`].
pub(crate) fn sort_key_with<'a>(
    text: &'a str,
    lang: Option<&str>,
    digit_policy: crate::confusables::DigitPolicy,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
    // `const` declared before the validate prologue to satisfy
    // clippy::items_after_statements; it has no runtime effect.
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
            // 1. NFKC normalization (canonical-composes accents: `é` stays one codepoint)
            Step::Nfkc,
            // 2. Strip bidi overrides + soft hyphen + format marks (#93)
            Step::StripBidi,
            // 2b. Strip the #413 smuggling / non-interchange classes: Unicode Tags,
            //     variation selectors, CGJ, noncharacters and the Private Use Area — the
            //     same policy `canonicalize` uses, for the same reason (#805).
            //
            //     A key builder exists so two spellings of one identity compare equal, and
            //     every class here is a way to vary the key invisibly. Measured before the
            //     fix, all three builders were evaded by a noncharacter, by a Tag character
            //     and by a plane-15 PUA code point; `sort_key` additionally by a variation
            //     selector and by CGJ. BMP PUA was already handled, which is what made the
            //     gap look narrower than it was.
            Step::StripInvisible(COMPARISON_STRIP),
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
            // 5b. Cap combining marks (#807). `sort_key` was the one key builder with
            //     neither `strip_zalgo` nor `strip_accents`, so nothing bounded them:
            //     `sort_key("a" + U+0301 * 40 + "b")` returned 41 characters and
            //     `has_anomalies` called its own output `zalgo`. The other two builders are
            //     clean only as a side effect — `strip_accents` removes the marks — and that
            //     is not available here, because keeping diacritics is what a sort key is
            //     FOR: `café` and `cafe` must not collide.
            //
            //     Capping rather than stripping preserves that. `DEFAULT_MAX_MARKS` is the
            //     figure `is_zalgo` flags above (#788), so this removes exactly what the
            //     library already calls abuse and nothing it calls ordinary — which is why
            //     #788 had to land first. A three-mark Bengali cluster or a pointed Hebrew
            //     consonant sorts unchanged.
            //
            //     Runs AFTER the strips above, matching `canonicalize` step 3b, so a
            //     stripped invisible between two marks cannot split a run and hide the
            //     count. #843 first placed it before them, and the split run then merged on
            //     the next pass and truncated further: `sort_key` of U+0301 * 3 + ZWSP +
            //     U+0301 returned four marks, and `sort_key` of *that* returned three.
            // 3a. Drop a mark that repeats on one base (UTS #39 5.4, #835). BEFORE the
            //     cap, not after, so the cap counts distinct marks: `a` + five acutes +
            //     five graves capped first keeps three acutes and loses the grave
            //     entirely, while deduping first keeps one of each — the marks a reader
            //     can actually tell apart. Shares the cap's ordering requirement and so
            //     its position: after the zero-width strip, because an invisible between
            //     two identical marks would otherwise hide the repeat (#121, #850).
            Step::DropRepeatedMarks,
            Step::Zalgo(crate::zalgo::DEFAULT_MAX_MARKS),
            // 6. Terminal NFC (#416): because sort_key now *preserves* Latin accents
            //    (#411) instead of folding them away, a combining mark separated from its
            //    base by a now-stripped zero-width would otherwise survive in decomposed
            //    form and only compose on the next pass — breaking idempotency. Recompose
            //    so `f(f(x)) == f(x)`.
            Step::NfcIfNonAscii,
        ]
    }
    crate::transliterate::validate_lang(lang)?;
    run_static_policy_fixed(
        MASK,
        text,
        &PresetCtx {
            lang,
            strict_iso9: false,
            emoji_cldr: false,
            digit_policy,
            input_len: text.len(),
        },
        apply,
    )
}

/// The TR39 identifier skeleton, plus the two prototype classes disarm's table keeps
/// apart (#650). A spoof key: its only job is to make two confusable identifiers collide.
///
/// # Why this is a builder and not a flag
///
/// TR39 puts `I`, `l` and `1` in one equivalence class and `O`/`0` in another. disarm's
/// table stops short of both, so `paypaI` survives every existing surface intact. Closing
/// it costs six collision groups in the 235,976 entries of `/usr/share/dict/words` —
/// `Ione`/`lone` is the only ordinary-word merge, the other five are proper nouns.
///
/// That price holds **only on cased text**. After a case fold, `I ≡ l` is `i ≡ l` and the
/// same class costs 264 groups of ordinary vocabulary: `boiling`/`bolling`, `doit`/`dolt`,
/// `ail`/`all`. A factor of 44.
///
/// No existing key builder offers that position. `catalog_key` folds case at step 3 and
/// reaches its confusable step at step 6, and the order cannot be swapped: `presets/keys.rs`
/// records that fold-before-transliterate is required for idempotency (#419), because a
/// cased letter whose folded form is in the transliteration table would otherwise convert
/// only on the second pass. So the class needs its own entry point, which is this.
///
/// # The digit half is the caller's decision
///
/// `digit_policy` is `Numeric` by default, and then only the letter half applies. Under
/// `Tr39` the digit half joins it — and it is not free. Every one of these collapses to a
/// single key:
///
/// | kind | inputs |
/// |---|---|
/// | part number | `SKU-100`, `SKU-1O0`, `SKU-IOO`, `SKU-l00` |
/// | plate | `B01`, `BOI`, `BOl`, `B0I` |
/// | version | `v1.0.1`, `vI.O.I`, `vl.o.l` |
///
/// For a spoof detector that is the point. For a deduplication key over anything carrying
/// a part number, a version or an ISBN it destroys the field, which is why `catalog_key`
/// is the worst available home for it and not the best.
///
/// # Not for display
///
/// The output is a key. It is more destructive than any preset that forwards text, in the
/// same way `canonicalize_strict` is more destructive than `canonicalize` — the more
/// aggressive rule lives in the entry point whose contract says so.
///
/// # Errors
///
/// Propagates the confusable fold's error.
pub(crate) fn skeleton_key<'a>(
    text: &'a str,
    digit_policy: &str,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
    // `const` declared before the validate prologue to satisfy
    // clippy::items_after_statements; it has no runtime effect.
    static_steps! {
        const STEPS;
        fn apply;
        [
            // FIRST, before `Nfkc` (#937). The renderer saw the code points as
            // written; NFKC would split `\u{FB01}` and change what the preceding
            // cell is, so the erase has to happen before anything else runs.
            Step::ResolveDeletions,
            // 1. The reordering and smuggling channels, before anything reads the text.
            //    A key exists so two spellings of one identity compare equal, and every
            //    class here is a way to vary the key invisibly (#805).
            //
            //    Before NFKC, not after it, and never after a fold. A character here that
            //    sits between a base and its mark blocks their composition, and deleting
            //    it afterwards leaves the pair decomposed where the same text without it
            //    arrives composed. `I` + a zero-width space + U+0301 reached step 4 as a
            //    bare `I`, and keyed as `l` + U+0301 while `I` + U+0301 keyed as U+00ED.
            //    Controls and zero-width characters ran after the last fold as well,
            //    which made the key itself not a fixed point: `a` + U+0001 + U+0300 keyed
            //    as `a` + U+0300, and that keyed as U+00E0. NFKC never emits a character
            //    these steps remove, so running them first loses nothing. Found by the
            //    Lean model in `formal/lean/Confusables` (F1).
            Step::StripBidi,
            Step::StripInvisible(COMPARISON_STRIP),
            Step::StripControl,
            Step::StripZeroWidth,
            // 2. NFKC, so a compatibility spelling reaches the fold as its base form.
            Step::Nfkc,
            // 3. The confusable fold, under the caller's policy. This is what brings the
            //    capital-I family to `I` and every non-Latin homoglyph to its Latin
            //    prototype.
            Step::ConfusablesCtx("latin"),
            // 4. TR39's last two classes, on CASED text — the whole reason this builder
            //    exists. Six collisions here, 264 one step later.
            Step::PrototypeFold,
            // 5. Fold case, then fold confusables AGAIN, to a fixed point.
            //
            //    The second pass is not redundant. The table's entry for a homoglyph is
            //    often on the *lowercase* form, so a capital that step 3 could not match
            //    becomes matchable the moment case is folded: `Ω` (U+2126 OHM SIGN)
            //    reaches step 5 as `Ω`, folds to `ω`, and only then folds to `w`. With a
            //    single pass `skeleton_key("Ω")` returned `ω` while `skeleton_key("ω")`
            //    returned `w` — not idempotent, and a key that is not a fixed point is
            //    not a key.
            //
            //    A second pass rather than moving the first: step 3 has to see cased text
            //    or step 4 has nothing to work with, and folding case first is what turns
            //    six collisions into 264. So the fix is another pass, never a reorder
            //    (#467's shape, and the reason `catalog_key` has a `FixedPoint` too).
            //
            //    And NFKC inside the loop, because both steps in it can leave the text
            //    decomposed with nothing after them to recompose it. Full case folding
            //    emits decomposed sequences (U+0390 becomes U+03B9 U+0308 U+0301), and
            //    the fold here does not compose (#522's interaction): U+00A5 + U+0300
            //    folds to `y` + U+0300, which is one character, U+1EF3, the next time
            //    round. Either way the key was not a fixed point, and the #522 pair
            //    U+04AA + U+0327 keyed as `c` + U+0327 while U+00E7 keyed as `c`. Found
            //    by the Lean model in `formal/lean/Confusables` (F1).
            Step::FixedPoint(&[Step::FoldCase, Step::ConfusablesCtx("latin"), Step::Nfkc]),
            // 6. Whitespace (#433).
            Step::CollapseWs,
        ]
    }
    let digit_policy = crate::confusables::DigitPolicy::from_token(digit_policy)?;
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
