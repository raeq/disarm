import Deletions.Model

/-! Small list lemmas the proofs need, proved here rather than borrowed (no Mathlib). -/

namespace Deletions

-- Keep `getD` as the model writes it, rather than simp's `l[i]?.getD` normal form.
attribute [-simp] List.getD_eq_getElem?_getD
attribute [local simp] List.getD_cons_zero List.getD_cons_succ

/-- 1 for a non-blank cell, 0 for a blank one: what `occupied` counts. -/
def nb (c : Cell) : Nat := if c.isEmpty then 0 else 1

/-- The number of non-blank cells in a line. -/
def countNB : List Cell → Nat
  | [] => 0
  | c :: l => nb c + countNB l

theorem getD_set (l : List Cell) (i j : Nat) (x : Cell) :
    (l.set i x).getD j [] = if i = j ∧ i < l.length then x else l.getD j [] := by
  induction l generalizing i j with
  | nil => simp
  | cons a l ih =>
    cases i <;> cases j
    · simp
    · simp only [List.set_cons_zero, List.getD_cons_succ]; simp
    · simp only [List.set_cons_succ, List.getD_cons_zero]; simp
    · simp only [List.set_cons_succ, List.getD_cons_succ, List.length_cons]; rw [ih]; simp

theorem getD_modify (l : List Cell) (i j : Nat) (f : Cell → Cell) :
    (l.modify i f).getD j [] = if i = j ∧ i < l.length then f (l.getD j []) else l.getD j [] := by
  induction l generalizing i j with
  | nil => simp
  | cons a l ih =>
    cases i <;> cases j
    · simp
    · simp only [List.modify_zero_cons, List.getD_cons_succ]; simp
    · simp only [List.modify_succ_cons, List.getD_cons_zero]; simp
    · simp only [List.modify_succ_cons, List.getD_cons_succ, List.length_cons]; rw [ih]; simp

theorem getD_append_single (l : List Cell) (x : Cell) (j : Nat) :
    (l ++ [x]).getD j [] = if j < l.length then l.getD j [] else if j = l.length then x else [] := by
  induction l generalizing j with
  | nil => cases j <;> simp
  | cons a l ih =>
    cases j with
    | zero => simp
    | succ j =>
      simp only [List.cons_append, List.getD_cons_succ, List.length_cons]; rw [ih]
      by_cases h1 : j < l.length
      · simp [h1, show j + 1 < l.length + 1 by omega]
      · by_cases h2 : j = l.length
        · subst h2; simp
        · simp [h1, h2, show ¬ (j + 1 < l.length + 1) by omega]

theorem countNB_set (l : List Cell) (i : Nat) (x : Cell) (h : i < l.length) :
    countNB (l.set i x) + nb (l.getD i []) = countNB l + nb x := by
  induction l generalizing i with
  | nil => simp at h
  | cons a l ih =>
    cases i with
    | zero => simp [countNB]; omega
    | succ i =>
      simp at h
      have := ih i (by omega)
      simp [countNB]; omega

theorem nb_append_single (c : Cell) (x : C) : nb (c ++ [x]) = 1 := by
  simp [nb]

theorem countNB_modify_app (l : List Cell) (i : Nat) (x : C) (h : i < l.length) :
    countNB (l.modify i (· ++ [x])) + nb (l.getD i []) = countNB l + 1 := by
  induction l generalizing i with
  | nil => simp at h
  | cons a l ih =>
    cases i with
    | zero => simp [countNB, nb_append_single]; omega
    | succ i =>
      simp at h
      have := ih i (by omega)
      simp [countNB]; omega

theorem countNB_append (l m : List Cell) : countNB (l ++ m) = countNB l + countNB m := by
  induction l with
  | nil => simp [countNB]
  | cons a l ih => simp [countNB, ih]; omega

theorem mem_set_cases {l : List Cell} {i : Nat} {x c : Cell} (h : c ∈ l.set i x) :
    c ∈ l ∨ c = x := by
  induction l generalizing i with
  | nil => simp at h
  | cons a l ih =>
    cases i with
    | zero =>
      simp at h
      rcases h with h | h
      · exact Or.inr h
      · exact Or.inl (List.mem_cons_of_mem _ h)
    | succ i =>
      simp at h
      rcases h with h | h
      · exact Or.inl (h ▸ List.mem_cons_self)
      · rcases ih h with h' | h'
        · exact Or.inl (List.mem_cons_of_mem _ h')
        · exact Or.inr h'

theorem mem_modify_cases {l : List Cell} {i : Nat} {f : Cell → Cell} {c : Cell}
    (h : c ∈ l.modify i f) : c ∈ l ∨ ∃ d ∈ l, c = f d := by
  induction l generalizing i with
  | nil => simp at h
  | cons a l ih =>
    cases i with
    | zero =>
      simp at h
      rcases h with h | h
      · exact Or.inr ⟨a, List.mem_cons_self, h⟩
      · exact Or.inl (List.mem_cons_of_mem _ h)
    | succ i =>
      simp at h
      rcases h with h | h
      · exact Or.inl (h ▸ List.mem_cons_self)
      · rcases ih h with h' | ⟨d, hd, e⟩
        · exact Or.inl (List.mem_cons_of_mem _ h')
        · exact Or.inr ⟨d, List.mem_cons_of_mem _ hd, e⟩

/-- `getD` inside the bounds is membership. -/
theorem getD_mem (l : List Cell) (i : Nat) (h : i < l.length) : l.getD i [] ∈ l := by
  induction l generalizing i with
  | nil => simp at h
  | cons a l ih =>
    cases i with
    | zero => simp
    | succ i => simp at h; simp [ih i (by omega)]

/-! ### Counting, for "no character is invented" -/

theorem count_flatten_append (l m : List Cell) (x : C) :
    (l ++ m).flatten.count x = l.flatten.count x + m.flatten.count x := by
  simp [List.count_append]

theorem count_flatten_set_le (l : List Cell) (i : Nat) (y : Cell) (x : C) :
    (l.set i y).flatten.count x ≤ l.flatten.count x + y.count x := by
  induction l generalizing i with
  | nil => simp
  | cons a l ih =>
    cases i with
    | zero => simp [List.count_append]; omega
    | succ i =>
      have := ih i
      simp [List.count_append]; omega

theorem count_flatten_modify_app_le (l : List Cell) (i : Nat) (y : C) (x : C) :
    (l.modify i (· ++ [y])).flatten.count x ≤ l.flatten.count x + [y].count x := by
  induction l generalizing i with
  | nil => simp
  | cons a l ih =>
    cases i with
    | zero => simp only [List.modify_zero_cons, List.flatten_cons, List.count_append]; omega
    | succ i =>
      have := ih i
      simp only [List.modify_succ_cons, List.flatten_cons, List.count_append] at this ⊢; omega

/-! ### Flattening with blank cells, for the no-`CR` stack correspondence -/

theorem flatten_replicate_nil (k : Nat) : (List.replicate k ([] : Cell)).flatten = [] := by
  induction k with
  | zero => rfl
  | succ k ih => simp [List.replicate_succ, ih]

theorem set_at_length_replicate (a : List Cell) (k : Nat) (x : Cell) :
    (a ++ List.replicate (k + 1) []).set a.length x = a ++ [x] ++ List.replicate k [] := by
  induction a with
  | nil => simp [List.replicate_succ]
  | cons b a ih => simp [ih]

theorem modify_last_app (a : List Cell) (b : Cell) (rest : List Cell) (f : Cell → Cell) :
    (a ++ b :: rest).modify a.length f = a ++ f b :: rest := by
  induction a with
  | nil => simp
  | cons c a ih => simp [ih]

theorem getD_at_length (a : List Cell) (b : Cell) (rest : List Cell) :
    (a ++ b :: rest).getD a.length [] = b := by
  induction a with
  | nil => simp
  | cons c a ih => simp [ih]

theorem getD_replicate_nil (a : List Cell) (k : Nat) :
    (a ++ List.replicate k []).getD a.length [] = [] := by
  induction a with
  | nil => cases k <;> simp [List.replicate_succ]
  | cons c a ih => simp [ih]

theorem countNB_replicate_nil (k : Nat) : countNB (List.replicate k []) = 0 := by
  induction k with
  | zero => rfl
  | succ k ih => simp [List.replicate_succ, countNB, nb, ih]

theorem countNB_all_nonblank (a : List Cell) (h : ∀ c ∈ a, c ≠ []) : countNB a = a.length := by
  induction a with
  | nil => rfl
  | cons c a ih =>
    have hc : c ≠ [] := h c List.mem_cons_self
    have := ih (fun d hd => h d (List.mem_cons_of_mem _ hd))
    cases c with
    | nil => exact absurd rfl hc
    | cons _ _ => simp [countNB, nb, this]; omega

end Deletions
