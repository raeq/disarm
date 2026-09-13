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
const KEY_BUF_CAP: usize = 64; // MAX_EMOJI_SEQ_LEN(9) × 5 hex + 8 '_' = 53 bytes; 64 is safe
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
    if window.len() >= 3 && window[1] == VS16 && window[2] == KEYCAP {
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
/// lookahead — the maximum the matching engine ever needs.  Characters are
/// consumed from the inner iterator one-by-one; advancing the window shifts
/// buffered chars left and refills from the iterator, requiring no heap
/// allocation regardless of input length.
pub(crate) struct CharWindow<'a> {
    buf: [char; MAX_WINDOW],
    /// Number of valid chars currently in `buf` (always <= MAX_WINDOW).
    len: usize,
    /// Chars pulled past the window while following a sequence longer than it, and not
    /// consumed by the match that pulled them. Refills take from here before `rest`, so
    /// the pull is a peek rather than a read. Empty for every input whose emoji fit the
    /// window, which is every input the CLDR name table can name — see
    /// [`CharWindow::presentation_len`].
    pushback: std::collections::VecDeque<char>,
    rest: std::str::Chars<'a>,
}

/// Window capacity = MAX_EMOJI_SEQ_LEN so we always have enough lookahead.
///
/// Derived from the single source of truth (`tables::max_emoji_seq_len()`, a
/// `const fn` over the build-generated `MAX_EMOJI_SEQ_LEN`) rather than a
/// duplicated literal, so the two cannot drift when the CLDR data updates
/// (#199 review). This also caps the look-ahead a custom Python emoji provider
/// can match; see the provider call site and `set_emoji_provider`.
const MAX_WINDOW: usize = tables::max_emoji_seq_len();

impl<'a> CharWindow<'a> {
    /// Create a new window, pre-filling the buffer from `chars`.
    pub(crate) fn new(mut chars: std::str::Chars<'a>) -> Self {
        let mut buf = ['\0'; MAX_WINDOW];
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
            Some(self.buf[0])
        } else {
            None
        }
    }

    /// A slice of all valid chars in the window (up to MAX_WINDOW chars).
    #[inline]
    pub(crate) fn as_slice(&self) -> &[char] {
        &self.buf[..self.len]
    }

    /// Advance the window by `n` chars.
    ///
    /// Shifts `buf[n..]` to the front, then refills. `n` may exceed the buffer: a match
    /// found by [`CharWindow::presentation_len`] can be longer than the window, and the
    /// chars past it are then dropped a bufferful at a time rather than shifted.
    pub(crate) fn advance(&mut self, mut n: usize) {
        debug_assert!(n > 0);
        while n >= self.len && self.len > 0 {
            n -= self.len;
            self.len = 0;
            self.refill();
            if n == 0 {
                return;
            }
        }
        if self.len == 0 {
            return;
        }
        // Shift remaining buffered chars to the front, then top the buffer back up.
        self.buf.copy_within(n..self.len, 0);
        self.len -= n;
        self.refill();
    }

    /// Fill `buf` from `self.len` up to `MAX_WINDOW`.
    fn refill(&mut self) {
        while self.len < MAX_WINDOW {
            match self.next_char() {
                Some(c) => {
                    self.buf[self.len] = c;
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
    /// bounds naming correctly and replacing not at all: a family of four with skin
    /// tones is eleven code points and RGI. Asking on the bare window cut such a
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
        // one the chain loop abandoned at a joiner because what followed it was not yet
        // in the window. A match that stopped on any other character is done, and no
        // amount of lookahead changes that.
        if len < self.len && self.buf[len] != ZWJ {
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
// `U+FE0F`, and the sequences built on those. That question needs two range tables and
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

/// How many chars of an emoji-presentation sequence start at `window[0]`, if any.
///
/// Returns `None` for anything the UCD does not call an emoji in this position: a keycap
/// base with no keycap after it (`1`, `#`), and an `Emoji=Yes` base with no `U+FE0F`
/// (`\u{00A9}`, `\u{263A}`).
///
/// A regional indicator is `Emoji_Presentation=Yes` on its own, so it returns `Some(1)`;
/// a pair returns `Some(2)`, because a flag is one emoji and must take one replacement.
/// One emoji-presentation *head*: a base and the modifiers bound to it, no ZWJ.
///
/// Split out of [`presentation_len_at`] so following a chain can be a loop instead of a
/// recursion (#995). The recursion descended once per link, which the nine-code-point
/// match window bounded by accident; once the window follows a sequence past its edge the
/// depth is whatever the input says, and a long enough chain overflowed the stack — an
/// abort no caller can catch, on input from outside. Chaining lives in the caller's loop,
/// so nothing here calls anything that calls this.
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
    let opens = opens_emoji_presentation(first) || (vs16_next && tables::is_emoji_property(first));
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
/// Both scanners call this, so the two cannot drift apart on what they rewrite.
pub(crate) fn unnamed_emoji_len_at(window: &[char]) -> Option<usize> {
    presentation_len_at(window).or_else(|| {
        window
            .first()
            .copied()
            .filter(|&c| is_tag(c))
            .map(|_| 1usize)
    })
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
            continue;
        }
        result.push(ch);
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
    result.clear();
    // Fast path: pure-ASCII text cannot contain emoji.
    if text.is_ascii() {
        result.push_str(text);
        return;
    }

    result.reserve(text.len());
    let mut win = CharWindow::new(text.chars());
    let mut last_was_emoji = false;

    while let Some(ch) = win.current() {
        if ch == VS16 || ch == VS15 || ch == ZWJ {
            win.advance(1);
            continue;
        }

        // #614/#757: hand this code point to the rest of the pipeline instead of naming
        // it. Emitted verbatim, so a later `confusables` step still sees it.
        if policy.skips(ch) {
            // The separator decision has to look at what this character will BECOME,
            // not what it is. `\u{20AC}` is not alphanumeric, but TR39 folds it to `e`,
            // so emitting it bare after an emoji name produced `"woman's hat"` + `"e"`
            // -> `"woman's hate"` once the fold ran: a word that was in neither the
            // input nor any name. `\u{2211}` -> `s` and `\u{2200}` -> `a` do the same.
            // Punctuation targets (`\u{2010}` -> `-`) still take no separator, matching
            // how every other non-alphanumeric is emitted here.
            let becomes_alphanumeric = crate::tables::lookup_confusable(ch, "latin")
                .is_some_and(|t| t.starts_with(char::is_alphanumeric));
            if last_was_emoji && (ch.is_alphanumeric() || becomes_alphanumeric) {
                result.push(' ');
            }
            result.push(ch);
            last_was_emoji = false;
            win.advance(1);
            continue;
        }

        if let Some((name, consumed)) = match_emoji_at(win.as_slice()) {
            let replacement = strip_modifier_suffix(name, strip_modifiers);
            pad_emoji_replacement(result, replacement);
            win.advance(consumed);
            while win.current().is_some_and(is_emoji_modifier) {
                win.advance(1);
            }
            last_was_emoji = true;
            continue;
        }

        // An emoji this scanner cannot name, or a lone Plane 14 tag — dropped, as it
        // always has been. What changed in #990 is only *what reaches here*: the test
        // was a block range, so `\u{2606}` WHITE STAR and 776 other characters carrying
        // no emoji property were dropped as emoji the library lacked data for.
        if let Some(consumed) = unnamed_emoji_len_at(win.as_slice()) {
            win.advance(consumed);
            last_was_emoji = false;
            continue;
        }

        if last_was_emoji && ch.is_alphanumeric() {
            result.push(' ');
        }
        result.push(ch);
        last_was_emoji = false;
        win.advance(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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
    /// family of four with skin tones is eleven code points and RGI.
    #[test]
    fn a_sequence_longer_than_the_window_is_still_one_sequence() {
        // U+1F468 U+1F3FB ZWJ U+1F469 U+1F3FB ZWJ U+1F467 U+1F3FB ZWJ U+1F466 U+1F3FB
        let family = "\u{1F468}\u{1F3FB}\u{200D}\u{1F469}\u{1F3FB}\u{200D}\
                      \u{1F467}\u{1F3FB}\u{200D}\u{1F466}\u{1F3FB}";
        assert_eq!(family.chars().count(), 11);
        assert_eq!(demojize_rust_replace(family, " "), " ");
        assert_eq!(demojize_rust_replace(family, ""), "");

        // The kiss sequence: ten code points, also RGI.
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
