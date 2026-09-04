use std::borrow::Cow;

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
pub(crate) const CONFUSABLE_FIXED_POINT_ITERS: usize = 8;

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
    /// The digit policy for the ctx-reading confusable steps (#650).
    ///
    /// `Step::Confusables` and friends carry their policy as const data, which is right
    /// for the eight presets that pick one and keep it. `skeleton_key` takes it from the
    /// caller, and threading a runtime value through a `static_steps!` const would mean
    /// three copies of the list — the tripling #646 §2 warned about. Carrying it here
    /// instead keeps one list per preset and leaves the monomorphisation of #695/#868
    /// alone. Every other preset sets `Numeric`, which is what they did implicitly.
    digit_policy: crate::confusables::DigitPolicy,
}

/// One preset stage. A preset is a `const &[Step]`; ordering, subsetting, and
/// repeats are expressed by the array. Mirrors `pipeline.rs` apply_step_into,
/// extended with the four non-uniform preset stages.
#[derive(Clone, Copy)]
enum Step {
    /// Resolve the deletion class — `BS`/`DEL` erase the preceding cell (#937).
    ///
    /// Must be the FIRST step of any list that carries it, and before `Nfkc` rather than
    /// merely before `StripControl`. The renderer saw the code points as written, and
    /// every earlier step changes what "the preceding cell" is: `ﬁ` + `BS` erases to
    /// nothing, and to `f` once NFKC has split the ligature.
    ///
    /// `CR` is deliberately not resolved here. No preset makes that call: a lone `CR` is
    /// a rendering overwrite in a terminal and a classic Mac OS line ending in a file
    /// from before 2001, and the two are byte-identical.
    ResolveDeletions,
    Nfkc,
    Nfc,
    NfcIfNonAscii,
    StripBidi,
    StripInvisible(invisibles::StripPolicy),
    StripControl,
    StripZeroWidth,
    CollapseWs,
    Zalgo(usize),
    /// Drop a nonspacing mark that repeats on one base (UTS #39 §5.4, #835).
    ///
    /// Separate from [`Step::Zalgo`] on purpose: the cap is paired with `is_zalgo` by
    /// #788 and must not touch a string the predicate calls ordinary, and two identical
    /// acutes are ordinary by count. This is about the repeat, not the amount.
    DropRepeatedMarks,
    FoldCase,
    StripAccents,
    Transliterate {
        mode: crate::ErrorMode,
        only_if_lang: bool,
    },
    TranslitPreservingLatin,
    /// The confusable fold, taking its policy from [`PresetCtx`] rather than the step.
    ///
    /// `skeleton_key` took it this way first (#650), and since #896 every key builder
    /// does; the profiles' pipeline carries the same field (#646). A const-policy twin
    /// existed until #951 and was constructed by nothing once the lists moved here. See
    /// the `digit_policy` field on `PresetCtx` for why the policy rides there and not
    /// on the step.
    ConfusablesCtx(&'static str),
    /// The Python pre-pass of #885, as a step (#896): under any policy but the default,
    /// fold confusables on the raw text before the preset's own steps run; under
    /// `Numeric` do nothing at all. Rides at the head of every key builder's list.
    ///
    /// A step rather than a call in the binding layer so that all seven surfaces get the
    /// one implementation, and a no-op under the default so that every default key is
    /// byte-identical to what it was — the fixture gate proves that. Positioned on raw
    /// text because that is where the pre-pass measured its reach: `catalog_key`
    /// transliterates before its own fold, and a policy applied after transliteration
    /// never sees the non-Latin digit it exists to read.
    PolicyPreFold(&'static str),
    /// The confusables→NFC fixed point (#416/#434), folding under the policy on
    /// [`PresetCtx`] (#896) rather than a const `Numeric` — which is what makes
    /// `preserve` hold (#949). The loop itself is
    /// [`confusables_nfc_fixed_point_into`].
    ConfusablesNfcFixedPointCtx(&'static str),
    /// The confusables→NFC fixed point and the #615 cross-script mark strip, iterated
    /// *together* (#638). Neither is a fixed point in the presence of the other; see
    /// `canonicalize_strict` for why, and for the convergence argument. Takes its policy
    /// from [`PresetCtx`] like its neighbour; the loop is
    /// [`confusables_mark_fixed_point_into`].
    ConfusablesMarkFixedPointCtx(&'static str),
    /// TR39's last two prototype classes — `I ≡ l` always, `1 ≡ l` and `0 ≡ O` under
    /// `Tr39` — applied on cased text (#650).
    ///
    /// Must sit after a confusable fold, which is what brings the whole capital-I family
    /// to `I`, and before any [`Step::FoldCase`]: the letter half costs 6 collisions in
    /// 235,976 dictionary words at this position and 264 after a fold.
    PrototypeFold,
    /// Iterate an inner step list to a fixed point (#467). The catalog key's
    /// romanization core (`transliterate → confusables → strip_accents`) is not a
    /// fixed point in a single pass: `strip_accents` can drop the U+0338 overlay of
    /// a negated relation and expose a confusable the fold already passed
    /// (`∤`→`∣`→`l`); `confusables` can emit a letter `transliterate` folds
    /// (`ᴔ`→`ǝo`, then `ǝ`→`e`); and the maps chain. Looping the whole core makes
    /// the preset idempotent. The inner list must not itself contain `FixedPoint`.
    FixedPoint(&'static [Step]),
    Demojize {
        only_if_cldr: bool,
        /// Which CLDR name rows to leave for the rest of the pipeline (#614, #757).
        /// Standalone `demojize` and the explicit `TextPipeline` step name every row.
        policy: crate::emoji::NamePolicy,
    },
}

/// One statically-known step list, emitted three ways: as the `Step` slice the fast-path
/// guard and `explain()` read, as a compile-time `Actionable` mask, and as a straight-line
/// applier.
///
/// The applier is why this exists. `apply_steps` walks a `&[Step]` and calls `apply_into`
/// with a *runtime* value, so the optimiser cannot prove any match arm unreachable and
/// every preset links every table a step could reach — `strip_format` declares five steps
/// that neither transliterate nor demojize and linked the Hanzi pinyin and CLDR emoji
/// tables anyway, at 663 KB against a possible 27 KB (#695).
///
/// Unrolling gives each call a `const` step, which `apply_into` being `#[inline(always)]`
/// lets LLVM fold to the one arm. The arms a preset does not name become unreachable *per
/// call site* rather than per program, and the linker drops their data.
///
/// `TextPipeline` keeps the dynamic path deliberately: it is configured at runtime, so it
/// can name any step and must link every table. The presets are static and need not.
macro_rules! static_steps {
    (
        $(#[$meta:meta])*
        const $steps:ident;
        fn $apply:ident;
        [$($step:expr),* $(,)?]
    ) => {
        $(#[$meta])*
        const $steps: &[Step] = &[$($step),*];

        /// The fast-path mask for the list above, computed at compile time.
        ///
        /// `Actionable::for_steps` matches every `Step` variant, so calling it at runtime
        /// kept the payload types — and the CLDR emoji table behind them — in any binary
        /// that reached it, through a function that only sets booleans (#695).
        const MASK: Actionable = Actionable::for_steps($steps);

        /// One pass of the step list above, unrolled. See `static_steps!`.
        #[inline]
        fn $apply(input: &str, ctx: &PresetCtx) -> Result<String, crate::ErrorRepr> {
            let mut cur = input.to_owned();
            let mut scratch = String::new();
            $(
                if apply_into($step, &cur, ctx, &mut scratch)? {
                    std::mem::swap(&mut cur, &mut scratch);
                }
            )*
            Ok(cur)
        }
    };
}

/// One confusables→NFC fixed point, the body of [`Step::ConfusablesNfcFixedPointCtx`].
///
/// A free function rather than an arm the `Ctx` twin re-enters (#974). `apply_into`
/// calling itself makes it self-recursive, and LLVM will not `alwaysinline` a recursive
/// function: the attribute is dropped, the match stops folding to one arm at each call
/// site, and every preset links every table again — 662,087 bytes for `strip_format`
/// against 27,490. Both arms call this instead, so the loop still lives once and nothing
/// recurses.
fn confusables_nfc_fixed_point_into(
    input: &str,
    target: &'static str,
    digits: crate::confusables::DigitPolicy,
    out: &mut String,
) -> Result<bool, crate::ErrorRepr> {
    // #416/#434: confusables→NFC iterated to a fixed point. Reuse buffers
    // across iterations (PR #454 review) instead of allocating a fresh
    // `String` per pass — `cur` holds the running text, `conf` the
    // confusables intermediate, `nxt` the NFC result; the two scratch
    // buffers are cleared-and-refilled (not reallocated) each pass, so the
    // loop allocates only as they reach their high-water mark, on the
    // hottest presets (`canonicalize` / `canonicalize_strict`).
    let mut cur = input.to_owned();
    let mut conf = String::new();
    let mut nxt = String::new();
    // P-2: once `cur` has been through an NFC pass it is NFC-stable, so when a
    // later confusables pass changes nothing (`conf == cur`) the trailing NFC
    // is a no-op — skip it and stop, sparing a full-string normalization on the
    // terminal iteration. On the first iteration `cur` is the step input, whose
    // NFC-ness is unknown (`canonicalize_strict` reaches this step without an
    // immediately-preceding NFC), so the NFC still runs there. The result is
    // byte-identical to normalizing on every pass.
    let mut cur_is_nfc = false;
    for _ in 0..CONFUSABLE_FIXED_POINT_ITERS {
        confusables::normalize_confusables_into(&cur, target, digits, &mut conf)?;
        if conf == cur && cur_is_nfc {
            break;
        }
        crate::normalize::normalize_into(&conf, "NFC", &mut nxt)?;
        if nxt == cur {
            break;
        }
        std::mem::swap(&mut cur, &mut nxt);
        cur_is_nfc = true;
    }
    if cur == input {
        Ok(false)
    } else {
        *out = cur;
        Ok(true)
    }
}

/// One confusables→NFC→strip-marks fixed point, the body of
/// [`Step::ConfusablesMarkFixedPointCtx`]. Free for the same reason as its neighbour (#974).
fn confusables_mark_fixed_point_into(
    input: &str,
    target: &'static str,
    digits: crate::confusables::DigitPolicy,
    out: &mut String,
) -> Result<bool, crate::ErrorRepr> {
    // #638. The generic `FixedPoint` combinator would do this, but it
    // allocates a fresh `String` per inner step per pass and pushed
    // `canonicalize_strict` from 6 allocations per call to 12, which
    // `preset_alloc_count` refuses. This mirrors `ConfusablesNfcFixedPoint`'s
    // buffer reuse and, crucially, exits after the FIRST strip when the strip
    // changed nothing — which is every input with no cross-script mark, i.e.
    // essentially all of them. The loop is only paid for by text that
    // actually triggers the interaction.
    let mut cur = input.to_owned();
    let mut conf = String::new();
    let mut nxt = String::new();
    let mut stripped = String::new();
    for _ in 0..CONFUSABLE_FIXED_POINT_ITERS {
        // Inner fold-to-fixed-point, same shape as ConfusablesNfcFixedPoint.
        let mut cur_is_nfc = false;
        for _ in 0..CONFUSABLE_FIXED_POINT_ITERS {
            confusables::normalize_confusables_into(&cur, target, digits, &mut conf)?;
            if conf == cur && cur_is_nfc {
                break;
            }
            crate::normalize::normalize_into(&conf, "NFC", &mut nxt)?;
            if nxt == cur {
                break;
            }
            std::mem::swap(&mut cur, &mut nxt);
            cur_is_nfc = true;
        }
        zalgo::strip_cross_script_marks_into(&cur, &mut stripped);
        if stripped == cur {
            // Nothing was removed, so nothing new can be exposed: the pair is
            // already at its fixed point and the outer loop has no work.
            break;
        }
        std::mem::swap(&mut cur, &mut stripped);
    }
    if cur == input {
        Ok(false)
    } else {
        *out = cur;
        Ok(true)
    }
}

/// Apply one step, writing into the reused scratch `out`. Returns `true` when `out`
/// holds the result (caller swaps it in) or `false` for a no-op (input unchanged,
/// `out` left as a spare). Every writing leaf clears `out` itself.
// `inline(always)`, against clippy's advice and deliberately (#695). This is an
// eighteen-arm match, which LLVM will not inline at its own discretion — measured, plain
// `#[inline]` leaves it out of line and every preset links every table again: 656,850
// bytes for `strip_format` against 27,384 with this attribute. Inlining is what lets each
// call site fold the `const` step to its one arm, which is the whole mechanism.
#[allow(clippy::inline_always)]
#[inline(always)]
fn apply_into(
    step: Step,
    input: &str,
    ctx: &PresetCtx,
    out: &mut String,
) -> Result<bool, crate::ErrorRepr> {
    match step {
        Step::Nfkc => {
            crate::normalize::normalize_into(input, "NFKC", out)?;
            // #768: NFKC is an amplification the caller cannot foresee from the input
            // size, which is the reason `limits.rs` gives for capping the replacement
            // pre-pass — and NFKC was not capped. `U+FDFA` expands to 18 characters, so
            // 6 MB in produced 60 MB out. Checked against produced output, the same shape
            // the replacement cap uses.
            if out.len() > crate::limits::MAX_NORMALIZE_OUTPUT_BYTES {
                return Err(crate::ErrorRepr::NormalizeOutputTooLarge {
                    size: out.len(),
                    max: crate::limits::MAX_NORMALIZE_OUTPUT_BYTES,
                });
            }
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
        Step::DropRepeatedMarks => Ok(zalgo::drop_repeated_marks_into(input, out)),
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
            transliterate_preserving_latin_into(input, ctx.lang, out);
            Ok(true)
        }
        Step::ResolveDeletions => Ok(crate::deletions::resolve_deletions_into(input, false, out)),
        Step::ConfusablesCtx(target) => {
            confusables::normalize_confusables_into(input, target, ctx.digit_policy, out)?;
            Ok(true)
        }
        Step::PolicyPreFold(target) => {
            if ctx.digit_policy == crate::confusables::DigitPolicy::Numeric {
                return Ok(false);
            }
            // The pre-pass was the *public* fold — the fixed-point form (#586), which
            // composes between passes — so a decomposed base + mark reaches the row keyed
            // on its composed form. The single-pass `_into` here left `a\u{304}` unfolded
            // where the pre-pass folded `ā` → `ã`, the one delta a 290k-probe sweep found.
            match confusables::normalize_confusables_fixed_cow(
                input,
                target,
                ctx.digit_policy.as_token(),
            )? {
                Cow::Borrowed(_) => Ok(false),
                Cow::Owned(folded) => {
                    *out = folded;
                    Ok(true)
                }
            }
        }
        // The two fixed-point twins resolve the policy and hand off to the const arm, so
        // the loops live once. The variant is const at every call site, so the outer
        // match still folds to one arm (#695).
        Step::ConfusablesNfcFixedPointCtx(target) => {
            confusables_nfc_fixed_point_into(input, target, ctx.digit_policy, out)
        }
        Step::ConfusablesMarkFixedPointCtx(target) => {
            confusables_mark_fixed_point_into(input, target, ctx.digit_policy, out)
        }
        Step::PrototypeFold => Ok(confusables::prototype_fold_into(
            input,
            ctx.digit_policy,
            out,
        )),
        Step::FixedPoint(inner) => {
            // #467: apply the inner sub-pipeline repeatedly until its output
            // stabilizes. Each pass runs `inner` once via the same ping-pong as
            // `run`; every pass folds at least one more form (a confusable exposed by
            // strip-accents, or a letter the next transliterate pass romanizes), so
            // it converges in a couple of passes and is bounded by the cap.
            let mut cur = input.to_owned();
            for _ in 0..CONFUSABLE_FIXED_POINT_ITERS {
                let next = apply_steps(inner, &cur, ctx)?;
                if next == cur {
                    break;
                }
                cur = next;
            }
            if cur == input {
                Ok(false)
            } else {
                *out = cur;
                Ok(true)
            }
        }
        Step::Demojize {
            only_if_cldr,
            policy,
        } => {
            if only_if_cldr && !ctx.emoji_cldr {
                return Ok(false);
            }
            emoji::demojize_rust_into(input, false, policy, out);
            Ok(true)
        }
    }
}

/// Which codepoint classes a preset's steps can change (#458 fast-path guard).
/// Some classes act only on ASCII bytes (`controls`, `collapse_ws`), some only on
/// non-ASCII code points (`norm`/`bidi`/`zero_width`/`invisible`/`transliterate`/
/// `demojize`), and `fold_case`/`confusables` span both tiers. `classify` applies
/// the relevant subset per character.
#[derive(Clone, Copy)]
struct Actionable {
    // ── ASCII-byte classes ──
    controls: bool,    // StripControl removes C0/DEL controls
    collapse_ws: bool, // CollapseWs trims/folds ASCII whitespace
    // ── both tiers ──
    fold_case: bool,   // FoldCase folds cased letters (ASCII A–Z and beyond)
    confusables: bool, // Confusables rewrites table sources (ASCII and non-ASCII)
    // ── non-ASCII code-point classes ──
    nfkc: bool, // Nfkc/Nfc/NfcIfNonAscii change NFKC-unstable chars (round-trips
    //                 // decomposables like Hangul/dakuten-kana/precomposed accents)
    marks: bool,         // Nfkc/Nfc/Zalgo/StripAccents touch standalone combining marks
    strip_accents: bool, // StripAccents removes the mark from precomposed accented letters
    zalgo_cap: Option<usize>, // Zalgo(cap): a char whose NFD has > cap marks is re-capped
    bidi: bool,          // StripBidi
    zero_width: bool,    // StripZeroWidth
    invisible: bool,     // StripInvisible (tags, VS, CGJ, noncharacters, PUA,
    // default-ignorable formats)
    transliterate: bool, // Transliterate / TranslitPreservingLatin — maps *any* non-ASCII
    demojize: bool,      // Demojize (emoji → CLDR names)
    /// `PrototypeFold` rewrites ASCII `I`, and `0`/`1` when the policy folds digits.
    ///
    /// It needs its own bit because nothing else covers it. `fold_case` catches the
    /// uppercase `I`, which is why `paypaI` worked — but `b0ok` has no uppercase letter,
    /// no control, and `0` is not a confusable *source*, so the guard called it inert and
    /// skipped a pipeline that would have returned `book`.
    ///
    /// Deliberately conservative: the mask is computed at compile time and the digit
    /// policy is a runtime value, so `0` and `1` count as actionable under every policy.
    /// Under `Numeric` that costs a pass on text the fold would not change, which is a
    /// wasted pass and never a wrong answer.
    prototype: bool,
}

impl Actionable {
    /// Union of the classes `steps` touch. Exhaustive match: a new `Step` will not
    /// compile until it is classified here, and the fast-path equivalence +
    /// mask-audit tests fail if it is classified wrong. Confusable steps are
    /// asserted Latin-only — the guard's confusable-source check is Latin-specific,
    /// so a non-Latin target panics here rather than silently mis-classifying.
    /// The mask for a step list, at **compile time** where the list is a const (#695).
    ///
    /// This matches every `Step` variant, which kept the payload types — and through them
    /// the CLDR emoji table — alive in any binary that called it. The preset fast-path
    /// guard calls it on every run, so `strip_format` linked 258 KB of emoji names through
    /// a function that only sets booleans. Measured on a single-export wasm probe: 275,449
    /// bytes calling this at runtime, 27,658 with the mask precomputed.
    ///
    /// `TextPipeline` still calls it at runtime and still pays, correctly.
    const fn for_steps(steps: &[Step]) -> Self {
        let mut m = Self {
            controls: false,
            collapse_ws: false,
            fold_case: false,
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
        let mut idx = 0;
        while idx < steps.len() {
            let step = steps[idx];
            idx += 1;
            match step {
                // `ResolveDeletions` shares the bit: it acts on `BS`/`DEL`, which are
                // exactly the ASCII controls `is_removed_control` already recognises, so
                // the guard cannot call a string inert that either step would change.
                Step::StripControl | Step::ResolveDeletions => m.controls = true,
                Step::CollapseWs => m.collapse_ws = true,
                Step::FoldCase => m.fold_case = true,
                Step::PrototypeFold => m.prototype = true,
                // The pre-fold is inert under the default policy, and under any other the
                // guard is bypassed entirely (`run_static`), so it contributes nothing to
                // the mask: `search_key` and `sort_key` keep the fast path they had (#951).
                Step::PolicyPreFold(_) => {}
                Step::ConfusablesCtx(target)
                | Step::ConfusablesNfcFixedPointCtx(target)
                | Step::ConfusablesMarkFixedPointCtx(target) => {
                    // The guard's confusable-source check is Latin-specific (the
                    // ASCII set is generated from confusables_to_latin.tsv and the
                    // non-ASCII check uses `resolve_confusable_map("latin")`). Other
                    // targets rewrite *different* sources — the Cyrillic map rewrites
                    // ASCII `A`/`B`/`a`/`b` — so a non-Latin target classified here
                    // would let the guard skip input the fold would change. Reject it
                    // loudly: a non-Latin confusable preset needs target-aware tables.
                    // Byte comparison rather than `==`: `str` equality is not const.
                    assert!(
                        matches!(target.as_bytes(), b"latin"),
                        // A plain message: formatting macros are not const, and the
                        // target is visible at the call site that trips this anyway.
                        "fast-path guard supports only Latin confusable targets; the \
                         Cyrillic map rewrites different sources (ASCII A/B/a/b), so a \
                         non-Latin target would let the guard skip input the fold \
                         changes — make the guard target-aware first"
                    );
                    m.confusables = true;
                    // #615/#638: `ConfusablesMarkFixedPoint` also strips cross-script
                    // marks. That touches combining marks only, never a base, and it
                    // deliberately does NOT set `strip_accents` — that flag means
                    // "every mark goes", and the rule keeps `Inherited` marks, so the
                    // fast path must not treat this preset as one that flattens `café`.
                    // `m.marks` below covers it.
                    // The confusables fold composes base+mark clusters at lookup (#475),
                    // so it acts on a decomposed homoglyph (`і`+◌̈ → folds like `ї`).
                    // Mark `m.marks` to match that behaviour (L-2): every shipped preset
                    // happens to set it via a preceding `Nfkc` step, so the guard is sound
                    // today, but a `Confusables`-only preset with no normalization step
                    // would otherwise have the guard skip a decomposed homoglyph the step
                    // would fold — a bypass. Self-consistent now, regardless of ordering.
                    m.marks = true;
                }
                Step::FixedPoint(inner) => {
                    // A fixed-point loop changes exactly what its inner steps change,
                    // so its mask is their union (#467). Recurses one level only —
                    // enforce that the inner list has no nested `FixedPoint`, keeping
                    // the `apply_into`/`apply_steps` recursion bounded (it runs in the
                    // equivalence tests over every preset, so a violation is caught).
                    // A hand-rolled loop: `Iterator::any` is not const. Same check.
                    let mut i = 0;
                    while i < inner.len() {
                        assert!(
                            !matches!(inner[i], Step::FixedPoint(_)),
                            "FixedPoint inner list must not contain a nested FixedPoint"
                        );
                        i += 1;
                    }
                    m.union(Self::for_steps(inner));
                }
                Step::Nfkc | Step::Nfc | Step::NfcIfNonAscii => {
                    m.nfkc = true;
                    m.marks = true; // normalization composes/reorders combining marks
                }
                Step::Zalgo(cap) => {
                    m.marks = true; // a run of standalone marks can exceed the cap
                    m.zalgo_cap = Some(cap);
                }
                // A standalone run of marks can repeat without any base at all, so this
                // is mark-touching for the same reason the cap is.
                Step::DropRepeatedMarks => m.marks = true,
                Step::StripAccents => {
                    m.marks = true;
                    m.strip_accents = true;
                }
                Step::StripBidi => m.bidi = true,
                Step::StripZeroWidth => m.zero_width = true,
                Step::StripInvisible(_) => m.invisible = true,
                Step::Transliterate { .. } | Step::TranslitPreservingLatin => {
                    m.transliterate = true;
                }
                Step::Demojize { .. } => m.demojize = true,
            }
        }
        m
    }

    /// OR another mask's classes into this one — used to fold a `FixedPoint`'s inner
    /// mask into the outer preset's (#467).
    const fn union(&mut self, o: Self) {
        self.controls |= o.controls;
        self.collapse_ws |= o.collapse_ws;
        self.fold_case |= o.fold_case;
        self.confusables |= o.confusables;
        self.nfkc |= o.nfkc;
        self.marks |= o.marks;
        self.strip_accents |= o.strip_accents;
        // A *smaller* cap marks more chars actionable (`nfd_mark_run_exceeds`), so the
        // conservative union is the minimum when both are `Some` — `or` alone would
        // under-approximate. (No shipped `FixedPoint` inner sets zalgo_cap, so this is
        // belt-and-suspenders, but it keeps `union` sound for any future inner list.)
        // Written out rather than via `min`/`or`, neither of which is const-stable.
        self.zalgo_cap = match (self.zalgo_cap, o.zalgo_cap) {
            (Some(a), Some(b)) => Some(if a < b { a } else { b }),
            (Some(a), None) => Some(a),
            (None, b) => b,
        };
        self.bidi |= o.bidi;
        self.zero_width |= o.zero_width;
        self.invisible |= o.invisible;
        self.transliterate |= o.transliterate;
        self.demojize |= o.demojize;
    }
}

/// ASCII fold-whitespace bytes — the subset of `whitespace::is_fold_whitespace`
/// below U+0080: TAB–CR, the information separators, and SPACE.
const fn is_ascii_fold_ws(b: u8) -> bool {
    matches!(b, 0x09..=0x0D | 0x1C..=0x1F | 0x20)
}
/// Bytes `strip_control_chars` removes: C0/DEL controls that are not whitespace.
const fn is_removed_control(b: u8) -> bool {
    (b < 0x20 && !is_ascii_fold_ws(b)) || b == 0x7F
}

/// True when NFKC changes `ch`. Unlike NFKD-stability, this is round-trip-aware:
/// Hangul syllables, dakuten kana, and precomposed accented letters decompose
/// under NFKD but **recompose** under NFKC, so they are NFKC-stable (inert for an
/// NFKC/NFC step). Allocation-free (iterator, no collect).
fn nfkc_changes(ch: char) -> bool {
    use unicode_normalization::UnicodeNormalization;
    let mut it = std::iter::once(ch).nfkc();
    !(it.next() == Some(ch) && it.next().is_none())
}

/// True when the NFD of `ch` contains a combining mark — i.e. `strip_accents`
/// (NFD → drop marks → NFC) would change it, even though NFKC round-trips it. Catches
/// precomposed accented letters (`é` → `e`) and dakuten kana. Allocation-free.
fn decomposes_to_mark(ch: char) -> bool {
    use unicode_normalization::char::is_combining_mark;
    use unicode_normalization::UnicodeNormalization;
    std::iter::once(ch).nfd().any(is_combining_mark)
}

/// True when `ch`'s NFD has more than `cap` combining marks — i.e. `strip_zalgo(cap)`
/// re-caps it (NFD → drop marks beyond `cap` → NFC). Catches precomposed code points
/// that pack many marks, e.g. polytonic Greek `ᾂ` (3 marks) under cap 2. Allocation-free.
fn nfd_mark_run_exceeds(ch: char, cap: usize) -> bool {
    use unicode_normalization::char::is_combining_mark;
    use unicode_normalization::UnicodeNormalization;
    let mut marks = 0usize;
    for c in std::iter::once(ch).nfd() {
        if is_combining_mark(c) {
            marks += 1;
            if marks > cap {
                return true;
            }
        }
    }
    false
}

/// Conservative: a char `demojize` might expand. The table lookups are exact; the
/// range predicates add a safety margin (over-marking only loses an optimization).
fn is_demojizable(ch: char) -> bool {
    crate::tables::lookup_emoji_single(ch).is_some()
        || crate::tables::is_emoji_multi_starter(ch)
        || emoji::is_emoji_codepoint(ch)
        || emoji::is_emoji_modifier(ch)
}

/// True when some step in the preset can change non-ASCII char `ch`. Each class is
/// a **conservative superset** of what the step actually touches (over-marking only
/// costs a skipped optimization; under-marking would be unsound), verified
/// exhaustively-in-distribution by the `fast_path_equivalence` proptest.
fn acts_on_nonascii(
    ch: char,
    m: Actionable,
    conf_map: Option<&'static phf::Map<char, &'static str>>,
) -> bool {
    // Transliterate can map *any* non-ASCII code point (the table covers Latin-1
    // symbols like `×`→`x` too, not just non-Latin scripts), so for a transliterating
    // preset every non-ASCII char is actionable — and it dominates the cost, so test
    // it first and short-circuit the whole scan to O(1)/char.
    if m.transliterate {
        return true;
    }
    // P-1: cheap pure-range / single-lookup classes first; the costliest predicates —
    // the single-scalar NFKC/NFD normalization *iterators* (`nfkc_changes`,
    // `decomposes_to_mark`, `nfd_mark_run_exceeds`) — run last, only when nothing
    // cheaper already marked the char. `||` is commutative for the *result*, so the
    // reordering is purely a per-char cost change; the `fast_path_equivalence`
    // proptest and the tier-3 exhaustive non-ASCII audit pin the result invariant.
    (m.marks && unicode_normalization::char::is_combining_mark(ch))
        // StripControl removes the C1 controls (U+0080–U+009F) too, not just C0.
        || (m.controls && ch.is_control() && !whitespace::is_fold_whitespace(ch))
        // CollapseWs folds non-ASCII whitespace (NEL, NBSP, the Unicode spaces) and
        // the blank-render set (U+2800, Hangul fillers) to a space.
        || (m.collapse_ws
            && (whitespace::is_fold_whitespace(ch) || whitespace::is_blank_render(ch)))
        || (m.bidi && is_bidi_or_format(ch))
        || (m.zero_width && whitespace::is_zero_width(ch))
        || (m.invisible
            && (invisibles::is_tag(ch)
                || invisibles::is_variation_selector(ch)
                || invisibles::is_noncharacter(ch)
                || invisibles::is_pua(ch)
                || invisibles::is_default_ignorable_format(ch)
                || ch == '\u{034F}')) // CGJ
        // FP-1: gate on the fold *table* (`case_folding.tsv`, the actual authority
        // `fold_case_into` consults), not std `is_alphabetic`. The table folds some
        // non-alphabetic code points (circled capitals `Ⓐ`, Roman numerals `Ⅰ`) that
        // `is_alphabetic` misses — an under-mark — and skips many alphabetics (CJK)
        // it never folds. The table match can neither under- nor over-mark relative
        // to the fold step, decoupling soundness from std's Unicode version.
        || (m.fold_case && crate::tables::case_folding_data::lookup(ch).is_some())
        || (m.confusables && conf_map.is_some_and(|map| map.contains_key(&ch)))
        || (m.demojize && is_demojizable(ch))
        // ── costliest last: single-scalar NFKC/NFD normalization iterators (P-1) ──
        // #471: the cheap conjoining-jamo range check runs first. NFKC *composes* an
        // L+V(+T) jamo sequence into one syllable — a cross-character operation; each
        // jamo is NFKC-stable in isolation, so the per-scalar `nfkc_changes` cannot
        // see it. A jamo must therefore always decline the fast path.
        || (m.nfkc && (is_conjoining_jamo(ch) || nfkc_changes(ch)))
        || (m.strip_accents && decomposes_to_mark(ch))
        || m.zalgo_cap.is_some_and(|cap| nfd_mark_run_exceeds(ch, cap))
}

/// Conjoining Hangul jamo (#471): the Hangul Jamo block (`U+1100–U+11FF`) plus Jamo
/// Extended-A (`U+A960–U+A97F`) and Extended-B (`U+D7B0–U+D7FF`). NFKC composes an
/// `L + V (+ T)` jamo *sequence* into a single precomposed syllable, but each jamo
/// is NFKC-stable alone and is not a combining mark, so the per-character guard
/// cannot detect the composition from any single code point. Marking the whole
/// blocks is a conservative superset — some archaic jamo never compose — which only
/// forgoes the fast path (over-marking is sound; under-marking would not be).
const fn is_conjoining_jamo(ch: char) -> bool {
    matches!(ch as u32, 0x1100..=0x11FF | 0xA960..=0xA97F | 0xD7B0..=0xD7FF)
}

/// Three-way verdict from the fast-path guard (#458 + #464).
enum Guard {
    /// No step can change `text`: return it borrowed, zero-alloc (#458).
    Inert,
    /// The *only* actionable class is ASCII whitespace collapse (#464): leading /
    /// trailing / run-of-spaces or a fold-control (TAB/CR/FS–US) needs folding, but
    /// nothing else does. Every other step is a no-op on this input *and* on
    /// `collapse_whitespace`'s output, so the whole pipeline collapses to that one
    /// step — run it alone instead of the full ~10× pipeline.
    WhitespaceOnly,
    /// Some non-whitespace step acts (or a non-ASCII char is actionable): the full
    /// pipeline is required.
    Actionable,
}

/// Classify `text` against the preset's step mask — the #458/#464 fast-path guard.
/// ASCII bytes are tested by byte arithmetic (controls, fold-whitespace, case, the
/// ASCII confusable set); whitespace is structural (collapse trims the ends and
/// folds runs/non-space whitespace, so a lone interior `0x20` is clean but a
/// leading/trailing/repeated one is not). Non-ASCII code points are tested by
/// `acts_on_nonascii` (Option D), so benign foreign text (CJK, Hangul, inert
/// accented Latin) skips too. `conf_map` is the resolved Latin confusable map (the
/// caller resolves it once when `mask.confusables`).
///
/// The whitespace classes are *noted* rather than terminal: any non-whitespace
/// action returns `Actionable` immediately; if only whitespace fired, the result is
/// `WhitespaceOnly`; if nothing fired, `Inert`. The `WhitespaceOnly` path is
/// restricted to ASCII-whitespace dirt — any actionable *non-ASCII* char (including
/// non-ASCII whitespace, whose fold could interact with NFKC ordering) returns
/// `Actionable` — which keeps its soundness trivial: when ASCII whitespace is the
/// only actionable class, every other step is a no-op so `collapse_whitespace(text)`
/// equals the full pipeline. The `run`-vs-`run_full` equivalence + ASCII-byte
/// mask-audit tests are the machine-checked oracle for that claim.
fn classify(
    text: &str,
    mask: Actionable,
    conf_map: Option<&'static phf::Map<char, &'static str>>,
) -> Guard {
    // Byte loop, not `char_indices`: the ASCII path (the deployment norm) stays a
    // tight per-byte scan with no UTF-8 decode; a multi-byte lead byte (≥ 0xC0) is
    // decoded once and tested by `acts_on_nonascii`, then its continuation bytes
    // are skipped via `len_utf8`.
    let bytes = text.as_bytes();
    let n = bytes.len();
    let mut prev_space = false;
    let mut saw_ws = false;
    let mut i = 0;
    while i < n {
        let b = bytes[i];
        if b < 0x80 {
            // ── Non-whitespace ASCII actions ⇒ the full pipeline is required. ──
            if mask.controls && is_removed_control(b) {
                return Guard::Actionable;
            }
            if mask.fold_case && b.is_ascii_uppercase() {
                return Guard::Actionable;
            }
            if mask.confusables && crate::tables::is_ascii_confusable_latin(b) {
                return Guard::Actionable;
            }
            // `I` is covered by `fold_case` wherever both are set; `0` and `1` are
            // covered by nothing else. See the `prototype` field.
            if mask.prototype && matches!(b, b'I' | b'0' | b'1') {
                return Guard::Actionable;
            }
            // ── ASCII whitespace `collapse_whitespace` would fold ⇒ note, keep
            //    scanning; if nothing else fires this is the #464 WhitespaceOnly case.
            if mask.collapse_ws && is_ascii_fold_ws(b) && b != b' ' {
                saw_ws = true; // TAB/CR/FS–US fold to a space
                prev_space = false;
            } else if mask.collapse_ws && b == b' ' {
                if i == 0 || i + 1 == n || prev_space {
                    saw_ws = true; // leading / trailing / run-of-spaces collapses
                }
                prev_space = true;
            } else {
                prev_space = false;
            }
            i += 1;
        } else {
            // SAFETY-free: `i` is always on a char boundary (we advance by 1 for
            // ASCII and by `len_utf8` for non-ASCII), so the slice decodes cleanly.
            let ch = text[i..].chars().next().unwrap_or('\u{FFFD}');
            if acts_on_nonascii(ch, mask, conf_map) {
                return Guard::Actionable;
            }
            prev_space = false;
            i += ch.len_utf8();
        }
    }
    if saw_ws {
        Guard::WhitespaceOnly
    } else {
        Guard::Inert
    }
}

#[cfg(test)]
thread_local! {
    /// Test hook: when set, `run` skips the #458 fast-path guard so the
    /// equivalence + mask-audit tests can compare each preset's guarded output
    /// against its un-guarded full pipeline (see `without_fastpath`).
    static FASTPATH_DISABLED: std::cell::Cell<bool> = const { std::cell::Cell::new(false) };
}

/// Execute a preset step list with a two-buffer ping-pong (the engine pattern
/// from `pipeline.rs`): O(1) live buffers regardless of step count.
///
/// #458 fast path: if no step can act on `text` (`Guard::Inert`), it is a no-op —
/// return it borrowed, with no per-stage scans/allocations. #464 fast path: if the
/// only actionable class is ASCII whitespace collapse (`Guard::WhitespaceOnly`),
/// the pipeline reduces to a single `collapse_whitespace` pass (every other step is
/// a no-op on the input and on collapse's output) — run that one step instead of
/// the ~10× full pipeline.
fn run<'a>(
    steps: &[Step],
    text: &'a str,
    ctx: &PresetCtx,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
    #[cfg(test)]
    let guard_on = !FASTPATH_DISABLED.with(std::cell::Cell::get);
    #[cfg(not(test))]
    let guard_on = true;
    if guard_on {
        let mask = Actionable::for_steps(steps);
        // Resolve the Latin confusable map once (it is `&'static`), not per char.
        let conf_map = if mask.confusables {
            crate::tables::resolve_confusable_map("latin")
        } else {
            None
        };
        match classify(text, mask, conf_map) {
            Guard::Inert => return Ok(Cow::Borrowed(text)),
            Guard::WhitespaceOnly => {
                // `WhitespaceOnly` ⇒ `Step::CollapseWs` is in `steps` (it is the only
                // class that sets the verdict), so this is byte-identical to the
                // pipeline's own collapse step run in isolation. One pass + one alloc.
                let mut out = String::new();
                whitespace::collapse_whitespace_into(text, &mut out);
                return Ok(Cow::Owned(out));
            }
            Guard::Actionable => {}
        }
    }
    Ok(Cow::Owned(apply_steps(steps, text, ctx)?))
}

/// `run`, with the application supplied by the caller instead of walked from `steps`.
///
/// The guard is identical, and takes the mask precomputed rather than deriving it — both
/// halves matter for #695. What changes is the final line: a preset passes its unrolled
/// applier, so the runtime `Step` value never reaches `apply_into` and the arms it does
/// not name stay out of the binary.
#[inline]
fn run_static<'a>(
    mask: Actionable,
    text: &'a str,
    ctx: &PresetCtx,
    apply: impl FnOnce(&str, &PresetCtx) -> Result<String, crate::ErrorRepr>,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
    #[cfg(test)]
    let guard_on = !FASTPATH_DISABLED.with(std::cell::Cell::get);
    #[cfg(not(test))]
    let guard_on = true;
    // The guard's confusable-source set is generated for the default policy, so under any
    // other policy the pre-fold can act on a row the guard cannot see (`ā` → `ã` is a
    // tr39-only row). The fast path is the default's; a policy always runs the steps (#896).
    if guard_on && ctx.digit_policy == crate::confusables::DigitPolicy::Numeric {
        let conf_map = if mask.confusables {
            crate::tables::resolve_confusable_map("latin")
        } else {
            None
        };
        match classify(text, mask, conf_map) {
            Guard::Inert => return Ok(Cow::Borrowed(text)),
            Guard::WhitespaceOnly => {
                let mut out = String::new();
                whitespace::collapse_whitespace_into(text, &mut out);
                return Ok(Cow::Owned(out));
            }
            Guard::Actionable => {}
        }
    }
    Ok(Cow::Owned(apply(text, ctx)?))
}

/// Apply a step list once via the two-buffer ping-pong, returning the owned result.
/// Shared by `run` (the top-level pass, after the fast-path guard) and
/// `Step::FixedPoint` (one pass of its inner sub-pipeline, #467).
fn apply_steps(steps: &[Step], input: &str, ctx: &PresetCtx) -> Result<String, crate::ErrorRepr> {
    let mut cur = input.to_owned();
    let mut scratch = String::new();
    for &step in steps {
        if apply_into(step, &cur, ctx, &mut scratch)? {
            std::mem::swap(&mut cur, &mut scratch);
        }
    }
    Ok(cur)
}

/// Run `f` with the #458 fast-path guard disabled (test-only): forces the full
/// pipeline so a test can compare it against the guarded path.
#[cfg(test)]
fn without_fastpath<R>(f: impl FnOnce() -> R) -> R {
    FASTPATH_DISABLED.with(|d| d.set(true));
    let r = f();
    FASTPATH_DISABLED.with(|d| d.set(false));
    r
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
    // ── UAX #9 §3.3.2 bidi formatting characters ───────
    // Defined once, in `crate::scripts::is_bidi_control`, so this set and the
    // hostname screen (#603) cannot drift apart.
    if crate::scripts::is_bidi_control(ch) {
        return true;
    }

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
    matches!(ch, '\u{206A}'..='\u{206F}' | '\u{FFF9}'..='\u{FFFB}')
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
            // 3b. Cap combining marks at 2 per base (#429), matching canonicalize_strict.
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
        },
        apply,
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
    const STEPS: &[Step; 10] = &[
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
    ];
    // #559: the `fold_case=false` variant, DERIVED from `STEPS` rather than written
    // out a second time — the two lists cannot drift, and `without_fold_case` const-
    // asserts that exactly one `FoldCase` was removed, so reordering or dropping the
    // step above fails the build instead of silently changing what the flag does.
    const STEPS_NO_FOLD: [Step; 9] = without_fold_case(STEPS);

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
        },
    )
}

/// Drop the single [`Step::FoldCase`] from a 9-step preset list, in `const` context.
///
/// Backs `ml_normalize`'s `fold_case=false` mode (#559). Deriving the shorter list from
/// the longer one — instead of maintaining two literals — means an edit to the pipeline
/// automatically reaches both, and the assertion below turns "someone removed or
/// duplicated `FoldCase`" into a build failure rather than a behaviour change nobody
/// notices. `Step::Nfkc` is only the array's initial filler; every slot is overwritten.
const fn without_fold_case(steps: &[Step; 10]) -> [Step; 9] {
    let mut out = [Step::Nfkc; 9];
    let mut read = 0;
    let mut write = 0;
    while read < steps.len() {
        if !matches!(steps[read], Step::FoldCase) {
            // Check before the write, not after the loop: with zero `FoldCase` steps
            // the 10th write would hit `out[9]` and abort const-eval with a generic
            // out-of-bounds panic, hiding the reason. Assert here so the message the
            // maintainer sees names the actual invariant.
            assert!(
                write < 9,
                "ml_normalize's step list must contain exactly one Step::FoldCase"
            );
            out[write] = steps[read];
            write += 1;
        }
        read += 1;
    }
    assert!(
        write == 9,
        "ml_normalize's step list must contain exactly one Step::FoldCase"
    );
    out
}

/// Library catalog key generation pipeline.
///
/// Pipeline: NFKC → strip_bidi → strip invisibles → fold_case → transliterate →
/// confusables → strip_accents → fold_case → collapse_whitespace
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
        },
        apply,
    )
}

/// Search index key generation pipeline.
///
/// Pipeline: NFKC → strip_bidi → strip invisibles → fold_case → transliterate →
/// strip_accents → fold_case → collapse_whitespace
///
/// Produces a case-insensitive, accent-insensitive, script-insensitive lookup
/// key.  Like `catalog_key` but without confusable normalization — lighter and
/// faster for search indexes where homoglyph attacks are not a concern.
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
        ]
    }
    crate::transliterate::validate_lang(lang)?;
    run_static(
        MASK,
        text,
        &PresetCtx {
            lang,
            strict_iso9: false,
            emoji_cldr: false,
            digit_policy,
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
fn transliterate_preserving_latin_into(text: &str, lang: Option<&str>, out: &mut String) {
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
        if ch.is_ascii()
            || matches!(
                crate::scripts::detect_char_script(ch),
                "Latin" | "Common" | "Inherited"
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
/// Pipeline: NFKC → strip_bidi → strip invisibles → fold_case → transliterate-non-Latin → fold_case
/// → collapse_whitespace → NFC (if non-ASCII)
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
/// the raw text is the whole reach, as it was for the pre-pass.
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
    run_static(
        MASK,
        text,
        &PresetCtx {
            lang,
            strict_iso9: false,
            emoji_cldr: false,
            digit_policy,
        },
        apply,
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
/// - **strip_zalgo**: caps combining marks at `DEFAULT_MAX_MARKS` (3) per base
///   character — the same figure `is_zalgo` flags above, so this preset never strips
///   from text the library calls ordinary (#788) — preventing
///   stacked diacritical abuse while preserving legitimate diacritics (é, ñ, ệ)
/// - **confusables**: neutralizes cross-script homoglyph attacks
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
        },
        apply,
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
/// reaches its confusable step at step 6, and the order cannot be swapped: `presets.rs`
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
            // 1. NFKC, so a compatibility spelling reaches the fold as its base form.
            Step::Nfkc,
            // 2. The reordering and smuggling channels, before anything reads the text.
            //    A key exists so two spellings of one identity compare equal, and every
            //    class here is a way to vary the key invisibly (#805).
            Step::StripBidi,
            Step::StripInvisible(COMPARISON_STRIP),
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
            Step::FixedPoint(&[Step::FoldCase, Step::ConfusablesCtx("latin")]),
            // 6. Controls, zero-width, whitespace (#433).
            Step::StripControl,
            Step::StripZeroWidth,
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
        },
        apply,
    )
}

/// Layer-1 core for `is_canonical` (#730) — the verification-path predicate.
///
/// Every other preset here is generation path: text in, normalized text out. This answers
/// the question a caller has about bytes that arrived already bound, where recomputing the
/// canonical form silently defends the comparison and leaves the stored value alone.
///
/// It is not [`crate::anomalies::has_anomalies`]. Over every assigned code point, 142,760
/// of them (5,292 outside the Private Use Area) are clean to the detector and are not
/// their own canonical form; none go the other way. CJK compatibility ideographs, Arabic
/// presentation forms and fullwidth Latin are in that set, and they belong there — `ＮＨＫ`
/// is ordinary Japanese text, so teaching the detector to fire on it would undo #633.
///
/// Defined as `preset(text) == text`, but it avoids materialising the normalized copy
/// whenever the pipeline's `Guard::Inert` classification hands back a borrow.
///
/// `preset` accepts the eight preset names, the three deprecated 0.11 aliases that
/// `PRESETS` still documents, and any policy-profile name.
pub(crate) fn is_canonical(text: &str, preset: &str) -> Result<bool, crate::ErrorRepr> {
    // A borrowed `Cow` proves no step touched the input. An owned one only proves a buffer
    // was allocated — several steps build one and write the input back unchanged — so it
    // still has to be compared.
    fn settled(out: Cow<'_, str>, text: &str) -> bool {
        match out {
            Cow::Borrowed(_) => true,
            Cow::Owned(s) => s == text,
        }
    }
    let out = match preset {
        // The second name in each of the first three arms is a 0.11 rename that `PRESETS`
        // still documents as a valid key, so the string dispatch has to accept it or the
        // registry claim is false. No deprecation warning fires here: the deprecation is
        // on the *function*, and this is a lookup key.
        "canonicalize" | "security_clean" => canonicalize(text)?,
        "canonicalize_strict" | "normalize_user_input" => canonicalize_strict(text)?,
        "strip_format" | "display_clean" => strip_format(text),
        "strip_obfuscation" => strip_obfuscation(text)?,
        "search_key" => search_key(text, None)?,
        "catalog_key" => catalog_key(text, None, false)?,
        "sort_key" => sort_key(text, None)?,
        "ml_normalize" => ml_normalize(text, None, "cldr", true)?,
        // Profiles are the other half of the registry. A pipeline returns an owned String,
        // so the borrow fast path is unavailable, but the comparison is still the answer.
        other => match crate::pipeline::get_pipeline(other)? {
            Some(p) => return Ok(p.process(text)? == text),
            None => {
                return Err(crate::ErrorRepr::UnknownProfile {
                    got: other.to_owned(),
                    available: crate::pipeline::profile_names().join(", "),
                })
            }
        },
    };
    Ok(settled(out, text))
}

#[cfg(test)]
mod is_canonical_tests {
    use super::*;

    /// The predicate is defined as `preset(text) == text` and must not drift from it.
    #[test]
    fn agrees_with_the_expression_it_replaces() {
        for text in [
            "abc",
            "",
            "paypal.com",
            "\u{FF21}\u{FF22}\u{FF23}", // ＡＢＣ
            "\u{216B}",                 // Ⅻ
            "a\"b",
            "caf\u{E9}",
            "e\u{301}", // decomposed — NFC changes it
        ] {
            let expected = canonicalize(text).unwrap() == text;
            assert_eq!(
                is_canonical(text, "canonicalize").unwrap(),
                expected,
                "{text:?}"
            );
        }
    }

    /// #730's premise: the detector stays silent on text that is not canonical. If this
    /// ever starts failing, `has_anomalies` has become a canonicity predicate and
    /// `is_canonical` is redundant — that is a decision, not a passing test.
    #[test]
    fn the_detector_is_silent_on_the_gap() {
        for text in ["\u{FF21}\u{FF22}\u{FF23}", "\u{FF4E}\u{FF48}\u{FF4B}"] {
            assert!(!crate::anomalies::has_anomalies(
                text,
                &std::collections::HashSet::new()
            ));
            assert!(!is_canonical(text, "canonicalize").unwrap());
        }
    }

    #[test]
    fn every_preset_name_dispatches() {
        // Plain ASCII is a fixed point of all eight.
        for preset in [
            "canonicalize",
            "canonicalize_strict",
            "strip_obfuscation",
            "strip_format",
            "search_key",
            "catalog_key",
            "sort_key",
            "ml_normalize",
        ] {
            assert!(
                is_canonical("abc", preset).unwrap(),
                "{preset} on plain ASCII"
            );
        }
        // Fullwidth separates them, which is the point of taking a preset argument at
        // all: `strip_format` has no NFKC step, so ＡＢＣ *is* its own canonical form
        // there while the other seven fold it to ABC.
        let fullwidth = "\u{FF21}\u{FF22}\u{FF23}";
        assert!(is_canonical(fullwidth, "strip_format").unwrap());
        for preset in [
            "canonicalize",
            "canonicalize_strict",
            "strip_obfuscation",
            "search_key",
            "catalog_key",
            "sort_key",
            "ml_normalize",
        ] {
            assert!(
                !is_canonical(fullwidth, preset).unwrap(),
                "{preset} on fullwidth"
            );
        }
    }

    /// `PRESETS` documents the 0.11 aliases as valid keys, so the string dispatch must
    /// accept them. Before this test they fell through to the profile lookup and came
    /// back as `UnknownProfile`, which made the registry claim in the docs false.
    #[test]
    fn the_deprecated_aliases_still_resolve() {
        let fullwidth = "\u{FF21}\u{FF22}\u{FF23}";
        for (alias, target) in [
            ("security_clean", "canonicalize"),
            ("display_clean", "strip_format"),
            ("normalize_user_input", "canonicalize_strict"),
        ] {
            for text in ["abc", fullwidth, "caf\u{E9}"] {
                assert_eq!(
                    is_canonical(text, alias).unwrap(),
                    is_canonical(text, target).unwrap(),
                    "{alias} disagrees with {target} on {text:?}"
                );
            }
        }
    }

    #[test]
    fn a_profile_name_dispatches_too() {
        for profile in crate::pipeline::profile_names() {
            let pipeline = crate::pipeline::get_pipeline(&profile).unwrap().unwrap();
            let expected =
                pipeline.process("\u{FF21}\u{FF22}\u{FF23}").unwrap() == "\u{FF21}\u{FF22}\u{FF23}";
            assert_eq!(
                is_canonical("\u{FF21}\u{FF22}\u{FF23}", &profile).unwrap(),
                expected,
                "{profile}"
            );
        }
    }

    #[test]
    fn an_unknown_name_is_an_error() {
        let err = is_canonical("abc", "not_a_preset").unwrap_err();
        assert!(format!("{err}").contains("not_a_preset"), "{err}");
    }

    /// The `Guard::Inert` fast path returns a borrow; the predicate must read that as
    /// "unchanged" rather than falling through to a comparison that was never needed.
    #[test]
    fn the_inert_fast_path_answers_true() {
        assert!(matches!(canonicalize("abc").unwrap(), Cow::Borrowed(_)));
        assert!(is_canonical("abc", "canonicalize").unwrap());
    }
}

#[cfg(test)]
mod tests {
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
        let src = include_str!("presets.rs");
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
            let script = crate::scripts::detect_char_script(b as char);
            assert!(
                matches!(script, "Latin" | "Common" | "Inherited"),
                "ASCII U+{b:02X} has script {script:?} — the P-3 ASCII fast path would mis-handle it"
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
        let src = include_str!("presets.rs");
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
        // `const STEPS: &[Step; 9]` because it selects between two lists at runtime — and
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
                // Only an array *literal*. `const STEPS_NO_FOLD: [Step; 8] =
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
        let names: Vec<&str> = step_arrays(include_str!("presets.rs"))
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
        const FULL: &[Step; 10] = &[
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
            let vowel =
                prop::option::of((0x1161u32..=0x1175).prop_map(|c| char::from_u32(c).unwrap()));
            let trail =
                prop::option::of((0x11A8u32..=0x11C2).prop_map(|c| char::from_u32(c).unwrap()));
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
}
