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
            rest: chars,
        }
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

    /// Advance the window by `n` chars (1 <= n <= self.len).
    ///
    /// Shifts `buf[n..]` to the front, then refills from the iterator.
    pub(crate) fn advance(&mut self, n: usize) {
        debug_assert!(n > 0 && n <= self.len);
        // Shift remaining buffered chars to the front.
        self.buf.copy_within(n..self.len, 0);
        let remaining = self.len - n;
        // Refill from the iterator.
        let mut fill = remaining;
        while fill < MAX_WINDOW {
            match self.rest.next() {
                Some(c) => {
                    self.buf[fill] = c;
                    fill += 1;
                }
                None => break,
            }
        }
        self.len = fill;
    }
}

/// Check if a codepoint is in an emoji range but not in our data.
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
        // emoji, and carries no RGI emoji property. Skipping it keeps demojize from
        // expanding legacy terminal art into emoji names.
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

    /// The policy every *pipeline* uses: leave the non-emoji CLDR rows for the confusable
    /// fold (#757), and let the fold answer the TR39-claimed rows too where a preset asks
    /// for that separately (#614).
    ///
    /// Named once rather than spelled out at each construction site, because spelling it
    /// out is how `ProfileSpec::build` and `Pipeline::new` came to disagree (#918).
    pub const PRESET: Self = Self {
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

        // Unknown emoji — drop it (Ignore mode)
        if is_emoji_codepoint(ch) {
            win.advance(1);
            while win.current().is_some_and(is_emoji_modifier) {
                win.advance(1);
            }
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
