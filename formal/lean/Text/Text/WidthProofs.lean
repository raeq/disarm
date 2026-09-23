import Text.Width

/-!
# General theorems about `grapheme_width` / `terminal_width` (induction and case analysis)

* `gw_le_two`, `tw_le` — every argument measures at most 2, so `terminal_width` is at
  most twice `grapheme_len` (I_w2 in #224), for every input.
* `gw_ascii_single` — a lone ASCII scalar measures 0 if it is a control and 1 otherwise
  (I_w1).
* `gw_amb_mono` — the ambiguous-wide policy never makes anything narrower.
* `gwFixed_spacing` — under the proposed fix, a cluster whose first scalar after its
  zero-width `Prepend` prefix takes a cell measures at least 1. The current code fails
  this (`Findings.lean`, `w1_*`).
-/

namespace Text.Width

theorem resolve_le_two (c : Nat) (amb : Bool) : resolve c amb ≤ 2 := by
  unfold resolve; split <;> (try split) <;> omega

theorem resolve_pos (c : Nat) (amb : Bool) (h : c ≠ 0) : resolve c amb ≥ 1 := by
  unfold resolve; split <;> (try split) <;> omega

theorem gw_le_two (amb : Bool) (l : List Sc) : gw amb l ≤ 2 := by
  unfold gw
  split
  · omega
  · simp only
    split
    · split <;> omega
    · split
      · omega
      · split
        · split
          · omega
          · exact resolve_le_two _ _
        · split
          · omega
          · exact resolve_le_two _ _

theorem tw_le (amb : Bool) (cls : List (List Sc)) : tw amb cls ≤ 2 * cls.length := by
  induction cls with
  | nil => simp [tw]
  | cons c cs ih =>
    simp only [tw, List.map_cons, List.sum_cons, List.length_cons] at ih ⊢
    have := gw_le_two amb c
    omega

theorem gw_ascii_single (amb : Bool) (c : Sc) (h : c.ascii = true) :
    gw amb [c] = if c.cls == 0 then 0 else 1 := by
  simp [gw, h]

theorem resolve_mono (c : Nat) : resolve c false ≤ resolve c true := by
  unfold resolve; split <;> simp

theorem gw_amb_mono (l : List Sc) : gw false l ≤ gw true l := by
  unfold gw
  split
  · omega
  · simp only
    split
    · omega
    · split
      · omega
      · split
        · split
          · omega
          · exact resolve_mono _
        · split
          · omega
          · exact resolve_mono _

/-- A scalar that takes a cell by itself (`spacing`) as the first scalar of an argument makes
the argument measure at least 1. -/
theorem gw_pos_of_spacing_head (amb : Bool) (b : Sc) (rest : List Sc) (hb : spacing b = true) :
    gw amb (b :: rest) ≥ 1 := by
  simp only [spacing, Bool.and_eq_true, bne_iff_ne, ne_eq] at hb
  obtain ⟨hc, _⟩ := hb
  unfold gw
  simp only
  split
  · split
    · rename_i h; simp at h; omega
    · omega
  · split
    · rename_i h; simp at h; omega
    · split
      · split
        · omega
        · exact resolve_pos _ _ hc
      · split
        · omega
        · exact resolve_pos _ _ hc

theorem dropZeroPrep_append (pre : List Sc) (b : Sc) (rest : List Sc)
    (hpre : ∀ p ∈ pre, p.prep = true ∧ p.cls = 0) (hb : b.cls ≠ 0) :
    dropZeroPrep (pre ++ b :: rest) = b :: rest := by
  induction pre with
  | nil =>
    simp only [List.nil_append, dropZeroPrep]
    have : (b.prep && b.cls == 0) = false := by simp [hb]
    simp [this]
  | cons p pre ih =>
    have hp := hpre p (by simp)
    simp only [List.cons_append, dropZeroPrep, hp.1, hp.2, beq_self_eq_true, Bool.and_self,
      ↓reduceIte]
    exact ih (fun q hq => hpre q (by simp [hq]))

/-- **The fix**: a zero-width `Prepend` prefix no longer hides the scalar it attaches to. -/
theorem gwFixed_spacing (amb : Bool) (pre : List Sc) (b : Sc) (rest : List Sc)
    (hpre : ∀ p ∈ pre, p.prep = true ∧ p.cls = 0) (hb : spacing b = true) :
    gwFixed amb (pre ++ b :: rest) ≥ 1 := by
  have hc : b.cls ≠ 0 := by
    simp only [spacing, Bool.and_eq_true, bne_iff_ne, ne_eq] at hb; exact hb.1
  unfold gwFixed
  rw [dropZeroPrep_append pre b rest hpre hc]
  exact gw_pos_of_spacing_head amb b rest hb

/-- The fix changes nothing for an argument that does not open with a zero-width `Prepend`. -/
theorem gwFixed_eq (amb : Bool) (b : Sc) (rest : List Sc) (h : (b.prep && b.cls == 0) = false) :
    gwFixed amb (b :: rest) = gw amb (b :: rest) := by
  simp [gwFixed, dropZeroPrep, h]

end Text.Width
