/-!
# The per-character → string lift, and exactly what it needs

`docs/formal-verification.md` discharges I2 (ASCII output) by exhaustion over
single BMP code points plus a *structural lift*: "the output of a character-wise
map that emits ASCII for every character is ASCII for every string". I3
(idempotence) is exhausted the same way, one code point at a time.

This file states that lift abstractly and proves it, with every premise explicit.
Strings are lists over an arbitrary alphabet `α`; "ASCII" is an arbitrary
Boolean predicate `asc` on the alphabet (instantiated to `c.toNat < 128` for
`Char` in `Counterexamples.lean`).

The premise that carries the weight is `IsHom f`:
`f (a ++ b) = f a ++ f b`. Everything below is conditional on it, except the
last section, which lifts I3 from string-level I1 + I2 *without* it.
-/

namespace Transliterate

variable {α : Type}

/-- Every symbol of `s` satisfies `asc` ("`s` is ASCII"). -/
def AllA (asc : α → Bool) (s : List α) : Prop := ∀ x ∈ s, asc x = true

theorem AllA.nil (asc : α → Bool) : AllA asc [] := by
  intro x hx; cases hx

theorem AllA.append {asc : α → Bool} {a b : List α} (ha : AllA asc a) (hb : AllA asc b) :
    AllA asc (a ++ b) := by
  intro x hx
  rcases List.mem_append.mp hx with h | h
  · exact ha x h
  · exact hb x h

theorem AllA.left {asc : α → Bool} {a b : List α} (h : AllA asc (a ++ b)) : AllA asc a :=
  fun x hx => h x (List.mem_append.mpr (Or.inl hx))

theorem AllA.right {asc : α → Bool} {a b : List α} (h : AllA asc (a ++ b)) : AllA asc b :=
  fun x hx => h x (List.mem_append.mpr (Or.inr hx))

theorem AllA.singleton {asc : α → Bool} {c : α} : AllA asc [c] ↔ asc c = true := by
  constructor
  · intro h; exact h c (List.mem_singleton.mpr rfl)
  · intro h x hx; rw [List.mem_singleton.mp hx]; exact h

/-- **Premise H.** `f` is a monoid homomorphism on the free monoid `List α`. -/
def IsHom (f : List α → List α) : Prop := ∀ a b, f (a ++ b) = f a ++ f b

/-- The concrete shape H describes: a character-wise map, `s ↦ concat (g c)`. -/
def charwise (g : α → List α) (s : List α) : List α := s.flatMap g

theorem charwise_isHom (g : α → List α) : IsHom (charwise g) := by
  intro a b; simp [charwise, List.flatMap_append]

theorem charwise_singleton (g : α → List α) (c : α) : charwise g [c] = g c := by
  simp [charwise]

/-- H forces `f [] = []` (length argument), so H needs no separate ε-premise. -/
theorem IsHom.nil {f : List α → List α} (h : IsHom f) : f [] = [] := by
  have e := h [] []
  simp only [List.nil_append] at e
  have hl := congrArg List.length e
  rw [List.length_append] at hl
  exact List.eq_nil_of_length_eq_zero (by omega)

/-- Conversely every homomorphism *is* `charwise` of its values on singletons, so
H is exactly "f is a character-wise map" — the doc's structural premise. -/
theorem IsHom.eq_charwise {f : List α → List α} (h : IsHom f) :
    ∀ s, f s = charwise (fun c => f [c]) s := by
  intro s
  induction s with
  | nil => simp [charwise, h.nil]
  | cons c t ih =>
    have : c :: t = [c] ++ t := rfl
    rw [this, h, ih]; simp [charwise]

/-! ## Lifts under H -/

/-- **I1 lift.** Per-character ASCII passthrough + H ⇒ string-level I1. -/
theorem lift_I1 {asc : α → Bool} {f : List α → List α} (hH : IsHom f)
    (h1 : ∀ c, asc c = true → f [c] = [c]) :
    ∀ s, AllA asc s → f s = s := by
  intro s
  induction s with
  | nil => intro _; exact hH.nil
  | cons c t ih =>
    intro hs
    have hc : asc c = true := hs c (List.mem_cons_self ..)
    have ht : AllA asc t := fun x hx => hs x (List.mem_cons_of_mem c hx)
    have : c :: t = [c] ++ t := rfl
    rw [this, hH, h1 c hc, ih ht]

/-- **I2 lift** (the doc's "(b) structural" step). Per-character ASCII output
+ H ⇒ ASCII output for every string. -/
theorem lift_I2 {asc : α → Bool} {f : List α → List α} (hH : IsHom f)
    (h2 : ∀ c, AllA asc (f [c])) :
    ∀ s, AllA asc (f s) := by
  intro s
  induction s with
  | nil => rw [hH.nil]; exact AllA.nil asc
  | cons c t ih =>
    have : c :: t = [c] ++ t := rfl
    rw [this, hH]; exact (h2 c).append ih

/-- **I3 lift, route 1.** Per-character idempotence + H ⇒ string idempotence.
(Needs only H: no ASCII premise at all.) -/
theorem lift_I3_hom {f : List α → List α} (hH : IsHom f)
    (h3 : ∀ c, f (f [c]) = f [c]) :
    ∀ s, f (f s) = f s := by
  intro s
  induction s with
  | nil => rw [hH.nil, hH.nil]
  | cons c t ih =>
    have : c :: t = [c] ++ t := rfl
    rw [this, hH, hH, h3, ih]

/-- **I3 lift, route 2** (the one the exhaustive tests actually support). Under
H, per-character I1 and per-character I2 already give string idempotence:
`f s` is ASCII (lift_I2) and ASCII is fixed (lift_I1). -/
theorem lift_I3_via_I1_I2 {asc : α → Bool} {f : List α → List α} (hH : IsHom f)
    (h1 : ∀ c, asc c = true → f [c] = [c]) (h2 : ∀ c, AllA asc (f [c])) :
    ∀ s, f (f s) = f s :=
  fun s => lift_I1 hH h1 (f s) (lift_I2 hH h2 s)

/-! ## I3 without H

The real `transliterate` is **not** a homomorphism (see `search/` and the
README), so the lifts above do not apply to it. But idempotence does not need
H: string-level I1 and string-level I2 suffice. This is the argument that is
actually available for the real code, provided string-level I1 and I2 are
established by other means (`Engine.lean`). -/

/-- **I3 from string-level I1 + I2**, for *any* `f` (no H). -/
theorem I3_of_I1_I2 {asc : α → Bool} {f : List α → List α}
    (i1 : ∀ s, AllA asc s → f s = s) (i2 : ∀ s, AllA asc (f s)) :
    ∀ s, f (f s) = f s :=
  fun s => i1 (f s) (i2 s)

/-- The same, restricted to the inputs where I2 holds — which is how the real
library behaves when an option (tones, context) breaks I2 on part of the input
space: I3 still holds wherever the output happens to be ASCII. -/
theorem I3_of_I1_at {asc : α → Bool} {f : List α → List α}
    (i1 : ∀ s, AllA asc s → f s = s) {s : List α} (h : AllA asc (f s)) :
    f (f s) = f s :=
  i1 (f s) h

end Transliterate
