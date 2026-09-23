import Text.Hom

/-!
# `fold_case` and `is_case_fold_stable` (`src/case_fold.rs`)

`fold_case` is the per-scalar map `pmap fold` (`fold_case_into`, L75-100: ASCII lowered
inline, everything else looked up, identity when absent). Its all-strings properties
follow from `Hom.lean` once the per-scalar premises hold, and `scripts/sweep.py` checks
those on every scalar.

`is_case_fold_stable_impl` (L132-157) claims to compute `fold_case(s) == s.to_lowercase()`
with a per-scalar scan, falling back to the whole-string comparison only when `U+03A3` is
present. A per-scalar scan deciding a whole-string equality is not sound in general: two
scalars that each disagree can agree once concatenated (`fold a = "xy", fold b = "z"`
against `lower a = "x", lower b = "yz"`). `stable_correct` proves the scan *is* sound under
four premises about the Unicode data, all checked exhaustively against the library's own
tables by `scripts/premises` (Rust, same `to_lowercase` as the library):

* `lenEq` / `ctx`: `str::to_lowercase` lowers position by position, and only `U+03A3`
  depends on its neighbours (the Rust tier-3 test `only_sigma_has_a_context_sensitive_lowercase`);
* `dom`: at every position the lowercase is no longer than the fold;
* `ascii`: on ASCII the fold and the lowercase agree, and ASCII is not `U+03A3`;
* `sigma`: `U+03A3` folds to what it lowercases to in isolation (`U+03C3`).
-/

set_option linter.unusedSectionVars false

namespace Text.CaseFold

open Text

variable {α : Type} [DecidableEq α]

/-- What the algorithm reads. `lowerCtx s` is `s.to_lowercase()` cut into one chunk per
input scalar. -/
structure Data (α : Type) where
  fold : α → List α
  low : α → List α
  ascii : α → Bool
  sigma : α
  lowerCtx : List α → List (List α)

/-- The premises, each checked on every scalar by `scripts/premises`. -/
structure Premises (D : Data α) : Prop where
  lenEq : ∀ s : List α, (D.lowerCtx s).length = s.length
  ctx : ∀ s : List α, ∀ p ∈ s.zip (D.lowerCtx s), p.1 ≠ D.sigma → p.2 = D.low p.1
  dom : ∀ s : List α, ∀ p ∈ s.zip (D.lowerCtx s), p.2.length ≤ (D.fold p.1).length
  ascii : ∀ c, D.ascii c = true → D.fold c = D.low c ∧ c ≠ D.sigma
  sigma : D.fold D.sigma = D.low D.sigma

def lower (D : Data α) (s : List α) : List α := (D.lowerCtx s).flatten

/-- The definition the function claims to compute. -/
def spec (D : Data α) (s : List α) : Bool := pmap D.fold s == lower D s

/-- `is_case_fold_stable_impl`: the ASCII bypass, the per-scalar scan, and the whole-string
comparison only when `U+03A3` was seen. -/
def stable (D : Data α) (s : List α) : Bool :=
  if s.all D.ascii then true
  else if s.all (fun c => D.fold c == D.low c) then
    (if s.contains D.sigma then pmap D.fold s == lower D s else true)
  else false

theorem pmap_eq_flatten (f : α → List α) (s : List α) : pmap f s = (s.map f).flatten := by
  simp [pmap, List.flatMap]

theorem eq_map_of_zip {β : Type} (g : α → β) :
    ∀ (s : List α) (cs : List β), cs.length = s.length →
      (∀ p ∈ s.zip cs, p.2 = g p.1) → cs = s.map g := by
  intro s
  induction s with
  | nil => intro cs h _; cases cs <;> simp_all
  | cons a s ih =>
    intro cs h hp
    cases cs with
    | nil => simp at h
    | cons c cs =>
      simp only [List.length_cons, Nat.add_right_cancel_iff] at h
      have h1 : c = g a := hp (a, c) (by simp)
      have h2 := ih cs h (fun p hq => hp p (by simp [List.zip_cons_cons, hq]))
      simp [h1, h2]

theorem mem_zip_map {β : Type} (g : α → β) :
    ∀ (s : List α) (c : α), c ∈ s → (c, g c) ∈ s.zip (s.map g) := by
  intro s
  induction s with
  | nil => intro c h; simp at h
  | cons a s ih =>
    intro c h
    simp only [List.mem_cons] at h
    rcases h with h | h
    · subst h; simp
    · simp [List.zip_cons_cons, ih c h]

/-- If every scalar of `s` agrees and none is `U+03A3`, the lowercase is the per-scalar
image. -/
theorem lower_eq_of_agree (D : Data α) (P : Premises D) (s : List α)
    (hns : ∀ c ∈ s, c ≠ D.sigma) : D.lowerCtx s = s.map D.low := by
  apply eq_map_of_zip D.low s _ (P.lenEq s)
  intro p hp
  apply P.ctx s p hp
  exact hns p.1 (List.of_mem_zip hp).1

theorem pmap_eq_of_pointwise (f g : α → List α) (s : List α) (h : ∀ c ∈ s, f c = g c) :
    pmap f s = pmap g s := by
  simp only [pmap_eq_flatten]
  congr 1
  exact List.map_congr_left h

/-- **The per-scalar scan decides the whole-string equality** under the premises. -/
theorem stable_correct (D : Data α) (P : Premises D) (s : List α) :
    stable D s = spec D s := by
  unfold stable spec
  by_cases ha : s.all D.ascii = true
  · -- ASCII: every scalar agrees and none is sigma
    have hs : ∀ c ∈ s, c ≠ D.sigma := fun c hc =>
      (P.ascii c (List.all_eq_true.mp ha c hc)).2
    have hl := lower_eq_of_agree D P s hs
    have : pmap D.fold s = lower D s := by
      rw [lower, hl, ← pmap_eq_flatten]
      exact pmap_eq_of_pointwise _ _ s (fun c hc => (P.ascii c (List.all_eq_true.mp ha c hc)).1)
    simp [ha, this]
  · simp only [ha, Bool.false_eq_true, ↓reduceIte]
    by_cases hg : s.all (fun c => D.fold c == D.low c) = true
    · simp only [hg, ↓reduceIte]
      by_cases hsig : s.contains D.sigma = true
      · simp only [hsig, ↓reduceIte]
      · simp only [hsig, Bool.false_eq_true, ↓reduceIte]
        have hs : ∀ c ∈ s, c ≠ D.sigma := by
          intro c hc heq
          subst heq
          exact hsig (List.contains_iff_mem.mpr hc)
        have hl := lower_eq_of_agree D P s hs
        have : pmap D.fold s = lower D s := by
          rw [lower, hl, ← pmap_eq_flatten]
          apply pmap_eq_of_pointwise
          intro c hc
          simpa using List.all_eq_true.mp hg c hc
        simp [this]
    · simp only [hg, Bool.false_eq_true, ↓reduceIte]
      -- some scalar disagrees; it is not sigma, and the lengths force a chunk-wise match
      symm
      rw [beq_eq_false_iff_ne]
      intro heq
      apply hg
      rw [List.all_eq_true]
      intro c hc
      have hchunks : s.map D.fold = D.lowerCtx s := by
        apply chunks_eq_of_flatten_eq
        · simp [P.lenEq s]
        · intro p hp
          -- p ∈ (s.map fold).zip (lowerCtx s): rewrite it through s.zip (lowerCtx s)
          rw [List.zip_map_left] at hp
          obtain ⟨q, hq, rfl⟩ := List.mem_map.mp hp
          exact P.dom s q hq
        · rw [← pmap_eq_flatten]; exact heq
      by_cases hcs : c = D.sigma
      · subst hcs; simp [P.sigma]
      · have hmem := mem_zip_map D.fold s c hc
        rw [hchunks] at hmem
        have := P.ctx s (c, D.fold c) hmem hcs
        simpa using this

end Text.CaseFold
