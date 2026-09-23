import Deletions.Invariants

/-!
# General theorems about the output (proved for every input, by induction)
-/

namespace Deletions

attribute [-simp] List.getD_eq_getElem?_getD
attribute [local simp] List.getD_cons_zero List.getD_cons_succ

/-! ## Which branches touch `out` -/

/-- The flush branch (L114-122), stated as an equation. -/
theorem step_flush {cr : Bool} {s : St} {ch : C} {next : Option C}
    (h1 : (ch == .bs || ch == .del) = false) (h2 : endsLine cr ch next = true) :
    step cr s ch next =
      { out := s.out ++ s.lead ++ s.line.flatten ++ [ch], lead := [], line := [], col := 0,
        occ := 0 } := by
  unfold step; simp [h1, h2]

/-- Every other branch leaves `out` alone. -/
theorem step_out_same {cr : Bool} {s : St} {ch : C} {next : Option C}
    (h : ¬ ((ch == .bs || ch == .del) = false ∧ endsLine cr ch next = true)) :
    (step cr s ch next).out = s.out := by
  unfold step
  split
  · split <;> rfl
  rename_i h1
  split
  · rename_i h2; exact absurd ⟨by simpa using h1, h2⟩ h
  repeat (first | rfl | split)

theorem run_cons (cr : Bool) (s : St) (ch : C) (rest : List C) :
    run cr s (ch :: rest) = run cr (step cr s ch rest.head?) rest := rfl

/-! ## The identity on already-clean text, and the transparency of the pre-check -/

theorem clean_cons {cr : Bool} {c : C} {r : List C} :
    Clean cr (c :: r) = (c != .bs && c != .del && (!cr || c != .cr || r.head?.all (· == .lf))
      && Clean cr r) := rfl

theorem flatten_modify_last (l : List Cell) (z : C) (h : l ≠ []) :
    (l.modify (l.length - 1) (· ++ [z])).flatten = l.flatten ++ [z] := by
  induction l with
  | nil => exact absurd rfl h
  | cons a l ih =>
    cases l with
    | nil => simp
    | cons b l =>
      have := ih (by simp)
      simp only [List.length_cons] at this ⊢
      simp only [show l.length + 1 + 1 - 1 = l.length + 1 by omega, List.modify_succ_cons,
        List.flatten_cons] at this ⊢
      rw [show l.length + 1 - 1 = l.length by omega] at this
      rw [this]; simp

/-- **Identity.** On text with no `BS`/`DEL` — and, under `cr`, no overwriting `CR` — the
loop rebuilds its input exactly. -/
theorem run_clean (cr : Bool) (rest : List C) (s : St)
    (hlead : s.lead = []) (hcol : s.col = s.line.length) (hocc : s.line = [] → s.occ = 0)
    (hc : Clean cr rest = true) :
    finish (run cr s rest) = s.out ++ s.line.flatten ++ rest := by
  induction rest generalizing s with
  | nil => simp [run, finish, hlead]
  | cons ch rest ih =>
    rw [clean_cons] at hc
    simp only [Bool.and_eq_true, bne_iff_ne, ne_eq, Bool.or_eq_true, Bool.not_eq_true'] at hc
    obtain ⟨⟨⟨hb, hd⟩, hcr⟩, hrest⟩ := hc
    rw [run_cons]
    have h1 : (ch == .bs || ch == .del) = false := by
      cases ch <;> simp_all
    cases ch with
    | bs => exact absurd rfl hb
    | del => exact absurd rfl hd
    | lf =>
      rw [step_flush h1 (by simp [endsLine])]
      rw [ih _ rfl rfl (fun _ => rfl) hrest]; simp [hlead]
    | cr =>
      have h2 : endsLine cr .cr rest.head? = true := by
        cases cr <;> simp_all [endsLine]
      rw [step_flush h1 h2]
      rw [ih _ rfl rfl (fun _ => rfl) hrest]; simp [hlead]
    | z i =>
      by_cases hl : s.line = []
      · have h0 := hocc hl
        have : step cr s (.z i) rest.head? =
            { s with line := s.line ++ [[.z i]], occ := s.occ + 1, col := s.col + 1 } := by
          unfold step; simp [endsLine, occupiesCell, hcol, hl, h0]
        rw [this, ih _ (by simp [hlead]) (by simp [hcol, hl]) (by simp) hrest]
        simp [hl]
      · have hpos : s.col > 0 := by
          cases h : s.line with
          | nil => exact absurd h hl
          | cons _ _ => rw [hcol, h]; simp
        have : step cr s (.z i) rest.head? =
            { s with occ := if (s.line.getD (s.col - 1) []).isEmpty then s.occ + 1 else s.occ
                     line := s.line.modify (s.col - 1) (· ++ [.z i]) } := by
          unfold step; simp [endsLine, occupiesCell, hpos]
        rw [this, ih _ (by simp [hlead]) (by simp [hcol])
          (by intro h; simp at h; exact absurd h hl) hrest]
        simp only
        rw [hcol, flatten_modify_last _ _ hl]; simp
    | v i =>
      have : step cr s (.v i) rest.head? =
          { s with line := s.line ++ [[.v i]], occ := s.occ + 1, col := s.col + 1 } := by
        unfold step; simp [endsLine, occupiesCell, hcol]
      rw [this, ih _ (by simp [hlead]) (by simp [hcol]) (by simp) hrest]
      simp
    | brk i =>
      have : step cr s (.brk i) rest.head? =
          { s with line := s.line ++ [[.brk i]], occ := s.occ + 1, col := s.col + 1 } := by
        unfold step; simp [endsLine, occupiesCell, hcol]
      rw [this, ih _ (by simp [hlead]) (by simp [hcol]) (by simp) hrest]
      simp

theorem finish_run_clean (cr : Bool) (t : List C) (hc : Clean cr t = true) :
    finish (run cr {} t) = t := by
  have := run_clean cr t {} rfl rfl (fun _ => rfl) hc
  simpa using this

/-- Text the pre-check of L68 skips is clean. -/
theorem clean_of_not_needsScan (cr : Bool) (t : List C) (h : needsScan cr t = false) :
    Clean cr t = true := by
  induction t with
  | nil => rfl
  | cons c r ih =>
    simp only [needsScan, List.any_cons, Bool.or_eq_false_iff] at h
    obtain ⟨hc, hr⟩ := h
    rw [clean_cons, ih hr]
    cases c <;> cases cr <;> simp_all

/-- **The pre-check and the changed-flag are transparent.** What a caller sees is the
loop's output, for every input: the early return of L68 and the `out != text` of L165
never change the answer, only whether it is allocated. -/
theorem resolve_eq_finish (cr : Bool) (t : List C) : resolve cr t = finish (run cr {} t) := by
  unfold resolve resolveInto
  by_cases h : needsScan cr t = true
  · simp only [h, Bool.not_true, Bool.false_eq_true, if_false]
    by_cases he : finish (run cr {} t) = t
    · simp [he]
    · simp [he]
  · have h' : needsScan cr t = false := by simpa using h
    simp only [h', Bool.not_false, if_true, Option.getD_none]
    exact (finish_run_clean cr t (clean_of_not_needsScan cr t h')).symm

/-! ## The output is clean: no `BS`/`DEL`, and under `cr` no overwriting `CR` -/

theorem clean_append (cr : Bool) (a b : List C) (ha : Clean cr a = true) (hb : Clean cr b = true)
    (hj : cr = true → a.getLast? = some .cr → b.head?.all (· == .lf) = true) :
    Clean cr (a ++ b) = true := by
  induction a with
  | nil => simpa using hb
  | cons c a ih =>
    rw [List.cons_append, clean_cons]
    rw [clean_cons] at ha
    simp only [Bool.and_eq_true] at ha ⊢
    obtain ⟨⟨⟨h1, h2⟩, h3⟩, h4⟩ := ha
    refine ⟨⟨⟨h1, h2⟩, ?_⟩, ih h4 ?_⟩
    · cases a with
      | nil =>
        cases cr <;> simp_all
        cases c <;> simp_all
      | cons d a => simpa using h3
    · intro hcr hl
      apply hj hcr
      cases a with
      | nil => simp at hl
      | cons d a => simpa using hl

theorem clean_text (cr : Bool) (l : List C) (h : ∀ x ∈ l, isText x = true) : Clean cr l = true := by
  induction l with
  | nil => rfl
  | cons c l ih =>
    rw [clean_cons, ih (fun x hx => h x (List.mem_cons_of_mem _ hx))]
    have := h c List.mem_cons_self
    cases c <;> simp_all [isText]

theorem text_flatten (line : List Cell) (h : ∀ c ∈ line, ∀ x ∈ c, isText x = true) :
    ∀ x ∈ line.flatten, isText x = true := by
  intro x hx
  obtain ⟨c, hc, hx⟩ := List.mem_flatten.mp hx
  exact h c hc x hx

theorem getLast_text_ne_cr (l : List C) (h : ∀ x ∈ l, isText x = true) :
    l.getLast? ≠ some .cr := by
  intro hl
  have := h _ (List.mem_of_getLast? hl)
  simp [isText] at this

/-- The loop invariant for cleanliness of `out`. -/
def CleanInv (cr : Bool) (s : St) (rest : List C) : Prop :=
  WF s ∧ Clean cr s.out = true ∧
  (cr = true → s.out.getLast? = some .cr →
    s.lead = [] ∧ s.line = [] ∧ rest.head?.all (· == .lf) = true)

theorem cleanInv_step (cr : Bool) (s : St) (ch : C) (rest : List C)
    (h : CleanInv cr s (ch :: rest)) : CleanInv cr (step cr s ch rest.head?) rest := by
  obtain ⟨hwf, hcl, hlast⟩ := h
  refine ⟨wf_step _ _ _ _ hwf, ?_⟩
  by_cases hf : (ch == .bs || ch == .del) = false ∧ endsLine cr ch rest.head? = true
  · obtain ⟨h1, h2⟩ := hf
    rw [step_flush h1 h2]
    have htext : ∀ x ∈ s.lead ++ s.line.flatten, isText x = true := by
      intro x hx
      rcases List.mem_append.mp hx with hx | hx
      · exact hwf.lead x hx
      · exact text_flatten _ hwf.cells x hx
    have hch : Clean cr [ch] = true := by
      cases ch <;> cases cr <;> simp_all [Clean, endsLine]
    have hmid : Clean cr (s.lead ++ s.line.flatten ++ [ch]) = true :=
      clean_append cr _ _ (clean_text cr _ htext) hch
        (fun _ hl => absurd hl (getLast_text_ne_cr _ htext))
    refine ⟨?_, ?_⟩
    · have := clean_append cr s.out _ hcl hmid ?_
      · simpa [List.append_assoc] using this
      · intro hcr hl
        obtain ⟨hl1, hl2, hl3⟩ := hlast hcr hl
        simp at hl3
        simp [hl1, hl2, hl3]
    · intro hcr hl
      simp at hl
      subst hl
      refine ⟨rfl, rfl, ?_⟩
      simpa [endsLine, hcr] using h2
  · have hout := step_out_same (s := s) hf
    refine ⟨by rw [hout]; exact hcl, ?_⟩
    intro hcr hl
    rw [hout] at hl
    obtain ⟨_, _, h3⟩ := hlast hcr hl
    -- the next character is `LF`, and `LF` always flushes: contradiction
    simp at h3
    subst h3
    exact absurd ⟨rfl, by simp [endsLine]⟩ hf

theorem cleanInv_run (cr : Bool) (rest : List C) (s : St) (h : CleanInv cr s rest) :
    CleanInv cr (run cr s rest) [] := by
  induction rest generalizing s with
  | nil => exact h
  | cons ch rest ih => exact ih _ (cleanInv_step cr s ch rest h)

/-- **The output is clean.** It holds no `BS` and no `DEL`; under `cr` every `CR` in it is
followed by `LF` or ends the text. -/
theorem resolve_clean (cr : Bool) (t : List C) : Clean cr (resolve cr t) = true := by
  rw [resolve_eq_finish]
  obtain ⟨hwf, hcl, hlast⟩ :=
    cleanInv_run cr t {} ⟨wf_init, rfl, fun _ h => by simp at h⟩
  have htext : ∀ x ∈ (run cr {} t).lead ++ (run cr {} t).line.flatten, isText x = true := by
    intro x hx
    rcases List.mem_append.mp hx with hx | hx
    · exact hwf.lead x hx
    · exact text_flatten _ hwf.cells x hx
  have := clean_append cr _ _ hcl (clean_text cr _ htext) (by
    intro hcr hl
    obtain ⟨h1, h2, _⟩ := hlast hcr hl
    simp [h1, h2])
  simpa [finish, List.append_assoc] using this

/-- No `BS` and no `DEL` survive, under either flag. -/
theorem resolve_no_erase (cr : Bool) (t : List C) :
    .bs ∉ resolve cr t ∧ .del ∉ resolve cr t := by
  have h := resolve_clean cr t
  generalize resolve cr t = o at h
  induction o with
  | nil => simp
  | cons c o ih =>
    rw [clean_cons] at h
    simp only [Bool.and_eq_true, bne_iff_ne, ne_eq] at h
    obtain ⟨⟨⟨h1, h2⟩, _⟩, h4⟩ := h
    have := ih h4
    simp only [List.mem_cons, not_or]
    exact ⟨⟨fun e => h1 e.symm, this.1⟩, ⟨fun e => h2 e.symm, this.2⟩⟩

/-- **Idempotence**, for each flag. -/
theorem resolve_idem (cr : Bool) (t : List C) : resolve cr (resolve cr t) = resolve cr t := by
  rw [resolve_eq_finish cr (resolve cr t)]
  exact finish_run_clean cr _ (resolve_clean cr t)

/-! ## No character is invented or duplicated -/

theorem count_finish_step (cr : Bool) (s : St) (ch : C) (next : Option C) (x : C) :
    (finish (step cr s ch next)).count x ≤ (finish s).count x + [ch].count x := by
  unfold finish step
  split
  · split
    · have := count_flatten_set_le s.line (s.col - 1) [] x
      simp [List.count_append] at this ⊢; omega
    · omega
  split
  · simp [List.count_append]; omega
  split
  · dsimp only; omega
  split
  · have := count_flatten_modify_app_le s.line (s.col - 1) ch x
    simp only [List.count_append] at this ⊢; omega
  split
  · simp only [List.count_append]; omega
  split
  · have := count_flatten_set_le s.line s.col [ch] x
    simp only [List.count_append] at this ⊢; omega
  · simp [List.count_append]; omega

theorem count_finish_run (cr : Bool) (rest : List C) (s : St) (x : C) :
    (finish (run cr s rest)).count x ≤ (finish s).count x + rest.count x := by
  induction rest generalizing s with
  | nil => simp [run]
  | cons ch rest ih =>
    rw [run_cons]
    have h1 := ih (step cr s ch rest.head?)
    have h2 := count_finish_step cr s ch rest.head? x
    have h3 : (ch :: rest).count x = rest.count x + [ch].count x := by
      simp [List.count_cons]
    omega

/-- **No invention, no duplication.** Every character of the output is a character of the
input, and none is output more often than it was input. Characters carry identities, so
with distinct identities in the input the output is a sub-multiset of it: nothing is
made up and nothing is repeated. (Order is a separate question: see `simple_sublist`.) -/
theorem resolve_count_le (cr : Bool) (t : List C) (x : C) :
    (resolve cr t).count x ≤ t.count x := by
  rw [resolve_eq_finish]
  have := count_finish_run cr t {} x
  simpa [finish] using this

/-! ## Line breaks are preserved exactly -/

theorem filter_text (p : C → Bool) (l : List C) (hp : ∀ x, isText x = true → p x = false)
    (h : ∀ x ∈ l, isText x = true) : l.filter p = [] := by
  induction l with
  | nil => rfl
  | cons c l ih =>
    rw [List.filter_cons, hp c (h c List.mem_cons_self)]
    exact ih (fun x hx => h x (List.mem_cons_of_mem _ hx))

/-- Characters `p` selects all flush, and flushing is the only way into `out`. -/
theorem filter_out_run (cr : Bool) (p : C → Bool)
    (hp : ∀ x, isText x = true → p x = false)
    (hbs : p .bs = false) (hdel : p .del = false)
    (hflush : ∀ ch next, p ch = true → endsLine cr ch next = true)
    (rest : List C) (s : St) (hwf : WF s) :
    (run cr s rest).out.filter p = s.out.filter p ++ rest.filter p := by
  induction rest generalizing s with
  | nil => simp [run]
  | cons ch rest ih =>
    rw [run_cons, ih _ (wf_step _ _ _ _ hwf)]
    by_cases hf : (ch == .bs || ch == .del) = false ∧ endsLine cr ch rest.head? = true
    · rw [step_flush hf.1 hf.2]
      have hl := filter_text p _ hp hwf.lead
      have hc := filter_text p _ hp (text_flatten _ hwf.cells)
      simp only [List.filter_append, hl, hc, List.filter_cons, List.filter_nil]
      split <;> simp
    · rw [step_out_same (s := s) hf]
      have : p ch = false := by
        cases hc : p ch
        · rfl
        · exfalso; apply hf
          refine ⟨?_, hflush ch _ hc⟩
          cases ch <;> simp_all
      simp [List.filter_cons, this]

theorem filter_finish (p : C → Bool) (hp : ∀ x, isText x = true → p x = false) (s : St)
    (hwf : WF s) : (finish s).filter p = s.out.filter p := by
  have hl := filter_text p _ hp hwf.lead
  have hc := filter_text p _ hp (text_flatten _ hwf.cells)
  simp [finish, List.filter_append, hl, hc]

/-- **Every `LF` survives, and nothing becomes one**, under either flag: the sequence of
`LF`s in the output is the sequence in the input. -/
theorem resolve_lf (cr : Bool) (t : List C) :
    (resolve cr t).filter (· == .lf) = t.filter (· == .lf) := by
  rw [resolve_eq_finish, filter_finish _ (by intro x hx; cases x <;> simp_all [isText]) _
    (wf_run _ _ _ wf_init)]
  rw [filter_out_run cr _ (by intro x hx; cases x <;> simp_all [isText]) rfl rfl
    (by intro ch next h; cases ch <;> simp_all [endsLine]) t {} wf_init]
  simp

/-- **Without the flag, every line terminator survives exactly**: the `CR`s and `LF`s of
the output, in order, are those of the input. -/
theorem resolve_crlf_nocr (t : List C) :
    (resolve false t).filter (fun c => c == .lf || c == .cr) =
      t.filter (fun c => c == .lf || c == .cr) := by
  rw [resolve_eq_finish, filter_finish _ (by intro x hx; cases x <;> simp_all [isText]) _
    (wf_run _ _ _ wf_init)]
  rw [filter_out_run false _ (by intro x hx; cases x <;> simp_all [isText]) rfl rfl
    (by intro ch next h; cases ch <;> simp_all [endsLine]) t {} wf_init]
  simp

end Deletions
