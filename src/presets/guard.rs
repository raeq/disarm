//! The #458/#464 fast-path guard: which code points a preset's steps can change, and
//! whether a given text contains any.

use super::bidi::is_bidi_or_format;
use super::steps::Step;
use crate::{emoji, invisibles, whitespace};

/// Which codepoint classes a preset's steps can change (#458 fast-path guard).
/// Some classes act only on ASCII bytes (`controls`, `collapse_ws`), some only on
/// non-ASCII code points (`norm`/`bidi`/`zero_width`/`invisible`/`transliterate`/
/// `demojize`), and `fold_case`/`confusables` span both tiers. `classify` applies
/// the relevant subset per character.
#[derive(Clone, Copy)]
pub(super) struct Actionable {
    // ── ASCII-byte classes ──
    pub(super) controls: bool,    // StripControl removes C0/DEL controls
    pub(super) collapse_ws: bool, // CollapseWs trims/folds ASCII whitespace
    // ── both tiers ──
    pub(super) fold_case: bool, // FoldCase folds cased letters (ASCII A–Z and beyond)
    pub(super) confusables: bool, // Confusables rewrites table sources (ASCII and non-ASCII)
    // ── non-ASCII code-point classes ──
    pub(super) nfkc: bool, // Nfkc/Nfc/NfcIfNonAscii change NFKC-unstable chars (round-trips
    //                 // decomposables like Hangul/dakuten-kana/precomposed accents)
    pub(super) marks: bool, // Nfkc/Nfc/Zalgo/StripAccents touch standalone combining marks
    pub(super) strip_accents: bool, // StripAccents removes the mark from precomposed accented letters
    pub(super) zalgo_cap: Option<usize>, // Zalgo(cap): a char whose NFD has > cap marks is re-capped
    pub(super) bidi: bool,               // StripBidi
    pub(super) zero_width: bool,         // StripZeroWidth
    pub(super) invisible: bool,          // StripInvisible (tags, VS, CGJ, noncharacters, PUA,
    // default-ignorable formats)
    pub(super) transliterate: bool, // Transliterate / TranslitPreservingLatin — maps *any* non-ASCII
    pub(super) demojize: bool,      // Demojize (emoji → CLDR names)
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
    pub(super) prototype: bool,
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
    pub(super) const fn for_steps(steps: &[Step]) -> Self {
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
pub(super) fn is_demojizable(ch: char) -> bool {
    crate::tables::lookup_emoji_single(ch).is_some()
        || crate::tables::is_emoji_multi_starter(ch)
        || emoji::is_emoji_codepoint(ch)
        || emoji::is_emoji_modifier(ch)
}

/// True when some step in the preset can change non-ASCII char `ch`. Each class is
/// a **conservative superset** of what the step actually touches (over-marking only
/// costs a skipped optimization; under-marking would be unsound), verified
/// exhaustively-in-distribution by the `fast_path_equivalence` proptest.
pub(super) fn acts_on_nonascii(
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
        // see it. A jamo must therefore always decline the fast path. The same holds
        // for the one other starter that composes with the character before it,
        // U+16D67 (Kirat Rai, Unicode 16): U+16D67 U+16D67 is the NFD of U+16D68, and
        // the default policy returned it unnormalized while `tr39`, which bypasses
        // this guard, composed it (F3, found by the Lean model in
        // `formal/lean/Confusables`).
        || (m.nfkc
            && (is_conjoining_jamo(ch)
                || crate::compose::composes_with_preceding_starter(ch)
                || nfkc_changes(ch)))
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
pub(super) enum Guard {
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
pub(super) fn classify(
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
