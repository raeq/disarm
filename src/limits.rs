//! Centralized resource-limit constants (#256).
//!
//! Every bound that protects the library against unbounded memory or CPU growth
//! from untrusted callers lives here, giving an operator a single surface to
//! audit and tune the library's resource posture. Each constant is referenced
//! from its consuming module rather than redefined there.
//!
//! The one cross-language limit, [`crate::MAX_BATCH_SIZE`] (re-exported to
//! Python as `_MAX_BATCH_SIZE`, #200), stays in `lib.rs` because it must be
//! kept consistent with the binding. The lone Python-only limit,
//! `_MAX_GRAPHEME_SPLIT_INPUT` (`python/disarm/_api.py`), has no Rust
//! counterpart by design (it bounds a binding-side grapheme split) and is
//! tracked there.

/// Maximum number of entries allowed in `GLOBAL_REPLACEMENTS`.
///
/// Prevents unbounded memory growth from untrusted callers supplying very
/// large replacement tables.
pub const MAX_REPLACEMENTS: usize = 10_000;

/// Maximum number of user-registered language profiles.
///
/// Prevents unbounded memory growth from untrusted callers repeatedly
/// registering new language codes.  Re-registering an existing code
/// (overwrite) does not count toward this limit.
pub const MAX_REGISTERED_LANGS: usize = 100;

/// Maximum iterations for unique slug generation before giving up.
/// Prevents infinite loops when all candidates are rejected.
pub const MAX_UNIQUE_ATTEMPTS: u64 = 10_000;

/// Maximum byte length of a caller-supplied regex pattern.
/// Prevents adversarial patterns from consuming excessive compile time or
/// memory. The regex crate guards against catastrophic backtracking at
/// match time, but compilation of an enormous pattern is also bounded here.
pub const MAX_REGEX_PATTERN_BYTES: usize = 512;

/// Maximum compiled DFA size for caller-supplied regex patterns, in bytes.
///
/// The `regex` crate uses finite automata (no catastrophic backtracking at
/// match time), but compiling a large pattern can consume substantial memory
/// and CPU.  This cap bounds both compile-time allocation and CPU for
/// adversarial patterns that would otherwise produce a very large DFA.
pub const MAX_REGEX_DFA_BYTES: usize = 1_048_576; // 1 MiB

/// Maximum output size, in bytes, of the global replacement pre-pass.
///
/// disarm does not cap raw input size — bounding untrusted input is the
/// caller's responsibility (all operations are linear time/memory; see #80).
/// This bound is one of two exceptions (#256, #768): registered replacement *values* are
/// caller-supplied and unbounded, so a tiny input can expand to an enormous
/// string via a separately-registered value (an amplification a caller's own
/// input-size check cannot foresee). The pre-pass output is therefore capped.
/// The other is [`MAX_NORMALIZE_OUTPUT_BYTES`], below: NFKC amplifies by up to 18× and
/// the same argument applies to it.
pub const MAX_REPLACEMENT_OUTPUT_BYTES: usize = 10 * 1024 * 1024; // 10 MiB

/// Output ceiling on the normalization pre-pass inside a preset (#768).
///
/// The comment above gives the reason for the replacement cap as *an amplification a
/// caller's own input-size check cannot foresee*. That is true of NFKC as well, and NFKC
/// was not capped. `U+FDFA` ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM expands to 18
/// characters, and a caller who bounds input at 6 MB — the mitigation the comment assigns
/// them — got 60 MB out of `canonicalize`, measured.
///
/// Applies to the **preset** path only. `normalize(text, form="NFKC")` is a caller naming
/// the operation whose expansion this is, and bounding a function against the thing it was
/// asked to do would be a different decision; the presets never mention normalization in
/// their names.
///
/// One shared ceiling rather than a tighter one for the key builders (#768 §2). A second
/// limit is a second thing to document, discover and get wrong, and the argument for it —
/// that a 3.6 MB search key is already meaningless — is an argument about the caller's
/// data, not about a bound disarm can defend.
pub const MAX_NORMALIZE_OUTPUT_BYTES: usize = MAX_REPLACEMENT_OUTPUT_BYTES;

/// Upper bound on the transliteration output-capacity hint.
///
/// The estimator samples the first few non-ASCII codepoints and picks the
/// largest expansion multiplier seen (CJK ideographs expand ~3–5× into pinyin/
/// romaji). The result is capped here: the previous 256 MiB cap was 32× too
/// large (#111). Any output exceeding 8 MiB reallocates at most once, while the
/// old value reserved 256 MiB of virtual memory per call on large CJK input.
pub const MAX_CAPACITY_HINT: usize = 8 * 1024 * 1024; // 8 MiB (#111)

/// Maximum number of leading characters scanned by script discriminators.
///
/// If a discriminator character exists in the text it will almost certainly
/// appear in the opening portion; scanning further is pure overhead for long
/// documents.
pub const SCAN_LIMIT: usize = 2_000;

/// Capacity-hint clamp for `ContextDict::from_bytes` (#116).
///
/// A corrupt header count must not drive a huge `HashMap` pre-allocation.
/// Using `data.len()` as the cap over-reserved buckets; 1,000,000 is a generous
/// upper bound for any real dictionary while still bounding a bogus count (e.g.
/// `u32::MAX`).
pub const MAX_DICT_ENTRIES: usize = 1_000_000;
