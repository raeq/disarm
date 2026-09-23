import Deletions.Spec

/-!
# Bounded exhaustive checks (`native_decide`)

Every word of length ≤ `N` over `alpha` — `BS`, `DEL`, `CR`, `LF`, two distinct cell
characters, one no-cell character, one non-`LF` mandatory break — 2,396,745 words at
`N = 7`. These are the properties not proved in general in `Output.lean`/`Simple.lean`,
either because they are about the *fixed* model or because a general proof would need a
second simulation relation and the bounded check was the better use of the time.
`native_decide` trusts the Lean compiler; the counterexamples in `Findings.lean` are
checked by the kernel with `decide` instead.
-/

namespace Deletions

/-- The bound. -/
abbrev N : Nat := 7

def allW (p : List C → Bool) : Bool := (wordsUpTo alpha N).all p

/-! ## The current code -/

/-- The Rust test `an_erase_costs_at_most_one_cell`, exhaustively rather than fuzzed: one
more `BS` at the end costs at most one text cell. Holds under both flags. -/
theorem erase_costs_one_cell :
    allW (fun t => [false, true].all fun cr =>
      countCells (resolve cr t) ≤ countCells (resolve cr (t ++ [.bs])) + 1) = true := by
  native_decide

/-- Without the flag, what is on screen does not depend on the no-cell characters: remove
every one of them from the input and the visible output is the same. -/
theorem seen_ignores_z_nocr :
    allW (fun t => seen (resolve false t) == seen (resolve false (dropZ t))) = true := by
  native_decide

/-! ## The proposed fix (Model.lean, `stepFixed`)

Everything the current code satisfies it still satisfies, and the three properties the
current code fails (Findings.lean) hold. -/

theorem fixed_idem :
    allW (fun t => [false, true].all fun cr =>
      resolveFixed cr (resolveFixed cr t) == resolveFixed cr t) = true := by
  native_decide

theorem fixed_clean :
    allW (fun t => [false, true].all fun cr => Clean cr (resolveFixed cr t)) = true := by
  native_decide

theorem fixed_lf :
    allW (fun t => [false, true].all fun cr =>
      (resolveFixed cr t).filter (· == .lf) == t.filter (· == .lf)) = true := by
  native_decide

theorem fixed_no_invention :
    allW (fun t => [false, true].all fun cr =>
      alpha.all fun x => (resolveFixed cr t).count x ≤ t.count x) = true := by
  native_decide

theorem fixed_erase_costs_one_cell :
    allW (fun t => [false, true].all fun cr =>
      countCells (resolveFixed cr t) ≤ countCells (resolveFixed cr (t ++ [.bs])) + 1) = true := by
  native_decide

/-- Finding 1, fixed: no-cell characters never change what is on screen, under either flag. -/
theorem fixed_seen_ignores_z :
    allW (fun t => [false, true].all fun cr =>
      seen (resolveFixed cr t) == seen (resolveFixed cr (dropZ t))) = true := by
  native_decide

/-- Finding 2, fixed: a `CR` the `deletion` detector does not report never changes what is on
screen. -/
theorem fixed_detector_agrees :
    allW (fun t => hasErase t || detectsCR t || seen (resolveFixed true t) == seen t) = true := by
  native_decide

/-- Finding 2, fixed: every mandatory break survives, under either flag. -/
theorem fixed_breaks_survive :
    allW (fun t => [false, true].all fun cr =>
      (resolveFixed cr t).filter (fun c => isLineBreak c && c != .cr) ==
        t.filter (fun c => isLineBreak c && c != .cr)) = true := by
  native_decide

/-- The fix moves nothing else: on input with no no-cell character and no non-`LF` break,
the fixed and current models agree exactly. -/
theorem fixed_agrees_elsewhere :
    allW (fun t => t.any (fun c => !occupiesCell c || c == .brk 0) ||
      [false, true].all fun cr => resolveFixed cr t == resolve cr t) = true := by
  native_decide

end Deletions
