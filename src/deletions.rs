//! Layer 1 (pure-Rust core): resolve the deletion class — `BS`, `DEL`, and a lone `CR`
//! behind its own flag (#937).
//!
//! Boucher et al., *Bad Characters* (IEEE S&P 2022) §IV-G names four classes of
//! imperceptible perturbation. #934 named the fourth and taught the detector to see it,
//! and recorded resolving it as out of scope: the class is renderer-dependent, so
//! reproducing one renderer's behaviour risked losing text a reader can see.
//!
//! #937 answered that. What an erase removes is **the cell before the control**, and in
//! every row of the paper's released corpus that cell is the attacker's inserted
//! character. Dropping it is the direction `strip_zero_width` already takes. The detector
//! is untouched, so a reader who saw a control picture is still told about it.
//!
//! Measured before this landed: 0 of 51 surface/form pairs recovered any of the three
//! forms, and the model below recovers all of them while changing none of the clean
//! inputs it was checked against.
//!
//! # A cursor over cells, not a stack over code points
//!
//! The obvious implementation — push characters, pop one on `BS` — is wrong twice, and
//! #937 says so about its own first draft:
//!
//! * `X` + `ZWSP` + `BS` leaves the `X`, because the pop removes the zero-width space.
//!   A format character occupies no cell, so the terminal erases the `X`.
//! * `e` + `U+0301` + `BS` leaves the `e` for the same reason. A combining mark joins the
//!   cell before it.
//!
//! So the model tracks cells. A cell is a base character plus whatever attaches to it.

use unicode_normalization::char::is_combining_mark;

/// Whether `ch` advances the cursor.
///
/// A combining mark joins the cell before it and a format character occupies none, so
/// neither advances. The format half is disarm's own predicates rather than a general
/// `Cf` test, and that is **narrower on purpose**: `U+0600`–`U+0605`, `U+06DD` and the
/// Kaithi and Egyptian layout controls are `Cf` and *render*, so they do occupy a cell.
/// [`crate::invisibles::is_default_ignorable_format`] already draws that line and
/// explains it; reusing it means the two cannot disagree.
fn occupies_cell(ch: char) -> bool {
    !(is_combining_mark(ch)
        || crate::invisibles::is_zero_width(ch)
        || crate::invisibles::is_variation_selector(ch)
        || crate::invisibles::is_default_ignorable_format(ch)
        || crate::invisibles::is_tag(ch)
        || crate::scripts::is_bidi_control(ch))
}

const BS: char = '\u{8}';
const DEL: char = '\u{7F}';
const CR: char = '\r';
const LF: char = '\n';

/// Resolve `BS`/`DEL`, and a lone overwriting `CR` when `cr` is set (#937).
///
/// Returns `true` when `out` holds a changed string; `false` leaves `out` untouched and
/// the caller keeps its input, so a string with no erasing control never allocates.
///
/// # `cr` is a separate decision, and defaults off
///
/// `CR` followed by `LF`, or at end of text, is a line ending and passes through either
/// way — the same guard `anomalies::overwriting_cr` applies, so the detector and the
/// resolver cannot disagree about what a line ending is. A `CR` followed by anything else
/// returns the cursor to column 0 and later text overwrites earlier text, which is a
/// rendering-overwrite in a terminal and a **classic Mac OS line ending** in a file from
/// before 2001. The two are byte-identical, so resolving them is the caller's call.
pub(crate) fn resolve_deletions_into(text: &str, cr: bool, out: &mut String) -> bool {
    if !text.chars().any(|c| c == BS || c == DEL || (cr && c == CR)) {
        return false;
    }
    out.clear();
    out.reserve(text.len());
    // `line` holds the current line's cells; a cell is a `String` because a base can carry
    // marks and format characters. `col` is the cursor, which is not `line.len()` once a
    // `CR` has moved it back.
    let mut line: Vec<String> = Vec::new();
    let mut col = 0usize;
    let mut chars = text.chars().peekable();
    while let Some(ch) = chars.next() {
        if ch == BS || ch == DEL {
            col = col.saturating_sub(1);
            line.truncate(col);
        } else if ch == LF || (ch == CR && (!cr || chars.peek().is_none_or(|&n| n == LF))) {
            for cell in line.drain(..) {
                out.push_str(&cell);
            }
            out.push(ch);
            col = 0;
        } else if ch == CR {
            // Only reachable with `cr` set: the cursor returns, the line does not clear.
            col = 0;
        } else if !occupies_cell(ch) && col > 0 {
            line[col - 1].push(ch);
        } else if col < line.len() {
            line[col] = ch.to_string();
            col += 1;
        } else {
            line.push(ch.to_string());
            col += 1;
        }
    }
    for cell in line {
        out.push_str(&cell);
    }
    // `true` means CHANGED, not "the scan ran". Under `cr` the pre-check fires on any
    // `CR`, including the `CRLF` and end-of-text ones this deliberately passes through, so
    // the answer is not known until the output exists (caught in review on #941).
    // Comparing here rather than pre-testing which `CR`s overwrite keeps one copy of that
    // rule — the loop's — instead of a second that can drift from it.
    out != text
}

#[cfg(test)]
mod tests {
    use super::*;

    fn resolve(s: &str, cr: bool) -> String {
        let mut out = String::new();
        if resolve_deletions_into(s, cr, &mut out) {
            out
        } else {
            s.to_owned()
        }
    }

    /// The paper's §VI-A construction: one printable character, then BKSP.
    #[test]
    fn the_attack_construction_resolves_to_the_clean_word() {
        let attack: String = "paypal".chars().flat_map(|c| [c, 'X', BS]).collect();
        assert_eq!(resolve(&attack, false), "paypal");
        let with_del: String = "paypal".chars().flat_map(|c| [c, 'X', DEL]).collect();
        assert_eq!(resolve(&with_del, false), "paypal");
    }

    /// The two branches a stack over code points gets wrong (#937's own first draft).
    #[test]
    fn a_format_character_and_a_mark_occupy_no_cell() {
        assert_eq!(
            resolve("X\u{200B}\u{8}", false),
            "",
            "ZWSP joins the X's cell"
        );
        assert_eq!(
            resolve("e\u{301}\u{8}", false),
            "",
            "the mark joins the e's cell"
        );
        assert_eq!(resolve("ab\u{200B}\u{8}", false), "a");
    }

    /// A `Cf` that renders still occupies a cell — narrower than a blanket category test.
    #[test]
    fn a_rendering_format_character_still_occupies_a_cell() {
        // U+0605 ARABIC NUMBER MARK ABOVE is Cf and renders.
        assert_eq!(
            resolve("a\u{605}\u{8}", false),
            "a",
            "the mark's own cell is erased"
        );
    }

    #[test]
    fn overstrike_bold_resolves_to_the_letter_every_renderer_shows() {
        assert_eq!(resolve("c\u{8}c", false), "c");
        assert_eq!(resolve("b\u{8}bo\u{8}old", false), "bold");
    }

    #[test]
    fn line_endings_pass_through_whatever_the_cr_flag_says() {
        for cr in [false, true] {
            assert_eq!(
                resolve("line1\r\nline2", cr),
                "line1\r\nline2",
                "CRLF, cr={cr}"
            );
            assert_eq!(
                resolve("trailing\r", cr),
                "trailing\r",
                "CR at EOF, cr={cr}"
            );
            assert_eq!(resolve("a\nb\nc", cr), "a\nb\nc", "LF, cr={cr}");
        }
    }

    /// A `CR` overwrites the line; it does not clear it. `abc\rxy` renders `xyc`.
    #[test]
    fn a_lone_cr_overwrites_only_under_its_flag() {
        assert_eq!(resolve("abc\rxy", false), "abc\rxy", "off by default");
        assert_eq!(resolve("abc\rxy", true), "xyc");
        assert_eq!(resolve("ZZZZZZ\rpaypal", true), "paypal");
        // The classic Mac cost, stated rather than hidden.
        assert_eq!(resolve("line1\rline2", true), "line2");
    }

    #[test]
    fn erasing_past_the_start_of_a_line_stops_there() {
        assert_eq!(resolve("\u{8}\u{8}abc", false), "abc");
        assert_eq!(resolve("a\u{8}\u{8}\u{8}b", false), "b");
    }

    /// `true` means changed, and a `CR` this step passes through is not a change.
    ///
    /// Caught in review on #941: the pre-check fires on any `CR` under `cr`, so a
    /// `CRLF`-only string entered the scan, was rebuilt byte-identically, and was reported
    /// as changed — an allocation the caller did not need, and a contract the docstring
    /// did not keep.
    #[test]
    fn a_cr_that_passes_through_is_not_a_change() {
        let mut out = String::new();
        for s in [
            "line1\r\nline2",
            "trailing\r",
            "a\r\nb\r\nc",
            "no cr at all",
        ] {
            assert!(
                !resolve_deletions_into(s, true, &mut out),
                "{s:?} under cr=true"
            );
            assert!(
                !resolve_deletions_into(s, false, &mut out),
                "{s:?} under cr=false"
            );
        }
        // ...while a CR that really overwrites still reports true.
        assert!(resolve_deletions_into("abc\rxy", true, &mut out));
    }

    /// The borrow signal must be exact.
    #[test]
    fn text_with_no_erasing_control_is_left_alone() {
        let mut out = String::new();
        for s in ["paypal", "", "caf\u{e9}", "line1\r\nline2", "\u{1F3F4}"] {
            assert!(!resolve_deletions_into(s, false, &mut out), "{s:?}");
        }
        // A CR is only interesting under the flag.
        assert!(!resolve_deletions_into("a\rb", false, &mut out));
        assert!(resolve_deletions_into("a\rb", true, &mut out));
    }

    #[test]
    fn it_is_idempotent() {
        let probes = [
            "paypal",
            "p\u{8}X",
            "X\u{200B}\u{8}",
            "abc\rxy",
            "line1\r\nline2",
            "e\u{301}\u{8}",
            "c\u{8}c",
        ];
        for cr in [false, true] {
            for p in probes {
                let once = resolve(p, cr);
                assert_eq!(resolve(&once, cr), once, "{p:?} cr={cr}");
            }
        }
    }
}
