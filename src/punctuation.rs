//! Typographic punctuation folded to its ASCII spelling (#703).
//!
//! Nothing else in disarm does this as a stated purpose, and the two functions that come
//! closest disagree with each other on the dash family in a way that is accidental:
//! `canonicalize` folds five dashes and skips `U+2014 EM DASH` and `U+2015 HORIZONTAL BAR`;
//! `transliterate` folds those two and rejects the other four. A key built from
//! `canonicalize` treats `a—b` and `a-b` as distinct while treating `a–b` and `a-b` as the
//! same, and both dashes are the same substitution performed by the same autocorrect.
//!
//! A separate primitive rather than a change to either function. `canonicalize` is a
//! security fold and entitled to map `“` to `''` — a confusable *skeleton* for a double
//! quote and a poor *replacement* for one — which is exactly why the typographic fold does
//! not belong on it.
//!
//! **Deliberately not covered.** `U+3002 IDEOGRAPHIC FULL STOP` and `U+060C ARABIC COMMA`
//! are the full stop and comma of those writing systems, not stylised ASCII; the middle
//! dot `U+00B7` is a letter in Catalan `l·l`; the bullet and the other punctuation ordinary
//! in prose and slides stay. The obvious hand-rolled table gets the first of these wrong.
//!
//! Spaces fold rather than delete, matching what `strip_format` and `canonicalize` already
//! do for `U+00A0`, so words do not glue together.

use std::borrow::Cow;

/// The ASCII spelling of a typographic code point, or `None` for everything else.
///
/// One table, kept in one place, so the coverage the module doc states is the coverage
/// the code has.
#[inline]
fn ascii_for(c: char) -> Option<&'static str> {
    Some(match c {
        // The dash family, and the minus sign: every one is the same autocorrect.
        '\u{2010}' | '\u{2011}' | '\u{2012}' | '\u{2013}' | '\u{2014}' | '\u{2015}'
        | '\u{2212}' => "-",
        // Single quotes: the curly pair, the low-9 form, and the prime.
        '\u{2018}' | '\u{2019}' | '\u{201A}' | '\u{2032}' => "'",
        // Double quotes: the curly pair, the low-9 form, and the double prime.
        '\u{201C}' | '\u{201D}' | '\u{201E}' | '\u{2033}' => "\"",
        '\u{2026}' => "...",
        // The non-standard spaces, folded to a space rather than deleted.
        '\u{00A0}' | '\u{2000}'..='\u{200A}' | '\u{202F}' | '\u{205F}' | '\u{3000}' => " ",
        _ => return None,
    })
}

/// Fold typographic punctuation to its ASCII spelling (#703). Borrows when there is
/// nothing to fold, which is the common case.
pub(crate) fn fold_punctuation(text: &str) -> Cow<'_, str> {
    let Some(first) = text.char_indices().find(|&(_, c)| ascii_for(c).is_some()) else {
        return Cow::Borrowed(text);
    };
    let mut out = String::with_capacity(text.len() + 2);
    out.push_str(&text[..first.0]);
    for c in text[first.0..].chars() {
        match ascii_for(c) {
            Some(ascii) => out.push_str(ascii),
            None => out.push(c),
        }
    }
    Cow::Owned(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_dash_family_is_one_character() {
        for c in [
            '\u{2010}', '\u{2011}', '\u{2012}', '\u{2013}', '\u{2014}', '\u{2015}', '\u{2212}',
        ] {
            assert_eq!(
                fold_punctuation(&format!("a{c}b")),
                "a-b",
                "U+{:04X}",
                c as u32
            );
        }
    }

    #[test]
    fn quotes_ellipsis_and_spaces() {
        assert_eq!(
            fold_punctuation("He said \u{201C}ok\u{201D}"),
            "He said \"ok\""
        );
        assert_eq!(fold_punctuation("it\u{2019}s"), "it's");
        assert_eq!(fold_punctuation("\u{201E}Ja\u{201C}"), "\"Ja\"");
        assert_eq!(fold_punctuation("5\u{2032} 10\u{2033}"), "5' 10\"");
        assert_eq!(fold_punctuation("wait\u{2026}"), "wait...");
        assert_eq!(fold_punctuation("a\u{00A0}b\u{2009}c\u{3000}d"), "a b c d");
    }

    #[test]
    fn the_non_goals_stay() {
        // CJK and Arabic punctuation are those scripts' own; the middle dot is a letter in
        // Catalan; the bullet is ordinary in prose.
        for text in [
            "a\u{3002}b",
            "a\u{060C}b",
            "l\u{00B7}l",
            "a\u{2022}b",
            "a\u{3001}b",
        ] {
            assert!(
                matches!(fold_punctuation(text), Cow::Borrowed(_)),
                "{text:?}"
            );
        }
    }

    #[test]
    fn ascii_borrows_and_the_fold_is_idempotent() {
        assert!(matches!(
            fold_punctuation("plain - 'text' ..."),
            Cow::Borrowed(_)
        ));
        let once = fold_punctuation("a\u{2014}b \u{201C}q\u{201D}\u{2026}").into_owned();
        assert_eq!(fold_punctuation(&once), once);
    }
}
