/-!
# Bounded enumeration

`allUpTo alpha n p` checks `p` on every word of length `≤ n` over `alpha`, without
materializing the word list (at `n = 7` over eight letters that list would not fit in
memory). The words are built by consing, so they come out reversed relative to the order
the letters were chosen in; since every word is visited, that does not matter.
-/

namespace Text

/-- `p` holds on every word of length `≤ n` over `alpha`, extending `acc`. -/
def allUpToFrom {α : Type} (alpha : List α) (p : List α → Bool) : Nat → List α → Bool
  | 0, acc => p acc
  | n + 1, acc => p acc && alpha.all (fun a => allUpToFrom alpha p n (a :: acc))

/-- `p` holds on every word of length `≤ n` over `alpha`. -/
def allUpTo {α : Type} (alpha : List α) (n : Nat) (p : List α → Bool) : Bool :=
  allUpToFrom alpha p n []

/-- Number of words of length `≤ n` over an alphabet of size `k`. -/
def countUpTo (k n : Nat) : Nat := ((List.range (n + 1)).map (k ^ ·)).foldl (· + ·) 0

/-- Soundness of the enumerator: a `true` answer covers every word of length `≤ n`. -/
theorem allUpToFrom_sound {α : Type} (alpha : List α) (p : List α → Bool) :
    ∀ (n : Nat) (acc w : List α), allUpToFrom alpha p n acc = true →
      w.length ≤ n → (∀ a ∈ w, a ∈ alpha) → p (w.reverse ++ acc) = true := by
  intro n
  induction n with
  | zero =>
    intro acc w h hl _
    have : w = [] := List.eq_nil_of_length_eq_zero (by omega)
    subst this
    simpa [allUpToFrom] using h
  | succ n ih =>
    intro acc w h hl hw
    simp only [allUpToFrom, Bool.and_eq_true, List.all_eq_true] at h
    match w with
    | [] => simpa using h.1
    | a :: w' =>
      have ha : a ∈ alpha := hw a (by simp)
      have hrec := ih (a :: acc) w' (h.2 a ha) (by simp at hl; omega)
        (fun b hb => hw b (by simp [hb]))
      simpa [List.reverse_cons, List.append_assoc] using hrec

theorem allUpTo_sound {α : Type} (alpha : List α) (n : Nat) (p : List α → Bool)
    (h : allUpTo alpha n p = true) (w : List α) (hl : w.length ≤ n)
    (hw : ∀ a ∈ w, a ∈ alpha) : p w = true := by
  have := allUpToFrom_sound alpha p n [] w.reverse h (by simpa using hl)
    (fun a ha => hw a (by simpa using ha))
  simpa using this

end Text
