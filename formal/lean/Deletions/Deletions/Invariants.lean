import Deletions.Lists

/-!
# The loop invariant, and what it says about the Rust

`WF` is the state invariant of the loop in `resolve_deletions_into`. Every clause is a
claim the Rust comments make or rely on:

* `col_le` — `col ≤ line.len()`, so `line[col - 1]` (L109, L112, L127, L130) and
  `line[col]` (L145, L148, guarded by L144) never index out of bounds: **no panic**.
* `pre` — every cell left of the cursor is non-blank. So the `line[col - 1].is_empty()`
  test at L127 is always false: `occupied += 1` on L128 is **dead code**.
* `occ_eq` — `occupied` is exactly the number of non-blank cells, as L80 says. With `pre`
  it gives `occupied ≥ 1` whenever L110 decrements it: **no `usize` underflow**.
* `cells`, `lead` — the cells and the lead buffer only ever hold text characters, never a
  control. That is what makes the output control-free.
-/

namespace Deletions

attribute [-simp] List.getD_eq_getElem?_getD
attribute [local simp] List.getD_cons_zero List.getD_cons_succ

/-- A character that can sit in a cell: anything but the four controls. -/
def isText : C → Bool
  | .v _ => true
  | .z _ => true
  | .brk _ => true
  | _ => false

structure WF (s : St) : Prop where
  col_le : s.col ≤ s.line.length
  pre : ∀ i, i < s.col → s.line.getD i [] ≠ []
  occ_eq : s.occ = countNB s.line
  cells : ∀ c ∈ s.line, ∀ x ∈ c, isText x = true
  lead : ∀ x ∈ s.lead, isText x = true

theorem wf_init : WF ({} : St) where
  col_le := by simp
  pre := by simp
  occ_eq := by simp [countNB]
  cells := by simp
  lead := by simp

theorem isText_of_fallthrough {cr : Bool} {ch : C} {next : Option C}
    (h1 : ¬ (ch == .bs || ch == .del) = true) (h2 : ¬ endsLine cr ch next = true)
    (h3 : ¬ (ch == .cr) = true) : isText ch = true := by
  cases ch <;> simp_all [endsLine, isText]

theorem nb_of_ne {c : Cell} (h : c ≠ []) : nb c = 1 := by
  cases c with
  | nil => exact absurd rfl h
  | cons _ _ => simp [nb]

theorem isEmpty_false_of_ne {c : Cell} (h : c ≠ []) : c.isEmpty = false := by
  cases c with
  | nil => exact absurd rfl h
  | cons _ _ => rfl

/-- The invariant is preserved by every branch of the loop body. -/
theorem wf_step (cr : Bool) (s : St) (ch : C) (next : Option C) (h : WF s) :
    WF (step cr s ch next) := by
  obtain ⟨hcol, hpre, hocc, hcells, hlead⟩ := h
  unfold step
  split
  · -- L88: BS / DEL
    split
    · rename_i hpos
      dsimp only
      have hlt : s.col - 1 < s.line.length := by omega
      have hne : s.line.getD (s.col - 1) [] ≠ [] := hpre _ (by omega)
      have hcnt := countNB_set s.line (s.col - 1) [] hlt
      rw [nb_of_ne hne] at hcnt
      simp only [nb, List.isEmpty_nil, ite_true] at hcnt
      refine ⟨?_, ?_, ?_, ?_, hlead⟩
      · simp; omega
      · intro i hi
        simp only at hi
        rw [getD_set]
        have : ¬ (s.col - 1 = i ∧ s.col - 1 < s.line.length) := by omega
        simp only [this, ite_false]; exact hpre i (by omega)
      · simp only [isEmpty_false_of_ne hne, Bool.false_eq_true, ite_false]; omega
      · intro c hc x hx
        rcases mem_set_cases hc with hc | hc
        · exact hcells c hc x hx
        · subst hc; simp at hx
    · exact ⟨hcol, hpre, hocc, hcells, hlead⟩
  rename_i h1
  split
  · -- L114: a line ending flushes
    exact ⟨by simp, by simp, by simp [countNB], by simp, by simp⟩
  rename_i h2
  split
  · -- L123: a lone CR under the flag
    exact ⟨by simp, by simp, hocc, hcells, hlead⟩
  rename_i h3
  split
  · -- L126: a no-cell character joins the cell left of the cursor
    rename_i h4
    simp only [Bool.and_eq_true, Bool.not_eq_true', decide_eq_true_eq] at h4
    have hlt : s.col - 1 < s.line.length := by omega
    have hne : s.line.getD (s.col - 1) [] ≠ [] := hpre _ (by omega)
    have hcnt := countNB_modify_app s.line (s.col - 1) ch hlt
    rw [nb_of_ne hne] at hcnt
    refine ⟨?_, ?_, ?_, ?_, hlead⟩
    · simp; omega
    · intro i hi
      rw [getD_modify]
      split
      · simp
      · exact hpre i hi
    · simp only [isEmpty_false_of_ne hne, Bool.false_eq_true, ite_false]; omega
    · intro c hc x hx
      rcases mem_modify_cases hc with hc | ⟨d, hd, e⟩
      · exact hcells c hc x hx
      · subst e
        simp at hx
        rcases hx with hx | hx
        · exact hcells d hd x hx
        · subst hx; exact isText_of_fallthrough h1 h2 h3
  rename_i h4
  split
  · -- L131: a no-cell character at column 0 with visible text to the right: `lead`
    refine ⟨hcol, hpre, hocc, hcells, ?_⟩
    intro x hx
    simp at hx
    rcases hx with hx | hx
    · exact hlead x hx
    · subst hx; exact isText_of_fallthrough h1 h2 h3
  rename_i h5
  split
  · -- L144: overwrite the cell under the cursor
    rename_i h6
    have hcnt := countNB_set s.line s.col [ch] h6
    refine ⟨?_, ?_, ?_, ?_, hlead⟩
    · simp; omega
    · intro i hi
      rw [getD_set]
      split
      · simp
      · rename_i hh
        simp only at hi
        exact hpre i (by omega)
    · by_cases he : s.line.getD s.col [] = []
      · simp only [he, List.isEmpty_nil, ite_true]
        rw [he] at hcnt; simp [nb] at hcnt; omega
      · simp only [isEmpty_false_of_ne he, Bool.false_eq_true, ite_false]
        rw [nb_of_ne he] at hcnt; simp [nb] at hcnt; omega
    · intro c hc x hx
      rcases mem_set_cases hc with hc | hc
      · exact hcells c hc x hx
      · subst hc; simp at hx; subst hx; exact isText_of_fallthrough h1 h2 h3
  · -- L150: push a new cell at the end of the line
    rename_i h6
    have hceq : s.col = s.line.length := by omega
    refine ⟨?_, ?_, ?_, ?_, hlead⟩
    · simp; omega
    · intro i hi
      rw [getD_append_single]
      split
      · exact hpre i (by omega)
      · split
        · simp
        · simp only at hi; omega
    · simp [countNB_append, countNB, nb]; omega
    · intro c hc x hx
      simp at hc
      rcases hc with hc | hc
      · exact hcells c hc x hx
      · subst hc; simp at hx; subst hx; exact isText_of_fallthrough h1 h2 h3

/-- The invariant holds at every point of every run. -/
theorem wf_run (cr : Bool) (t : List C) (s : St) (h : WF s) : WF (run cr s t) := by
  induction t generalizing s with
  | nil => exact h
  | cons ch rest ih => exact ih _ (wf_step cr s ch _ h)

/-- **No panic.** Every index the loop body takes is in bounds, and `occupied` is at least
one whenever L110 decrements it. -/
theorem no_panic (cr : Bool) (pre : List C) (s : St) (hs : s = run cr {} pre) :
    s.col ≤ s.line.length ∧
    (s.col > 0 → s.col - 1 < s.line.length) ∧
    (s.col > 0 → s.line.getD (s.col - 1) [] ≠ [] → s.occ ≥ 1) := by
  have h := wf_run cr pre {} wf_init
  rw [← hs] at h
  refine ⟨h.col_le, fun hp => by have := h.col_le; omega, fun hp hne => ?_⟩
  have hlt : s.col - 1 < s.line.length := by have := h.col_le; omega
  have hcnt := countNB_set s.line (s.col - 1) [] hlt
  rw [nb_of_ne hne] at hcnt
  simp [nb] at hcnt
  rw [h.occ_eq]; omega

/-- **Dead code.** At L127 the cell left of the cursor is never blank, so the
`occupied += 1` on L128 never runs. -/
theorem l128_dead (cr : Bool) (pre : List C) (hp : (run cr {} pre).col > 0) :
    ((run cr {} pre).line.getD ((run cr {} pre).col - 1) []).isEmpty = false := by
  have h := wf_run cr pre {} wf_init
  exact isEmpty_false_of_ne (h.pre _ (by omega))

end Deletions
