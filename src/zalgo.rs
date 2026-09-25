//! Zalgo text detection and stripping.
//!
//! Zalgo text abuses Unicode combining marks by stacking dozens of diacriticals
//! on a single base character, producing visually disruptive "glitchy" text.
//! Legitimate text rarely exceeds 2–3 combining marks per base character
//! (e.g. Vietnamese `ệ` = e + combining circumflex + combining dot below).
//!
//! This module provides:
//! - `is_zalgo()` — detect whether text contains excessive combining marks
//! - `strip_zalgo()` — cap the marks of each combining class on one base character,
//!   preserving legitimate diacritics while removing the stacked abuse
//!
//! Both count per base *and per combining class* (#842), over everything up to the next
//! non-mark: a class-0 mark neither counts nor splits the count (Z1 in
//! `formal/lean/Text`). The two read one table, [`MarkTally`], so they agree.
//!
//! Layer 1 (pure-Rust core): no pyo3. Shim in `src/py/zalgo.rs`; crates.io
//! surface is `crate::api::{is_zalgo, strip_zalgo}`.

use unicode_normalization::char::{canonical_combining_class, is_combining_mark};
use unicode_normalization::UnicodeNormalization;

/// Default threshold: a base character with more than this many combining marks of
/// one combining class is considered zalgo.  Vietnamese `ệ` has 2 combining marks in NFD, so 3
/// is a safe default that catches abuse while preserving all real-world text.
pub(crate) const DEFAULT_THRESHOLD: usize = 3;

/// Default cap for `strip_zalgo`: keep at most this many combining marks of one
/// combining class per base character.
///
/// **Equal to [`DEFAULT_THRESHOLD`] on purpose (#788).** It was 2 while the threshold
/// was 3, so the library stripped from text it had just declined to call suspicious:
/// `is_zalgo("\u05d0\u05b8\u05c1\u0591")` is `false` — pointed and cantillated
/// Hebrew routinely puts a vowel, a dot and an accent on one consonant — and
/// `strip_zalgo` removed the accent anyway.
///
/// The two constants must move together, and the direction is forced. Lowering the
/// threshold to 2 would make `is_zalgo` call ordinary Torah text zalgo; raising the cap
/// to 3 makes the transform act only on what the predicate flags. #429 set the cap to
/// preserve legitimate diacritics, and 3-mark Hebrew is legitimate — so this serves
/// that decision rather than reversing it.
///
/// `tests/test_zalgo_cap.py` holds the invariant, stated as **marks preserved** rather
/// than string equality: for every `s` where `is_zalgo(s)` is false,
/// `strip_zalgo(s)` loses no combining mark. Byte equality is the wrong claim — this
/// function recomposes to NFC, so a decomposed input legitimately comes back spelled
/// differently, and an earlier draft of that test reported 750 "violations" that were
/// all recomposition.
pub(crate) const DEFAULT_MAX_MARKS: usize = DEFAULT_THRESHOLD;

/// How many distinct combining classes one base can be tallied for.
///
/// Unicode assigns 56 canonical combining classes, 0 included (the test
/// `every_combining_class_fits_the_tally` holds that against the normalization tables), so
/// every class a base can carry has a slot. Were a future Unicode to exceed this, a mark of
/// a class that finds no free slot counts as over any cap: a base carrying marks of more
/// than 63 distinct classes is stacking by any reading.
const TALLY_SLOTS: usize = 64;

/// The marks of each combining class on the current base: the one table the predicate and
/// the cap both read, so they cannot disagree about what a position carries.
///
/// **Per base, not per run (Z1, `formal/lean/Text`).** #842 counted per combining class
/// because canonical ordering sorts a base's marks by class, so interleaving classes cannot
/// split a run. But canonical ordering only sorts *between starters*, and a class-0 mark is
/// a starter: `a` + three acutes + `U+034F` + three acutes is six acutes on one base in two
/// runs of three, and resetting the count at the class-0 mark let a base carry any number
/// of stacked marks. 1,493 of the 1,496 class-0 marks did it, among them the invisible
/// `U+034F`, `U+180B`-`U+180F` and `U+17B4`/`U+17B5`, which `canonicalize` keeps. So the
/// table is cleared only at a non-mark, and a class-0 mark neither counts nor resets it.
///
/// **The first negation overlay on a symbol is not counted (Z2).** The cap keeps one
/// `U+0338`/`U+20D2` on a relation beyond `max_marks` (#749): it is part of the symbol,
/// not a diacritic. The predicate counted it, so `strip_zalgo`'s own output was still
/// zalgo at the same threshold. Both now skip it here.
struct MarkTally {
    classes: [u8; TALLY_SLOTS],
    counts: [usize; TALLY_SLOTS],
    len: usize,
    base: Option<char>,
    negation_kept: bool,
}

impl MarkTally {
    fn new() -> Self {
        Self {
            classes: [0; TALLY_SLOTS],
            counts: [0; TALLY_SLOTS],
            len: 0,
            base: None,
            negation_kept: false,
        }
    }

    /// Feed the next scalar of an NFD stream. Returns `false` when it is a mark beyond
    /// `cap` at its position, which the cap drops and the predicate reports.
    #[inline]
    fn admit(&mut self, ch: char, cap: usize) -> bool {
        if !self.negation_kept && crate::transliterate::is_negation_of(ch, self.base) {
            // #749: not a diacritic. On a symbol, `U+0338` and `U+20D2` are the stroke
            // through a relation, so dropping one leaves the *positive* operator: `\u{2260}`
            // became `=`. Exactly one per base: a relation carries a single stroke, and a
            // *run* of them is stacking whatever the base is, so overlays after the first
            // are counted like any other mark. On a *letter* the same code point is
            // strikethrough obfuscation, which is why `is_negation_of` asks about the base.
            self.negation_kept = true;
            return true;
        }
        if !is_combining_mark(ch) {
            self.len = 0;
            self.base = Some(ch);
            self.negation_kept = false;
            return true;
        }
        let class = canonical_combining_class(ch);
        // Marks with combining class 0 are POSITIONED by the renderer rather than stacked
        // at one spot: Burmese vowel signs and medials, Indic matras, Thai vowels. Counting
        // them as stacking is what made `is_zalgo` call 142 ordinary Burmese place names
        // zalgo (#842): `\u{1019}\u{103C}\u{102D}\u{102F}\u{1037}` is one syllable carrying
        // a base, a medial, two vowel signs and a tone. They neither count nor, since Z1,
        // reset the count of the marks around them.
        //
        // A cap of 0 is not a stacking judgement at all: it means no mark is acceptable,
        // so the exemption does not apply there. `strip_zalgo` documents `max_marks=0` as
        // stripping every combining mark (the negation overlay above aside, #749), and
        // `strip_obfuscation` depends on it (#846 review).
        if class == 0 && cap > 0 {
            return true;
        }
        self.bump(class) <= cap
    }

    /// Count one more mark of `class` on the current base; returns the new count.
    #[inline]
    fn bump(&mut self, class: u8) -> usize {
        let len = self.len;
        if let Some(i) = self.classes[..len].iter().position(|&c| c == class) {
            self.counts[i] += 1;
            return self.counts[i];
        }
        if len == TALLY_SLOTS {
            return usize::MAX;
        }
        self.classes[len] = class;
        self.counts[len] = 1;
        self.len = len + 1;
        1
    }
}

/// Call `visit(base, run)` for each maximal run of characters that are not
/// [plain](crate::normalize::is_nfd_plain), where `base` is the plain character before the
/// run (`None` at the start of the text), until `visit` returns `true`. Returns whether it
/// did.
///
/// The per-base walks below only ever need these runs. A plain character is its own NFD
/// and a starter NFD never reorders across, so the NFD of the text is the NFD of the pieces
/// between them; and it is not a mark, so it ends the base before it and leaves
/// [`MarkTally`] and [`RepeatTracker`] in the state a fresh one has after reading it. So a
/// walk that feeds `base` and then the NFD of `run` to a fresh tracker sees exactly what
/// the same tracker sees at that point of the NFD of the whole text, and the text between
/// runs, nearly all of it in ordinary text, is never decomposed. ASCII is plain and is
/// never decoded.
fn any_mark_run(text: &str, mut visit: impl FnMut(Option<char>, &str) -> bool) -> bool {
    let bytes = text.as_bytes();
    let mut base = None; // the plain character before `i`, when the byte before it ends one
    let mut run = None; // start of the run being read
    let mut i = 0;
    while i < bytes.len() {
        let (c, len) = if bytes[i] < 0x80 {
            (char::from(bytes[i]), 1)
        } else {
            let c = text[i..].chars().next().expect("`i` is a char boundary");
            (c, c.len_utf8())
        };
        if len == 1 || crate::normalize::is_nfd_plain(c) {
            if let Some(start) = run.take() {
                if visit(base, &text[start..i]) {
                    return true;
                }
            }
            base = Some(c);
        } else if run.is_none() {
            run = Some(i);
        }
        i += len;
    }
    run.is_some_and(|start| visit(base, &text[start..]))
}

/// Streaming check: does any base carry **more than** `threshold` marks of one combining
/// class, counted in NFD up to the next non-mark? [`MarkTally`] says what counts.
///
/// Returns the instant the first position exceeds `threshold`, so a short zalgo burst
/// at the front of a long benign tail settles in `O(burst)`, not `O(len)` — no
/// full NFD walk once the verdict is decided (review H-P2/H-P3).
fn exceeds_combining_run(text: &str, threshold: usize) -> bool {
    any_mark_run(text, |base, run| {
        let mut tally = MarkTally::new();
        base.into_iter()
            .chain(run.nfd())
            .any(|ch| !tally.admit(ch, threshold))
    })
}

/// Detect whether text contains zalgo-style combining mark abuse.
///
/// Returns `True` if any base character carries more than `threshold` marks of one
/// combining class in NFD decomposition (Z3: the cap is per combining class on one base,
/// not per base, since #842). Class-0 marks, which a renderer positions rather than
/// stacks, are not counted unless `threshold` is 0, and neither is the first negation
/// overlay on a symbol (#749).
///
/// # Parameters
/// - `threshold`: Maximum allowed marks of one combining class on one base (default: 3).
///   Vietnamese `e` + circumflex + dot below has 2 marks in NFD — the default of 3 is
///   safe for all legitimate scripts.
pub(crate) fn is_zalgo(text: &str, threshold: usize) -> bool {
    // Fast path: pure ASCII has no combining marks.
    if text.is_ascii() {
        return false;
    }
    exceeds_combining_run(text, threshold)
}

/// Remembers the last stacking mark on the current base, to spot one repeated (#835).
///
/// A class-0 mark is transparent: it neither counts as the previous mark nor clears it
/// (Z1, `formal/lean/Text`). Canonical ordering sorts a base's marks by class only between
/// starters, and a class-0 mark is one, so clearing on it let `a` + acute + `U+180B` +
/// acute carry the repeat past every surface: the key builders' repeat-dropper, and the
/// `duplicate_mark` detector, which calls [`first_repeated_mark`]. Only a non-mark ends
/// the base.
#[derive(Default)]
struct RepeatTracker {
    previous: Option<char>,
}

impl RepeatTracker {
    /// Feed the next scalar of an NFD stream; `true` when it repeats the stacking mark
    /// immediately before it on the same base.
    #[inline]
    fn repeats(&mut self, ch: char) -> bool {
        if !is_combining_mark(ch) {
            self.previous = None;
            return false;
        }
        if canonical_combining_class(ch) == 0 {
            return false;
        }
        if self.previous == Some(ch) {
            return true;
        }
        self.previous = Some(ch);
        false
    }
}

/// Drop a nonspacing mark that repeats immediately on the same base (#835).
///
/// UTS #39 §5.4 lists a sequence of the same nonspacing mark as an optional detection,
/// and the reason is legibility rather than volume: `a` + two acutes renders exactly like
/// `a` + one, so the two spellings are indistinguishable to a reader while producing
/// different bytes, and therefore different keys.
///
/// Deliberately NOT part of [`strip_zalgo_into`]. That function is the cap, and #788
/// paired it with [`is_zalgo`] so the two agree: `strip_zalgo` must not remove a mark
/// from a string `is_zalgo` calls ordinary. Two acutes IS ordinary by the threshold —
/// the repeat is a different fact about the text, not a larger amount of the same one —
/// so folding this into the cap broke that pairing on 540 strings. It is its own step,
/// used by the key builders, and the cap keeps its contract.
///
/// Nonzero combining class only, matching the cap's own discriminator (#842): a class-0
/// mark is positioned rather than stacked, so a doubled Indic matra is an orthography
/// question rather than this one. A class-0 mark between two copies of one stacking mark
/// does not separate them ([`RepeatTracker`]).
/// Returns `false` when there was no repeat, leaving `out` untouched — the caller keeps
/// its input, which is the `apply_into` no-op contract.
///
/// The earlier draft normalized to NFC on that path instead, and every pipeline using
/// this step runs [`strip_zalgo_into`] immediately after it, which does its own NFD→NFC
/// pass — so the overwhelming majority of strings, the ones with no repeat at all, paid
/// for two full normalizations to reach the same bytes. Nothing here owes the pipeline an
/// NFC form: each list carries an explicit `Step::Nfc` after the cap for that (#874
/// review).
pub(crate) fn drop_repeated_marks_into(text: &str, out: &mut String) -> bool {
    // The check is much cheaper than the rewrite, and most text has no repeat at all.
    if first_repeated_mark(text).is_none() {
        return false;
    }
    out.clear();
    let mut filtered = String::with_capacity(text.len());
    let mut tracker = RepeatTracker::default();
    filtered.extend(text.nfd().filter(|&ch| !tracker.repeats(ch)));
    crate::normalize::nfc_into(&filtered, out);
    true
}

/// The first stacking mark that some base carries twice in a row (#835), or `None`.
///
/// Cheap and streaming like [`exceeds_combining_run`], and needed for the same reason:
/// the rewrite above cannot run if this decides there is nothing to do. The anomaly
/// detector's `duplicate_mark` finding reads the same answer, so the finding and the
/// key builders' repeat-dropper cannot disagree about what a repeat is.
pub(crate) fn first_repeated_mark(text: &str) -> Option<char> {
    let mut found = None;
    any_mark_run(text, |_, run| {
        // A fresh tracker is the state after a plain base: `previous` is `None`.
        let mut tracker = RepeatTracker::default();
        found = run.nfd().find(|&ch| tracker.repeats(ch));
        found.is_some()
    });
    found
}

/// Strip excessive combining marks, keeping at most `max_marks` of each combining class
/// per base character.  Operates in NFD (decomposed) space and recomposes to NFC.
///
/// This preserves legitimate diacritics (é, ñ, ệ) while removing zalgo
/// stacking abuse.
///
/// # Parameters
/// - `max_marks`: Maximum marks of one combining class to keep on one base (default: 3).
///   Set to 0 to strip every combining mark except the first negation overlay on a
///   symbol (#749), which is what `strip_accents` removes too.
pub(crate) fn strip_zalgo(text: &str, max_marks: usize) -> String {
    let mut out = String::new();
    strip_zalgo_into(text, max_marks, &mut out);
    out
}

/// In-place form of [`strip_zalgo`] writing the final NFC result into `out`
/// (cleared first), so the pipeline can reuse one buffer across steps
/// (#236 item 7). The NFD/NFC two-pass still needs one internal temporary.
pub(crate) fn strip_zalgo_into(text: &str, max_marks: usize, out: &mut String) {
    out.clear();
    // Fast path: pure ASCII has no combining marks.
    if text.is_ascii() {
        out.push_str(text);
        return;
    }

    // Fast path (H-P3): if no base exceeds `max_marks`, the mark-filtering step
    // is a no-op, so skip the intermediate `filtered` buffer and just normalize
    // to NFC (`NFC(NFD(x)) == NFC(x)`), preserving the documented NFC output
    // contract without the per-char copy. Most non-ASCII text has no zalgo.
    if !exceeds_combining_run(text, max_marks) {
        crate::normalize::nfc_into(text, out);
        return;
    }

    // The cap is counted over the *NFD (decomposed)* sequence, so it bounds the
    // number of combining marks per base in decomposed space — a precomposed
    // accented letter (e.g. `é` = one mark in NFD) costs one toward the cap, and a
    // base carrying N stacked marks is capped to `max_marks` of them. The final NFC
    // recompose may then re-attach kept marks into precomposed forms; the count is
    // deliberately taken *before* that recompose so stacking is measured uniformly
    // regardless of the input's composition.
    //
    // The same `MarkTally` as the predicate above, so the cap drops exactly the marks
    // the predicate counts as excess: `strip_zalgo` removes nothing from text `is_zalgo`
    // calls ordinary (#788), and its output is never zalgo at the same threshold (Z2).
    let mut filtered = String::with_capacity(text.len());
    let mut tally = MarkTally::new();
    filtered.extend(text.nfd().filter(|&ch| tally.admit(ch, max_marks)));

    // Recompose to NFC for consistency with the rest of the library.
    crate::normalize::nfc_into(&filtered, out);
}

/// Remove a combining mark whose own script is a *specific* script differing from the
/// script of the base it attaches to (#615, CVE-2017-7833).
///
/// The CVE is domain spoofing "through the combination of Arabic and Indic vowel marker
/// characters with Latin characters", which "can obscure non-Latin characters in domain
/// names, making them invisible to most users while avoiding punycode encoding".
///
/// `strip_zalgo`'s cap cannot reach it. That is a **count**, and by count one Arabic
/// shadda is indistinguishable from one acute accent, so no threshold removes the spoof
/// and keeps `café`. The discriminator the count lacks is already in disarm's script
/// data:
///
/// | mark | `detect_char_script` | |
/// |---|---|---|
/// | `U+0301` COMBINING ACUTE | `Inherited` | a legitimate diacritic — kept |
/// | `U+0651` ARABIC SHADDA | `Arabic` | the CVE's vector — stripped off a Latin base |
/// | `U+0E31` THAI MAI HAN AKAT | `Thai` | likewise |
///
/// This is UTS #39's mixed-script reasoning applied at the grapheme level rather than
/// across the whole string. A mark whose script is `Inherited` attaches to anything and
/// is never touched, which is why `café`, `naïve`, `Việt Nam` and Arabic *with* its own
/// vowel marks all pass through unchanged.
///
/// Deliberately **not** in `canonicalize`, and not public. Scholarly transliteration, IPA
/// and linguistic transcription legitimately place marks from one script on bases of
/// another, and a strip that fires on those would be destructive in exactly the corpus
/// least able to notice. `canonicalize_strict` is where a caller has already accepted a
/// stricter contract.
///
/// Only the in-place form exists: the preset runner reuses one scratch buffer across
/// steps (#236 item 7), so an owned wrapper would have no caller.
pub(crate) fn strip_cross_script_marks_into(text: &str, out: &mut String) {
    out.clear();
    out.reserve(text.len());
    // The script of the most recent non-mark character — what a mark attaches to.
    let mut base_script: Option<&'static str> = None;
    for ch in text.chars() {
        if is_combining_mark(ch) {
            let mark_script = crate::scripts::detect_char_script(ch);
            // `Inherited` means "takes the script of its base", so it can never
            // conflict. `Common` marks (rare) are treated the same way.
            let specific = mark_script != "Inherited" && mark_script != "Common";
            if specific && base_script.is_some_and(|b| b != mark_script) {
                continue; // cross-script mark on a foreign base — the CVE's shape
            }
            out.push(ch);
            continue;
        }
        base_script = match crate::scripts::detect_char_script(ch) {
            // Punctuation, digits and whitespace do not re-anchor the base script.
            "Common" | "Inherited" => base_script,
            s => Some(s),
        };
        out.push(ch);
    }
}

#[cfg(test)]
mod tests {
    /// The run walks see what the whole-text NFD walks they replaced saw.
    mod run_walk {
        use super::super::*;
        use unicode_normalization::char::canonical_combining_class;

        fn whole_exceeds(text: &str, threshold: usize) -> bool {
            let mut tally = MarkTally::new();
            text.nfd().any(|ch| !tally.admit(ch, threshold))
        }

        fn whole_repeat(text: &str) -> Option<char> {
            let mut tracker = RepeatTracker::default();
            text.nfd().find(|&ch| tracker.repeats(ch))
        }

        fn check(text: &str) {
            for threshold in [0, 1, 2, 3] {
                assert_eq!(
                    exceeds_combining_run(text, threshold),
                    whole_exceeds(text, threshold),
                    "threshold {threshold} on {text:?}"
                );
            }
            assert_eq!(first_repeated_mark(text), whole_repeat(text), "{text:?}");
        }

        /// Every scalar that is not plain, or that decomposes, or is a mark.
        fn interesting() -> Vec<char> {
            (0x80u32..0x11_0000)
                .filter_map(char::from_u32)
                .filter(|&c| {
                    !crate::normalize::is_nfd_plain(c)
                        || is_combining_mark(c)
                        || canonical_combining_class(c) != 0
                        || c.to_string().nfd().ne(std::iter::once(c))
                })
                .collect()
        }

        /// Plain bases of every kind the walks treat differently (a letter, a symbol a
        /// negation overlay keeps, an astral letter), the overlays, stacking marks of two
        /// classes, class-0 marks, and characters whose NFD carries a mark.
        const CONTEXTS: [&str; 16] = [
            "a",
            "=",
            "<",
            "\u{10400}",
            "\u{0338}",
            "\u{20D2}",
            "\u{0301}",
            "\u{0301}\u{0301}",
            "\u{0316}",
            "\u{034F}",
            "\u{180B}",
            "\u{102D}",
            "\u{00E9}",
            "\u{2260}",
            "\u{1E09}",
            "\u{AC00}",
        ];

        #[test]
        fn every_interesting_scalar_in_every_context() {
            let set = interesting();
            assert!(set.len() > 3_000, "only {} interesting scalars", set.len());
            for &c in &set {
                for x in CONTEXTS {
                    check(&format!("{x}{c}{c}"));
                    check(&format!("{c}{x}{x}"));
                    check(&format!("{x}{c}{x}{c}{c}"));
                }
            }
        }

        #[test]
        fn random_strings() {
            let set = interesting();
            let mut state: u64 = 0x9E37_79B9_7F4A_7C15;
            let mut next = move || {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                state
            };
            for _ in 0..50_000 {
                let len = (next() % 16) as usize;
                let text: String = (0..len)
                    .map(|_| match next() % 4 {
                        0 => CONTEXTS[(next() % CONTEXTS.len() as u64) as usize].to_owned(),
                        1 => char::from(b' ' + (next() % 95) as u8).to_string(),
                        _ => set[(next() % set.len() as u64) as usize].to_string(),
                    })
                    .collect();
                check(&text);
            }
        }
    }

    /// #846 review: the class-0 exemption must not reach `max_marks == 0`.
    ///
    /// Three doc comments promise that 0 strips **all** combining marks and is equivalent
    /// to `strip_accents`, and `strip_obfuscation` is built on it. Counting per class is a
    /// judgement about *stacking*, which a threshold of zero is not making.
    #[test]
    fn zero_max_marks_strips_class_zero_marks_too() {
        // Each of these is a combining mark with canonical combining class 0 — the class
        // the per-class count exempts, because a renderer positions them rather than
        // stacking them at one spot.
        for (mark, name) in [
            ('\u{0E31}', "THAI CHARACTER MAI HAN-AKAT"),
            ('\u{093F}', "DEVANAGARI VOWEL SIGN I"),
            ('\u{102D}', "MYANMAR VOWEL SIGN I"),
            ('\u{09BE}', "BENGALI VOWEL SIGN AA"),
        ] {
            assert_eq!(
                canonical_combining_class(mark),
                0,
                "{name} is no longer class 0; pick another example",
            );
            let input = format!("\u{0E01}{mark}");
            let stripped = strip_zalgo(&input, 0);
            assert!(
                !stripped.contains(mark),
                "max_marks=0 left {name} in {stripped:?}",
            );
            assert!(
                is_zalgo(&input, 0),
                "threshold 0 must call {name} excess, to match what strip_zalgo removes",
            );
        }
    }

    /// The other half of the same rule: above zero, class-0 marks stay exempt. This is
    /// #842 — capping them truncated ordinary Burmese, Bengali and Thai.
    #[test]
    fn nonzero_max_marks_still_exempts_class_zero_marks() {
        let burmese = "\u{1019}\u{103C}\u{102D}\u{102F}\u{1037}";
        assert_eq!(strip_zalgo(burmese, DEFAULT_MAX_MARKS), burmese);
        assert!(!is_zalgo(burmese, DEFAULT_MAX_MARKS));
    }

    use super::*;

    #[test]
    fn test_is_zalgo_clean_text() {
        assert!(!is_zalgo("hello world", 3));
        assert!(!is_zalgo("café résumé", 3));
        assert!(!is_zalgo("", 3));
    }

    #[test]
    fn test_is_zalgo_ascii_fast_path() {
        assert!(!is_zalgo("just ascii text 12345!@#$%", 3));
    }

    #[test]
    fn test_is_zalgo_vietnamese() {
        // Vietnamese ệ = e + combining circumflex + combining dot below (2 marks)
        assert!(!is_zalgo("Việt Nam", 3));
        assert!(!is_zalgo("ệ", 2));
    }

    #[test]
    fn test_is_zalgo_detects_stacking() {
        // Build zalgo: 'a' + 10 combining marks
        let mut zalgo = String::from("a");
        for _ in 0..10 {
            zalgo.push('\u{0300}'); // combining grave accent
        }
        assert!(is_zalgo(&zalgo, 3));
    }

    #[test]
    fn test_is_zalgo_threshold_boundary() {
        // Exactly at threshold: not zalgo
        let mut text = String::from("a");
        for _ in 0..3 {
            text.push('\u{0300}');
        }
        assert!(!is_zalgo(&text, 3));

        // One above threshold: zalgo
        text.push('\u{0300}');
        assert!(is_zalgo(&text, 3));
    }

    #[test]
    fn test_strip_zalgo_clean_text_unchanged() {
        assert_eq!(strip_zalgo("hello world", 2), "hello world");
        assert_eq!(strip_zalgo("café", 2), "café");
    }

    #[test]
    fn test_strip_zalgo_preserves_legitimate_diacritics() {
        // Vietnamese ệ has 2 combining marks — should be preserved with max_marks=2
        let input = "Việt Nam";
        assert_eq!(strip_zalgo(input, 2), input);

        // French accents — 1 combining mark each
        assert_eq!(strip_zalgo("résumé", 2), "résumé");
    }

    #[test]
    fn test_strip_zalgo_removes_excess() {
        // 'a' + 10 combining graves → should keep only max_marks
        let mut zalgo = String::from("a");
        for _ in 0..10 {
            zalgo.push('\u{0300}'); // combining grave accent
        }
        let result = strip_zalgo(&zalgo, 2);
        // Result should be 'a' with exactly 2 combining graves (in NFC: à + 1 extra grave)
        // NFD: a + grave + grave, NFC: à + grave (combining grave after precomposed à)
        // The key assertion: no more than 2 combining marks survived
        assert!(result.chars().count() <= 3); // base + at most 2 marks after NFC
        assert!(result.starts_with('à'));
    }

    #[test]
    fn test_strip_zalgo_max_marks_zero_strips_all() {
        assert_eq!(strip_zalgo("café", 0), "cafe");
        assert_eq!(strip_zalgo("résumé", 0), "resume");
    }

    #[test]
    fn test_strip_zalgo_ascii_fast_path() {
        let input = "just ascii";
        assert_eq!(strip_zalgo(input, 2), input);
    }

    #[test]
    fn test_strip_zalgo_multiple_base_chars() {
        // Multiple base chars each with excessive stacking
        let mut zalgo = String::new();
        for base in ['H', 'i'] {
            zalgo.push(base);
            for _ in 0..8 {
                zalgo.push('\u{0300}');
                zalgo.push('\u{0301}');
                zalgo.push('\u{0302}');
            }
        }
        let result = strip_zalgo(&zalgo, 2);
        // Each base char should have at most 2 combining marks
        let mut mark_count = 0;
        for ch in result.nfd() {
            if is_combining_mark(ch) {
                mark_count += 1;
                assert!(mark_count <= 2, "Too many combining marks in output");
            } else {
                mark_count = 0;
            }
        }
    }

    #[test]
    fn test_exceeds_combining_run() {
        assert!(!exceeds_combining_run("hello", 0));
        assert!(!exceeds_combining_run("café", 1)); // 1 mark, threshold 1
        assert!(!exceeds_combining_run("", 0));

        let mut text = String::from("a");
        for _ in 0..5 {
            text.push('\u{0300}');
        }
        assert!(exceeds_combining_run(&text, 2)); // 5 marks > 2
        assert!(!exceeds_combining_run(&text, 5)); // 5 marks, threshold 5
    }

    /// NFD marks of `mark` in `text`.
    fn count(text: &str, mark: char) -> usize {
        text.nfd().filter(|&c| c == mark).count()
    }

    /// Z1 (`formal/lean/Text`): a class-0 mark between two runs of one mark reset the
    /// count, so a base could carry any number of stacked marks.
    #[test]
    fn class_zero_mark_does_not_reset_the_count() {
        // CGJ, a Mongolian free variation selector, a Khmer inherent vowel (all three
        // render as nothing), and a visible Thai vowel sign.
        for sep in ['\u{034F}', '\u{180B}', '\u{17B4}', '\u{0E31}'] {
            assert!(is_combining_mark(sep) && canonical_combining_class(sep) == 0);
            let split = format!("a\u{0301}\u{0301}\u{0301}{sep}\u{0301}\u{0301}\u{0301}");
            assert!(is_zalgo(&split, 3), "U+{:04X}", sep as u32);
            let stripped = strip_zalgo(&split, 3);
            assert_eq!(count(&stripped, '\u{0301}'), 3, "U+{:04X}", sep as u32);
            assert!(stripped.contains(sep), "the class-0 mark itself is kept");

            let alternating = format!("a{}", format!("\u{0301}{sep}").repeat(20));
            assert!(is_zalgo(&alternating, 3));
            assert_eq!(count(&strip_zalgo(&alternating, 3), '\u{0301}'), 3);
        }
        // The kernel's minimal counterexample (`z1_minimal`), at max_marks = 1.
        assert!(is_zalgo("a\u{0301}\u{0E31}\u{0301}", 1));
        assert_eq!(
            strip_zalgo("a\u{0301}\u{0E31}\u{0301}", 1),
            "\u{00E1}\u{0E31}"
        );
        // A non-mark still starts a new base.
        assert!(!is_zalgo(
            "a\u{0301}\u{0301}\u{0301}b\u{0301}\u{0301}\u{0301}",
            3
        ));
    }

    /// Z1 for the repeat-dropper: a class-0 mark does not separate two copies of a mark.
    #[test]
    fn class_zero_mark_does_not_hide_a_repeat() {
        assert_eq!(
            first_repeated_mark("a\u{0301}\u{180B}\u{0301}"),
            Some('\u{0301}')
        );
        assert_eq!(first_repeated_mark("a\u{0301}b\u{0301}"), None);
        assert_eq!(first_repeated_mark("a\u{0301}\u{0300}\u{0301}"), None);
        let mut out = String::new();
        assert!(drop_repeated_marks_into(
            "a\u{0301}\u{180B}\u{0301}\u{180B}",
            &mut out
        ));
        assert_eq!(out, "\u{00E1}\u{180B}\u{180B}");
    }

    /// Z2 (`formal/lean/Text`): the negation overlay the cap keeps beyond `max_marks`
    /// (#749) is not counted by the predicate either, so the cap's output is never zalgo
    /// at the same threshold.
    #[test]
    fn strip_zalgo_output_is_not_zalgo() {
        let stacked = format!("={}", "\u{0338}".repeat(4));
        let out = strip_zalgo(&stacked, 3);
        assert_eq!(count(&out, '\u{0338}'), 4, "one stroke plus three");
        assert!(!is_zalgo(&out, 3));
        assert!(!is_zalgo("\u{2260}", 0));
        assert_eq!(strip_zalgo("\u{2260}", 0), "\u{2260}");
        // A second overlay is counted, and on a letter none is exempt.
        assert!(is_zalgo("=\u{0338}\u{0338}", 0));
        assert!(is_zalgo("a\u{0338}", 0));
        for text in [
            stacked.as_str(),
            "a\u{0301}\u{0301}\u{0301}\u{034F}\u{0301}\u{0301}",
            "\u{2260}\u{20D2}\u{20D2}\u{20D2}\u{20D2}\u{20D2}",
        ] {
            for k in 0..4 {
                assert!(!is_zalgo(&strip_zalgo(text, k), k), "{text:?} at {k}");
            }
        }
    }

    /// Every canonical combining class has a slot in [`MarkTally`].
    #[test]
    fn every_combining_class_fits_the_tally() {
        let mut seen = [false; 256];
        for c in '\0'..=char::MAX {
            seen[usize::from(canonical_combining_class(c))] = true;
        }
        let classes = seen.iter().filter(|&&s| s).count();
        assert!(classes < TALLY_SLOTS, "{classes} classes");
    }

    proptest::proptest! {
        /// H-P3: `strip_zalgo` always returns NFC — the fast path that skips the
        /// filter must still normalize.
        #[test]
        fn strip_zalgo_output_is_nfc(s in "\\PC*", max in 0usize..4) {
            let out = strip_zalgo(&s, max);
            proptest::prop_assert!(unicode_normalization::is_nfc(&out));
        }

        /// The fast path (no excess marks) must produce the same bytes as the
        /// full filter path would on the same input.
        #[test]
        fn strip_zalgo_fast_path_matches_filter(s in "\\PC*") {
            // With a high cap, no run is ever excess, so the fast path is taken;
            // it must equal a plain NFC normalization.
            let out = strip_zalgo(&s, 1000);
            let nfc: String = s.nfc().collect();
            proptest::prop_assert_eq!(out, nfc);
        }

        /// Z1/Z2: the cap's output is never zalgo at the same threshold, over an alphabet
        /// built from the shapes that broke it: stacked marks, class-0 separators and
        /// negation overlays on a symbol and on a letter.
        #[test]
        fn strip_zalgo_output_is_never_zalgo(
            s in "[a=\u{0301}\u{0316}\u{0334}\u{0338}\u{20D2}\u{034F}\u{0E31}\u{180B}]{0,24}",
            k in 0usize..4,
        ) {
            proptest::prop_assert!(!is_zalgo(&strip_zalgo(&s, k), k));
        }
    }
}
