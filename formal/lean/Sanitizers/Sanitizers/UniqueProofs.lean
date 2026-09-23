import Sanitizers.Unique

/-!
# General theorems about `UniqueSlugifier`

For every configuration, every `MAX_UNIQUE_ATTEMPTS` and every sequence of calls.
Induction only: no `native_decide`, no `sorry`.

| Theorem | Statement |
|---|---|
| `run_nodup` | **Uniqueness**: the slugs one instance returns are pairwise distinct |
| `runNoHint_nodup` | the same for the walk without the per-base hint (the `check` path) |
| `runFixed_nodup` | the fixed model returns pairwise distinct *non-empty* slugs (it returns the empty slug unsuffixed, as `slugify` does) |

Whether the hint changes any output (`run = runNoHint`) is checked bounded in
`Bounded.lean`.
-/

set_option linter.deprecated false  -- `if_pos` / `if_neg` read better here than their replacements

namespace Sanitizers.Unique

open Sanitizers.Slug

def oks : List (Except Err (List Char)) → List (List Char)
  | [] => []
  | .ok c :: rs => c :: oks rs
  | .error _ :: rs => oks rs

theorem walk_fresh (sep base : List Char) (ml ma : Nat) (seen : List (List Char)) :
    ∀ (fuel counter : Nat) (lossy : Bool) (k : Nat) (c : List Char),
      walk sep base ml ma seen fuel counter lossy = .ok (k, c) → c ∉ seen
  | 0, _, _, _, _, h => by simp [walk] at h
  | fuel + 1, counter, lossy, k, c, h => by
    unfold walk at h
    split at h
    · simp at h
    · split at h
      · simp at h
      · simp only at h
        split at h
        · rename_i hfree
          simp at h
          obtain ⟨_, rfl⟩ := h
          simpa using hfree
        · exact walk_fresh sep base ml ma seen fuel _ _ k c h

/-- The contract a call satisfies: a returned slug was not seen before and is recorded;
an error leaves the state alone. -/
def Fresh (f : St → List Char → Except Err (List Char) × St) : Prop :=
  ∀ st t, match f st t with
    | (.ok c, st') => st'.seen = c :: st.seen ∧ c ∉ st.seen
    | (.error _, st') => st' = st

theorem runAll_nodup (f : St → List Char → Except Err (List Char) × St) (hf : Fresh f) :
    ∀ (st : St) (ts : List (List Char)),
      (oks (runAll f st ts)).Nodup ∧ ∀ c ∈ oks (runAll f st ts), c ∉ st.seen
  | _, [] => by simp [runAll, oks]
  | st, t :: ts => by
    have h := hf st t
    simp only [runAll]
    revert h
    generalize f st t = r
    obtain ⟨res, st'⟩ := r
    intro h
    obtain ⟨ih1, ih2⟩ := runAll_nodup f hf st' ts
    cases res with
    | ok c =>
      simp only at h
      obtain ⟨hs, hc⟩ := h
      simp only [oks]
      refine ⟨List.nodup_cons.mpr ⟨?_, ih1⟩, ?_⟩
      · intro hm
        have := ih2 c hm
        rw [hs] at this
        exact this (by simp)
      · intro d hd
        rcases List.mem_cons.mp hd with e | e
        · subst e; exact hc
        · have := ih2 d e
          rw [hs] at this
          intro hin; exact this (List.mem_cons_of_mem _ hin)
    | error e =>
      simp only at h
      subst h
      simp only [oks]
      exact ⟨ih1, ih2⟩

theorem step_fresh (cfg : Config) (ma : Nat) : Fresh (step cfg ma) := by
  intro st t
  unfold step
  simp only
  generalize hw : walk cfg.sep (slugify cfg t) cfg.maxLen ma st.seen (ma + 2)
    (hintOf st.hint (slugify cfg t)) false = w
  cases w with
  | ok kc =>
    obtain ⟨k, c⟩ := kc
    exact ⟨rfl, walk_fresh _ _ _ _ _ _ _ _ k c hw⟩
  | error e => rfl

theorem stepNoHint_fresh (cfg : Config) (ma : Nat) : Fresh (stepNoHint cfg ma) := by
  intro st t
  unfold stepNoHint
  simp only
  generalize hw : walk cfg.sep (slugify cfg t) cfg.maxLen ma st.seen (ma + 2) 0 false = w
  cases w with
  | ok kc =>
    obtain ⟨k, c⟩ := kc
    exact ⟨rfl, walk_fresh _ _ _ _ _ _ _ _ k c hw⟩
  | error e => rfl

/-- **Uniqueness.** -/
theorem run_nodup (cfg : Config) (ma : Nat) (ts : List (List Char)) : (oks (run cfg ma ts)).Nodup :=
  (runAll_nodup _ (step_fresh cfg ma) St.empty ts).1

theorem runNoHint_nodup (cfg : Config) (ma : Nat) (ts : List (List Char)) :
    (oks (runNoHint cfg ma ts)).Nodup :=
  (runAll_nodup _ (stepNoHint_fresh cfg ma) St.empty ts).1

/-! ## The fixed model -/

theorem candidateFixed_zero (sep base : List Char) (ml : Nat) :
    candidateFixed sep base ml 0 = some base := by
  simp [candidateFixed]

theorem walkFixed_fresh (sep base : List Char) (ml ma : Nat) (seen : List (List Char)) :
    ∀ (fuel counter k : Nat) (c : List Char),
      walkFixed sep base ml ma seen fuel counter = .ok (k, c) → c = [] ∨ c ∉ seen
  | 0, _, _, _, h => by simp [walkFixed] at h
  | fuel + 1, counter, k, c, h => by
    unfold walkFixed at h
    split at h
    · simp at h
    · split at h
      · rename_i hnone
        split at h
        · rename_i h0
          have : counter = 0 := by simpa using h0
          subst this
          rw [candidateFixed_zero] at hnone
          simp at hnone
        · simp at h
      · rename_i cand _
        split at h
        · rename_i hb
          simp at h; obtain ⟨_, rfl⟩ := h
          left; simpa using hb
        · split at h
          · rename_i hfree
            simp at h; obtain ⟨_, rfl⟩ := h
            right; simpa using hfree
          · exact walkFixed_fresh sep base ml ma seen fuel _ k c h

/-- The fixed contract: a non-empty slug is fresh and recorded; the empty slug and errors
leave the state alone. -/
def FreshNE (f : St → List Char → Except Err (List Char) × St) : Prop :=
  ∀ st t, match f st t with
    | (.ok c, st') => (c ≠ [] ∧ st'.seen = c :: st.seen ∧ c ∉ st.seen) ∨ (c = [] ∧ st' = st)
    | (.error _, st') => st' = st

theorem runAll_nodup_ne (f : St → List Char → Except Err (List Char) × St) (hf : FreshNE f) :
    ∀ (st : St) (ts : List (List Char)),
      ((oks (runAll f st ts)).filter (· ≠ [])).Nodup ∧
        ∀ c ∈ (oks (runAll f st ts)).filter (· ≠ []), c ∉ st.seen
  | _, [] => by simp [runAll, oks]
  | st, t :: ts => by
    have h := hf st t
    simp only [runAll]
    revert h
    generalize f st t = r
    obtain ⟨res, st'⟩ := r
    intro h
    obtain ⟨ih1, ih2⟩ := runAll_nodup_ne f hf st' ts
    cases res with
    | ok c =>
      simp only at h
      rcases h with ⟨hne, hs, hc⟩ | ⟨he, hst⟩
      · simp only [oks, List.filter_cons, hne, ne_eq, not_false_eq_true, decide_true, if_true]
        refine ⟨List.nodup_cons.mpr ⟨?_, ih1⟩, ?_⟩
        · intro hm
          have := ih2 c hm
          rw [hs] at this
          exact this (by simp)
        · intro d hd
          rcases List.mem_cons.mp hd with e | e
          · subst e; exact hc
          · have := ih2 d e
            rw [hs] at this
            intro hin; exact this (List.mem_cons_of_mem _ hin)
      · subst he; subst hst
        simp only [oks, List.filter_cons, ne_eq, not_true_eq_false, decide_false]
        exact ⟨ih1, ih2⟩
    | error e =>
      simp only at h
      subst h
      simp only [oks]
      exact ⟨ih1, ih2⟩

theorem stepFixed_fresh (cfg : Config) (ma : Nat) : FreshNE (stepFixed cfg ma) := by
  intro st t
  unfold stepFixed
  simp only
  generalize hw : walkFixed cfg.sep (slugifyFixed cfg t) cfg.maxLen ma st.seen (ma + 2)
    (hintOf st.hint (slugifyFixed cfg t)) = w
  cases w with
  | ok kc =>
    obtain ⟨k, c⟩ := kc
    simp only
    by_cases he : c.isEmpty = true
    · rw [if_pos he]
      right; exact ⟨by simpa using he, rfl⟩
    · rw [if_neg he]
      left
      have hne : c ≠ [] := by intro e; subst e; exact he rfl
      refine ⟨hne, rfl, ?_⟩
      rcases walkFixed_fresh _ _ _ _ _ _ _ k c hw with h | h
      · exact absurd h hne
      · exact h
  | error e => rfl

theorem runFixed_nodup (cfg : Config) (ma : Nat) (ts : List (List Char)) :
    ((oks (runFixed cfg ma ts)).filter (· ≠ [])).Nodup :=
  (runAll_nodup_ne _ (stepFixed_fresh cfg ma) St.empty ts).1

end Sanitizers.Unique
