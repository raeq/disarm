//! Emoji-to-text expansion (demojize). Layer 1 — pure core, no pyo3 (#38).
//!
//! Converts emoji sequences to their CLDR short-name text descriptions.
//! The matching engine handles ZWJ sequences, skin tone modifiers, flag
//! sequences, keycap sequences, and presentation selectors.
//!
//! Data is supplied by the built-in CLDR PHF tables. The custom Python
//! `EmojiProvider` override (and the provider-aware demojize loop) is
//! binding-layer-only and lives in the PyO3 shim `crate::py::emoji`.

use crate::tables;

/// Zero-Width Joiner — joins emoji into compound sequences (e.g. family groups).
pub(crate) const ZWJ: char = '\u{200D}';
/// Variation Selector 16 — request emoji presentation.
pub(crate) const VS16: char = '\u{FE0F}';
/// Variation Selector 15 — request text presentation.
pub(crate) const VS15: char = '\u{FE0E}';
/// Combining Enclosing Keycap — the third code point of `1\u{FE0F}\u{20E3}`.
pub(crate) const KEYCAP: char = '\u{20E3}';

// #112: key_buf and sep_positions were stack-allocated to avoid two heap
// allocations per emoji-multi-starter character in the former hex-key matcher.
// #242 item 4: the production matcher now walks the code-point trie
// (`tables::match_emoji_sequence`), so the hex-key encoder is retained
// **test-only** as the reference oracle (`match_emoji_at_reference`).
#[cfg(test)]
const KEY_BUF_CAP: usize = 128; // MAX_WINDOW(18) × 5 hex + 17 '_' = 107 bytes; 128 is safe
                                // P9: tie the test buffer to the real window size (`MAX_WINDOW`, derived from the
                                // build-generated MAX_EMOJI_SEQ_LEN) so it can never silently under-size if the
                                // CLDR data grows. Worst case: every code point emits up to 5 hex digits, with a
                                // `_` separator between the MAX_WINDOW code points → MAX_WINDOW*5 + (MAX_WINDOW-1).
#[cfg(test)]
const _: () = assert!(KEY_BUF_CAP >= MAX_WINDOW * 6 - 1);

/// Write a slice of codepoints as an uppercase hex key into `buf`.
///
/// Returns the number of bytes written.  The buffer must be at least
/// `KEY_BUF_CAP` bytes long.  Using a caller-supplied stack buffer avoids
/// repeated heap allocation inside the O(max_seq_len) candidate loop in
/// `match_emoji_at_reference`.
#[cfg(test)]
fn encode_key_into(buf: &mut [u8; KEY_BUF_CAP], cps: &[char]) -> usize {
    let mut pos = 0usize;
    for (i, &c) in cps.iter().enumerate() {
        if i > 0 {
            buf[pos] = b'_';
            pos += 1;
        }
        // Format codepoint as uppercase hex (4–6 digits) into the stack buffer.
        // All emoji codepoints fit in 5 hex digits (max U+10FFFF = 6 digits, but
        // emoji top out at ~1FAFF), and {:04X} zero-pads to at least 4.
        let cp = c as u32;
        // Determine digit count (minimum 4 per the format spec).
        let digits: u32 = if cp >= 0x10_0000 {
            6
        } else if cp >= 0x1_0000 {
            5
        } else {
            4
        };
        for d in (0..digits).rev() {
            let nibble = ((cp >> (d * 4)) & 0xF) as u8;
            buf[pos] = if nibble < 10 {
                b'0' + nibble
            } else {
                b'A' + nibble - 10
            };
            pos += 1;
        }
    }
    pos
}

/// Try to match the longest emoji sequence starting at `window[0]`.
///
/// `window` is a fixed-size lookahead slice of up to `MAX_EMOJI_SEQ_LEN`
/// chars beginning at the current position; `window.len()` equals the number
/// of chars still available.  Returns `(short_name, chars_consumed)` or
/// `None`.
///
/// # #112 / #113
/// Stack-only allocations: `key_buf` is a `[u8; KEY_BUF_CAP]` array and
/// `sep_positions` is a `[usize; MAX_WINDOW]` array — no heap
/// allocation occurs here regardless of input.
///
/// # Panics
/// Panics if `window` is empty (it indexes `window[0]`). Every caller advances
/// only while characters remain, so the slice is always non-empty here; the
/// `debug_assert!` documents and (in debug builds) enforces that contract. (C4)
pub(crate) fn match_emoji_at(window: &[char]) -> Option<(&'static str, usize)> {
    debug_assert!(
        !window.is_empty(),
        "match_emoji_at requires a non-empty window"
    );
    let ch = window[0];

    // Try multi-codepoint sequences first (longest match).  #242 item 4: walk
    // the code-point trie directly — no per-length hex-key construction.
    if tables::is_emoji_multi_starter(ch) {
        if let Some(hit) = tables::match_emoji_sequence(window) {
            return Some(hit);
        }
    }

    // #972: the RGI keycap is `base + U+FE0F + U+20E3`, and CLDR keys it without the
    // selector (`0031_20E3`). The trie walk above therefore missed the form people
    // actually type: `demojize("x1\u{FE0F}\u{20E3}y")` returned `x1\u{20E3}y`, dropping
    // the selector and leaving the combining keycap on the digit. Retry without the
    // selector and report all three code points consumed.
    // A text-style keycap, `1\u{FE0E}\u{20E3}`, is the same keycap asking for text
    // presentation, and CLDR names it the same way. Without this arm the scanner skipped
    // the VS15 and left `1\u{20E3}`, which the next pass named (Lean model).
    if window.len() >= 3 && (window[1] == VS16 || window[1] == VS15) && window[2] == KEYCAP {
        if let Some((name, _)) = tables::match_emoji_sequence(&[ch, KEYCAP]) {
            return Some((name, 3));
        }
    }

    // Try single-codepoint lookup
    if let Some(name) = tables::lookup_emoji_single(ch) {
        // Check if followed by variation selector — consume it too
        let consumed = if window.len() > 1 && (window[1] == VS16 || window[1] == VS15) {
            2
        } else {
            1
        };
        return Some((name, consumed));
    }

    None
}

/// Reference matcher (the pre-#242-item-4 hex-key PHF probe), retained
/// **test-only** as the equivalence oracle for [`match_emoji_at`].
/// `emoji_trie_matches_reference` asserts the two agree on every emoji
/// sequence; keeping this here documents the behaviour the trie replicates.
#[cfg(test)]
fn match_emoji_at_reference(window: &[char]) -> Option<(&'static str, usize)> {
    let ch = window[0];
    let remaining = window.len();

    if tables::is_emoji_multi_starter(ch) {
        let max_len = MAX_WINDOW.min(remaining);

        let mut key_buf = [0u8; KEY_BUF_CAP];
        let total_len = encode_key_into(&mut key_buf, &window[..max_len]);

        let mut sep_positions = [0usize; MAX_WINDOW];
        let mut sep_count = 0usize;
        for (idx, &b) in key_buf[..total_len].iter().enumerate() {
            if b == b'_' {
                sep_positions[sep_count] = idx;
                sep_count += 1;
            }
        }

        for len in (2..=max_len).rev() {
            let last = window[len - 1];
            if last == ZWJ || last == VS16 || last == VS15 {
                continue;
            }

            let key_slice = if len < max_len {
                std::str::from_utf8(&key_buf[..sep_positions[len - 1]]).unwrap_or("")
            } else {
                std::str::from_utf8(&key_buf[..total_len]).unwrap_or("")
            };

            if let Some(name) = tables::lookup_emoji_multi(key_slice) {
                return Some((name, len));
            }
        }
    }

    if let Some(name) = tables::lookup_emoji_single(ch) {
        let consumed = if window.len() > 1 && (window[1] == VS16 || window[1] == VS15) {
            2
        } else {
            1
        };
        return Some((name, consumed));
    }

    None
}

/// Fixed-size sliding window over the character stream.
///
/// # #113
/// Replaces the `Vec<char>` full-input materialisation in `demojize_impl` and
/// `demojize_rust`.  The buffer holds up to `MAX_EMOJI_SEQ_LEN` chars of
/// lookahead — the maximum the *name* matcher ever needs.  Characters are
/// consumed from the inner iterator one-by-one; advancing the window shifts
/// buffered chars left and refills from the iterator. That path allocates
/// nothing. Following a ZWJ chain past the window's edge (#995) does: it
/// collects the chain into a `Vec` and parks what it pulled but did not use in
/// `pushback`, so allocation is bounded by the longest chain in the input.
pub(crate) struct CharWindow<'a> {
    /// Room for two windows, so advancing moves `head` and shifts the valid chars back to
    /// the front only once `head` has passed a whole window: one shift per `MAX_WINDOW`
    /// chars read, where shifting on every advance moved the window once per char.
    buf: [char; 2 * MAX_WINDOW],
    /// Index in `buf` of the window's first char.
    head: usize,
    /// Number of valid chars in the window, `buf[head..head + len]` (always <= MAX_WINDOW).
    len: usize,
    /// Chars pulled past the window while following a sequence longer than it, and not
    /// consumed by the match that pulled them. Refills take from here before `rest`, so
    /// the pull is a peek rather than a read. It fills whenever the window cannot rule
    /// out a longer chain — a joiner within `HEAD_LOOKAHEAD` of its end — which can
    /// happen after an emoji that fits: `👨‍👨‍👨‍👨` followed by a joiner and text does.
    /// See [`CharWindow::presentation_len`].
    pushback: std::collections::VecDeque<char>,
    rest: std::str::Chars<'a>,
}

/// Window capacity: twice `MAX_EMOJI_SEQ_LEN`, so a match always has its lookahead.
///
/// Derived from the single source of truth (`tables::max_emoji_seq_len()`, a
/// `const fn` over the build-generated `MAX_EMOJI_SEQ_LEN`) rather than a
/// duplicated literal, so the two cannot drift when the CLDR data updates
/// (#199 review). It does **not** set what a custom Python emoji provider can
/// match: the provider call site passes `max_emoji_seq_len()` as its own cap.
///
/// Twice the longest key, not the key itself: the table stores sequences unqualified, and
/// the trie walk accepts a U+FE0F after any component, so a fully qualified sequence is
/// longer than its key — the RGI kiss with skin tones is ten code points to its key's
/// nine. Doubling covers a selector after every component; `a_fully_qualified_key_fits`
/// holds every table key to it.
const MAX_WINDOW: usize = 2 * tables::max_emoji_seq_len();

// The window's growth loop stops once a doubled scan leaves the match unchanged, and that
// stop is sound only from four code points up (`grow_stop_sound` in the Lean model,
// `formal/lean/Emoji`). At three, `👨 U+FE0E U+FE0E ZWJ 1 U+FE0F U+20E3` stops one
// character short of the keycap that completes it (`window3_is_not_enough`). Nothing
// asserted it; a table update that shrank the longest key would have broken it silently.
const _: () = assert!(
    MAX_WINDOW >= 4,
    "CharWindow needs at least four code points"
);

impl<'a> CharWindow<'a> {
    /// Create a new window, pre-filling the buffer from `chars`.
    pub(crate) fn new(mut chars: std::str::Chars<'a>) -> Self {
        let mut buf = ['\0'; 2 * MAX_WINDOW];
        let mut len = 0;
        while len < MAX_WINDOW {
            match chars.next() {
                Some(c) => {
                    buf[len] = c;
                    len += 1;
                }
                None => break,
            }
        }
        CharWindow {
            buf,
            head: 0,
            len,
            pushback: std::collections::VecDeque::new(),
            rest: chars,
        }
    }

    /// The next char of the input, taking anything a previous peek pushed back first.
    #[inline]
    fn next_char(&mut self) -> Option<char> {
        self.pushback.pop_front().or_else(|| self.rest.next())
    }

    /// The current character (first in the window), or `None` if exhausted.
    #[inline]
    pub(crate) fn current(&self) -> Option<char> {
        if self.len > 0 {
            Some(self.buf[self.head])
        } else {
            None
        }
    }

    /// A slice of all valid chars in the window (up to MAX_WINDOW chars).
    #[inline]
    pub(crate) fn as_slice(&self) -> &[char] {
        &self.buf[self.head..self.head + self.len]
    }

    /// Advance the window by `n` chars.
    ///
    /// Drops the first `n` chars, then refills. `n` may exceed the buffer: a match
    /// found by [`CharWindow::presentation_len`] can be longer than the window, and the
    /// chars past it are then dropped a bufferful at a time rather than shifted.
    pub(crate) fn advance(&mut self, mut n: usize) {
        debug_assert!(n > 0);
        while n >= self.len && self.len > 0 {
            n -= self.len;
            self.head = 0;
            self.len = 0;
            self.refill();
            if n == 0 {
                return;
            }
        }
        if self.len == 0 {
            return;
        }
        self.head += n;
        self.len -= n;
        self.refill();
    }

    /// Top the window up to `MAX_WINDOW` chars, first moving it to the front of `buf`
    /// when a full window no longer fits after `head`.
    fn refill(&mut self) {
        if self.head > MAX_WINDOW {
            self.buf.copy_within(self.head..self.head + self.len, 0);
            self.head = 0;
        }
        while self.len < MAX_WINDOW {
            match self.next_char() {
                Some(c) => {
                    self.buf[self.head + self.len] = c;
                    self.len += 1;
                }
                None => break,
            }
        }
    }

    /// The emoji-presentation sequence at the cursor, followed past the window's edge.
    ///
    /// [`presentation_len_at`] recurses over a ZWJ chain, which UTS #51 does not bound,
    /// so the length it can return is not bounded either. `MAX_WINDOW` is
    /// `max_emoji_seq_len()` — the longest run the CLDR **name** table holds — which
    /// bounds naming correctly and replacing not at all: the RGI kiss with skin tones
    /// is ten code points, and a family of four with skin tones — a valid ZWJ sequence,
    /// though not RGI — is eleven. Asking on the bare window cut such a
    /// sequence at nine, which emitted two replacements where one was right and, worse,
    /// passed the joiner at the seam through as ordinary text (#995).
    ///
    /// A match that ends before the window's edge is complete, and that is every input
    /// here bar the long ones — they return without touching `pushback` or the heap.
    /// Only a match that reaches the edge pulls more, and it pulls a doubling chunk at a
    /// time so that following a chain of *n* code points costs O(n) rather than the
    /// O(n²) a one-at-a-time rescan would: this is a sanitiser, and its worst case is
    /// somebody's input.
    pub(crate) fn presentation_len(&mut self) -> Option<usize> {
        let len = presentation_len_at(self.as_slice())?;
        if self.len < MAX_WINDOW {
            // The buffer is short because the input ended, so the slice is the whole
            // remainder and the answer is already final.
            return Some(len);
        }
        // A full buffer does not by itself mean the match is unfinished — and keying on
        // fullness alone sent every emoji in any input longer than the window through the
        // heap scan below. More input can only extend a match that ran to the edge, or
        // one the chain loop abandoned at a joiner it could not yet judge. A match that
        // stopped anywhere else is done, and no amount of lookahead changes that.
        //
        // "Could not yet judge" is the narrow part: the chain loop abandoned that joiner
        // because `head_len_at` answered `None` for what came after it, and that answer
        // is final as soon as it had `HEAD_LOOKAHEAD` chars to look at. Treating every
        // joiner as unjudged instead cost a windowful of read-ahead per emoji on input
        // shaped like `emoji + ZWJ + text` — 20.5 ms against 7.9 ms for 100k of them.
        if len < self.len && (self.as_slice()[len] != ZWJ || self.len - (len + 1) >= HEAD_LOOKAHEAD)
        {
            return Some(len);
        }
        // A full buffer cannot tell a finished sequence from one it merely ran out of
        // room for. The two look identical from inside: the recursion breaks on a `ZWJ`
        // with nothing joinable after it, and "nothing after it" is what the edge looks
        // like. So grow until growing stops changing the answer, rather than trying to
        // read completeness off a length — an eleven-code-point family with skin tones
        // reports 8 of 9 here, one short of the edge and still unfinished.
        let mut scan: Vec<char> = self.as_slice().to_vec();
        let mut len = len;
        loop {
            let before = scan.len();
            for _ in 0..before {
                match self.next_char() {
                    Some(c) => scan.push(c),
                    None => break,
                }
            }
            if scan.len() == before {
                break; // input exhausted
            }
            let grown = presentation_len_at(&scan).unwrap_or(len);
            if grown == len {
                break; // more input did not extend the match
            }
            len = grown;
        }
        // Hand back **everything** the peek pulled, in order — not just the part the
        // match declined. The peek has to leave the stream exactly as it found it,
        // because the length it returns is what `advance` is called with, and `advance`
        // counts from the window: chars consumed here as well as skipped there would be
        // skipped twice, silently dropping the text after a long sequence.
        for &c in scan[self.len..].iter().rev() {
            self.pushback.push_front(c);
        }
        Some(len)
    }
}

/// A conservative block-range superset of "some emoji step might touch this" (#990).
///
/// **Not a definition of emoji**, and no longer used as one. `presets::is_demojizable`
/// is its only caller: a fast-path guard where over-marking costs a skipped optimisation
/// and under-marking would be unsound, so a loose range answer is the right shape there.
///
/// The scanners ask `unnamed_emoji_len_at` instead (#990): a block range is not a
/// definition of emoji, and `U+2600..27BF` is Miscellaneous Symbols and Dingbats.
pub(crate) fn is_emoji_codepoint(ch: char) -> bool {
    let cp = ch as u32;
    // Emoticons, Dingbats, Symbols, Transport, Supplemental Symbols, etc.
    matches!(cp,
        0x2600..=0x27BF |     // Misc Symbols, Dingbats
        0x2B50..=0x2B55 |     // Additional symbols
        0xFE00..=0xFE0F |     // Variation selectors
        0x1F000..=0x1FAFF |   // Supplementary emoji blocks
        // GAP — U+1FB00..=U+1FBFF (Symbols for Legacy Computing) is intentionally
        // excluded: it is box-drawing / teletext / segmented-display graphics, not
        // emoji, and carries no RGI emoji property. It kept `demojize` from expanding
        // legacy terminal art into emoji names until #990 moved that decision to
        // `unnamed_emoji_len_at`; what the exclusion buys now is a fast path that does
        // not mark a page of box-drawing as actionable for a step that would not
        // touch it.
        0x1FC00..=0x1FFFF |   // Future emoji blocks
        0xE0020..=0xE007F     // Tags (used in flag sequences)
    )
}

/// Check if a codepoint is an emoji modifier (skin tone, ZWJ, VS, tag).
pub(crate) fn is_emoji_modifier(ch: char) -> bool {
    let cp = ch as u32;
    matches!(cp,
        0x200D |              // ZWJ
        0xFE0E..=0xFE0F |    // Variation selectors
        0x1F3FB..=0x1F3FF |   // Skin tone modifiers
        0xE0020..=0xE007F |   // Tags
        0x20E3               // Combining Enclosing Keycap
    )
}

/// Advance `win` past the modifiers that belong to the match just consumed (#992).
///
/// A *named* match consumes whatever the CLDR table held; anything bound to it that the
/// table did not spell out is swept here. The set is `is_emoji_modifier`'s **minus
/// `U+20E3`**, and that difference is the point: the keycap makes a sequence only after a
/// digit, `#` or `*`, which `match_emoji_at` has already matched whole when it applies.
/// After anything else the keycap is a combining mark of its own, and sweeping it made
/// `demojize("\u{1F600}\u{20E3}")` drop an assigned character — the very thing
/// [`head_len_at`] refuses to do, ten lines from where it says so. The two halves of the
/// scanner now agree.
///
/// `ZWJ` stays swept, though [`head_len_at`] does not take it either — but not to keep
/// joiners out of prose. Both scanners drop every `VS15`, `VS16` and `ZWJ` at the top
/// of their loop wherever it stands, so a joiner between two named emoji never reaches
/// the output either way. What sweeping it buys is carrying on *past* it to a modifier
/// the match did not take: `\u{1F468}\u{200D}\u{1F3FB}` names as `man`, where stopping
/// at the joiner names the skin tone on its own (#996 review).
///
/// One function for all three call sites — the pure-Rust scanner and both of the pyo3
/// one's — because three copies of a predicate is how the two scanners came apart.
pub(crate) fn advance_past_trailing_modifiers(win: &mut CharWindow<'_>) {
    while win
        .current()
        .is_some_and(|c| is_emoji_modifier(c) && c != KEYCAP)
    {
        win.advance(1);
    }
}

/// Strip modifier suffixes (": light skin tone", etc.) from a CLDR short name
/// when `strip_modifiers` is true.
#[inline]
pub(crate) fn strip_modifier_suffix(name: &str, strip_modifiers: bool) -> &str {
    if strip_modifiers {
        if let Some(base_end) = name.find(": ") {
            return &name[..base_end];
        }
    }
    name
}

/// Whether `ch`, emitted straight after an emoji name, needs a space in front of it.
///
/// The question is what the character will DO to the name, not what it is. Three ways it
/// can join one, and one function so the scanner's two emit sites cannot answer them
/// differently — they did, which is how the third went unnoticed (#992):
///
/// * **Alphanumeric.** `"grinning face"` + `"x"` is one word at the seam.
/// * **Folds to alphanumeric.** `\u{20AC}` is not alphanumeric, but TR39 folds it to `e`,
///   so `"woman's hat"` + `\u{20AC}` became `"woman's hate"` once `confusables` ran — a
///   word in neither the input nor any name. `\u{2211}` -> `s` and `\u{2200}` -> `a` too.
/// * **A combining mark**, which attaches to whatever precedes it, and after a name that
///   is the name's last letter: `demojize("\u{1F600}\u{301}")` read `"grinning facé"`.
///   The accent was on the emoji in the input and ended up on a word that was not.
///
/// Punctuation that stays punctuation (`\u{2010}` -> `-`) still takes no separator.
pub(crate) fn needs_separator_after_a_name(ch: char) -> bool {
    ch.is_alphanumeric()
        || unicode_normalization::char::is_combining_mark(ch)
        || crate::tables::lookup_confusable(ch, "latin")
            .is_some_and(|t| t.starts_with(char::is_alphanumeric))
}

/// Insert emoji replacement text with leading space padding.
///
/// Adds a leading space only if the result is non-empty and doesn't already end
/// with whitespace. Checking for any whitespace (not just `' '`) avoids a
/// double separator when the preceding char is a tab or newline: `"a\t😀"`
/// becomes `"a\tgrinning face"`, not `"a\t grinning face"`. The caller must set
/// `last_was_emoji = true` so the next non-emoji alphanumeric also gets a space.
#[inline]
pub(crate) fn pad_emoji_replacement(result: &mut String, text: &str) {
    let ends_with_ws = result.chars().next_back().is_some_and(char::is_whitespace);
    if !result.is_empty() && !ends_with_ws {
        result.push(' ');
    }
    result.push_str(text);
}

// ─── Replacement mode (#972) ────────────────────────────────────────────────────
//
// Naming and replacing ask different questions of different tables, and they are
// separate code paths on purpose.
//
// Naming asks "what does CLDR call this?", so its domain is the name table — which is
// wider than the emoji: `demojize("x\u{2122}y")` is "x trade mark y" because CLDR
// annotates `U+2122`. Replacing with `""` over that domain would delete `\u{2122}` and
// `\u{00A9}` from ordinary prose, which is not what a caller removing emoji asked for.
//
// So replacement asks "is this an emoji by the UCD's own properties?" and its domain is
// the emoji-presentation set: `Emoji_Presentation=Yes`, an `Emoji=Yes` base carrying
// `U+FE0F` (#992), and the sequences built on those. That question needs two range tables and
// no names, which is the second reason the paths are separate: a build that only
// replaces links neither the CLDR name trie nor the 182 KB behind it (#695).

/// Skin-tone modifiers, `U+1F3FB`..`U+1F3FF`.
#[inline]
fn is_skin_tone(ch: char) -> bool {
    matches!(ch, '\u{1F3FB}'..='\u{1F3FF}')
}

/// Tag characters, used by the subdivision flag sequences.
#[inline]
fn is_tag(ch: char) -> bool {
    matches!(ch, '\u{E0020}'..='\u{E007F}')
}

// `EMOJI_CANDIDATE`: one bit per BMP code point (codegen/emoji_candidate.rs).
include!(concat!(env!("OUT_DIR"), "/emoji_candidate.rs"));

/// Whether a scanner may do anything at `ch` but copy it: a skipped selector or joiner,
/// a name, the start of a named sequence, or an emoji presentation opener. Astral
/// characters always answer yes, so only the BMP rule, [`may_act_at_lookup`], has to be
/// right, and `candidate_bitmap_covers_the_scanners` holds the bitmap to it.
#[inline]
fn may_act_at(ch: char) -> bool {
    let cp = u32::from(ch);
    cp > 0xFFFF || EMOJI_CANDIDATE[(cp >> 6) as usize] >> (cp & 63) & 1 == 1
}

/// The rule [`may_act_at`] tabulates, stated as the tests the scanners make.
#[cfg(test)]
fn may_act_at_lookup(ch: char) -> bool {
    ch == VS16
        || ch == VS15
        || ch == ZWJ
        || tables::is_emoji_multi_starter(ch)
        || tables::lookup_emoji_single(ch).is_some()
        || opens_emoji_presentation(ch)
        || is_tag(ch)
}

/// Regional indicators, which pair into a flag.
#[inline]
fn is_regional_indicator(ch: char) -> bool {
    matches!(ch, '\u{1F1E6}'..='\u{1F1FF}')
}

/// Whether `ch` can open an emoji-presentation sequence on its own.
///
/// `Emoji=Yes` alone is not enough: `\u{00A9}` and `\u{2122}` carry it and render as
/// text, which is why the `U+FE0F` case is handled by the caller rather than here.
#[inline]
fn opens_emoji_presentation(ch: char) -> bool {
    tables::is_emoji_presentation(ch) || is_regional_indicator(ch)
}

/// How many chars [`head_len_at`] may need to see before it can answer `None`.
///
/// Its deepest read is the keycap arm's `window[2]` — base, `U+FE0F`, keycap. So a `None`
/// from a slice at least this long is final, and one from a shorter slice might have been
/// a `Some` with more input behind it. [`CharWindow::presentation_len`] needs that
/// distinction to tell a joiner it has disproved from one it merely ran out of room to
/// judge. `head_lookahead_is_enough` below holds it to the number.
const HEAD_LOOKAHEAD: usize = 3;

/// One emoji-presentation **head**: a base and the modifiers bound to it, no ZWJ chain.
///
/// Returns `None` for anything the UCD does not call an emoji in this position: a keycap
/// base with no keycap after it (`1`, `#`), and a text-default base with no `U+FE0F`
/// (`\u{00A9}`, `\u{263A}`).
///
/// A regional indicator is `Emoji_Presentation=Yes` on its own, so it returns `Some(1)`;
/// a pair returns `Some(2)`, because a flag is one emoji and must take one replacement.
///
/// Split out of [`presentation_len_at`] so that following a chain can be a loop instead
/// of a recursion (#995). The recursion descended once per link, which the
/// nine-code-point match window bounded by accident; once the window follows a sequence
/// past its edge the depth is whatever the input says, and a long enough chain overflowed
/// the stack — an abort no caller can catch, on input from outside. Chaining lives in the
/// caller's loop, so nothing here calls anything that calls this.
fn head_len_at(window: &[char]) -> Option<usize> {
    let first = *window.first()?;

    // A pair of regional indicators is one flag, and one emoji: `replacement=" "` must
    // put a single space where the flag was, not two. A lone regional indicator is still
    // `Emoji_Presentation=Yes` and still an emoji — it renders as a letter in a box —
    // so it goes too, just on its own.
    if is_regional_indicator(first) {
        return Some(
            if window.get(1).copied().is_some_and(is_regional_indicator) {
                2
            } else {
                1
            },
        );
    }

    // Keycap: `base + U+FE0F? + U+20E3`. The base is a digit, `#` or `*` — ordinary
    // characters, so the keycap itself is what makes the sequence an emoji.
    if matches!(first, '0'..='9' | '#' | '*') {
        let after_selector = usize::from(window.get(1) == Some(&VS16));
        return if window.get(1 + after_selector) == Some(&KEYCAP) {
            Some(2 + after_selector)
        } else {
            None
        };
    }

    // Two ways to open: the code point renders as emoji on its own, or it *can* and the
    // next code point says to.
    let vs16_next = window.get(1) == Some(&VS16);
    let opens = opens_emoji_presentation(first) || (vs16_next && tables::is_emoji_yes(first));
    if !opens {
        return None;
    }

    let mut len = 1;
    while let Some(&c) = window.get(len) {
        if c == VS16 || c == VS15 || is_skin_tone(c) || is_tag(c) {
            len += 1;
        } else {
            break;
        }
    }
    Some(len)
}

/// How many chars of an emoji-presentation sequence start at `window[0]`, if any.
///
/// One head ([`head_len_at`]) followed by the ZWJ chain hanging off it, so this is the
/// length of the whole emoji — the thing that must take exactly one replacement.
///
/// The answer is a function of the slice it is given, which is the caller's problem and
/// not a small one: UTS #51 puts no limit on a ZWJ chain, so there is no window size that
/// is always enough, and a slice that stops mid-sequence returns a short answer rather
/// than saying so. [`CharWindow::presentation_len`] is what deals with that; a caller
/// passing a bare fixed slice will split long sequences (#995).
///
/// A flag and a keycap take no continuation, so neither chains.
pub(crate) fn presentation_len_at(window: &[char]) -> Option<usize> {
    let first = *window.first()?;
    let mut len = head_len_at(window)?;

    // A flag and a keycap take no continuation: UTS #51 defines neither as joinable, and
    // chaining one would swallow a following emoji into it.
    if is_regional_indicator(first) || matches!(first, '0'..='9' | '#' | '*') {
        return Some(len);
    }

    // Extend over the modifiers and joined heads that belong to this emoji. A trailing
    // ZWJ with nothing joinable after it is left alone: it is not part of a sequence,
    // and consuming it would delete a character the caller did not ask about.
    loop {
        match window.get(len) {
            Some(&c) if c == VS16 || c == VS15 || is_skin_tone(c) || is_tag(c) => len += 1,
            // No `KEYCAP` arm. UTS #51 defines the keycap sequence only for the ten
            // digits, `#` and `*`, which `head_len_at` already answered. Consuming one
            // here would make `\u{263A}\u{FE0F}\u{20E3}` — an emoji followed by a
            // stray combining mark — one emoji, and remove a character that is not part
            // of any sequence the standard defines.
            Some(&c) if c == ZWJ => match head_len_at(&window[len + 1..]) {
                Some(joined) => len += 1 + joined,
                None => break,
            },
            _ => break,
        }
    }
    Some(len)
}

/// How many chars of a run `demojize` treats as an emoji it has no name for (#990).
///
/// `presentation_len_at` answers the emoji half. The Plane 14 TAG block is the other:
/// a lone tag character is *not* an emoji — it is the concealment carrier
/// `strip_plane14` exists for — but removing it here is the only coverage of that block
/// `ml_normalize` has, and #914 is explicit that demojize's Plane 14 removal must not
/// move until something else carries it. No preset declares `Step::StripPlane14`, so
/// nothing does yet. It keeps a named arm rather than riding a block range, and giving
/// `ml_normalize` the real step is a change with a `KEY_SCHEMA_VERSION` cost of its own.
///
/// Only a sequence whose head renders as emoji **without being asked** counts. A
/// text-default `Emoji=Yes` base that `U+FE0F` opens — `\u{00A9}`, `\u{00AE}` — is an
/// emoji presentation sequence to [`presentation_len_at`], and `replace_emoji` is right
/// to replace it. Here it is not an emoji *with no name*: it is a symbol with no name
/// that was asked to render as emoji, and dropping it deletes an assigned character on
/// the strength of a selector. Excluded, the scanners keep the base and drop the
/// selector, as they did before #990. Without this the branch took 2,141 such symbols —
/// the VS16 arm then read `Emoji` OR `Extended_Pictographic`, which reaches `\u{2605}`
/// and unassigned code points too, until #992 narrowed it to `Emoji=Yes` — and a ZWJ
/// chain opened by one, `\u{00A9}\u{FE0F}\u{200D}🔥`, took the named `🔥` down with it. The keycap bases open no sequence without a keycap
/// after them, and every keycap has a CLDR name, so they need no exception.
///
/// Both scanners call this, so the two cannot drift apart on what they rewrite.
pub(crate) fn unnamed_emoji_len_at(window: &[char]) -> Option<usize> {
    let first = *window.first()?;
    if opens_emoji_presentation(first) {
        presentation_len_at(window)
    } else if is_tag(first) {
        Some(1)
    } else {
        None
    }
}

/// Replace every emoji-presentation sequence in `text` with `replacement` (#972).
///
/// The counterpart to [`demojize_rust_into`], which names emoji instead. Everything
/// outside the emoji-presentation set is emitted verbatim, including stray variation
/// selectors and the CLDR-annotated punctuation naming would have replaced with a word.
/// `replacement` is inserted exactly as given — no padding and no whitespace collapse —
/// because the two useful values want opposite things: `""` closes an intra-word split
/// (`aa\u{1F525}bb` -> `aabb`) and `" "` keeps two words apart
/// (`stop\u{1F6D1}now` -> `stop now`), and a rule that served one would break the other.
pub fn demojize_rust_replace_into(text: &str, replacement: &str, result: &mut String) {
    result.clear();
    // Emoji are all non-ASCII, so ASCII text cannot contain one — including the keycap
    // bases, which need a non-ASCII keycap after them to become an emoji.
    if text.is_ascii() {
        result.push_str(text);
        return;
    }

    result.reserve(text.len());
    let mut win = CharWindow::new(text.chars());
    while let Some(ch) = win.current() {
        if let Some(consumed) = win.presentation_len() {
            result.push_str(replacement);
            win.advance(consumed);
            drop_marks_the_seam_would_bind(&mut win, result);
            continue;
        }
        result.push(ch);
        win.advance(1);
    }
}

/// After a match is replaced, drop a selector or keycap that would bind to what now
/// precedes it — the replacement's last character, or with `""` the text before the emoji.
///
/// A keycap or a presentation selector after an emoji is not part of that emoji (#996),
/// so replacing the emoji leaves it behind — and if the character now before it can take
/// it, the two are an emoji the input never had: `1\u{1F600}\u{20E3}` gave `1\u{20E3}`,
/// a keycap, and a second pass removed it along with the caller's digit. Only a mark
/// that would **form** an emoji with the last character written goes; one that joins
/// nothing is still text, so `replace_emoji("1\u{1F600}\u{20E3}", " ")` keeps it.
pub(crate) fn drop_marks_the_seam_would_bind(win: &mut CharWindow<'_>, result: &str) {
    // The deepest head is base, selector, keycap: three chars, `HEAD_LOOKAHEAD`. So the
    // seam reaches back up to two characters of output, not one: a keycap left by a
    // removal can bind across `1\u{FE0F}` as well as `1` — `replace_emoji` on
    // `1\u{FE0F}😀\u{20E3}` built the keycap `1\u{FE0F}\u{20E3}` when it looked back at
    // the selector alone (Lean model, `formal/lean/Emoji`).
    let mut tail = ['\0'; HEAD_LOOKAHEAD - 1];
    let mut kept = 0;
    for c in result.chars().rev().take(HEAD_LOOKAHEAD - 1) {
        kept += 1;
        tail[HEAD_LOOKAHEAD - 1 - kept] = c;
    }
    let tail = &tail[HEAD_LOOKAHEAD - 1 - kept..];
    while let Some(mark) = win.current() {
        if !matches!(mark, VS15 | VS16 | KEYCAP) {
            return;
        }
        let ahead = win.as_slice();
        // A mark binds if a head starting `back` characters into the output reaches
        // past the output and into it.
        let binds = (1..=tail.len()).rev().any(|back| {
            let mut seam = ['\0'; HEAD_LOOKAHEAD];
            let from_tail = &tail[tail.len() - back..];
            let n = ahead.len().min(HEAD_LOOKAHEAD - back);
            seam[..back].copy_from_slice(from_tail);
            seam[back..back + n].copy_from_slice(&ahead[..n]);
            head_len_at(&seam[..back + n]).is_some_and(|len| len > back)
        });
        if !binds {
            return;
        }
        win.advance(1);
    }
}

/// Owned form of [`demojize_rust_replace_into`].
#[must_use]
pub fn demojize_rust_replace(text: &str, replacement: &str) -> String {
    let mut out = String::new();
    demojize_rust_replace_into(text, replacement, &mut out);
    out
}

/// Pure Rust demojize for use by TextPipeline (no Python provider support).
///
/// # #113
/// Uses a `CharWindow` sliding buffer instead of `Vec<char>` to avoid
/// materialising the full input for non-ASCII text.
pub fn demojize_rust(text: &str, strip_modifiers: bool) -> String {
    let mut out = String::new();
    demojize_rust_into(text, strip_modifiers, NamePolicy::NAME_EVERYTHING, &mut out);
    out
}

/// Standalone `demojize` (`api::demojize` and every binding): name every row, and
/// give an emoji the table cannot name to `error_mode` — `Replace` writes `replace_with`,
/// `Ignore` drops it, `Preserve` keeps it.
///
/// The pipeline's own step ([`demojize_rust`], [`demojize_rust_into`]) keeps dropping,
/// which is what a preset wants. The standalone function used to drop too, while
/// Python's documented default wrote `[?]`, so the same call disagreed across the
/// bindings on 3,105 inputs (`formal/bindings`, D1). The Python binding calls this when
/// no `EmojiProvider` is in play, so its `errors=` and every other binding's default are
/// one code path.
pub fn demojize_named(
    text: &str,
    strip_modifiers: bool,
    error_mode: crate::ErrorMode,
    replace_with: &str,
) -> String {
    let mut out = String::new();
    demojize_rust_into_with(
        text,
        strip_modifiers,
        NamePolicy::NAME_EVERYTHING,
        Unnamed::from_mode(error_mode, replace_with),
        &mut out,
    );
    out
}

/// What the scanner writes for an emoji it cannot name.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Unnamed<'r> {
    /// Nothing: the pipeline step, and `errors="ignore"`.
    Drop,
    /// This string, verbatim (`errors="replace"`; may be empty).
    Replace(&'r str),
    /// The emoji itself (`errors="preserve"`).
    Preserve,
}

impl<'r> Unnamed<'r> {
    pub(crate) fn from_mode(mode: crate::ErrorMode, replace_with: &'r str) -> Self {
        match mode {
            crate::ErrorMode::Replace => Unnamed::Replace(replace_with),
            crate::ErrorMode::Ignore => Unnamed::Drop,
            crate::ErrorMode::Preserve => Unnamed::Preserve,
        }
    }
}

/// Which CLDR name rows a caller wants left alone.
///
/// CLDR `annotationsDerived` names characters that are not emoji: typographic
/// punctuation, currency, math operators, brackets. Naming them is right for standalone
/// `demojize` — `demojize("I \u{2764} \u{20AC}5")` -> "I red heart euro 5" is what that
/// function is for — and wrong inside a preset, where the name is a word that was in
/// neither the input nor any emoji.
///
/// The two reasons are separate flags because they are separate sets: six of the 49 rows
/// #614 found (`\u{203C}`, `\u{2049}`, `\u{2139}`, `\u{2795}`, `\u{2796}`, `\u{2797}`) are
/// genuine emoji, so neither set contains the other.
#[derive(Clone, Copy, Default, PartialEq, Eq, Debug)]
pub struct NamePolicy {
    /// #614: leave the 49 code points the TR39 confusable table also claims for the
    /// confusable step to fold, instead of naming them here.
    ///
    /// Set only by comparison presets. `strip_obfuscation("\u{20AC}xample.com")` named the
    /// euro sign — "euro xample.com" — so the spoof and the genuine string stopped being
    /// equal rather than becoming equal, and CVE-2017-5383 survived a preset documented
    /// as maximum-strength deobfuscation.
    pub skip_tr39_claimed: bool,
    /// #757: leave the 326 code points that carry neither the Unicode `Emoji` nor the
    /// `Extended_Pictographic` property.
    ///
    /// Set by every preset. `ml_normalize` — documented for tokenizers, embeddings and
    /// feature extraction — turned `film\u{2019}s` into `film right apostrophe s`, one token
    /// to four with the possessive gone, and returned 47 words for a 30-word English
    /// sentence carrying nothing but typographic punctuation. That is the
    /// spurious-token-insertion mechanism `docs/security/adversarial-defense.md`
    /// disqualifies `unidecode` for.
    pub skip_non_emoji: bool,
}

impl NamePolicy {
    /// Name every row — standalone `demojize` only, where the caller asked for the name
    /// by name and there is no later step to leave anything for.
    pub const NAME_EVERYTHING: Self = Self {
        skip_tr39_claimed: false,
        skip_non_emoji: false,
    };

    /// The baseline for a [`crate::pipeline::Pipeline`]: leave the non-emoji CLDR rows for
    /// the confusable fold (#757), and name the TR39-claimed rows.
    ///
    /// Used by `Pipeline::new` and `ProfileSpec::build`, which is every hand-built
    /// `TextPipeline` and every named profile. Named once rather than spelled out at each
    /// site, because spelling it out is how those two came to disagree (#918).
    ///
    /// **Not** what the presets use. A preset carries its own policy on its own
    /// `Step::Demojize` and never reads `Pipeline::emoji_name_policy` — a separate code
    /// path with, since #918, the same intent. A *comparison* preset tightens this
    /// further: `strip_obfuscation` sets `skip_tr39_claimed` so the fold wins over the
    /// name (#614), which this baseline deliberately does not do.
    pub const PIPELINE_BASELINE: Self = Self {
        skip_tr39_claimed: false,
        skip_non_emoji: true,
    };

    /// Whether `ch` is left for the rest of the pipeline instead of being named.
    #[inline]
    fn skips(self, ch: char) -> bool {
        (self.skip_tr39_claimed && crate::tables::is_tr39_claimed_emoji_row(ch))
            || (self.skip_non_emoji && crate::tables::is_non_emoji_cldr_row(ch))
    }
}

/// In-place form of [`demojize_rust`] writing into `result` (cleared first), so
/// the pipeline can reuse one buffer across steps (#236 item 7).
///
/// Skipping here rather than reordering the steps is deliberate: `normalize_confusables`
/// runs *after* `demojize` so typographic punctuation inside emoji names (the `\u{2019}`
/// in "woman\u{2019}s hat") is folded too, and swapping them would break idempotency.
pub fn demojize_rust_into(
    text: &str,
    strip_modifiers: bool,
    policy: NamePolicy,
    result: &mut String,
) {
    demojize_rust_into_with(text, strip_modifiers, policy, Unnamed::Drop, result);
}

/// [`demojize_rust_into`] with a choice of what to write for an emoji the table cannot
/// name. The body is the one the Python binding's provider loop mirrors
/// (`crate::py::emoji::demojize_impl`); with no provider Python calls this.
pub(crate) fn demojize_rust_into_with(
    text: &str,
    strip_modifiers: bool,
    policy: NamePolicy,
    unnamed: Unnamed<'_>,
    result: &mut String,
) {
    demojize_scan::<true>(text, strip_modifiers, policy, unnamed, result);
}

/// The body of [`demojize_rust_into_with`]. `FAST` copies a character that is not an
/// [emoji candidate](may_act_at) without asking the tables; the test
/// `the_fast_scan_is_the_full_scan` holds the two instantiations byte-equal.
fn demojize_scan<const FAST: bool>(
    text: &str,
    strip_modifiers: bool,
    policy: NamePolicy,
    unnamed: Unnamed<'_>,
    result: &mut String,
) {
    result.clear();
    // Fast path: pure-ASCII text cannot contain emoji.
    if text.is_ascii() {
        result.push_str(text);
        return;
    }

    result.reserve(text.len());
    let mut win = CharWindow::new(text.chars());
    let mut last_was_emoji = false;
    // Set with `last_was_emoji` when what was written is the emoji itself
    // (`Unnamed::Preserve`) rather than a word: a mark after it was on the emoji in the
    // input and stays on it, and only an alphanumeric is separated (#200, #996 review).
    let mut last_was_raw = false;

    while let Some(ch) = win.current() {
        // Every branch below but the last needs `ch` to be a candidate, and the last,
        // with no emoji before it, writes `ch` and clears both flags (which `last_was_raw`
        // only ever holds with `last_was_emoji`).
        if FAST && !last_was_emoji && !may_act_at(ch) {
            result.push(ch);
            win.advance(1);
            continue;
        }

        if ch == VS16 || ch == VS15 || ch == ZWJ {
            win.advance(1);
            // Skipping is a removal, and what follows now meets what came before: a
            // keycap after `1\u{200D}` bound to the `1` (Lean model).
            drop_marks_the_seam_would_bind(&mut win, result);
            continue;
        }

        // #614/#757: hand this code point to the rest of the pipeline instead of naming
        // it. Emitted verbatim, so a later `confusables` step still sees it.
        if policy.skips(ch) {
            if last_was_emoji && needs_separator_after_a_name(ch) {
                result.push(' ');
            }
            result.push(ch);
            last_was_emoji = false;
            last_was_raw = false;
            win.advance(1);
            continue;
        }

        if let Some((name, consumed)) = match_emoji_at(win.as_slice()) {
            let replacement = strip_modifier_suffix(name, strip_modifiers);
            pad_emoji_replacement(result, replacement);
            win.advance(consumed);
            advance_past_trailing_modifiers(&mut win);
            last_was_emoji = true;
            last_was_raw = false;
            continue;
        }

        // An emoji this scanner cannot name, or a lone Plane 14 tag. What changed in #990
        // is only *what reaches here*: the test was a block range, so `\u{2606}` WHITE
        // STAR and 776 other characters carrying no emoji property were handled as emoji
        // the library lacked data for.
        if let Some(consumed) = unnamed_emoji_len_at(win.as_slice()) {
            let wrote = match unnamed {
                Unnamed::Drop => false,
                Unnamed::Replace(with) => {
                    result.push_str(with);
                    !with.is_empty()
                }
                Unnamed::Preserve => {
                    // `take` rather than a slice: the run is already measured.
                    result.extend(win.as_slice().iter().take(consumed).copied());
                    true
                }
            };
            win.advance(consumed);
            if wrote {
                // Parity with the named path (#200): a visible token flags the position
                // so a following alphanumeric is separated.
                last_was_emoji = true;
                last_was_raw = matches!(unnamed, Unnamed::Preserve);
            } else {
                // Nothing is written, so both flags keep their values: a name written
                // before the dropped emoji still needs its separator. Resetting them
                // glued the next word on — `\u{1F600}\u{1F1E6}x` gave `grinning facex`
                // (Lean model).
                //
                // Dropped, so what follows meets what came before: the seam
                // `replace_emoji` closes (#995 follow-up) is open here too.
                drop_marks_the_seam_would_bind(&mut win, result);
            }
            continue;
        }

        let separate = last_was_emoji
            && if last_was_raw {
                ch.is_alphanumeric()
            } else {
                needs_separator_after_a_name(ch)
            };
        if separate {
            result.push(' ');
        }
        result.push(ch);
        last_was_emoji = false;
        last_was_raw = false;
        win.advance(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn candidate_bitmap_covers_the_scanners() {
        for c in (0u32..0x1_0000).filter_map(char::from_u32) {
            assert_eq!(
                may_act_at(c),
                may_act_at_lookup(c),
                "U+{:04X}",
                u32::from(c)
            );
        }
    }

    /// Copying a non-candidate without asking the tables writes what asking them did,
    /// for every BMP scalar, after a name, after a preserved emoji, and around the
    /// sequences a character could join: keycaps, selectors, flags, skin tones, ZWJ.
    #[test]
    fn the_fast_scan_is_the_full_scan() {
        let policies = [
            NamePolicy::default(),
            NamePolicy {
                skip_tr39_claimed: true,
                skip_non_emoji: false,
            },
            NamePolicy {
                skip_tr39_claimed: false,
                skip_non_emoji: true,
            },
            NamePolicy {
                skip_tr39_claimed: true,
                skip_non_emoji: true,
            },
        ];
        let unnamed = [Unnamed::Drop, Unnamed::Replace("?"), Unnamed::Preserve];
        let (mut fast, mut full) = (String::new(), String::new());
        for (i, c) in (0u32..0x1_0000).filter_map(char::from_u32).enumerate() {
            for text in [
                format!("x{c}y"),
                format!("\u{1F600}{c}\u{2122}{c}"),
                format!("\u{1F1E6}{c}a\u{1F1FF}"),
                format!("{c}\u{FE0F}\u{20E3}1{c}\u{20E3}"),
                format!("\u{1F44D}{c}\u{1F3FD}\u{1F1E6}{c}"),
                format!("\u{1F468}\u{200D}{c}\u{200D}\u{1F469}{c}\u{FE0F}"),
            ] {
                for policy in policies {
                    let unnamed = unnamed[i % unnamed.len()];
                    let strip = i % 2 == 0;
                    demojize_scan::<true>(&text, strip, policy, unnamed, &mut fast);
                    demojize_scan::<false>(&text, strip, policy, unnamed, &mut full);
                    assert_eq!(fast, full, "{text:?} {policy:?}");
                }
            }
        }
    }

    /// The keycap CLDR keys without a selector, written the way people type it (#972).
    #[test]
    fn the_rgi_keycap_names_the_same_as_the_bare_one() {
        assert_eq!(demojize_rust("x1\u{FE0F}\u{20E3}y", false), "x keycap: 1 y");
        assert_eq!(demojize_rust("x1\u{20E3}y", false), "x keycap: 1 y");
        assert_eq!(demojize_rust("x#\u{FE0F}\u{20E3}y", false), "x keycap: # y");
        // The base alone is a digit and stays one.
        assert_eq!(demojize_rust("x1y", false), "x1y");
    }

    /// One sequence is one emoji, which only a non-empty replacement can see.
    #[test]
    fn a_sequence_takes_one_replacement() {
        for text in [
            "x\u{1F1EC}\u{1F1E7}y",                          // flag
            "x\u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467}y", // ZWJ family
            "x\u{1F44D}\u{1F3FD}y",                          // skin tone
            "x1\u{FE0F}\u{20E3}y",                           // keycap
        ] {
            assert_eq!(demojize_rust_replace(text, " "), "x y", "{text:?}");
        }
    }

    /// Replacing reads the UCD; naming reads CLDR, which annotates more than the emoji.
    #[test]
    fn replacing_leaves_what_only_cldr_claims() {
        assert_eq!(demojize_rust_replace("x\u{2122}y", ""), "x\u{2122}y");
        assert_eq!(demojize_rust("x\u{2122}y", false), "x trade mark y");
        assert_eq!(demojize_rust_replace("x\u{00A9}y", ""), "x\u{00A9}y");
        // The same base with and without the selector, which is the whole distinction.
        assert_eq!(demojize_rust_replace("x\u{263A}y", ""), "x\u{263A}y");
        assert_eq!(demojize_rust_replace("x\u{263A}\u{FE0F}y", ""), "xy");
    }

    /// Verbatim: the two useful replacements want opposite things.
    #[test]
    fn the_replacement_is_inserted_without_padding() {
        assert_eq!(demojize_rust_replace("aa \u{1F525} bb", ""), "aa  bb");
        assert_eq!(demojize_rust_replace("stop\u{1F6D1}now", ""), "stopnow");
        assert_eq!(demojize_rust_replace("stop\u{1F6D1}now", " "), "stop now");
        assert_eq!(
            demojize_rust_replace("aa\u{1F525}bb", "[emoji]"),
            "aa[emoji]bb"
        );
    }

    /// A trailing joiner is not a sequence, and consuming it would eat a character the
    /// caller did not ask about.
    #[test]
    fn a_dangling_joiner_is_left_alone() {
        assert_eq!(demojize_rust_replace("\u{1F525}\u{200D}", ""), "\u{200D}");
        assert_eq!(demojize_rust_replace("a\u{200D}b", ""), "a\u{200D}b");
    }

    /// A stray keycap is not part of the emoji before it (#992).
    ///
    /// `U+20E3 COMBINING ENCLOSING KEYCAP` makes a keycap sequence only after a digit,
    /// `#` or `*`, which is why [`head_len_at`] has no keycap arm and says so. The sweep
    /// after a *named* match used `is_emoji_modifier`, which does include it, so the
    /// named half of the scanner did exactly what the unnamed half refuses to: swallowed
    /// an assigned character that belongs to no sequence the standard defines. The two
    /// scanners disagreeing about what an emoji is is the defect #990 was about.
    #[test]
    fn a_stray_keycap_survives_a_named_emoji() {
        assert_eq!(
            demojize_rust("\u{1F600}\u{20E3}", false),
            "grinning face \u{20E3}"
        );
        assert_eq!(
            demojize_rust("\u{263A}\u{FE0F}\u{20E3}", false),
            "smiling face \u{20E3}"
        );
        // The replacing half already got this right; the two now agree.
        assert_eq!(demojize_rust_replace("\u{1F600}\u{20E3}", ""), "\u{20E3}");
    }

    /// A combining mark after an emoji must not land on the name (#992).
    ///
    /// The separator rule already exists for exactly this reason, one class narrower:
    /// emitting `\u{20AC}` bare after a name produced `"woman's hat"` + `"e"` ->
    /// `"woman's hate"`, a word in neither the input nor any name. A combining mark does
    /// the same thing more directly — it attaches to whatever precedes it, and after a
    /// name that is the name's last letter. In the input it was on the emoji.
    #[test]
    fn a_combining_mark_does_not_attach_to_the_name() {
        assert_eq!(
            demojize_rust("\u{1F600}\u{301}", false),
            "grinning face \u{301}"
        );
        assert_eq!(
            demojize_rust("\u{1F600}\u{20E3}", false),
            "grinning face \u{20E3}"
        );
        // Not a mark, not alphanumeric: the existing rule stands, no separator.
        assert_eq!(demojize_rust("\u{1F600}.", false), "grinning face.");
    }

    /// A real keycap sequence is still one emoji (#992).
    #[test]
    fn a_keycap_on_its_proper_base_is_still_one_emoji() {
        assert_eq!(demojize_rust("x1\u{FE0F}\u{20E3}y", false), "x keycap: 1 y");
        assert_eq!(demojize_rust("x1\u{20E3}y", false), "x keycap: 1 y");
        assert_eq!(demojize_rust_replace("x1\u{FE0F}\u{20E3}y", ""), "xy");
        assert_eq!(demojize_rust("x#\u{FE0F}\u{20E3}y", false), "x keycap: # y");
    }

    /// The joiner arm of the sweep, and what it is actually for (#992, #996 review).
    ///
    /// It carries the sweep past a joiner to a modifier the match did not take. The
    /// joiners between separately named emoji are gone either way — the loop drops every
    /// `ZWJ` it meets — so those assertions guard the output, not the arm; the first one
    /// is what fails with `ZWJ` taken out of the sweep.
    #[test]
    fn a_joiner_between_named_emoji_is_still_consumed() {
        assert_eq!(demojize_rust("\u{1F468}\u{200D}\u{1F3FB}", false), "man");
        assert_eq!(
            demojize_rust("\u{1F468}\u{200D}\u{1F468}", false),
            "man man"
        );
        assert_eq!(
            demojize_rust("\u{1F468}\u{200D}\u{1F468}\u{200D}\u{1F468}", false),
            "man man man"
        );
        // A named sequence is matched whole, so the sweep never sees its joiners.
        assert_eq!(
            demojize_rust("\u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467}", false),
            "family: man, woman, girl"
        );
    }

    /// `HEAD_LOOKAHEAD` is the number `head_len_at` actually needs (#995).
    ///
    /// The fast path in `CharWindow::presentation_len` rests on this: a `None` from a
    /// slice at least this long cannot become a `Some` when more input arrives, so a
    /// joiner that far from the edge has been disproved rather than merely unjudged.
    /// Asserted by exhaustion over everything the head arms branch on, rather than by
    /// reading the function and counting — the reading is how the constant rots.
    #[test]
    fn head_lookahead_is_enough() {
        let alphabet = [
            '\u{1F525}', // emoji presentation
            '\u{00A9}',  // Emoji=Yes, presentation No — needs a following VS16
            VS16,
            VS15,
            '\u{1F3FB}', // skin tone
            ZWJ,
            '1', // keycap base
            KEYCAP,
            '\u{1F1EC}', // regional indicator
            '\u{E0061}', // tag
            'a',
        ];
        let mut window = Vec::new();
        let probe = |window: &[char]| {
            if window.len() < HEAD_LOOKAHEAD || head_len_at(window).is_some() {
                return;
            }
            // A `None` this far from the end must survive anything appended to it.
            for &extra in &alphabet {
                for &more in &alphabet {
                    let mut longer = window.to_vec();
                    longer.push(extra);
                    longer.push(more);
                    assert_eq!(
                        head_len_at(&longer),
                        None,
                        "{window:?} answered None with {} chars, then Some once \
                         {extra:?}{more:?} followed — HEAD_LOOKAHEAD is too small",
                        window.len()
                    );
                }
            }
        };
        for &a in &alphabet {
            window.push(a);
            probe(&window);
            for &b in &alphabet {
                window.push(b);
                probe(&window);
                for &c in &alphabet {
                    window.push(c);
                    probe(&window);
                    window.pop();
                }
                window.pop();
            }
            window.pop();
        }
    }

    /// The window agrees with a scanner that can see the whole input (#995).
    ///
    /// `CharWindow` exists so the scanner never materialises its input, and everything
    /// subtle here comes from that: what the window can prove, what it must read ahead
    /// for, and what it has to hand back afterwards. The predicate deciding it has been
    /// wrong twice — once too narrow, splitting real sequences, once too broad, reading
    /// ahead for matches already finished — so it is gated against the thing it is an
    /// optimisation of: the same match with the whole input in hand.
    #[test]
    fn the_window_agrees_with_an_unbounded_scanner() {
        fn oracle(text: &str, replacement: &str) -> String {
            let chars: Vec<char> = text.chars().collect();
            let mut out = String::new();
            let mut i = 0;
            while i < chars.len() {
                if let Some(n) = presentation_len_at(&chars[i..]) {
                    out.push_str(replacement);
                    i += n;
                    // The seam rule, stated over the whole input rather than the window.
                    // A mark binds if a head starting one or two characters back in the
                    // output reaches past it.
                    while let Some(&mark) = chars.get(i) {
                        let tail: Vec<char> = out.chars().rev().take(2).collect();
                        let binds = matches!(mark, VS15 | VS16 | KEYCAP)
                            && (1..=tail.len()).any(|back| {
                                let seam: Vec<char> = tail[..back]
                                    .iter()
                                    .rev()
                                    .copied()
                                    .chain(chars[i..].iter().copied().take(3 - back))
                                    .collect();
                                head_len_at(&seam).is_some_and(|len| len > back)
                            });
                        if !binds {
                            break;
                        }
                        i += 1;
                    }
                } else {
                    out.push(chars[i]);
                    i += 1;
                }
            }
            out
        }

        // Everything the window branches on, joiners over-weighted so chains get long.
        let alphabet = [
            '\u{1F525}',
            '\u{1F468}',
            '\u{00A9}',
            VS16,
            VS15,
            '\u{1F3FB}',
            ZWJ,
            ZWJ,
            ZWJ,
            '1',
            KEYCAP,
            '\u{1F1EC}',
            '\u{1F1E7}',
            '\u{E0061}',
            'a',
            ' ',
        ];
        let mut state = 0x9E37_79B9_7F4A_7C15u64;
        for _ in 0..120_000 {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            let len = 1 + (state % 40) as usize;
            let mut probe = String::new();
            let mut bits = state;
            for _ in 0..len {
                bits = bits.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(1);
                probe.push(alphabet[(bits >> 33) as usize % alphabet.len()]);
            }
            for replacement in ["", " ", "[x]"] {
                assert_eq!(
                    demojize_rust_replace(&probe, replacement),
                    oracle(&probe, replacement),
                    "{probe:?} replacement={replacement:?}"
                );
            }
        }
    }

    /// Following a chain must not recurse: input decides the depth (#995).
    ///
    /// `presentation_len_at` recursed once per link. While the slice was capped at
    /// `MAX_WINDOW` that bounded the depth at nine by accident; once the window follows a
    /// sequence past its edge, the depth is whatever the input says, and a long enough
    /// chain overflows the stack — a hard abort, not a catchable error, on attacker
    /// input. A sanitiser cannot have that.
    #[test]
    fn a_long_chain_does_not_recurse() {
        let chain: String = std::iter::repeat_n("\u{1F468}", 100_000)
            .collect::<Vec<_>>()
            .join("\u{200D}");
        assert_eq!(demojize_rust_replace(&chain, ""), "");
        assert_eq!(demojize_rust_replace(&chain, "x"), "x");
    }

    /// Ordinary emoji must not take the growable path (#995).
    ///
    /// The match can only continue past the window when it reached the edge or stopped
    /// at a joiner. Anything else is finished, whatever the buffer's fill. Keying the
    /// decision on fullness instead sent every emoji in any input longer than the window
    /// through a heap scan. `pushback` is the tell: the growable path always peeks past
    /// the buffer, the fast path never does.
    #[test]
    fn an_ordinary_emoji_never_peeks_past_the_window() {
        for text in [
            "\u{1F525}aaaaaaaaaaaaaaaaaaaaaaaa",
            "aaaa\u{1F525}aaaaaaaaaaaaaaaaaaaa",
            "\u{1F44D}\u{1F3FD}aaaaaaaaaaaaaaaaaaaa",
            "\u{1F1EC}\u{1F1E7}aaaaaaaaaaaaaaaaaaaa",
            "1\u{FE0F}\u{20E3}aaaaaaaaaaaaaaaaaaaa",
            // A joiner the chain loop has already disproved: the char after it is in
            // the window, so no more input can make it part of the sequence.
            "\u{1F525}\u{200D}aaaaaaaaaaaaaaaaaaaa",
            "\u{1F525}\u{200D}\u{200D}aaaaaaaaaaaaaaaaaa",
        ] {
            let mut win = CharWindow::new(text.chars());
            while win.current().is_some() {
                let n = win.presentation_len();
                assert!(
                    win.pushback.is_empty(),
                    "{text:?} took the growable path for a finished match"
                );
                win.advance(n.unwrap_or(1));
            }
        }
    }

    /// A sequence longer than the window is still one sequence (#995).
    ///
    /// `MAX_WINDOW` is `max_emoji_seq_len()` — the longest run the CLDR *name* table
    /// holds. Naming cannot need more than that; replacing can, because
    /// `presentation_len_at` follows a ZWJ chain the UCD allows to be any length. A
    /// family of four with skin tones is a valid eleven-code-point ZWJ sequence, though
    /// not an RGI one; the kiss below is RGI at ten.
    /// A removal must not leave a mark that binds to what precedes it: that is an emoji
    /// the input never had, and a second pass would take the caller's digit with it.
    #[test]
    fn a_removal_manufactures_no_emoji_at_the_seam() {
        for (text, want) in [
            ("1\u{1F600}\u{20E3}", "1"),
            ("\u{263A}1\u{20E3}\u{FE0F}", "\u{263A}"),
            ("\u{00A9}\u{1F1EC}\u{1F1E7}\u{FE0F}", "\u{00A9}"),
            ("1\u{1F1EC}\u{1F1E7}\u{FE0F}\u{20E3}", "1"),
        ] {
            let once = demojize_rust_replace(text, "");
            assert_eq!(once, want, "{text:?}");
            assert_eq!(demojize_rust_replace(&once, ""), once, "not a fixed point");
        }
        // A mark that joins nothing is still text (#996).
        assert_eq!(
            demojize_rust_replace("1\u{1F600}\u{20E3}", " "),
            "1 \u{20E3}"
        );
        assert_eq!(demojize_rust_replace("a\u{1F600}\u{20E3}", ""), "a\u{20E3}");
        assert_eq!(demojize_rust_replace("a\u{1F600}\u{20E3}", "#"), "a#");
        // The pure-Rust demojize drops what it cannot name, which opens the same seam.
        let once = demojize_rust("x9\u{E0041}\u{20E3}", false);
        assert_eq!(once, "x9");
        assert_eq!(demojize_rust(&once, false), once);
    }

    #[test]
    fn a_sequence_longer_than_the_window_is_still_one_sequence() {
        // U+1F468 U+1F3FB ZWJ U+1F469 U+1F3FB ZWJ U+1F467 U+1F3FB ZWJ U+1F466 U+1F3FB
        let family = "\u{1F468}\u{1F3FB}\u{200D}\u{1F469}\u{1F3FB}\u{200D}\
                      \u{1F467}\u{1F3FB}\u{200D}\u{1F466}\u{1F3FB}";
        assert_eq!(family.chars().count(), 11);
        assert_eq!(demojize_rust_replace(family, " "), " ");
        assert_eq!(demojize_rust_replace(family, ""), "");

        // The kiss sequence: ten code points, and RGI.
        let kiss = "\u{1F468}\u{1F3FB}\u{200D}\u{2764}\u{FE0F}\u{200D}\
                    \u{1F48B}\u{200D}\u{1F468}\u{1F3FB}";
        assert_eq!(kiss.chars().count(), 10);
        assert_eq!(demojize_rust_replace(kiss, " "), " ");
    }

    /// Whatever the peek pulled and did not use must come back (#995).
    ///
    /// Following a sequence past the window reads ahead. Those chars have already left
    /// the iterator, so counting them again when the window advances drops them — the
    /// trailing `b` here vanished on the first draft of the fix, and no test above saw
    /// it because none put text after a long sequence.
    #[test]
    fn text_after_a_sequence_longer_than_the_window_survives() {
        let family = "\u{1F468}\u{1F3FB}\u{200D}\u{1F469}\u{1F3FB}\u{200D}\
                      \u{1F467}\u{1F3FB}\u{200D}\u{1F466}\u{1F3FB}";
        assert_eq!(demojize_rust_replace(&format!("a{family}b"), " "), "a b");
        assert_eq!(demojize_rust_replace(&format!("{family}tail"), ""), "tail");
        assert_eq!(
            demojize_rust_replace(&format!("x{family}y{family}z"), ""),
            "xyz"
        );
        // A dangling joiner after a long sequence is still not part of it.
        let dangling = format!("{family}\u{200D}");
        assert_eq!(demojize_rust_replace(&dangling, ""), "\u{200D}");
    }

    /// The window edge must not leave an invisible character behind (#995).
    ///
    /// This is the half that matters: splitting a sequence emitted two replacements,
    /// which is wrong but visible, *and* passed the joiner at the seam through as
    /// ordinary text — a `U+200D` surviving the step whose job is removing emoji, in a
    /// library whose whole subject is invisible characters.
    #[test]
    fn no_joiner_survives_a_sequence_of_any_length() {
        for links in 1..=12usize {
            let chain: String = std::iter::repeat_n("\u{1F468}", links)
                .collect::<Vec<_>>()
                .join("\u{200D}");
            let out = demojize_rust_replace(&chain, "");
            assert!(
                !out.contains('\u{200D}'),
                "{links} links left a joiner: {out:?}"
            );
            assert_eq!(out, "", "{links} links");
        }
    }

    /// Removing emoji twice is removing them once.
    #[test]
    fn replacement_reaches_a_fixed_point() {
        for cp in (0x1F300u32..=0x1FAFF).chain(0x2600..=0x27BF) {
            let Some(c) = char::from_u32(cp) else {
                continue;
            };
            let s = format!("aa{c}bb");
            let once = demojize_rust_replace(&s, "");
            assert_eq!(demojize_rust_replace(&once, ""), once, "U+{cp:04X}");
        }
    }

    #[test]
    fn test_encode_key_single() {
        // #112: encode_key_into now writes into a stack [u8; KEY_BUF_CAP].
        let mut buf = [0u8; KEY_BUF_CAP];
        let n = encode_key_into(&mut buf, &['\u{1F600}']);
        assert_eq!(std::str::from_utf8(&buf[..n]).unwrap(), "1F600");
    }

    #[test]
    fn test_encode_key_multi() {
        let mut buf = [0u8; KEY_BUF_CAP];
        let n = encode_key_into(&mut buf, &['\u{1F468}', ZWJ, '\u{1F469}']);
        assert_eq!(std::str::from_utf8(&buf[..n]).unwrap(), "1F468_200D_1F469");
    }

    /// Decode an `EMOJI_MULTI` hex-underscore key into its code-point sequence.
    fn key_to_chars(key: &str) -> Vec<char> {
        key.split('_')
            .map(|h| char::from_u32(u32::from_str_radix(h, 16).unwrap()).unwrap())
            .collect()
    }

    /// #242 item 4: the production trie matcher must be byte-identical to the
    /// retained hex-key PHF reference on every multi-codepoint sequence — and
    /// on windows that overrun a sequence (extra trailing char) or chain two
    /// sequences, which exercise the longest-match/terminal-skip boundaries.
    #[test]
    fn emoji_trie_matches_reference() {
        let keys: Vec<&str> = crate::tables::emoji_data::EMOJI_MULTI
            .keys()
            .copied()
            .collect();
        assert!(keys.len() > 2000, "expected the full multi-emoji table");

        for key in &keys {
            let seq = key_to_chars(key);

            // Exact sequence.
            assert_eq!(
                match_emoji_at(&seq),
                match_emoji_at_reference(&seq),
                "trie/reference disagree on key {key}"
            );

            // Sequence + a non-emoji char (longest match must stop at the seq).
            let mut padded = seq.clone();
            padded.push('x');
            assert_eq!(
                match_emoji_at(&padded),
                match_emoji_at_reference(&padded),
                "trie/reference disagree on padded key {key}"
            );

            // Sequence chained with another sequence (overrun beyond a terminal).
            let mut chained = seq.clone();
            chained.extend(key_to_chars(keys[0]));
            assert_eq!(
                match_emoji_at(&chained),
                match_emoji_at_reference(&chained),
                "trie/reference disagree on chained key {key}"
            );
        }
    }

    /// #990: the unknown-emoji branch asks the UCD, not a block range.
    ///
    /// `is_emoji_codepoint` still answers for `\u{2606}` — it is a deliberately loose
    /// fast-path superset and keeps its block shape. What must not is the branch that
    /// decides whether `demojize` rewrites a character, which is `presentation_len_at`.
    #[test]
    fn unknown_emoji_branch_ignores_non_emoji_in_emoji_blocks() {
        for ch in ['\u{2606}', '\u{2613}', '\u{2605}', '\u{2295}'] {
            assert_eq!(
                unnamed_emoji_len_at(&[ch]),
                None,
                "U+{:04X} carries no emoji presentation and must not reach the \
                 unknown-emoji branch",
                ch as u32
            );
        }
        // And the block predicate still claims them, which is why asking it was wrong.
        assert!(is_emoji_codepoint('\u{2606}'));
    }

    /// #990 narrowed what reaches the unknown branch; it did not change what happens
    /// there. An emoji this scanner cannot name is still dropped, and so is a lone
    /// Plane 14 tag — the only coverage of that block `ml_normalize` has (#914).
    #[test]
    fn the_pure_rust_scanner_drops_only_what_is_an_emoji_or_a_tag() {
        // A lone regional indicator is `Emoji_Presentation=Yes` and CLDR names no
        // single one of them, so it is the shape the branch exists for.
        assert_eq!(demojize_rust("x\u{1F1E6}y", false), "xy");
        // A lone TAG character, which `ml_normalize` relies on this branch to remove.
        assert_eq!(demojize_rust("x\u{E0061}y", false), "xy");
        // And a character that is not an emoji at all now travels through untouched.
        assert_eq!(demojize_rust("a\u{2606}b", false), "a\u{2606}b");
    }

    /// A selector asks for emoji presentation; it does not make an unnamed symbol an
    /// unnamed *emoji*. Before this, `\u{00A9}\u{FE0F}` reached the drop branch and the
    /// copyright sign went with it, as did a named emoji joined after it.
    #[test]
    fn a_selector_does_not_send_an_unnamed_symbol_to_the_drop_branch() {
        for base in ['\u{00A9}', '\u{00AE}', '\u{2388}', '\u{2605}', '\u{1FC00}'] {
            assert_eq!(
                unnamed_emoji_len_at(&[base, VS16]),
                None,
                "U+{:04X} + FE0F",
                base as u32
            );
            let input = format!("a{base}\u{FE0F}b");
            assert_eq!(demojize_rust(&input, false), format!("a{base}b"));
        }
        // `replace_emoji` still counts it as the emoji presentation sequence it is.
        assert_eq!(presentation_len_at(&['\u{00A9}', VS16]), Some(2));
        // The named emoji at the end of a chain opened by one keeps its name.
        let out = demojize_rust("a\u{00A9}\u{FE0F}\u{200D}\u{1F525}b", false);
        assert!(out.contains('\u{00A9}') && out.contains("fire"), "{out:?}");
        // What the branch is for still reaches it.
        assert_eq!(unnamed_emoji_len_at(&['\u{1F1E6}']), Some(1));
        assert_eq!(unnamed_emoji_len_at(&['\u{E0061}']), Some(1));
    }

    /// The window holds the fully qualified form of every key: a U+FE0F after every
    /// component that is not a joiner, a skin tone, a tag or a keycap mark. The table
    /// stores keys unqualified, and a sequence cut at the window edge is named in pieces.
    #[test]
    fn a_fully_qualified_key_fits() {
        let longest = include_str!("tables/data/emoji_multi.tsv")
            .lines()
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
            .map(|l| {
                let key = l.split('\t').next().unwrap_or_default();
                key.split('_').count() * 2
            })
            .max()
            .unwrap_or_default();
        assert!(longest <= MAX_WINDOW, "{longest} > {MAX_WINDOW}");
        // And the named case the model found, whole, from the fully qualified form.
        let kiss =
            "\u{1F468}\u{1F3FB}\u{200D}\u{2764}\u{FE0F}\u{200D}\u{1F48B}\u{200D}\u{1F468}\u{1F3FB}";
        assert_eq!(
            demojize_rust(kiss, false),
            demojize_rust(&kiss.replace('\u{FE0F}', ""), false)
        );
        assert_eq!(
            demojize_rust("\u{2764}\u{FE0F}\u{200D}\u{1F525}", false),
            "heart on fire"
        );
    }

    /// The selector rule, class by class (Copilot review on #1015).
    #[test]
    fn a_selector_follows_only_an_emoji_base() {
        for base in [
            '\u{2764}',
            '\u{1F3F3}',
            '1',
            '#',
            '*',
            '\u{00A9}',
            '\u{1F468}',
        ] {
            assert!(tables::selector_may_follow(base), "{base:?}");
        }
        for not_base in [
            '\u{200D}',
            '\u{FE0E}',
            '\u{FE0F}',
            '\u{20E3}',
            '\u{1F1E6}',
            '\u{1F1FF}',
            '\u{1F3FB}',
            '\u{1F3FF}',
            '\u{E0067}',
            'a',
            '\u{20AC}',
        ] {
            assert!(!tables::selector_may_follow(not_base), "{not_base:?}");
        }
    }

    #[test]
    fn test_is_emoji_codepoint() {
        assert!(is_emoji_codepoint('\u{1F600}'));
        assert!(is_emoji_codepoint('\u{2600}'));
        assert!(!is_emoji_codepoint('A'));
        assert!(!is_emoji_codepoint('€'));
    }

    #[test]
    fn test_is_emoji_modifier() {
        assert!(is_emoji_modifier(ZWJ)); // ZWJ
        assert!(is_emoji_modifier(VS16)); // VS16
        assert!(is_emoji_modifier('\u{1F3FB}')); // Light skin tone
        assert!(!is_emoji_modifier('A'));
    }

    #[test]
    fn test_match_single_emoji() {
        // #113: match_emoji_at now takes a window slice (pos=0 is always current).
        let chars: Vec<char> = "😀".chars().collect();
        let result = match_emoji_at(&chars);
        assert!(result.is_some());
        let (name, consumed) = result.unwrap();
        assert_eq!(name, "grinning face");
        assert_eq!(consumed, 1);
    }

    #[test]
    fn test_demojize_rust_basic() {
        let result = demojize_rust("Hello 😀 world", false);
        assert_eq!(result, "Hello grinning face world");
    }

    #[test]
    fn test_demojize_rust_no_emoji() {
        let result = demojize_rust("Hello world", false);
        assert_eq!(result, "Hello world");
    }

    #[test]
    fn test_demojize_rust_multiple() {
        let result = demojize_rust("😀😂", false);
        assert_eq!(result, "grinning face face with tears of joy");
    }

    #[test]
    fn test_demojize_rust_empty() {
        assert_eq!(demojize_rust("", false), "");
    }
}
