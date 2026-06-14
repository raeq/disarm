//! Layer 3b: the PyO3 binding shims for `disarm._disarm`.
//!
//! Each shim is a thin wrapper over a Layer-1 algorithm fn (or a Layer-2
//! [`crate::api`] fn), exposing the underscore-prefixed names the extension
//! module registers. Keeping the shims here — out of the algorithm modules — is
//! what lets the pure core compile without pyo3 once the extraction completes;
//! at that point this whole module is gated behind `feature = "extension-module"`
//! and the `pyo3` dependency becomes optional (the final extraction sub-PR).

pub mod case_fold;
pub mod confusables;
pub mod encoders;
pub mod filename;
pub mod grapheme;
pub mod normalize;
pub mod reverse;
pub mod scripts;
pub mod whitespace;
pub mod width;
pub mod zalgo;
