//! The preset vocabulary: [`Step`], its runtime context [`PresetCtx`], the
//! `static_steps!` macro that unrolls a list, and [`apply_into`], which applies one step.

use std::borrow::Cow;

use super::bidi::strip_bidi_into;
use super::keys::transliterate_preserving_latin_into;
use super::runner::apply_steps;
use super::CONFUSABLE_FIXED_POINT_ITERS;
use crate::{case_fold, confusables, emoji, invisibles, transliterate, whitespace, zalgo};

// ---------------------------------------------------------------------------
// Shared ping-pong runner for the preset step lists (#453)
// ---------------------------------------------------------------------------

/// Runtime parameters for steps whose behaviour depends on call-site args.
/// Compile-time params (zalgo cap, strip policy, confusable target) ride in the
/// `Step` enum payload so step arrays stay `const`.
pub(super) struct PresetCtx<'a> {
    pub(super) lang: Option<&'a str>,
    pub(super) strict_iso9: bool,
    pub(super) emoji_cldr: bool,
    /// The digit policy for the ctx-reading confusable steps (#650).
    ///
    /// `Step::Confusables` and friends carry their policy as const data, which is right
    /// for the eight presets that pick one and keep it. `skeleton_key` takes it from the
    /// caller, and threading a runtime value through a `static_steps!` const would mean
    /// three copies of the list — the tripling #646 §2 warned about. Carrying it here
    /// instead keeps one list per preset and leaves the monomorphisation of #695/#868
    /// alone. Every other preset sets `Numeric`, which is what they did implicitly.
    pub(super) digit_policy: crate::confusables::DigitPolicy,
    /// The byte length of the text the preset was called with: the base the output ceiling
    /// measures growth from ([`check_growth`](super::runner::check_growth)).
    ///
    /// On the context rather than read from each step's input, because a step inside a
    /// `FixedPoint`, and every pass of the policy iteration, sees an intermediate string
    /// that has already grown. Measuring from there would let each pass grow by the full
    /// allowance again.
    pub(super) input_len: usize,
}

/// One preset stage. A preset is a `const &[Step]`; ordering, subsetting, and
/// repeats are expressed by the array. Mirrors `pipeline.rs` apply_step_into,
/// extended with the four non-uniform preset stages.
#[derive(Clone, Copy)]
pub(super) enum Step {
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
    /// [`Step::Zalgo`] that leaves text it would not cut as it is, rather than
    /// normalizing it to NFC. For a second cap after a step that can add a mark to a
    /// stack, where text with no stack over the cap should come out unchanged: nearly
    /// every call is then one scan.
    ZalgoIfOver(usize),
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
                    check_growth(&cur, ctx)?;
                }
            )*
            Ok(cur)
        }
    };
}

pub(super) use static_steps;

/// One confusables→NFC fixed point, the body of [`Step::ConfusablesNfcFixedPointCtx`].
///
/// A free function rather than an arm, so the step arm can call it without `apply_into`
/// calling itself (#974). Self-recursion is what LLVM will not `alwaysinline`: the
/// attribute is dropped, the match stops folding to one arm at each call site, and every
/// preset links every table again — 662,087 bytes for `strip_format` against 27,490.
///
/// The loop lives here once, which was the point of the arm that used to re-enter the
/// dispatch to resolve the policy. It reaches the same place without the recursion.
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
pub(super) fn apply_into(
    step: Step,
    input: &str,
    ctx: &PresetCtx,
    out: &mut String,
) -> Result<bool, crate::ErrorRepr> {
    match step {
        // #768's ceiling used to sit here, on NFKC alone. It is on the runners now, after
        // every step, because NFKC is not the only step that grows the text: see
        // `check_growth`.
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
        Step::ZalgoIfOver(cap) => {
            if !zalgo::exceeds_combining_run(input, cap) {
                return Ok(false);
            }
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
        // Both take their policy from the ctx and hand off to a free function (#974).
        // Re-entering `apply_into` with a policy-carrying variant would read as the same
        // thing and is not: it makes the dispatch recursive, which costs the inlining
        // that #695 rests on. The variant is const at every call site, so the match still
        // folds to one arm.
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
