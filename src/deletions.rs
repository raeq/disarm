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
use crate::anomalies::is_line_break;

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
    // Characters that occupy no cell, met at column 0: they have no cell to their left to
    // join, and must not take one. See the branch that fills this.
    let mut lead = String::new();
    let mut chars = text.chars().peekable();
    while let Some(ch) = chars.next() {
        if ch == BS || ch == DEL {
            // Erase the cell *before* the cursor, leaving the cells right of it where
            // they are — in a terminal a backspace moves the cursor and the screen does
            // not shift; shifting is what a line editor does. `truncate(col)` is
            // the same thing only while `col == line.len()`, which holds for every input
            // without a `CR` — so the two agreed until #937 added the `cr` flag that can
            // move the cursor back. After a `CR` the truncate discarded the whole rest of
            // the line, and at column 0 it discarded the line: `"abc\rX\u{8}"` gave `""`,
            // losing the `bc` a terminal still shows. The model here is #937's — erase the
            // cell before the cursor, which in the paper's corpus is the attacker's
            // inserted character — so it gives `"bc"`; a terminal, whose backspace moves
            // the cursor and erases nothing, shows `Xbc`. Losing text the reader can see
            // is the risk #934 declined to take.
            if col > 0 {
                col -= 1;
                // Blanking, not `remove`: the cell stops contributing text and every
                // other cell keeps its column. `remove` would shift, which is both the
                // wrong model (above) and O(1) only at the end of a line — it made
                // `"a"*n + "\r" + "X\u{8}"*n` quadratic, 4x per doubling, measured.
                // Keeping the column is what lets a later overwrite land where the
                // terminal would put it.
                line[col].clear();
            }
        } else if (ch != CR && is_line_break(ch))
            || (ch == CR && (!cr || chars.peek().is_none_or(|&n| n == LF)))
        {
            // Every line break the detector knows, not only `LF`: VT, FF, NEL, LS and PS
            // start a line for `anomalies::overwriting_cr`, and treated as cells here a `CR`
            // after one overwrote the line above it while the detector saw nothing, and a
            // backspace erased the break and joined two lines (Lean model,
            // `formal/lean/Deletions`).
            out.push_str(&lead);
            lead.clear();
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
        } else if !occupies_cell(ch) {
            // Column 0 after a `CR`, with the line still to the right. Falling through to
            // the overwrite below took cell 0 *and advanced the cursor*, so the next
            // character overwrote cell 1: `"abc\r\u{200B}Y"` gave `"\u{200B}Yc"`, losing
            // the `b` a terminal still shows as `Ybc` (#995 review). A character that takes
            // no cell does not move the cursor either. It is kept, ahead of the line — it
            // is text the caller passed, and removing it is `strip_zero_width`'s job.
            //
            //
            // On an empty line too. #1005 kept it here only with visible text to the right,
            // and on an empty line it took cell 0, so every overwrite after a later `CR`
            // landed a column off: `"\u{200B}ZZZZZZ\rpaypal"` gave `"paypalZ"` (Lean model,
            // `formal/lean/Deletions`). A consequence, the terminal's: a backspace at column
            // 0 has no cell to erase, so `"\u{200B}\u{8}a"` keeps the U+200B.
            lead.push(ch);
        } else if col < line.len() {
            line[col] = ch.to_string();
            col += 1;
        } else {
            line.push(ch.to_string());
            col += 1;
        }
    }
    out.push_str(&lead);
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

    /// A character that takes no cell does not move the cursor, at column 0 included.
    /// After a `CR` it fell through to the overwrite branch and advanced, so the next
    /// letter overwrote a cell the reader can still see (#995 review).
    /// A character that takes no cell never takes one, on an empty line either
    /// (Lean model, `formal/lean/Deletions`). The #1005 guard sent it ahead of the line
    /// only when visible text lay to the right; on an empty line it took cell 0, so every
    /// later overwrite after a `CR` landed a column off and one leading U+200B defeated
    /// resolution: `"\u{200B}ZZZZZZ\rpaypal"` gave `"paypalZ"`.
    #[test]
    fn a_no_cell_character_never_takes_a_cell() {
        assert_eq!(resolve("\u{200B}ZZZZZZ\rpaypal", true), "\u{200B}paypal");
        assert_eq!(resolve("\u{301}ZZZZZZ\rpaypal", true), "\u{301}paypal");
        assert_eq!(resolve("\u{200B}a\ra", true), "\u{200B}a");
        assert_eq!(resolve("\u{200B}\ra", true), "\u{200B}a");
    }

    /// VT, FF, NEL, LS and PS end a line for the detector (`anomalies::is_line_break`),
    /// and the resolver treated them as ordinary cells: a `CR` after one overwrote the
    /// line above it while `has_anomalies` reported nothing, and a backspace erased the
    /// break itself and joined two lines, which it can never do to an `LF` (Lean model).
    #[test]
    fn every_line_break_the_detector_knows_ends_a_line_here_too() {
        for b in ['\u{B}', '\u{C}', '\u{85}', '\u{2028}', '\u{2029}'] {
            assert_eq!(
                resolve(&format!("abc{b}\rX"), true),
                format!("abc{b}X"),
                "{b:?}"
            );
            assert_eq!(
                resolve(&format!("pay{b}\u{8}pal"), false),
                format!("pay{b}pal"),
                "{b:?}"
            );
        }
        // The LF behaviour both now match.
        assert_eq!(resolve("abc\n\rX", true), "abc\nX");
        assert_eq!(resolve("pay\n\u{8}pal", false), "pay\npal");
    }

    #[test]
    fn a_zero_width_at_column_zero_does_not_move_the_cursor() {
        assert_eq!(resolve("abc\r\u{200B}Y", true), "\u{200B}Ybc");
        assert_eq!(resolve("abc\r\u{0301}Y", true), "\u{0301}Ybc");
        assert_eq!(resolve("abc\rX\u{8}\u{200B}Y", true), "\u{200B}Ybc");
        // A no-cell character at column 0 has no cell for a backspace to erase, with or
        // without a `CR`, and whatever lies to the right: the two inputs below agree, which
        // is what Copilot asked of #1005, and both keep the U+200B, as a terminal does.
        assert_eq!(resolve("\u{200B}\u{8}a", false), "\u{200B}a");
        assert_eq!(resolve("ab\u{8}\u{8}\u{200B}\u{8}", false), "\u{200B}");
        assert_eq!(resolve("\u{200B}\u{8}", false), "\u{200B}");
        assert_eq!(resolve("ab\u{8}\u{8}\u{200B}Y", false), "\u{200B}Y");
    }

    /// The paper's §VI-A construction: one printable character, then BKSP.
    #[test]
    fn the_attack_construction_resolves_to_the_clean_word() {
        let attack: String = "paypal".chars().flat_map(|c| [c, 'X', BS]).collect();
        assert_eq!(resolve(&attack, false), "paypal");
        let with_del: String = "paypal".chars().flat_map(|c| [c, 'X', DEL]).collect();
        assert_eq!(resolve(&with_del, false), "paypal");
    }

    /// An erase removes the cell before the cursor, not everything after it (#995).
    ///
    /// `truncate(col)` is `pop` only while the cursor sits at the end of the line, which
    /// is every input without a `CR`. Once `cr` has returned the cursor to column 0 the
    /// two part company, and the truncate discards the whole rest of the line — the text
    /// a reader can see, which is the loss #934 refused to risk.
    #[test]
    fn an_erase_after_a_carriage_return_removes_one_cell() {
        assert_eq!(resolve("abc\rX\u{8}", true), "bc");
        assert_eq!(resolve("abc\rXY\u{8}", true), "Xc");
        // Nothing sits before column 0, so there is nothing to erase.
        assert_eq!(resolve("abc\r\u{8}", true), "abc");
        assert_eq!(resolve("abc\r\u{7F}", true), "abc");
    }

    /// The no-`CR` behaviour the truncate happened to get right must not move.
    #[test]
    fn an_erase_at_the_end_of_a_line_still_pops_one_cell() {
        assert_eq!(resolve("abc\u{8}", false), "ab");
        assert_eq!(resolve("abc\u{8}\u{8}", false), "a");
        assert_eq!(resolve("\u{8}abc", false), "abc");
        assert_eq!(resolve("ab\nc\u{8}", false), "ab\n");
    }

    /// An erase blanks a cell; it does not shift the ones to its right (#995).
    ///
    /// The distinction is invisible without a `CR` — there is nothing right of the cursor
    /// to shift — and this is the shortest input where the two models part company. A
    /// terminal moves the cursor and leaves the screen alone: `"aa"`, return, overwrite
    /// column 0, erase it, overwrite it again, and both columns are still there. Shifting
    /// answers `"a"`, having eaten a character the reader can still see. `remove` was the
    /// first draft of the fix above and this is why it is not the last.
    #[test]
    fn an_erase_does_not_shift_the_rest_of_the_line() {
        assert_eq!(resolve("aa\ra\u{8}a", true), "aa");
        // Same shape, distinguishable cells.
        assert_eq!(resolve("ab\rX\u{8}Y", true), "Yb");
    }

    /// An erase takes one cell, never the rest of the line (#995).
    ///
    /// This is the invariant `truncate` broke, stated so that breaking it again fails
    /// here rather than in somebody's text. A backspace erases the cell before the
    /// cursor; the cells to its right are untouched, because in a terminal the cursor
    /// moves and the screen does not shift. So the output cannot be shorter than the
    /// cells that went in, less one per erase — `truncate` lost a whole line per
    /// backspace and this counts that.
    ///
    /// Fuzzed over an alphabet of everything the cursor model treats differently, with
    /// idempotence and the no-control-survives rule checked on the same corpus.
    #[test]
    fn an_erase_costs_at_most_one_cell() {
        let alphabet = ['a', 'b', 'X', BS, DEL, CR, LF, '\u{301}', '\u{200B}'];
        let mut state = 0x2545_F491_4F6C_DD1Du64;
        for _ in 0..200_000 {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            let len = 1 + (state % 12) as usize;
            let mut probe = String::new();
            let mut bits = state;
            for _ in 0..len {
                bits = bits.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(1);
                probe.push(alphabet[(bits >> 33) as usize % alphabet.len()]);
            }
            // `occupies_cell` is about rendering width, so it answers `true` for the
            // controls too; the cursor model consumes those rather than drawing them.
            let text_cell = |c: char| occupies_cell(c) && !matches!(c, BS | DEL | CR | LF);
            for cr in [false, true] {
                let out = resolve(&probe, cr);
                // One backspace costs at most one cell. Stated as a difference rather
                // than a total because an overwriting `CR` is *meant* to lose cells, and
                // it loses the same ones either side of this comparison — which is what
                // makes the property bite in the `cr` case, where the defect lived.
                // `truncate` failed it outright: "abc\rX" is three cells and
                // "abc\rX\u{8}" was none.
                for erase in [BS, DEL] {
                    let erased = resolve(&format!("{probe}{erase}"), cr);
                    let before = out.chars().filter(|&c| text_cell(c)).count();
                    let after = erased.chars().filter(|&c| text_cell(c)).count();
                    assert!(
                        after + 1 >= before,
                        "{probe:?} cr={cr}: one {erase:?} took {} cells, \
                         {out:?} -> {erased:?}",
                        before - after
                    );
                }
                assert!(
                    !out.contains(BS) && !out.contains(DEL),
                    "{probe:?} cr={cr} left a control in {out:?}"
                );
                assert_eq!(
                    resolve(&out, cr),
                    out,
                    "{probe:?} cr={cr} is not idempotent"
                );
            }
        }
    }

    /// Erasing stays linear in the length of the line (#995).
    ///
    /// Removing the cell instead of blanking it shifts every cell to its right, which is
    /// free only at the end of a line: an intermediate draft of the fix above did that
    /// and measured 4x per doubling. The budget is loose by three orders of magnitude
    /// against the linear answer and an order of magnitude under the quadratic one, so it
    /// catches the regression without being a stopwatch.
    #[test]
    fn erasing_a_long_line_is_not_quadratic() {
        let n = 40_000;
        let probe = format!("{}\r{}", "a".repeat(n), "X\u{8}".repeat(n));
        let started = std::time::Instant::now();
        let out = resolve(&probe, true);
        let elapsed = started.elapsed();
        // Each `X` overwrites cell 0 and each backspace blanks it again, so what is left
        // is the original line with its first cell gone.
        assert_eq!(
            out.chars().count(),
            n - 1,
            "{:?}",
            &out[..out.len().min(40)]
        );
        assert!(
            elapsed < std::time::Duration::from_secs(5),
            "{n} erases took {elapsed:?} — the shift is back"
        );
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
