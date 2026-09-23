import Text.Zalgo

/-!
# General theorems about `strip_zalgo` (induction; no `native_decide`)

These hold for every input and every `max_marks`.

* `strip_sublist` — the output is a subsequence of the NFD of the input: nothing is
  invented and nothing is reordered.
* `strip_keeps_bases` — every non-mark survives, in order.
* `strip_keeps_protected` — for `max_marks > 0` every class-0 mark survives too (#842).
* `strip_zero_only_negation` — with `max_marks = 0` the only marks left are negation
  overlays (#749): "0 strips all combining marks" holds except for those.
* `strip_id_of_not_zalgo` — when `is_zalgo` is false the result is the NFD of the input,
  so no mark is lost (#788's invariant).
-/

namespace Text.Zalgo

/-- What `strip_zalgo` never drops at threshold `k`: a non-mark, and (for `k > 0`) a class-0
mark. -/
def protected_ (k : Nat) (c : Ch) : Bool := !isMark c || (k > 0 && ccc c == 0)

theorem stripStep_out (k : Nat) (st : SSt) (c : Ch) :
    ((stripStep k st c).out = st.out ++ [c]) ∨
      ((stripStep k st c).out = st.out ∧ protected_ k c = false) := by
  unfold stripStep
  split
  · left; rfl
  · cases c with
    | base sym id => left; rfl
    | mark cl neg id =>
      simp only
      split
      · left; rfl
      · rename_i h
        have hp : protected_ k (.mark cl neg id) = false := by
          simp only [Bool.and_eq_true, beq_iff_eq, decide_eq_true_eq, not_and] at h
          simp only [protected_, isMark, ccc, Bool.not_true, Bool.false_or, Bool.and_eq_false_iff,
            decide_eq_false_iff_not, Nat.not_lt, beq_eq_false_iff_ne]
          by_cases hk : k = 0
          · left; omega
          · right; intro hc; exact h hc (by omega)
        split <;> split <;> first | (left; rfl) | (right; exact ⟨rfl, hp⟩)

/-- At threshold 0, a mark that is not taken by the negation branch is dropped. -/
theorem stripStep_zero_drop (st : SSt) (cl : Nat) (neg : Bool) (id : Nat)
    (hn : ¬(isNegationOf (.mark cl neg id) st.base && !st.negKept) = true) :
    (stripStep 0 st (.mark cl neg id)).out = st.out := by
  unfold stripStep
  simp only [hn, Bool.false_eq_true, ↓reduceIte, Nat.lt_irrefl, decide_false, Bool.and_false, Bool.false_eq_true, ↓reduceIte]
  split <;> simp

theorem foldl_out (k : Nat) : ∀ (l : List Ch) (st : SSt), ∃ l',
    (l.foldl (stripStep k) st).out = st.out ++ l' ∧ l'.Sublist l ∧
      l'.filter (protected_ k) = l.filter (protected_ k) := by
  intro l
  induction l with
  | nil => intro st; exact ⟨[], by simp, List.Sublist.slnil, rfl⟩
  | cons c l ih =>
    intro st
    obtain ⟨l', h1, h2, h3⟩ := ih (stripStep k st c)
    rcases stripStep_out k st c with h | ⟨h, hp⟩
    · refine ⟨c :: l', ?_, h2.cons_cons c, ?_⟩
      · simp only [List.foldl_cons, h1, h, List.append_assoc, List.singleton_append]
      · simp only [List.filter_cons, h3]
    · refine ⟨l', ?_, h2.cons c, ?_⟩
      · simp only [List.foldl_cons, h1, h]
      · simp [hp, h3]

/-- The output is a subsequence of NFD(input). -/
theorem strip_sublist (k : Nat) (s : List Ch) : (strip k s).Sublist (canon s) := by
  unfold strip
  split
  · obtain ⟨l', h1, h2, _⟩ := foldl_out k (canon s) {}
    unfold stripSlow; rw [h1]; simpa using h2
  · exact List.Sublist.refl _

/-- Every non-mark and (for `k > 0`) every class-0 mark survives, in order. -/
theorem strip_keeps_protected (k : Nat) (s : List Ch) :
    (strip k s).filter (protected_ k) = (canon s).filter (protected_ k) := by
  unfold strip
  split
  · obtain ⟨l', h1, _, h3⟩ := foldl_out k (canon s) {}
    unfold stripSlow; rw [h1]; simpa using h3
  · rfl

theorem strip_keeps_bases (k : Nat) (s : List Ch) :
    (strip k s).filter (fun c => !isMark c) = (canon s).filter (fun c => !isMark c) := by
  have h := congrArg (List.filter (fun c => !isMark c)) (strip_keeps_protected k s)
  simp only [List.filter_filter] at h
  have e : (fun c => (!isMark c && protected_ k c)) = (fun c => !isMark c) := by
    funext c; cases c <;> simp [protected_, isMark]
  rw [e] at h
  exact h

/-- When the predicate is false the transform returns NFD(input): no mark is lost. -/
theorem strip_id_of_not_zalgo (k : Nat) (s : List Ch) (h : isZalgo k s = false) :
    strip k s = canon s := by
  simp [strip, h]

/-- At threshold 0 the predicate fires on any mark at all. -/
theorem exceedsGo_zero_of_mark : ∀ (l : List Ch) (r p : Nat), (∃ c ∈ l, isMark c = true) →
    exceedsGo 0 r p l = true := by
  intro l
  induction l with
  | nil => intro r p ⟨c, hc, _⟩; simp at hc
  | cons c l ih =>
    intro r p ⟨d, hd, hm⟩
    cases c with
    | base sym id =>
      simp only [exceedsGo]
      simp only [List.mem_cons] at hd
      rcases hd with hd | hd
      · subst hd; simp [isMark] at hm
      · exact ih 0 0 ⟨d, hd, hm⟩
    | mark cl neg id =>
      simp only [exceedsGo, Nat.lt_irrefl, decide_false, Bool.and_false, Bool.false_eq_true,
        ↓reduceIte]
      split <;> simp

theorem stripStep_zero_mark (st : SSt) (c : Ch) (hm : isMark c = true)
    (hkept : (stripStep 0 st c).out = st.out ++ [c]) : ∃ cl id, c = .mark cl true id := by
  cases c with
  | base _ _ => simp [isMark] at hm
  | mark cl neg id =>
    by_cases hn : (isNegationOf (.mark cl neg id) st.base && !st.negKept) = true
    · cases neg with
      | true => exact ⟨cl, id, rfl⟩
      | false => simp [isNegationOf] at hn
    · rw [stripStep_zero_drop st cl neg id hn] at hkept
      have := congrArg List.length hkept
      simp at this

theorem foldl_zero_marks : ∀ (l : List Ch) (st : SSt),
    ∀ c ∈ (l.foldl (stripStep 0) st).out, c ∈ st.out ∨ (isMark c = true → ∃ cl id, c = .mark cl true id) := by
  intro l
  induction l with
  | nil => intro st c hc; left; exact hc
  | cons d l ih =>
    intro st c hc
    rcases ih (stripStep 0 st d) c hc with h | h
    · rcases stripStep_out 0 st d with ho | ⟨ho, _⟩
      · rw [ho] at h
        simp only [List.mem_append, List.mem_singleton] at h
        rcases h with h | h
        · left; exact h
        · subst h; right; intro hm; exact stripStep_zero_mark st c hm ho
      · rw [ho] at h; left; exact h
    · right; exact h

/-- **`max_marks = 0`**: every mark left is a negation overlay (`U+0338`/`U+20D2`). The
Rust doc's "0 strips all combining marks" holds up to #749's deliberate exception. -/
theorem strip_zero_only_negation (s : List Ch) :
    ∀ c ∈ strip 0 s, isMark c = true → ∃ cl id, c = .mark cl true id := by
  intro c hc hm
  unfold strip at hc
  split at hc
  · rcases foldl_zero_marks (canon s) {} c hc with h | h
    · simp at h
    · exact h hm
  · rename_i hz
    exfalso
    have : exceedsGo 0 0 0 (canon s) = true := exceedsGo_zero_of_mark _ 0 0 ⟨c, hc, hm⟩
    simp only [isZalgo] at hz
    rw [this] at hz
    exact absurd hz (by decide)

end Text.Zalgo
