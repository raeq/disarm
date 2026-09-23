import Detection.Anomaly

/-!
# General theorems about the anomaly model (induction, no `native_decide`)

* **Locality.** A line feed is a hard cut: `has_anomalies (u ++ LF ++ v)` is
  `has_anomalies u || has_anomalies v` for every `u` and `v`, `CR` included. A space is a
  cut when neither side holds a `CR`; with one, it is not, and should not be: `a \r X`
  overwrites the `a ` that precedes the `CR`, which neither half sees.
* **Canonical equivalence.** On this alphabet `nfd` and `nfc` are the Unicode ones. The
  proposed fix (classify the NFD) gives one verdict per canonical-equivalence class, and
  agrees with the current code on every input with no precomposed letter.
-/

namespace Detection

open C

/-! ## Tokens and the CR rule over concatenation -/

theorem splitAux_append_boundary (cur u v : List C) (b : C) (hb : b.boundary = true) :
    splitAux cur (u ++ b :: v) = splitAux cur u ++ splitAux [] v := by
  induction u generalizing cur with
  | nil => simp [splitAux, hb]
  | cons c u ih =>
    by_cases hc : c.boundary = true
    · simp [splitAux, hc, ih, List.append_assoc]
    · simp [splitAux, hc, ih]

theorem splitTokens_append_boundary (u v : List C) (b : C) (hb : b.boundary = true) :
    splitTokens (u ++ b :: v) = splitTokens u ++ splitTokens v :=
  splitAux_append_boundary [] u v b hb

theorem crAux_append_lf (s : Bool) (u v : List C) :
    crAux s (u ++ .lf :: v) = (crAux s u || crAux false v) := by
  induction u generalizing s with
  | nil => simp [crAux, C.lineBreak]
  | cons c u ih =>
    cases u with
    | nil => cases c <;> simp [crAux, C.lineBreak]
    | cons n u' =>
      by_cases hcr : c = .cr
      · subst hcr
        have := ih false
        simp only [List.cons_append] at this ⊢
        simp only [crAux, ite_true] at this ⊢
        rw [this]; simp [Bool.or_assoc]
      · by_cases hlb : c.lineBreak = true
        · have := ih false
          simp only [List.cons_append] at this ⊢
          simp only [crAux, hcr, ite_false, hlb, ite_true] at this ⊢
          exact this
        · have := ih true
          simp only [List.cons_append] at this ⊢
          simp only [crAux, hcr, ite_false, hlb] at this ⊢
          exact this

theorem crAux_noCR (s : Bool) (t : List C) (h : C.cr ∉ t) : crAux s t = false := by
  induction t generalizing s with
  | nil => simp [crAux]
  | cons c t ih =>
    have hc : c ≠ .cr := fun e => h (e ▸ List.mem_cons_self)
    have ht : C.cr ∉ t := fun m => h (List.mem_cons_of_mem _ m)
    by_cases hlb : c.lineBreak = true
    · simp [crAux, hc, hlb, ih _ ht]
    · simp [crAux, hc, hlb, ih _ ht]

/-- **Locality across a line feed**, for every `u` and `v`. -/
theorem hasAnomalies_append_lf (u v : List C) :
    hasAnomalies (u ++ .lf :: v) = (hasAnomalies u || hasAnomalies v) := by
  simp only [hasAnomalies, overwritingCR, crAux_append_lf,
    splitTokens_append_boundary u v .lf rfl, List.any_append]
  cases crAux false u <;> cases crAux false v <;> simp [Bool.or_comm]

/-- **Locality across a space**, when neither side holds a `CR`. -/
theorem hasAnomalies_append_sp (u v : List C) (hu : C.cr ∉ u) (hv : C.cr ∉ v) :
    hasAnomalies (u ++ .sp :: v) = (hasAnomalies u || hasAnomalies v) := by
  have huv : C.cr ∉ u ++ .sp :: v := by simp [hu, hv]
  simp only [hasAnomalies, overwritingCR, crAux_noCR _ _ huv, crAux_noCR _ _ hu,
    crAux_noCR _ _ hv, splitTokens_append_boundary u v .sp rfl, List.any_append]
  simp

/-- ...and the side condition is needed: the `CR` in `v` overwrites `u`'s text. -/
example : hasAnomalies ([.a] ++ .sp :: [.cr, .a]) = true ∧
    hasAnomalies [.a] = false ∧ hasAnomalies [.cr, .a] = false := by decide

/-! ## Canonical equivalence -/

/-- NFC on this alphabet: decompose, then compose `a m` to `p` (`e` + `U+0301` is `U+00E9`;
no other pair composes, and `m` is the only non-starter). -/
def compose : List C → List C
  | .a :: .m :: rest => .p :: compose rest
  | c :: rest => c :: compose rest
  | [] => []

def nfc (t : List C) : List C := compose (nfd t)

theorem nfd_cons (c : C) (t : List C) : nfd (c :: t) = nfdChar c ++ nfd t := by
  simp [nfd]

theorem nfd_append (u v : List C) : nfd (u ++ v) = nfd u ++ nfd v := by
  simp [nfd]

theorem nfdChar_nfd (c : C) : nfd (nfdChar c) = nfdChar c := by
  cases c <;> rfl

theorem nfd_nfd (t : List C) : nfd (nfd t) = nfd t := by
  induction t with
  | nil => rfl
  | cons c t ih => rw [nfd_cons, nfd_append, nfdChar_nfd, ih]

theorem nfd_compose (t : List C) : nfd (compose t) = nfd t := by
  induction t using compose.induct with
  | case1 rest ih => simp [compose, nfd_cons, ih, nfdChar]
  | case2 c rest h ih =>
    rw [compose, nfd_cons, nfd_cons, ih]
    all_goals (intro r e; exact h r e)
  | case3 => rfl

/-- `nfc` and `nfd` land in the same canonical-equivalence class. -/
theorem nfd_nfc (t : List C) : nfd (nfc t) = nfd t := by
  rw [nfc, nfd_compose, nfd_nfd]

/-- **The fix is canonical-equivalence invariant**: two canonically equivalent inputs
(equal NFD) get one verdict, so in particular NFC and NFD agree. -/
theorem hasAnomaliesNfd_canonical (s t : List C) (h : nfd s = nfd t) :
    hasAnomaliesNfd s = hasAnomaliesNfd t := by
  simp [hasAnomaliesNfd, h]

theorem hasAnomaliesNfd_nfc_nfd (t : List C) :
    hasAnomaliesNfd (nfc t) = hasAnomaliesNfd (nfd t) :=
  hasAnomaliesNfd_canonical _ _ (by rw [nfd_nfc, nfd_nfd])

theorem hasAnomaliesFixed_canonical (s t : List C) (h : nfd s = nfd t) :
    hasAnomaliesFixed s = hasAnomaliesFixed t := by
  simp [hasAnomaliesFixed, h]

theorem nfd_of_no_p (t : List C) (h : C.p ∉ t) : nfd t = t := by
  induction t with
  | nil => rfl
  | cons c t ih =>
    have hc : c ≠ .p := fun e => h (e ▸ List.mem_cons_self)
    have ht : C.p ∉ t := fun m => h (List.mem_cons_of_mem _ m)
    rw [nfd_cons, ih ht]
    cases c <;> first | rfl | exact absurd rfl hc

/-- The NFD fix changes nothing on input with no precomposed letter. -/
theorem hasAnomaliesNfd_eq_of_no_p (t : List C) (h : C.p ∉ t) :
    hasAnomaliesNfd t = hasAnomalies t := by
  simp [hasAnomaliesNfd, nfd_of_no_p t h]

/-! ## The fixed number-run rule says what the documentation says -/

/-- `anyRlmBeforeDigit` is exactly "some `RLM` is immediately followed by a digit", the
rule `docs/user-guide/anomaly-detection.md` states (#741). -/
theorem anyRlmBeforeDigit_iff (t : List C) :
    anyRlmBeforeDigit t = true ↔ ∃ u v, t = u ++ .rlm :: .d :: v := by
  induction t using anyRlmBeforeDigit.induct with
  | case1 rest => exact ⟨fun _ => ⟨[], rest, rfl⟩, fun _ => rfl⟩
  | case2 c rest h ih =>
    rw [anyRlmBeforeDigit.eq_2 c rest h, ih]
    constructor
    · rintro ⟨u, v, rfl⟩; exact ⟨c :: u, v, rfl⟩
    · rintro ⟨u, v, e⟩
      cases u with
      | nil =>
        simp only [List.nil_append, List.cons.injEq] at e
        obtain ⟨rfl, rfl⟩ := e
        exact absurd rfl (h v rfl)
      | cons c' u =>
        simp only [List.cons_append, List.cons.injEq] at e
        obtain ⟨-, rfl⟩ := e
        exact ⟨u, v, rfl⟩
  | case3 => simp [anyRlmBeforeDigit]

end Detection
