//! The runners: a step list applied through the fast-path guard, once or to a fixed
//! point, with the output ceiling checked after every step.

use std::borrow::Cow;

use super::guard::{classify, Actionable, Guard};
use super::steps::{apply_into, PresetCtx, Step};
use super::CONFUSABLE_FIXED_POINT_ITERS;
use crate::whitespace;

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
pub(super) fn run<'a>(
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
pub(super) fn run_static<'a>(
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

/// [`run_static`], iterated to a fixed point under any digit policy but the default.
///
/// For the two key builders with no confusable fold of their own, `search_key` and
/// `sort_key`. Under `Tr39` or `Preserve` their only fold is [`Step::PolicyPreFold`], on
/// the raw text, and three later steps make new sources it never saw: `FoldCase` turns a
/// capital with no row into a lowercase letter that has one (`U+A760` to `U+A761`, which
/// folds to `w`; under `tr39`, `U+0100` to `U+0101`, which folds to `U+00E3`), and
/// `Transliterate` emits `|`, `"` and `` ` ``, which are sources too (`U+01C1` to `||`,
/// then `ll`). So the key was not a fixed point: `search_key("\u{A760}", tr39)` was
/// `\u{A761}`, and the key of that was `w`. Finding 2 of the Lean model in
/// `formal/lean/Presets`.
///
/// Moving the fold would not do: it runs on the raw text so that it reads a non-Latin
/// digit before transliteration consumes it (#896). Iterating the whole builder closes
/// every one of those routes at once, bounded like `Step::FixedPoint`.
///
/// Under `Numeric` the pre-fold is a no-op and the builders were already fixed points, so
/// this returns [`run_static`]'s answer untouched and the default key cannot move.
pub(super) fn run_static_policy_fixed<'a>(
    mask: Actionable,
    text: &'a str,
    ctx: &PresetCtx,
    apply: impl Fn(&str, &PresetCtx) -> Result<String, crate::ErrorRepr>,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
    let first = run_static(mask, text, ctx, &apply)?;
    if ctx.digit_policy == crate::confusables::DigitPolicy::Numeric {
        return Ok(first);
    }
    let mut cur = first.into_owned();
    for _ in 0..CONFUSABLE_FIXED_POINT_ITERS {
        let next = apply(&cur, ctx)?;
        if next == cur {
            break;
        }
        cur = next;
    }
    Ok(Cow::Owned(cur))
}

/// Apply a step list once via the two-buffer ping-pong, returning the owned result.
/// Shared by `run` (the top-level pass, after the fast-path guard) and
/// `Step::FixedPoint` (one pass of its inner sub-pipeline, #467).
pub(super) fn apply_steps(
    steps: &[Step],
    input: &str,
    ctx: &PresetCtx,
) -> Result<String, crate::ErrorRepr> {
    let mut cur = input.to_owned();
    let mut scratch = String::new();
    for &step in steps {
        if apply_into(step, &cur, ctx, &mut scratch)? {
            std::mem::swap(&mut cur, &mut scratch);
            check_growth(&cur, ctx)?;
        }
    }
    Ok(cur)
}

/// The preset output ceiling (#768): no step may leave the text more than
/// [`MAX_NORMALIZE_OUTPUT_BYTES`](crate::limits::MAX_NORMALIZE_OUTPUT_BYTES) longer than the
/// input the preset was called with.
///
/// Checked after every step that wrote, by both runners, so the one rule holds whichever
/// step does the growing. It used to be an absolute size test on the `Nfkc` arm alone,
/// and that was wrong twice over (Finding 6 of the Lean model in `formal/lean/Presets`):
///
/// * NFKC is not the only amplifier. `ml_normalize`'s `Demojize` runs after it and names
///   U+1FAF0 in 40 bytes, so 10.4 MB of it became 106.6 MB with no error.
/// * An absolute size is a cap on *input*, which `limits.rs` says disarm does not impose.
///   11 MiB of `a` was accepted, and the same text with one `"` in front was rejected as
///   having "expanded", because the quote made the fast path decline and NFKC then saw
///   11 MiB.
///
/// Growth is what an input-size check cannot foresee, which is the reason the ceiling
/// exists; so growth is what it bounds.
#[inline]
pub(super) fn check_growth(out: &str, ctx: &PresetCtx) -> Result<(), crate::ErrorRepr> {
    if out.len().saturating_sub(ctx.input_len) > crate::limits::MAX_NORMALIZE_OUTPUT_BYTES {
        return Err(crate::ErrorRepr::NormalizeOutputTooLarge {
            input: ctx.input_len,
            size: out.len(),
            max: crate::limits::MAX_NORMALIZE_OUTPUT_BYTES,
        });
    }
    Ok(())
}

/// Run `f` with the #458 fast-path guard disabled (test-only): forces the full
/// pipeline so a test can compare it against the guarded path.
#[cfg(test)]
pub(super) fn without_fastpath<R>(f: impl FnOnce() -> R) -> R {
    FASTPATH_DISABLED.with(|d| d.set(true));
    let r = f();
    FASTPATH_DISABLED.with(|d| d.set(false));
    r
}
