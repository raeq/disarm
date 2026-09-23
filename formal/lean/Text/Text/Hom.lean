/-!
# Per-scalar maps

`fold_case`, `fold_punctuation` and the strip filters are all *per-scalar*: the output is
the concatenation of an image computed from each scalar alone. Everything claimed about
such a map over all strings follows from a claim about its per-scalar image, which is the
reasoning the Rust comment on `exhaustive_fold_case_invariants` gives ("single-code-point
enumeration is a complete proof"). These lemmas make that step explicit, so the exhaustive
per-scalar sweeps in `scripts/sweep.py` discharge the premises.
-/

namespace Text

/-- A per-scalar map. -/
def pmap {α : Type} (f : α → List α) (s : List α) : List α := s.flatMap f

theorem pmap_nil {α : Type} (f : α → List α) : pmap f [] = [] := rfl

theorem pmap_cons {α : Type} (f : α → List α) (a : α) (s : List α) :
    pmap f (a :: s) = f a ++ pmap f s := by
  simp [pmap, List.flatMap_cons]

/-- A per-scalar map is a monoid homomorphism: it commutes with concatenation. -/
theorem pmap_append {α : Type} (f : α → List α) (s t : List α) :
    pmap f (s ++ t) = pmap f s ++ pmap f t := by
  simp [pmap, List.flatMap_append]

/-- **Idempotence lifts.** If the image of every scalar is a fixed point, the map is
idempotent on every string. -/
theorem pmap_idem {α : Type} (f : α → List α) (h : ∀ a, pmap f (f a) = f a) (s : List α) :
    pmap f (pmap f s) = pmap f s := by
  induction s with
  | nil => rfl
  | cons a s ih => rw [pmap_cons, pmap_append, h, ih]

/-- **Nothing is dropped.** If no scalar maps to the empty string, the output is at least
as long as the input. -/
theorem pmap_length_ge {α : Type} (f : α → List α) (h : ∀ a, (f a).length ≥ 1) (s : List α) :
    (pmap f s).length ≥ s.length := by
  induction s with
  | nil => simp [pmap]
  | cons a s ih =>
    rw [pmap_cons, List.length_append, List.length_cons]
    have := h a
    omega

/-- **A property of scalars is kept.** If every image consists of scalars satisfying `p`,
so does every output. (Used with `p` = "not an ASCII uppercase letter".) -/
theorem pmap_all {α : Type} (f : α → List α) (p : α → Bool) (h : ∀ a, (f a).all p = true)
    (s : List α) : (pmap f s).all p = true := by
  induction s with
  | nil => rfl
  | cons a s ih => rw [pmap_cons, List.all_append, h, ih]; rfl

/-- **The identity where the scalar map is the identity.** -/
theorem pmap_id_on {α : Type} (f : α → List α) (p : α → Bool) (h : ∀ a, p a = true → f a = [a])
    (s : List α) (hs : s.all p = true) : pmap f s = s := by
  induction s with
  | nil => rfl
  | cons a s ih =>
    simp only [List.all_cons, Bool.and_eq_true] at hs
    rw [pmap_cons, h a hs.1, ih hs.2]; rfl

/-- A filter is a per-scalar map, and is idempotent. -/
theorem filter_idem {α : Type} (p : α → Bool) (s : List α) :
    (s.filter p).filter p = s.filter p := by
  simp [List.filter_filter]

/-- Two filters commute, so the order of two deletion steps never matters. -/
theorem filter_comm {α : Type} (p q : α → Bool) (s : List α) :
    (s.filter p).filter q = (s.filter q).filter p := by
  simp [List.filter_filter, Bool.and_comm]

/-- A filter's output is a subsequence of its input: nothing is invented or reordered. -/
theorem filter_sublist {α : Type} (p : α → Bool) (s : List α) : (s.filter p).Sublist s :=
  List.filter_sublist

/-! ## Equal concatenations with dominated pieces

The key step for `is_case_fold_stable`: if two lists of chunks have equal concatenations,
the same number of chunks, and each chunk on the right is no longer than its partner on
the left, the chunks are equal one by one. -/

theorem sum_lengths_eq {α : Type} (xs : List (List α)) :
    xs.flatten.length = (xs.map List.length).sum := by
  induction xs with
  | nil => rfl
  | cons x xs ih => simp [List.flatten_cons, ih]

theorem chunks_eq_of_flatten_eq {α : Type} :
    ∀ (xs ys : List (List α)), xs.length = ys.length →
      (∀ p ∈ xs.zip ys, p.2.length ≤ p.1.length) →
      xs.flatten = ys.flatten → xs = ys := by
  intro xs
  induction xs with
  | nil => intro ys hl _ _; cases ys <;> simp_all
  | cons x xs ih =>
    intro ys hl hle hf
    cases ys with
    | nil => simp at hl
    | cons y ys =>
      simp only [List.length_cons, Nat.add_right_cancel_iff] at hl
      have hxy : y.length ≤ x.length := hle (x, y) (by simp)
      have hrest : ∀ p ∈ xs.zip ys, p.2.length ≤ p.1.length :=
        fun p hp => hle p (by simp [List.zip_cons_cons, hp])
      simp only [List.flatten_cons] at hf
      -- total lengths agree, and the tails are dominated, so the heads have equal length
      have hsum : ∀ (as bs : List (List α)), as.length = bs.length →
          (∀ p ∈ as.zip bs, p.2.length ≤ p.1.length) →
          (bs.map List.length).sum ≤ (as.map List.length).sum := by
        intro as
        induction as with
        | nil => intro bs h _; cases bs <;> simp_all
        | cons a as iha =>
          intro bs h hd
          cases bs with
          | nil => simp at h
          | cons b bs =>
            simp only [List.length_cons, Nat.add_right_cancel_iff] at h
            have h1 : b.length ≤ a.length := hd (a, b) (by simp)
            have h2 := iha bs h (fun p hp => hd p (by simp [List.zip_cons_cons, hp]))
            simp only [List.map_cons, List.sum_cons]
            omega
      have hlen := congrArg List.length hf
      simp only [List.length_append, sum_lengths_eq] at hlen
      have htail := hsum xs ys hl hrest
      have hx : x.length = y.length := by omega
      obtain ⟨h1, h2⟩ := List.append_inj hf hx
      rw [h1, ih ys hl hrest h2]

end Text
