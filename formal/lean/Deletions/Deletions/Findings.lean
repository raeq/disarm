import Deletions.Spec

/-!
# Failed properties: the counterexamples, minimal and kernel-checked

Each abstract counterexample is the shortest over `alpha` (found by exhaustive search in
length order) and is checked with `decide`, so by the kernel, not the compiler. The
concrete strings beside them are the repro inputs for the real library; README.md has the
Python one-liners and their actual output.
-/

namespace Deletions

/-! ## Finding 1 — a no-cell character at the start of a line takes a cell

L126-143 route a no-cell character at column 0 to `lead` only when `occupied > 0`. On an
empty (or all-blank) line it falls through to L144/L150 and takes a cell of its own,
moving the cursor. That contradicts L136 ("A character that takes no cell does not move
the cursor either") and the #1005 changelog entry ("It now takes no cell and moves
nothing"), and under `resolve_cr` it shifts every later overwrite one column right of
where the terminal puts it. -/

/-- A zero-width space on an empty line moves the cursor. -/
theorem z_moves_cursor : (step true {} (.z 0) none).col = 1 := by decide

/-- …so a later overwrite lands one column off. `"\u200ba\ra"`: a terminal shows `a`; the
resolver answers `aa`. Without the `U+200B` it answers `a`. The visible output depends on
an invisible character. -/
theorem seen_depends_on_z :
    resolve true [.z 0, .v 0, .cr, .v 0] = [.v 0, .v 0] ∧
    resolve true (dropZ [.z 0, .v 0, .cr, .v 0]) = [.v 0] := by decide

/-- The paper-shaped instance: `ZZZZZZ<CR>paypal` resolves to `paypal`, and one leading
`U+200B` defeats it. -/
theorem zwsp_defeats_cr_resolution :
    resolve true (enc "ZZZZZZ\rpaypal") = enc "paypal" ∧
    resolve true (enc "\u200bZZZZZZ\rpaypal") = enc "paypalZ" := by native_decide

/-- The no-cell character itself is then overwritten and lost — the text L136-137 says
is "kept … removing it is `strip_zero_width`'s job". -/
theorem z_overwritten : resolve true [.z 0, .cr, .v 0] = [.v 0] := by decide

/-- In the fixed model a no-cell character never moves the cursor, in any state. -/
theorem fixed_z_keeps_cursor (cr : Bool) (s : St) (i : Nat) (next : Option C) :
    (stepFixed cr s (.z i) next).col = s.col := by
  unfold stepFixed
  simp only [endsLineFixed, endsLine, occupiesCell]
  repeat (first | rfl | (split <;> try rfl) | simp at *)

/-! ## Finding 2 — `VT`, `FF`, `NEL`, `LS`, `PS` are line breaks to the detector, cells to the resolver

L61-63: "the same guard `anomalies::overwriting_cr` applies, so the detector and the
resolver cannot disagree about what a line ending is". `overwriting_cr` starts a line
after every UAX #14 mandatory break (`anomalies::is_line_break`); the resolver ends a
line only at `LF` or a passing `CR`, and `occupies_cell` gives the other five a cell. -/

/-- A `CR` right after `LS` is at the start of its line: the detector does not fire… -/
theorem detector_silent : detectsCR [.brk 0, .cr, .v 0] = false := by decide

/-- …and the resolver overwrites the line break itself. `"\u2028\rX"` becomes `"X"`. -/
theorem resolver_eats_break : resolve true [.brk 0, .cr, .v 0] = [.v 0] := by decide

/-- With text before the break, text the reader sees on the line above is overwritten:
`"abc\u2028\rX"` becomes `"Xbc\u2028"`, and the detector calls the input clean. -/
theorem resolver_eats_previous_line :
    detectsCR (enc "abc\u2028\rX") = false ∧
    resolve true (enc "abc\u2028\rX") = enc "Xbc\u2028" := by native_decide

/-- Without the flag too: a backspace erases the break, joining two lines — something it
can never do to an `LF`. `"abc\u2028\b"` becomes `"abc"`; `"abc\n\b"` stays. -/
theorem bs_erases_break :
    resolve false [.v 0, .brk 0, .bs] = [.v 0] ∧
    resolve false [.v 0, .lf, .bs] = [.v 0, .lf] := by decide

end Deletions
