import Confusables.Props

/-!
# Theorems proved in general (kernel-checked, every input)

None of these evaluates a string, and none relies on `native_decide`. Except where a
statement names a table fact (`isMark_ascii`), no proof unfolds a table, so each holds
for the *full* tables and not only for their projection onto the alphabet.
-/

namespace Confusables
open Tables

@[simp] theorem Policy.beq_eq (a b : Policy) : (a == b) = decide (a = b) := by
  cases a <;> cases b <;> rfl

/-! ## The fixed-point loop: idempotence follows from convergence -/

/-- The loop only reports convergence at a string the next pass leaves alone
(confusables.rs:291-298). -/
theorem fixedLoop_stable (p : Policy) :
    ∀ (n : Nat) (cur : List Char), (fixedLoop p n cur).2 = true →
      foldPass p (fixedLoop p n cur).1 = none ∨
        foldPass p (fixedLoop p n cur).1 = some (fixedLoop p n cur).1
  | 0, cur, h => by simp [fixedLoop] at h
  | n + 1, cur, h => by
    unfold fixedLoop at h ⊢
    cases hf : foldPass p cur with
    | none => simp [hf]
    | some next =>
      simp only [hf] at h ⊢
      by_cases he : (next == cur) = true
      · have : next = cur := by simpa using he
        simp [this, hf]
      · simp only [he] at h ⊢
        exact fixedLoop_stable p n next h

theorem fixedFoldB_stable (p : Policy) (s : List Char) (h : (fixedFoldB p s).2 = true) :
    foldPass p (fixedFold p s) = none ∨ foldPass p (fixedFold p s) = some (fixedFold p s) := by
  unfold fixedFold fixedFoldB at *
  cases hf : foldPass p s with
  | none => simp [hf]
  | some cur =>
    simp only [hf] at h ⊢
    exact fixedLoop_stable p maxPasses cur h

/-- A string the pass leaves alone is returned unchanged by the whole fold. -/
theorem fixedFold_of_stable (p : Policy) (y : List Char)
    (h : foldPass p y = none ∨ foldPass p y = some y) : fixedFold p y = y := by
  unfold fixedFold fixedFoldB
  rcases h with h | h
  · simp [h]
  · simp only [maxPasses, fixedLoop, h]
    simp

/-- **Idempotence, in general**: whenever the fold converges within its pass budget,
`f(f(x)) = f(x)`. What is left to the tables is only convergence itself, which
`Checks.lean` bounds and the probe sweeps (no input tried ever hit the cap). -/
theorem fixedFold_idem (p : Policy) (s : List Char) (h : (fixedFoldB p s).2 = true) :
    fixedFold p (fixedFold p s) = fixedFold p s :=
  fixedFold_of_stable p _ (fixedFoldB_stable p s h)

/-! ## Detection and location agree -/

theorem any_eq_not_isEmpty_filterMap {α β : Type} (P : α → Bool) (f : α → Option β)
    (hf : ∀ a, (f a).isSome = P a) : ∀ l : List α, l.any P = !(l.filterMap f).isEmpty
  | [] => by simp
  | a :: l => by
    have ih := any_eq_not_isEmpty_filterMap P f hf l
    cases h : f a with
    | none =>
      have : P a = false := by rw [← hf a, h]; rfl
      simp [h, this, ih]
    | some b =>
      have : P a = true := by rw [← hf a, h]; rfl
      simp [h, this]

/-- `is_confusable` is true exactly when `find_confusables` reports something
(confusables.rs:413-435 and 480-497 walk the same composed stream with the same test). -/
theorem isConfusable_eq_find (s : List Char) :
    isConfusable s = !(findConfusables s).isEmpty := by
  unfold isConfusable findConfusables
  apply any_eq_not_isEmpty_filterMap
  intro c
  by_cases ha : asciiGraphic c = true
  · simp [ha]
  · simp only [ha]; cases latinMap c <;> simp

/-! ## The digit policies act only at their rows -/

theorem lookup_tr39_of_no_override (c : Char) (h : tr39Override c = none) :
    lookup .tr39 c = lookup .numeric c := by
  simp [lookup, h]

theorem lookup_numeric (c : Char) : lookup .numeric c = latinMap c := by
  unfold lookup; cases latinMap c <;> simp

theorem lookup_preserve (c : Char) :
    lookup .preserve c = if (latinMap c).any isDigitValue then none else lookup .numeric c := by
  unfold lookup; cases latinMap c <;> simp

theorem flatMap_congr_mem {α β : Type} (f g : α → List β) :
    ∀ (l : List α), (∀ a ∈ l, f a = g a) → l.flatMap f = l.flatMap g
  | [], _ => rfl
  | a :: l, h => by
    simp only [List.flatMap_cons]
    rw [h a (by simp), flatMap_congr_mem f g l (fun x hx => h x (by simp [hx]))]

theorem any_congr_mem {α : Type} (f g : α → Bool) :
    ∀ (l : List α), (∀ a ∈ l, f a = g a) → l.any f = l.any g
  | [], _ => rfl
  | a :: l, h => by
    simp only [List.any_cons]
    rw [h a (by simp), any_congr_mem f g l (fun x hx => h x (by simp [hx]))]

/-- **tr39 changes nothing away from an override row**: on a string none of whose
characters (as written, and as composed) is a tr39 override source, one tr39 pass is
exactly one numeric pass. -/
theorem foldPass_tr39_eq_numeric (s : List Char)
    (h1 : ∀ c ∈ s, tr39Override c = none) (h2 : ∀ c ∈ composed s, tr39Override c = none) :
    foldPass .tr39 s = foldPass .numeric s := by
  have e1 : ∀ c ∈ s, foldChar .tr39 c = foldChar .numeric c := fun c hc => by
    simp [foldChar, lookup_tr39_of_no_override c (h1 c hc)]
  have e2 : ∀ c ∈ composed s, foldChar .tr39 c = foldChar .numeric c := fun c hc => by
    simp [foldChar, lookup_tr39_of_no_override c (h2 c hc)]
  have e3 : ∀ c ∈ s, (lookup .tr39 c).isSome = (lookup .numeric c).isSome := fun c hc => by
    rw [lookup_tr39_of_no_override c (h1 c hc)]
  unfold foldPass
  rw [flatMap_congr_mem _ _ _ e2, flatMap_congr_mem _ _ _ e1, any_congr_mem _ _ _ e3]

/-- Same for `preserve`, away from the digit rows. -/
theorem foldPass_preserve_eq_numeric (s : List Char)
    (h1 : ∀ c ∈ s, (latinMap c).any isDigitValue = false)
    (h2 : ∀ c ∈ composed s, (latinMap c).any isDigitValue = false) :
    foldPass .preserve s = foldPass .numeric s := by
  have l : ∀ c, (latinMap c).any isDigitValue = false → lookup .preserve c = lookup .numeric c :=
    fun c hc => by rw [lookup_preserve, hc]; simp
  have e1 : ∀ c ∈ s, foldChar .preserve c = foldChar .numeric c := fun c hc => by
    simp [foldChar, l c (h1 c hc)]
  have e2 : ∀ c ∈ composed s, foldChar .preserve c = foldChar .numeric c := fun c hc => by
    simp [foldChar, l c (h2 c hc)]
  have e3 : ∀ c ∈ s, (lookup .preserve c).isSome = (lookup .numeric c).isSome := fun c hc => by
    rw [l c (h1 c hc)]
  unfold foldPass
  rw [flatMap_congr_mem _ _ _ e2, flatMap_congr_mem _ _ _ e1, any_congr_mem _ _ _ e3]

/-! ## Completeness where the pass borrows -/

/-- Table fact: no ASCII character is a combining mark. -/
theorem isMark_ascii (c : Char) (h : c.toNat < 0x80) : isMark c = false := by
  simp only [isMark]
  have : c.toNat ≠ 0x300 ∧ c.toNat ≠ 0x301 ∧ c.toNat ≠ 0x303 ∧ c.toNat ≠ 0x304 ∧
      c.toNat ≠ 0x308 ∧ c.toNat ≠ 0x327 ∧ c.toNat ≠ 0x344 := by omega
  simp [this]

/-- `composed` is the identity on a string with no combining mark (compose.rs:179-182). -/
theorem composed_no_mark : ∀ (s : List Char), (∀ c ∈ s, isMark c = false) → composed s = s
  | [], _ => by simp [composed]
  | [c], _ => by simp [composed]
  | c :: m :: t, h => by
    have hm : isMark m = false := h m (by simp)
    rw [composed]
    simp only [hm]
    have := composed_no_mark (m :: t) (fun x hx => h x (by simp [hx]))
    simp [this]

/-- **Completeness where the pass borrows**: under `numeric` or `tr39`, a string the
pass leaves borrowed (`Cow::Borrowed`, confusables.rs:256) is not confusable. Together
with `fixedFoldB_stable` this is completeness for every fold that ends on a borrowing
pass; the other exit (an owned pass equal to its input, possible only on input with a
combining mark) is table-dependent and is what `Checks.lean` and the probe bound.
Under `preserve` it is false, by `F2_preserve_incomplete` in `Checks.lean`. -/
theorem borrowed_not_confusable (p : Policy) (hp : p ≠ .preserve) (s : List Char)
    (h : foldPass p s = none) : isConfusable s = false := by
  unfold foldPass at h
  by_cases hc : (!isAsciiStr s && needsComposition s) = true
  · simp [hc] at h
  · simp only [hc] at h
    by_cases ha : s.any (fun c => (lookup p c).isSome) = true
    · simp [ha] at h
    · have nomark : ∀ c ∈ s, isMark c = false := by
        intro c hcs
        by_cases hasc : isAsciiStr s = true
        · have : c.toNat < 0x80 := by
            have := List.all_eq_true.mp hasc c hcs
            simpa using this
          exact isMark_ascii c this
        · have hn : needsComposition s = false := by
            simp only [hasc, Bool.not_false, Bool.true_and] at hc
            simpa using hc
          have := List.any_eq_false.mp hn c hcs
          simp only [couldCompose, Bool.or_eq_true, not_or] at this
          simpa using this.1
      unfold isConfusable
      rw [composed_no_mark s nomark]
      apply List.any_eq_false.mpr
      intro c hcs
      have hl : lookup p c = none := by
        have h' : ∀ x ∈ s, lookup p x = none := by simpa using ha
        exact h' c hcs
      have : latinMap c = none := by
        cases p with
        | numeric => rwa [lookup_numeric] at hl
        | tr39 =>
          unfold lookup at hl
          cases ho : tr39Override c with
          | some o => simp [ho] at hl
          | none => simp only [ho] at hl; cases hm : latinMap c <;> simp_all
        | preserve => exact absurd rfl hp
      simp [this]

end Confusables
