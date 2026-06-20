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
            transliterate_preserving_latin_into(input, ctx.lang, out);
            Ok(true)
        }
        Step::Confusables(target) => {
            confusables::normalize_confusables_into(input, target, out)?;
            Ok(true)
        }
        Step::ConfusablesNfcFixedPoint(target) => {
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
                confusables::normalize_confusables_into(&cur, target, &mut conf)?;
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
        Step::Demojize { only_if_cldr } => {
            if only_if_cldr && !ctx.emoji_cldr {
                return Ok(false);
            }
            emoji::demojize_rust_into(input, false, out);
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
    invisible: bool,     // StripInvisible (tags, VS, CGJ, noncharacters, PUA)
    transliterate: bool, // Transliterate / TranslitPreservingLatin — maps *any* non-ASCII
    demojize: bool,      // Demojize (emoji → CLDR names)
}

impl Actionable {
    /// Union of the classes `steps` touch. Exhaustive match: a new `Step` will not
    /// compile until it is classified here, and the fast-path equivalence +
    /// mask-audit tests fail if it is classified wrong. Confusable steps are
    /// asserted Latin-only — the guard's confusable-source check is Latin-specific,
    /// so a non-Latin target panics here rather than silently mis-classifying.
    fn for_steps(steps: &[Step]) -> Self {
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
        };
        for &step in steps {
            match step {
                Step::StripControl => m.controls = true,
                Step::CollapseWs => m.collapse_ws = true,
                Step::FoldCase => m.fold_case = true,
                Step::Confusables(target) | Step::ConfusablesNfcFixedPoint(target) => {
                    // The guard's confusable-source check is Latin-specific (the
                    // ASCII set is generated from confusables_to_latin.tsv and the
                    // non-ASCII check uses `resolve_confusable_map("latin")`). Other
                    // targets rewrite *different* sources — the Cyrillic map rewrites
                    // ASCII `A`/`B`/`a`/`b` — so a non-Latin target classified here
                    // would let the guard skip input the fold would change. Reject it
                    // loudly: a non-Latin confusable preset needs target-aware tables.
                    assert!(
                        target == "latin",
                        "fast-path guard supports only Latin confusable targets; \
                         {target:?} rewrites different sources — make the guard \
                         target-aware first"
                    );
                    m.confusables = true;
                }
                Step::FixedPoint(inner) => {
                    // A fixed-point loop changes exactly what its inner steps change,
                    // so its mask is their union (#467). Recurses one level; the inner
                    // list is asserted not to contain another `FixedPoint`.
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
    fn union(&mut self, o: Self) {
        self.controls |= o.controls;
        self.collapse_ws |= o.collapse_ws;
        self.fold_case |= o.fold_case;
        self.confusables |= o.confusables;
        self.nfkc |= o.nfkc;
        self.marks |= o.marks;
        self.strip_accents |= o.strip_accents;
        self.zalgo_cap = self.zalgo_cap.or(o.zalgo_cap);
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
        || (m.nfkc && nfkc_changes(ch))
        || (m.strip_accents && decomposes_to_mark(ch))
        || m.zalgo_cap.is_some_and(|cap| nfd_mark_run_exceeds(ch, cap))
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
pub(crate) fn canonicalize(text: &str) -> Result<Cow<'_, str>, crate::ErrorRepr> {
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
pub(crate) fn ml_normalize<'a>(
    text: &'a str,
    lang: Option<&str>,
    emoji_style: &str,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
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
pub(crate) fn catalog_key<'a>(
    text: &'a str,
    lang: Option<&str>,
    strict_iso9: bool,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
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
            Step::Confusables("latin"),
            Step::StripAccents,
        ]),
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
pub(crate) fn search_key<'a>(
    text: &'a str,
    lang: Option<&str>,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
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
/// Pipeline: NFKC → strip_bidi → fold_case → transliterate-non-Latin → fold_case
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
pub(crate) fn sort_key<'a>(
    text: &'a str,
    lang: Option<&str>,
) -> Result<Cow<'a, str>, crate::ErrorRepr> {
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
pub(crate) fn strip_format(text: &str) -> Cow<'_, str> {
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
pub(crate) fn canonicalize_strict(text: &str) -> Result<Cow<'_, str>, crate::ErrorRepr> {
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
pub(crate) fn strip_obfuscation(text: &str) -> Result<Cow<'_, str>, crate::ErrorRepr> {
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
                Box::new(|s| ml_normalize(s, None, "cldr").unwrap().into_owned()),
            ),
            (
                "ml_normalize_none",
                Box::new(|s| ml_normalize(s, None, "none").unwrap().into_owned()),
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
        let _ = Actionable::for_steps(&[Step::Confusables("cyrillic")]);
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
            ("\u{2204}", "e"),  // ∄ THERE DOES NOT EXIST → ∃ → e
            ("\u{2224}", "l"),  // ∤ DOES NOT DIVIDE → ∣ → l
            ("\u{2226}", "ll"), // ∦ NOT PARALLEL TO → ∥ → ll
            ("\u{2241}", "~"),  // ≁ NOT TILDE → ∼ → ~
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

            // ml_normalize is the one preset that is *not* a fixed point under the
            // "cldr" emoji style: `demojize` expands typographic punctuation inside
            // CLDR names (e.g. the U+2019 in "woman’s hat" → "right apostrophe") on a
            // second pass. With emoji_style="none" there is no demojize, so it *is*
            // idempotent — pin that across both the lang-present and lang-absent paths.
            #[test]
            fn ml_normalize_idempotent_emoji_none(
                s in adversarial(),
                lang in prop::option::of(prop::sample::select(vec!["de", "ru", "ja"])),
            ) {
                let once = ml_normalize(&s, lang, "none").unwrap();
                let twice = ml_normalize(&once, lang, "none").unwrap();
                prop_assert_eq!(&once, &twice);
            }

            // Structural post-conditions that hold for ALL four conditional paths
            // (lang present/absent × emoji_style cldr/none), since full idempotency
            // is excluded above. Verifies the case-fold and whitespace-collapse stages
            // actually took effect regardless of which conditional stages ran.
            #[test]
            fn ml_normalize_postconditions_all_modes(
                s in adversarial(),
                lang in prop::option::of(prop::sample::select(vec!["de", "ru", "ja"])),
                style in prop::sample::select(vec!["cldr", "none"]),
            ) {
                let out = ml_normalize(&s, lang, style).unwrap();
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
