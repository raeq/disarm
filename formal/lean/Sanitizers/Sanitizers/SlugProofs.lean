import Sanitizers.Slug

/-!
# General theorems about `slugify` (ASCII path)

For every input and every configuration, including separators that are empty, long, or
made of word characters. Induction only: no `native_decide`, no `sorry`.

| Theorem | Statement |
|---|---|
| `slugify_chars` | S1: every character is a separator character, or an ASCII alphanumeric of the (lowercased) input |
| `slugify_length` | S3: at most `max_length` characters (bytes, on ASCII) when `max_length > 0` |

The separator-*position* properties (S2) are not general theorems: they fail for
multi-character separators (Finding 5), and `Bounded.lean` checks them for the
separators where they hold.
-/

namespace Sanitizers.Slug

theorem build_good (sep : List Char) :
    ∀ (l : List Char) (prev : Bool) (c : Char), c ∈ build sep l prev →
      c ∈ sep ∨ (isAlnum c = true ∧ c ∈ l)
  | [], _, c, h => by simp [build] at h
  | x :: xs, prev, c, h => by
    unfold build at h
    split at h
    · rename_i hx
      rcases List.mem_cons.mp h with h' | h'
      · subst h'; exact Or.inr ⟨hx, by simp⟩
      · rcases build_good sep xs false c h' with h'' | ⟨a, b⟩
        · exact Or.inl h''
        · exact Or.inr ⟨a, List.mem_cons_of_mem _ b⟩
    · split at h
      · rcases List.mem_append.mp h with h' | h'
        · exact Or.inl h'
        · rcases build_good sep xs true c h' with h'' | ⟨a, b⟩
          · exact Or.inl h''
          · exact Or.inr ⟨a, List.mem_cons_of_mem _ b⟩
      · rcases build_good sep xs prev c h with h'' | ⟨a, b⟩
        · exact Or.inl h''
        · exact Or.inr ⟨a, List.mem_cons_of_mem _ b⟩

theorem stripOnce_sub (sep l : List Char) (c : Char) (h : c ∈ stripOnce sep l) : c ∈ l := by
  unfold stripOnce at h
  split at h
  · exact List.mem_of_mem_take h
  · exact h

theorem stripOnce_length (sep l : List Char) : (stripOnce sep l).length ≤ l.length := by
  unfold stripOnce
  split
  · simp
  · exact Nat.le_refl _

theorem stripPartial_sub (sep s : List Char) (c : Char) (h : c ∈ stripPartial sep s) : c ∈ s := by
  unfold stripPartial at h
  split at h
  · exact h
  · simp only at h
    split at h
    · exact List.mem_of_mem_take h
    · exact h

theorem stripPartial_length (sep s : List Char) : (stripPartial sep s).length ≤ s.length := by
  unfold stripPartial
  split
  · exact Nat.le_refl _
  · simp only
    split
    · simp
    · exact Nat.le_refl _

theorem splitF_sub (sep : List Char) :
    ∀ (n : Nat) (acc l : List Char) (w : List Char), w ∈ splitF sep n acc l →
      ∀ c ∈ w, c ∈ acc ∨ c ∈ l
  | 0, acc, l, w, hw, c, hc => by
    simp [splitF] at hw; subst hw
    rcases List.mem_append.mp hc with h | h
    · exact Or.inl (List.mem_reverse.mp h)
    · exact Or.inr h
  | n + 1, acc, l, w, hw, c, hc => by
    unfold splitF at hw
    split at hw
    · simp at hw; subst hw; exact Or.inl (List.mem_reverse.mp hc)
    · rename_i x xs
      split at hw
      · rcases List.mem_cons.mp hw with h | h
        · subst h; exact Or.inl (List.mem_reverse.mp hc)
        · rcases splitF_sub sep n [] _ w h c hc with h' | h'
          · simp at h'
          · exact Or.inr (List.mem_of_mem_drop h')
      · rcases splitF_sub sep n (x :: acc) xs w hw c hc with h' | h'
        · rcases List.mem_cons.mp h' with h'' | h''
          · subst h''; exact Or.inr (by simp)
          · exact Or.inl h''
        · exact Or.inr (List.mem_cons_of_mem _ h')

theorem split_sub (sep l : List Char) (w : List Char) (hw : w ∈ split sep l) :
    ∀ c ∈ w, c ∈ l := by
  intro c hc
  unfold split at hw
  split at hw
  · simp at hw
    rcases hw with h | ⟨a, ha, h⟩ | h
    · subst h; simp at hc
    · subst h; simp at hc; subst hc; exact ha
    · subst h; simp at hc
  · rcases splitF_sub sep _ [] l w hw c hc with h | h
    · simp at h
    · exact h

theorem join_sub (sep : List Char) :
    ∀ (ws : List (List Char)) (c : Char), c ∈ join sep ws → c ∈ sep ∨ ∃ w ∈ ws, c ∈ w
  | [], c, h => by simp [join] at h
  | [w], c, h => by simp [join] at h; exact Or.inr ⟨w, by simp, h⟩
  | w :: v :: ws, c, h => by
    simp only [join] at h
    rcases List.mem_append.mp h with h' | h'
    · rcases List.mem_append.mp h' with h'' | h''
      · exact Or.inr ⟨w, by simp, h''⟩
      · exact Or.inl h''
    · rcases join_sub sep (v :: ws) c h' with h'' | ⟨u, hu, hc⟩
      · exact Or.inl h''
      · exact Or.inr ⟨u, List.mem_cons_of_mem _ hu, hc⟩

theorem mem_of_mem_dropWhile' {α : Type} {p : α → Bool} :
    ∀ {l : List α} {c : α}, c ∈ l.dropWhile p → c ∈ l
  | [], _, h => by simp at h
  | x :: xs, c, h => by
    simp only [List.dropWhile] at h
    cases hx : p x
    · simp only [hx] at h; exact h
    · simp only [hx] at h; exact List.mem_cons_of_mem _ (mem_of_mem_dropWhile' h)

theorem filterStop_mem (sep : List Char) (stop : List (List Char)) (so : Bool) (slug : List Char)
    (c : Char) (h : c ∈ filterStop sep stop so slug) : c ∈ sep ∨ c ∈ slug := by
  unfold filterStop at h
  simp only at h
  split at h
  · rcases join_sub sep _ c h with h' | ⟨w, hw, hc⟩
    · exact Or.inl h'
    · right
      have hw1 := List.mem_reverse.mp (mem_of_mem_dropWhile' (List.mem_reverse.mp hw))
      have hw2 := mem_of_mem_dropWhile' hw1
      exact split_sub sep slug w hw2 c hc
  · rcases join_sub sep _ c h with h' | ⟨w, hw, hc⟩
    · exact Or.inl h'
    · right
      exact split_sub sep slug w (List.mem_filter.mp hw).1 c hc

theorem truncWord_sub (slug : List Char) (ml : Nat) (sep : List Char) (c : Char)
    (h : c ∈ truncWord slug ml sep) : c ∈ slug := by
  unfold truncWord at h
  split at h
  · exact h
  · simp only at h
    split at h
    · exact List.mem_of_mem_take (List.mem_of_mem_take h)
    · exact List.mem_of_mem_take (stripPartial_sub sep _ c h)

theorem truncate_sub (cfg : Config) (slug : List Char) (c : Char) (h : c ∈ truncate cfg slug) :
    c ∈ slug := by
  unfold truncate at h
  split at h
  · split at h
    · exact truncWord_sub slug cfg.maxLen cfg.sep c h
    · exact List.mem_of_mem_take (stripOnce_sub _ _ c h)
  · exact h

/-- S1: every output character comes from the separator, or is an ASCII alphanumeric of
the lowercased input. With a separator made of non-alphanumerics, the slug's words are
exactly `[A-Za-z0-9]` (`[a-z0-9]` when lowercasing). -/
theorem slugify_chars (cfg : Config) (text : List Char) :
    ∀ c ∈ slugify cfg text, c ∈ cfg.sep ∨ (isAlnum c = true ∧ c ∈ lower cfg text) := by
  intro c hc
  unfold slugify at hc
  split at hc
  · simp at hc
  · simp only at hc
    have h1 := truncate_sub cfg _ c hc
    have h2 : c ∈ cfg.sep ∨ c ∈ stripOnce cfg.sep (build cfg.sep (lower cfg text) true) := by
      split at h1
      · exact Or.inr h1
      · exact filterStop_mem _ _ _ _ c h1
    rcases h2 with h2 | h2
    · exact Or.inl h2
    · exact build_good cfg.sep _ true c (stripOnce_sub _ _ c h2)

theorem truncate_length (cfg : Config) (slug : List Char) (h : 0 < cfg.maxLen) :
    (truncate cfg slug).length ≤ cfg.maxLen := by
  unfold truncate
  split
  · split
    · unfold truncWord
      split
      · omega
      · simp only
        split
        · simp only [List.length_take]; omega
        · have := stripPartial_length cfg.sep (slug.take cfg.maxLen)
          simp only [List.length_take] at this; omega
    · have := stripOnce_length cfg.sep (slug.take cfg.maxLen)
      simp only [List.length_take] at this; omega
  · rename_i hn
    simp only [Bool.and_eq_true, decide_eq_true_eq] at hn
    omega

/-- S3. -/
theorem slugify_length (cfg : Config) (text : List Char) (h : 0 < cfg.maxLen) :
    (slugify cfg text).length ≤ cfg.maxLen := by
  unfold slugify
  split
  · simp
  · exact truncate_length cfg _ h

end Sanitizers.Slug
