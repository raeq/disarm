//! Compose-only "local NFC" at lookup time (#475 / #477).
//!
//! The confusables and transliteration tables are keyed per code point on the
//! *precomposed* form (`ї` U+0457 → …), so a *decomposed* input (`і` U+0456 +
//! combining diaeresis U+0308) never reaches the entry — the base maps and the mark
//! survives, which lets an attacker evade the fold/romanization by decomposing.
//!
//! Fixing this by normalizing the whole input to NFC is wrong: NFC also *decomposes*
//! composition-excluded singletons (Hebrew presentation forms like `שׂ` U+FB2B), which
//! destroys their precomposed table entry, and it changes character counts. Instead,
//! [`composed`] makes only the *lookup* form-complete: it canonically composes each
//! base + combining-mark cluster (compose-only, never decompose) so any normal form
//! reaches the same precomposed entry, while
//!
//! * a starter **not** followed by a combining mark (ASCII, CJK, a lone precomposed
//!   `שׂ`) is yielded verbatim — the hot path pays one combining-class check per char,
//!   in the spirit of the #458 guard;
//! * a composition-**excluded** pair (`ש` + sin dot) stays decomposed, because NFC
//!   does not recompose it — so today's output is preserved with no exclusion list;
//! * the **whole** cluster is composed (canonical order, multi-mark): Vietnamese `ệ`
//!   (base + two marks) and polytonic Greek `ᾷ` reach their precomposed scalar.

use std::collections::VecDeque;

use unicode_normalization::char::{canonical_combining_class, is_combining_mark};
use unicode_normalization::UnicodeNormalization;

/// Iterate `text` yielding `(char, byte_offset)` with each base+mark cluster locally
/// NFC-composed. `byte_offset` is the start of the cluster (or the char) in the
/// original `text` — for diagnostics like `find_untranslatable`. See the module docs.
pub(crate) fn composed(text: &str) -> Composed<'_> {
    Composed {
        text,
        iter: text.char_indices().peekable(),
        pending: VecDeque::new(),
    }
}

/// Apply [`composed`] over the whole string: a borrowed `Cow` when `text` has no
/// combining mark (nothing can compose — the ASCII / common case pays one scan), an
/// owned, cluster-composed string otherwise. This is "local NFC on each grapheme
/// cluster": it lets a per-code-point engine see the precomposed form without ever
/// decomposing a composition-excluded singleton.
pub(crate) fn compose_str(text: &str) -> std::borrow::Cow<'_, str> {
    if has_combining_mark(text) {
        std::borrow::Cow::Owned(composed(text).map(|(c, _)| c).collect())
    } else {
        std::borrow::Cow::Borrowed(text)
    }
}

/// True if `text` contains a combining mark (General_Category=Mark) — the cheap gate
/// that decides whether [`composed`] can change anything. Tests category, not ccc, so
/// it also catches the spacing marks (Mc) in Brahmic two-part vowels. Mark-free input
/// (ASCII, CJK, lone precomposed letters) takes a borrow/identity fast path instead.
pub(crate) fn has_combining_mark(text: &str) -> bool {
    text.chars().any(is_combining_mark)
}

pub(crate) struct Composed<'a> {
    text: &'a str,
    iter: std::iter::Peekable<std::str::CharIndices<'a>>,
    /// Chars of a composed cluster's NFC result, waiting to be yielded.
    pending: VecDeque<(char, usize)>,
}

impl Iterator for Composed<'_> {
    type Item = (char, usize);

    fn next(&mut self) -> Option<Self::Item> {
        if let Some(item) = self.pending.pop_front() {
            return Some(item);
        }
        let (start, ch) = self.iter.next()?;

        // Gate: a *reordering* leading mark (ccc != 0 with no base before it) is yielded
        // verbatim. Otherwise the char anchors a cluster iff it is followed by a
        // combining mark. The follower test is General_Category=Mark, not ccc != 0:
        // Brahmic two-part vowels compose a base with a *spacing* mark (Mc, ccc == 0)
        // — e.g. Bengali `ো` U+09CB = U+09C7 + U+09BE — which a ccc test would miss.
        // A starter with no following mark (ASCII / CJK / a lone precomposed letter or
        // presentation form) falls through to a verbatim yield, the hot path.
        if canonical_combining_class(ch) != 0 {
            return Some((ch, start));
        }
        let next_is_mark = self.iter.peek().is_some_and(|&(_, c)| is_combining_mark(c));
        if !next_is_mark {
            return Some((ch, start));
        }

        // Collect the cluster: anchor + the run of following combining marks.
        let mut end = start + ch.len_utf8();
        while let Some(&(j, c)) = self.iter.peek() {
            if !is_combining_mark(c) {
                break;
            }
            end = j + c.len_utf8();
            self.iter.next();
        }

        // Local NFC composes the cluster (canonical order, full multi-mark, exclusions
        // left decomposed). Offsets collapse to the cluster start — exact enough for
        // diagnostics, and the common single-mark cluster yields one char anyway.
        for c in self.text[start..end].nfc() {
            self.pending.push_back((c, start));
        }
        self.pending.pop_front()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn chars(text: &str) -> Vec<char> {
        composed(text).map(|(c, _)| c).collect()
    }

    #[test]
    fn ascii_and_mark_free_pass_through_verbatim() {
        assert_eq!(chars("abc 123"), "abc 123".chars().collect::<Vec<_>>());
        assert_eq!(chars("日本語"), vec!['日', '本', '語']);
        // a lone precomposed char with no following mark is untouched
        assert_eq!(chars("\u{0457}"), vec!['\u{0457}']); // precomposed ї
    }

    #[test]
    fn decomposed_homoglyph_composes_to_precomposed() {
        // і (U+0456) + combining diaeresis (U+0308) → ї (U+0457)
        assert_eq!(chars("\u{0456}\u{0308}"), vec!['\u{0457}']);
        // embedded in text, offsets preserved at the cluster start
        // bytes: a@0, і@1 (2B), ◌̈@3 (2B), b@5 — composed ї keeps the cluster start.
        let got: Vec<_> = composed("a\u{0456}\u{0308}b").collect();
        assert_eq!(got, vec![('a', 0), ('\u{0457}', 1), ('b', 5)]);
    }

    #[test]
    fn multi_mark_clusters_compose_fully() {
        // Vietnamese ệ = e + ◌̣ (U+0323, ccc 220) + ◌̂ (U+0302, ccc 230) → U+1EC7
        assert_eq!(chars("e\u{0323}\u{0302}"), vec!['\u{1EC7}']);
        // …in the other input order too (canonical reordering happens inside NFC)
        assert_eq!(chars("e\u{0302}\u{0323}"), vec!['\u{1EC7}']);
        // polytonic Greek ᾷ (U+1FB7) = α + ◌̃-ish marks → precomposed
        assert_eq!(chars("\u{03B1}\u{0342}\u{0345}"), vec!['\u{1FB7}']);
    }

    #[test]
    fn brahmic_two_part_vowels_compose_via_spacing_marks() {
        // Bengali O (U+09CB) = E (U+09C7) + AA (U+09BE) — both spacing marks (Mc,
        // ccc 0). A ccc-only gate misses these; the category=Mark gate composes them.
        assert_eq!(chars("\u{09C7}\u{09BE}"), vec!['\u{09CB}']);
        // Tamil AU (U+0B94) = O (U+0B92, a *letter* base) + AU length mark (U+0BD7).
        assert_eq!(chars("\u{0B92}\u{0BD7}"), vec!['\u{0B94}']);
        // Kannada OO (U+0CCB) = E (U+0CC6) + UU (U+0CC2) + length mark (U+0CD5).
        assert_eq!(chars("\u{0CC6}\u{0CC2}\u{0CD5}"), vec!['\u{0CCB}']);
    }

    #[test]
    fn composition_excluded_pairs_stay_decomposed() {
        // ש (U+05E9) + sin dot (U+05C2) is composition-excluded → NOT recomposed to
        // U+FB2B; it stays as the base + mark, exactly today's behaviour.
        assert_eq!(chars("\u{05E9}\u{05C2}"), vec!['\u{05E9}', '\u{05C2}']);
        // the precomposed presentation form, with no following mark, is left intact.
        assert_eq!(chars("\u{FB2B}"), vec!['\u{FB2B}']);

        // Same phenomenon, different script — and the residual the #479-review oracle
        // could not see: Devanagari QA (U+0958) canonically decomposes to KA (U+0915) +
        // nukta (U+093C) and is composition-excluded, so compose-only leaves the cluster
        // decomposed. It does NOT reconstruct QA. Downstream this is exactly why
        // `transliterate(KA + nukta)` degrades to "ka", where raw `क़` U+0958 → "qa":
        // recovering an excluded singleton from its decomposition is what we must not do.
        assert_eq!(chars("\u{0915}\u{093C}"), vec!['\u{0915}', '\u{093C}']);
    }

    #[test]
    fn compose_str_borrows_mark_free_and_owns_composed() {
        use std::borrow::Cow;
        // mark-free input borrows (no allocation, identity)
        assert!(matches!(compose_str("hello"), Cow::Borrowed("hello")));
        assert!(matches!(compose_str("\u{FB2B}"), Cow::Borrowed(_))); // lone שׂ, no mark
                                                                      // mark-bearing input is composed into an owned string
        assert_eq!(compose_str("\u{0456}\u{0308}"), "\u{0457}"); // і+◌̈ → ї
        assert_eq!(compose_str("e\u{0323}\u{0302}"), "\u{1EC7}"); // ệ
                                                                  // excluded base+mark stays decomposed, but still owned (a mark was present)
        assert_eq!(compose_str("\u{05E9}\u{05C2}"), "\u{05E9}\u{05C2}");
    }

    #[test]
    fn legitimate_accents_recompose_unchanged() {
        // café decomposed (e + ◌́) recomposes to é — a no-op for already-NFC callers.
        assert_eq!(chars("cafe\u{0301}"), vec!['c', 'a', 'f', 'é']);
    }
}
