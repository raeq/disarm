import Sanitizers.Filename
import Sanitizers.Lists

/-!
# General theorems about `sanitize_filename`

For every ASCII input, every separator, every `max_length`, every platform and both
`preserve_extension` values. Induction and case analysis only: no `native_decide`, no
`sorry`.

| Theorem | Statement |
|---|---|
| `sanitize_ne_nil` | P1: the output is never empty |
| `sanitize_no_leading_dot_space`, `sanitize_no_trailing_dot_space` | P6 |
| `sanitize_not_dot`, `sanitize_not_dotdot` | P2: never `"."` or `".."` |
| `sanitize_chars` | every character is a separator character or one `dropped` rejects |
| `sanitize_legal` | P3/P4: with a separator free of them, no illegal, control or whitespace character |
| `sanitize_length` | P7: at most `max_length` characters (bytes, on ASCII) when `max_length > 0` |
-/

set_option linter.deprecated false  -- `if_pos` / `if_neg` read better here than their replacements

namespace Sanitizers.Filename

open Sanitizers.Lists

theorem rtrim_eq (p : Char → Bool) (l : List Char) : Filename.rtrim p l = Lists.rtrim p l := rfl

/-! ## `finalize_name` -/

theorem finalize_ne_nil (n : List Char) : finalize n ≠ [] := by
  unfold finalize
  simp only
  split
  · simp
  · rename_i h
    intro h'
    rw [h'] at h
    simp at h

theorem finalize_cases (n : List Char) :
    finalize n = ['_'] ∨ finalize n = Lists.rtrim isDS (n.dropWhile isDS) := by
  unfold finalize
  simp only
  split
  · exact Or.inl rfl
  · exact Or.inr rfl

theorem finalize_head {n : List Char} {c : Char} (h : (finalize n).head? = some c) :
    isDS c = false := by
  rcases finalize_cases n with h1 | h1
  · rw [h1] at h; simp at h; subst h; decide
  · rw [h1] at h
    exact head_dropWhile (head_rtrim h)

theorem finalize_last {n : List Char} {c : Char} (h : (finalize n).getLast? = some c) :
    isDS c = false := by
  rcases finalize_cases n with h1 | h1
  · rw [h1] at h; simp at h; subst h; decide
  · rw [h1] at h
    exact getLast_rtrim h

theorem finalize_mem {n : List Char} {c : Char} (h : c ∈ finalize n) : c = '_' ∨ c ∈ n := by
  rcases finalize_cases n with h1 | h1
  · rw [h1] at h; simp at h; exact Or.inl h
  · rw [h1] at h; exact Or.inr (mem_of_mem_dropWhile (mem_of_mem_rtrim h))

theorem finalize_length (n : List Char) : (finalize n).length ≤ max 1 n.length := by
  rcases finalize_cases n with h1 | h1
  · rw [h1]; exact Nat.le_max_left _ _
  · rw [h1]
    have a := length_rtrim_le isDS (n.dropWhile isDS)
    have b := length_dropWhile_le (p := isDS) n
    omega

/-! ## The whole function ends in `finalize` -/

/-- Every return path of `sanitize` is `finalize` of something (L337, L374). -/
theorem sanitize_is_finalize (text sep : List Char) (ml : Nat) (p : Platform) (pe : Bool) :
    ∃ n, sanitize text sep ml p pe = finalize n := by
  unfold sanitize
  simp only
  split
  · exact ⟨_, rfl⟩
  · exact ⟨_, rfl⟩

theorem sanitize_ne_nil (text sep : List Char) (ml : Nat) (p : Platform) (pe : Bool) :
    sanitize text sep ml p pe ≠ [] := by
  obtain ⟨n, h⟩ := sanitize_is_finalize text sep ml p pe
  rw [h]; exact finalize_ne_nil n

theorem sanitize_no_leading_dot_space (text sep : List Char) (ml : Nat) (p : Platform) (pe : Bool)
    {c : Char} (h : (sanitize text sep ml p pe).head? = some c) : c ≠ '.' ∧ c ≠ ' ' := by
  obtain ⟨n, hn⟩ := sanitize_is_finalize text sep ml p pe
  rw [hn] at h
  have := finalize_head h
  unfold isDS at this
  constructor <;> intro e <;> subst e <;> simp at this

theorem sanitize_no_trailing_dot_space (text sep : List Char) (ml : Nat) (p : Platform)
    (pe : Bool) {c : Char} (h : (sanitize text sep ml p pe).getLast? = some c) :
    c ≠ '.' ∧ c ≠ ' ' := by
  obtain ⟨n, hn⟩ := sanitize_is_finalize text sep ml p pe
  rw [hn] at h
  have := finalize_last h
  unfold isDS at this
  constructor <;> intro e <;> subst e <;> simp at this

theorem sanitize_not_dot (text sep : List Char) (ml : Nat) (p : Platform) (pe : Bool) :
    sanitize text sep ml p pe ≠ ['.'] := by
  intro h
  have := sanitize_no_leading_dot_space text sep ml p pe (c := '.') (by rw [h]; rfl)
  exact this.1 rfl

theorem sanitize_not_dotdot (text sep : List Char) (ml : Nat) (p : Platform) (pe : Bool) :
    sanitize text sep ml p pe ≠ ['.', '.'] := by
  intro h
  have := sanitize_no_leading_dot_space text sep ml p pe (c := '.') (by rw [h]; rfl)
  exact this.1 rfl

/-! ## Character set -/

/-- The property every output character has: it came from the separator, or it is a
character the platform's filter lets through. -/
def Good (p : Platform) (sep : List Char) (c : Char) : Prop := c ∈ sep ∨ dropped p c = false

theorem good_dot (p : Platform) (sep : List Char) : Good p sep '.' := by
  right; cases p <;> decide

theorem good_underscore (p : Platform) (sep : List Char) : Good p sep '_' := by
  right; cases p <;> decide

theorem stemLoop_good (p : Platform) (sep : List Char) :
    ∀ (l : List Char) (prev : Bool) (c : Char), c ∈ stemLoop p sep l prev → Good p sep c
  | [], _, c, h => by simp [stemLoop] at h
  | x :: xs, prev, c, h => by
    unfold stemLoop at h
    split at h
    · split at h
      · rcases List.mem_append.mp h with h' | h'
        · exact Or.inl h'
        · exact stemLoop_good p sep xs true c h'
      · exact stemLoop_good p sep xs prev c h
    · rename_i hx
      rcases List.mem_cons.mp h with h' | h'
      · subst h'; right; simpa using hx
      · exact stemLoop_good p sep xs false c h'

theorem stripSepF_sub (sep : List Char) :
    ∀ (n : Nat) (l : List Char) (c : Char), c ∈ stripSepF sep n l → c ∈ l
  | 0, l, c, h => by simpa [stripSepF] using h
  | n + 1, l, c, h => by
    unfold stripSepF at h
    split at h
    · exact List.mem_of_mem_take (stripSepF_sub sep n _ c h)
    · exact h

theorem stripSepF_length (sep : List Char) :
    ∀ (n : Nat) (l : List Char), (stripSepF sep n l).length ≤ l.length
  | 0, l => by simp [stripSepF]
  | n + 1, l => by
    unfold stripSepF
    split
    · have := stripSepF_length sep n (l.take (l.length - sep.length))
      simp only [List.length_take] at this
      omega
    · exact Nat.le_refl _

theorem cleanStem_good (p : Platform) (sep stem : List Char) (c : Char)
    (h : c ∈ cleanStem p sep stem) : Good p sep c := by
  unfold cleanStem at h
  rw [rtrim_eq] at h
  have h1 := mem_of_mem_dropWhile (mem_of_mem_rtrim h)
  unfold stripSep at h1
  exact stemLoop_good p sep stem true c (stripSepF_sub sep _ _ c h1)

theorem cleanExt_good (p : Platform) (sep e : List Char) (c : Char) (h : c ∈ cleanExt p e) :
    Good p sep c := by
  unfold cleanExt at h
  rcases List.mem_cons.mp h with h' | h'
  · subst h'; exact good_dot p sep
  · right
    have := (List.mem_filter.mp h').2
    simpa using this

theorem applyMax_sub (name : List Char) (ext : Option (List Char)) (ml : Nat) (pe : Bool)
    (c : Char) (h : c ∈ applyMax name ext ml pe) : c ∈ name ∨ ∃ e, ext = some e ∧ c ∈ e := by
  unfold applyMax at h
  by_cases h0 : (ml == 0 || name.length ≤ ml) = true
  · rw [if_pos h0] at h; exact Or.inl h
  · rw [if_neg h0] at h
    cases pe with
    | false => exact Or.inl (List.mem_of_mem_take h)
    | true =>
      cases ext with
      | none => exact Or.inl (List.mem_of_mem_take h)
      | some e =>
        simp only [if_true] at h
        by_cases h1 : e.length ≥ ml
        · rw [if_pos h1] at h; exact Or.inl (List.mem_of_mem_take h)
        · rw [if_neg h1] at h
          rcases List.mem_append.mp h with h' | h'
          · exact Or.inl (List.mem_of_mem_take h')
          · exact Or.inr ⟨e, rfl, h'⟩

theorem sext_good (p : Platform) (sep : List Char) (ext : Option (List Char)) :
    ∀ e, ext.map (cleanExt p) = some e → ∀ c ∈ e, Good p sep c := by
  intro e he c hc
  cases ext with
  | none => simp at he
  | some x =>
    simp at he
    subst he
    exact cleanExt_good p sep x c hc

theorem getD_good (p : Platform) (sep : List Char) (ext : Option (List Char)) :
    ∀ c ∈ (ext.map (cleanExt p)).getD [], Good p sep c := by
  intro c hc
  cases ext with
  | none => simp at hc
  | some x => simp at hc; exact cleanExt_good p sep x c hc

theorem applyMax_good (p : Platform) (sep : List Char) (name : List Char)
    (ext : Option (List Char)) (ml : Nat) (pe : Bool)
    (hn : ∀ c ∈ name, Good p sep c) (he : ∀ e, ext = some e → ∀ c ∈ e, Good p sep c) :
    ∀ c ∈ applyMax name ext ml pe, Good p sep c := by
  intro c hc
  rcases applyMax_sub name ext ml pe c hc with h | ⟨e, h1, h2⟩
  · exact hn c h
  · exact he e h1 c h2

theorem finalize_good (p : Platform) (sep n : List Char) (hn : ∀ c ∈ n, Good p sep c) :
    ∀ c ∈ finalize n, Good p sep c := by
  intro c hc
  rcases finalize_mem hc with h | h
  · subst h; exact good_underscore p sep
  · exact hn c h

/-- Every output character is from the separator or passes the platform's filter. -/
theorem sanitize_chars (text sep : List Char) (ml : Nat) (p : Platform) (pe : Bool) :
    ∀ c ∈ sanitize text sep ml p pe, Good p sep c := by
  unfold sanitize
  simp only
  generalize hsp : split pe (rtrim isDS (collapse (collapse text))) = sp
  obtain ⟨stem, ext⟩ := sp
  simp only
  have hr : ∀ c ∈ cleanStem p sep stem, Good p sep c := cleanStem_good p sep stem
  have hx := sext_good p sep ext
  have hg := getD_good p sep ext
  have hname : ∀ c ∈ cleanStem p sep stem ++ (ext.map (cleanExt p)).getD [], Good p sep c := by
    intro c hc
    rcases List.mem_append.mp hc with h | h
    · exact hr c h
    · exact hg c h
  have hname' : ∀ c ∈ '_' :: (cleanStem p sep stem ++ (ext.map (cleanExt p)).getD []),
      Good p sep c := by
    intro c hc
    rcases List.mem_cons.mp hc with h | h
    · subst h; exact good_underscore p sep
    · exact hname c h
  split
  · exact finalize_good p sep _ (applyMax_good p sep _ _ ml pe hname' hx)
  · apply finalize_good
    have h0 := applyMax_good p sep _ _ ml pe hname hx
    split
    · apply applyMax_good p sep _ _ ml pe _ hx
      intro c hc
      rcases List.mem_cons.mp hc with h | h
      · subst h; exact good_underscore p sep
      · exact h0 c h
    · exact h0

/-- P3/P4 on every platform: when the separator itself passes the filter, the output holds
no illegal, control or whitespace character. -/
theorem sanitize_legal (text sep : List Char) (ml : Nat) (p : Platform) (pe : Bool)
    (hsep : ∀ c ∈ sep, dropped p c = false) :
    ∀ c ∈ sanitize text sep ml p pe, dropped p c = false := by
  intro c hc
  rcases sanitize_chars text sep ml p pe c hc with h | h
  · exact hsep c h
  · exact h

/-! ## Length -/

theorem applyMax_length (name : List Char) (ext : Option (List Char)) (ml : Nat) (pe : Bool)
    (hml : 0 < ml) : (applyMax name ext ml pe).length ≤ ml := by
  unfold applyMax
  split
  · rename_i h
    simp only [Bool.or_eq_true, beq_iff_eq, decide_eq_true_eq] at h
    omega
  · split
    · split
      · rename_i e _
        split
        · simp only [List.length_take]; omega
        · rename_i h2
          simp only [List.length_append, List.length_take]
          omega
      · simp only [List.length_take]; omega
    · simp only [List.length_take]; omega

theorem sanitize_length (text sep : List Char) (ml : Nat) (p : Platform) (pe : Bool)
    (hml : 0 < ml) : (sanitize text sep ml p pe).length ≤ ml := by
  unfold sanitize
  simp only
  generalize split pe (rtrim isDS (collapse (collapse text))) = sp
  obtain ⟨stem, ext⟩ := sp
  simp only
  split
  · have a := finalize_length (applyMax ('_' :: (cleanStem p sep stem ++ (ext.map (cleanExt p)).getD []))
      (ext.map (cleanExt p)) ml pe)
    have b := applyMax_length ('_' :: (cleanStem p sep stem ++ (ext.map (cleanExt p)).getD []))
      (ext.map (cleanExt p)) ml pe hml
    omega
  · split
    · rename_i f0 _
      have a := finalize_length (applyMax ('_' :: applyMax (cleanStem p sep stem ++ (ext.map (cleanExt p)).getD [])
        (ext.map (cleanExt p)) ml pe) (ext.map (cleanExt p)) ml pe)
      have b := applyMax_length ('_' :: applyMax (cleanStem p sep stem ++ (ext.map (cleanExt p)).getD [])
        (ext.map (cleanExt p)) ml pe) (ext.map (cleanExt p)) ml pe hml
      omega
    · have a := finalize_length (applyMax (cleanStem p sep stem ++ (ext.map (cleanExt p)).getD [])
        (ext.map (cleanExt p)) ml pe)
      have b := applyMax_length (cleanStem p sep stem ++ (ext.map (cleanExt p)).getD [])
        (ext.map (cleanExt p)) ml pe hml
      omega

end Sanitizers.Filename
