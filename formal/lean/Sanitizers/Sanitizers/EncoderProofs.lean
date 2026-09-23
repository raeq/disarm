import Sanitizers.Encoders
import Sanitizers.LogInjection

/-!
# General theorems: `escape_html`, `percent_encode`, `strip_log_injection`

For every input. Induction only: no `native_decide`, no `sorry`. The `decide` calls
evaluate closed statements over at most 256 values.

| Theorem | Statement |
|---|---|
| `unescape_escape` | E1: the five-entity decoder inverts `escape_html` |
| `escape_no_raw_meta` | E1: no raw `<` `>` `"` `'` in the output |
| `pctDecode_pctEncode` | E2: `unquote` (`unquote_plus` for `form`) inverts `percent_encode`, on bytes |
| `pctEncode_ascii`, `pctEncode_safe` | E2: output bytes are ASCII, and each is `%`, an upper-case hex digit, `+` (form) or a byte the component keeps |
| `strip_clean` | L1: with an accepted replacement, no neutralized character survives |
| `strip_idem` | L2: idempotent |
| `strip_nil_eq_filter` | L3: with `replacement = ""`, the output is the input with the neutralized characters removed, in order |
| `strip_length_one` | with a one-character replacement, the length is preserved (the docs' `len(out) == len(attack)`) |
| `neutralizes_documented` | CR, LF, NEL, LS, PS, NUL, ESC, DEL and CSI are neutralized, TAB unless `keep_tab` |
-/

set_option linter.deprecated false  -- `if_pos` / `if_neg` read better here than their replacements

namespace Sanitizers.Enc

/-! ## `escape_html` -/

theorem unescape_cons_of_ne {c : Char} (hc : c ≠ '&') (r : List Char) :
    unescapeHtml (c :: r) = c :: unescapeHtml r := by
  rw [unescapeHtml.eq_def]
  split <;> simp_all

theorem unescape_escape : ∀ s : List Char, unescapeHtml (escapeHtml s) = s
  | [] => rfl
  | c :: cs => by
    have ih := unescape_escape cs
    unfold escapeHtml
    by_cases h1 : c = '&'
    · subst h1; simp [amp, unescapeHtml, ih]
    by_cases h2 : c = '<'
    · subst h2; simp [lt, unescapeHtml, ih]
    by_cases h3 : c = '>'
    · subst h3; simp [gt, unescapeHtml, ih]
    by_cases h4 : c = '"'
    · subst h4; simp [quot, unescapeHtml, ih]
    by_cases h5 : c = '\''
    · subst h5; simp [apos, unescapeHtml, ih]
    simp only [beq_iff_eq, h1, h2, h3, h4, h5, if_false, List.singleton_append]
    rw [unescape_cons_of_ne h1, ih]

theorem escape_no_raw_meta : ∀ (s : List Char) (c : Char), c ∈ escapeHtml s →
    c ≠ '<' ∧ c ≠ '>' ∧ c ≠ '"' ∧ c ≠ '\''
  | [], _, h => by simp [escapeHtml] at h
  | x :: xs, c, h => by
    unfold escapeHtml at h
    rcases List.mem_append.mp h with h' | h'
    · by_cases h1 : x = '&'
      · subst h1; simp [amp] at h'; rcases h' with h' | h' | h' | h' | h' <;> subst h' <;> decide
      by_cases h2 : x = '<'
      · subst h2; simp [lt] at h'; rcases h' with h' | h' | h' | h' <;> subst h' <;> decide
      by_cases h3 : x = '>'
      · subst h3; simp [gt] at h'; rcases h' with h' | h' | h' | h' <;> subst h' <;> decide
      by_cases h4 : x = '"'
      · subst h4; simp [quot] at h'
        rcases h' with h' | h' | h' | h' | h' | h' <;> subst h' <;> decide
      by_cases h5 : x = '\''
      · subst h5; simp [apos] at h'
        rcases h' with h' | h' | h' | h' | h' | h' <;> subst h' <;> decide
      simp only [beq_iff_eq, h1, h2, h3, h4, h5, if_false, List.mem_singleton] at h'
      subst h'
      exact ⟨h2, h3, h4, h5⟩
    · exact escape_no_raw_meta xs c h'

/-! ## `percent_encode` -/

theorem hexVal_hexDigit : ∀ n, n < 16 → hexVal (hexDigit n) = some n := by decide

theorem keep_ne_pct (comp : Component) : keep comp 37 = false := by cases comp <;> decide

theorem keep_form_ne_plus : keep .form 43 = false := by decide

theorem pctDecode_cons_of_ne {b : Nat} (hb : b ≠ 37) (ps : Bool) (r : List Nat) :
    pctDecode ps (b :: r) = (if ps && b == 43 then 32 else b) :: pctDecode ps r := by
  rw [pctDecode.eq_def]
  split <;> simp_all

theorem pctDecode_escape (ps : Bool) {h l a b : Nat} (r : List Nat) (ha : hexVal h = some a)
    (hb : hexVal l = some b) : pctDecode ps (37 :: h :: l :: r) = (16 * a + b) :: pctDecode ps r := by
  rw [pctDecode.eq_def]
  simp [ha, hb]

theorem pctDecode_pctEncode (comp : Component) :
    ∀ bs : List Nat, (∀ b ∈ bs, b < 256) → pctDecode (plus comp) (pctEncode comp bs) = bs
  | [], _ => rfl
  | b :: bs, hbs => by
    have hb : b < 256 := hbs b (by simp)
    have ih := pctDecode_pctEncode comp bs (fun x hx => hbs x (by simp [hx]))
    unfold pctEncode
    by_cases hp : (plus comp && b == 32) = true
    · rw [if_pos hp]
      have hpc : plus comp = true := by simp_all
      have hb32 : b = 32 := by simp_all
      simp only [List.singleton_append]
      rw [pctDecode_cons_of_ne (by decide), ih, hpc, hb32]
      rfl
    · rw [if_neg hp]
      by_cases hk : keep comp b = true
      · rw [if_pos hk]
        have h37 : b ≠ 37 := by
          intro e; subst e; rw [keep_ne_pct] at hk; exact absurd hk (by decide)
        simp only [List.singleton_append]
        rw [pctDecode_cons_of_ne h37, ih]
        congr 1
        cases comp with
        | form =>
          have : b ≠ 43 := by intro e; subst e; rw [keep_form_ne_plus] at hk; exact absurd hk (by decide)
          simp [plus, this]
        | path => simp [plus]
        | segment => simp [plus]
        | query => simp [plus]
      · rw [if_neg hk]
        have h1 : b / 16 < 16 := by omega
        have h2 : b % 16 < 16 := Nat.mod_lt _ (by decide)
        simp only [List.cons_append, List.nil_append]
        rw [pctDecode_escape _ _ (hexVal_hexDigit _ h1) (hexVal_hexDigit _ h2), ih]
        congr 1
        omega

theorem hexDigit_lt (n : Nat) (h : n < 16) : hexDigit n < 128 ∧ hexDigit n ≠ 37 := by
  unfold hexDigit; split <;> omega

theorem keep_lt (comp : Component) (b : Nat) (h : keep comp b = true) : b < 128 := by
  cases comp <;> simp [keep, keepSegment, unreserved, isAlnumB] at h <;> omega

/-- Every output byte is ASCII. -/
theorem pctEncode_ascii (comp : Component) :
    ∀ bs : List Nat, (∀ b ∈ bs, b < 256) → ∀ o ∈ pctEncode comp bs, o < 128
  | [], _, o, h => by simp [pctEncode] at h
  | b :: bs, hbs, o, h => by
    have hb : b < 256 := hbs b (by simp)
    unfold pctEncode at h
    rcases List.mem_append.mp h with h' | h'
    · split at h'
      · simp at h'; omega
      · split at h'
        · simp at h'; subst h'; exact keep_lt comp _ (by assumption)
        · simp at h'
          rcases h' with h' | h' | h'
          · omega
          · subst h'; exact (hexDigit_lt _ (by omega)).1
          · subst h'; exact (hexDigit_lt _ (Nat.mod_lt _ (by decide))).1
    · exact pctEncode_ascii comp bs (fun x hx => hbs x (by simp [hx])) o h'

def isUpperHex (d : Nat) : Bool := (48 ≤ d && d ≤ 57) || (65 ≤ d && d ≤ 70)

theorem hexDigit_upper (n : Nat) (h : n < 16) : isUpperHex (hexDigit n) = true := by
  unfold hexDigit isUpperHex; split <;> simp <;> omega

/-- Every output byte is `%`, an upper-case hex digit, `+` under `form`, or a byte the
component keeps. (`%` itself is never kept, `keep_ne_pct`, so every `%` in the output
starts an escape.) -/
theorem pctEncode_safe (comp : Component) :
    ∀ bs : List Nat, (∀ b ∈ bs, b < 256) → ∀ o ∈ pctEncode comp bs,
      o = 37 ∨ isUpperHex o = true ∨ (plus comp = true ∧ o = 43) ∨ keep comp o = true
  | [], _, o, h => by simp [pctEncode] at h
  | b :: bs, hbs, o, h => by
    have hb : b < 256 := hbs b (by simp)
    unfold pctEncode at h
    rcases List.mem_append.mp h with h' | h'
    · split at h'
      · rename_i hp; simp at h'; subst h'; simp at hp; exact Or.inr (Or.inr (Or.inl ⟨hp.1, rfl⟩))
      · split at h'
        · simp at h'; subst h'; exact Or.inr (Or.inr (Or.inr (by assumption)))
        · simp at h'
          rcases h' with h' | h' | h'
          · exact Or.inl h'
          · subst h'; exact Or.inr (Or.inl (hexDigit_upper _ (by omega)))
          · subst h'; exact Or.inr (Or.inl (hexDigit_upper _ (Nat.mod_lt _ (by decide))))
    · exact pctEncode_safe comp bs (fun x hx => hbs x (by simp [hx])) o h'

end Sanitizers.Enc

namespace Sanitizers.Log

theorem strip_append (rep : List Char) (kt : Bool) :
    ∀ a b : List Char, strip rep kt (a ++ b) = strip rep kt a ++ strip rep kt b
  | [], b => rfl
  | x :: xs, b => by simp [strip, strip_append rep kt xs b]

theorem strip_clean {rep : List Char} {kt : Bool} (hrep : validRep rep kt = true) :
    ∀ (s : List Char) (c : Char), c ∈ strip rep kt s → isNeut kt c = false
  | [], _, h => by simp [strip] at h
  | x :: xs, c, h => by
    unfold strip at h
    rcases List.mem_append.mp h with h' | h'
    · split at h'
      · unfold validRep at hrep
        have := List.all_eq_true.mp hrep c h'
        simpa using this
      · simp at h'; subst h'; simpa using (by assumption : ¬ isNeut kt c = true)
    · exact strip_clean hrep xs c h'

theorem strip_id_of_clean (rep : List Char) (kt : Bool) :
    ∀ s : List Char, (∀ c ∈ s, isNeut kt c = false) → strip rep kt s = s
  | [], _ => rfl
  | x :: xs, h => by
    unfold strip
    have hx : isNeut kt x = false := h x (by simp)
    simp only [hx, Bool.false_eq_true, if_false, List.singleton_append]
    rw [strip_id_of_clean rep kt xs (fun c hc => h c (by simp [hc]))]

theorem strip_idem {rep : List Char} {kt : Bool} (hrep : validRep rep kt = true)
    (s : List Char) : strip rep kt (strip rep kt s) = strip rep kt s :=
  strip_id_of_clean rep kt _ (strip_clean hrep s)

theorem strip_nil_eq_filter (kt : Bool) :
    ∀ s : List Char, strip [] kt s = s.filter (fun c => !isNeut kt c)
  | [] => rfl
  | x :: xs => by
    unfold strip
    rw [strip_nil_eq_filter kt xs]
    cases h : isNeut kt x <;> simp [h]

theorem strip_length_one (r : Char) (kt : Bool) :
    ∀ s : List Char, (strip [r] kt s).length = s.length
  | [] => rfl
  | x :: xs => by
    unfold strip
    have := strip_length_one r kt xs
    split <;> simp [this]

theorem neutralizes_documented (kt : Bool) :
    isNeut kt '\r' ∧ isNeut kt '\n' ∧ isNeut kt (Char.ofNat 0x85) ∧ isNeut kt (Char.ofNat 0x2028)
      ∧ isNeut kt (Char.ofNat 0x2029) ∧ isNeut kt (Char.ofNat 0) ∧ isNeut kt (Char.ofNat 0x1B)
      ∧ isNeut kt (Char.ofNat 0x7F) ∧ isNeut kt (Char.ofNat 0x9B)
      ∧ isNeut kt '\t' = !kt := by
  cases kt <;> decide

end Sanitizers.Log
