//! The presets and key builders: fixed step lists over the text primitives.
//!
//! A preset is a `const` list of [`steps::Step`]s, run by the two-buffer ping-pong in
//! [`runner`] behind the fast-path guard in [`guard`], which returns inert input
//! borrowed. The lists themselves are in [`text`] (text out) and [`keys`] (a key out),
//! and [`verify`] answers whether a string is already a preset's fixed point.

use crate::invisibles;

mod bidi;
mod guard;
mod keys;
mod runner;
mod steps;
mod text;
mod verify;

pub(crate) use bidi::{strip_bidi, strip_bidi_into};
pub(crate) use keys::{
    catalog_key, catalog_key_with, search_key, search_key_with, skeleton_key, sort_key,
    sort_key_with,
};
pub(crate) use text::{
    canonicalize, canonicalize_strict, canonicalize_strict_with, canonicalize_with, ml_normalize,
    strip_format, strip_obfuscation, strip_obfuscation_with,
};
pub(crate) use verify::is_canonical;

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
/// preset is non-idempotent). Most input converges in a couple of iterations,
/// each folding pass removing at least one mark. A fold cycle removes only one a
/// pass (`C` + U+0327 NFCs to `Ç`, which folds to `C`), so a loop that reaches
/// this bound unsettled hands its text to `confusables::converge_slow`, which
/// finishes it without one pass per mark.
pub(crate) const CONFUSABLE_FIXED_POINT_ITERS: usize = 8;

// disarm does not cap input size in the pipeline presets — bounding untrusted
// input is the caller's responsibility (every stage is linear time/memory;
// see #80). The only retained size guard is the register_replacements output
// amplification bound (`MAX_REPLACEMENT_OUTPUT_BYTES` in src/limits.rs, #256),
// enforced in `tables::apply_replacements`.

#[cfg(test)]
mod tests;

/// Regression tests for the findings of the Lean model of the presets, `formal/lean/Presets`.
///
/// Each finding is a string that a preset maps to something it would map again. The
/// witnesses are the model's own; the sweeps are small enough for every run.
#[cfg(test)]
mod presets_formal_findings;
