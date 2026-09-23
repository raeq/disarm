import Deletions.Output

/-!
# Without an overwriting `CR`, the cursor model is a stack

Under `cr = false`, and under `cr = true` on input with no `CR`, the loop computes exactly
the simple stack algorithm `simple` (Model.lean): an erase pops the top cell, a no-cell
character joins the top cell or starts one, anything else pushes a cell. The
correspondence is a simulation relation, `Rel`, and it also proves the claim of L80-83:
without a `CR`, every cell at or right of the cursor is blank, and `lead` stays empty.
-/

namespace Deletions


attribute [-simp] List.getD_eq_getElem?_getD
attribute [local simp] List.getD_cons_zero List.getD_cons_succ

structure Rel (s : St) (ss : SSt) : Prop where
  out : s.out = ss.out
  lead : s.lead = []
  line : ∃ k, s.line = ss.stack.reverse ++ List.replicate k []
  col : s.col = ss.stack.length
  nonblank : ∀ c ∈ ss.stack, c ≠ []
  occ : s.occ = ss.stack.length

theorem set_mid (a : List Cell) (b y : Cell) (rest : List Cell) :
    (a ++ b :: rest).set a.length y = a ++ y :: rest := by
  induction a with
  | nil => simp
  | cons c a ih => simp [ih]

theorem rel_step (cr : Bool) (s : St) (ss : SSt) (ch : C) (next : Option C)
    (hcr : cr = false ∨ ch ≠ .cr) (h : Rel s ss) :
    Rel (step cr s ch next) (simpleStep ss ch) := by
  obtain ⟨hout, hlead, ⟨k, hline⟩, hcol, hnb, hocc⟩ := h
  cases ch with
  | bs | del =>
    cases hst : ss.stack with
    | nil =>
      have hc0 : s.col = 0 := by rw [hcol, hst]; rfl
      have e1 : ∀ d, (d = C.bs ∨ d = C.del) → step cr s d next = s := by
        intro d hd
        have hdd : (d == .bs || d == .del) = true := by rcases hd with hd | hd <;> subst hd <;> rfl
        unfold step; simp [hdd, hc0]
      first
        | rw [e1 _ (Or.inl rfl)]
        | rw [e1 _ (Or.inr rfl)]
      simp only [simpleStep, hst]
      refine ⟨hout, hlead, ⟨k, by rw [hline, hst]; simp⟩, by simp [hc0], by simp, by simp [hocc, hst]⟩
    | cons b a =>
      have hb : b ≠ [] := hnb b (by rw [hst]; exact List.mem_cons_self)
      have hc : s.col = a.length + 1 := by rw [hcol, hst]; rfl
      have hl : s.line = a.reverse ++ b :: List.replicate k [] := by rw [hline, hst]; simp
      have hg : s.line.getD (s.col - 1) [] = b := by
        rw [hl, hc, show a.length + 1 - 1 = a.reverse.length by simp]; exact getD_at_length _ _ _
      have hset : s.line.set (s.col - 1) [] = a.reverse ++ List.replicate (k + 1) [] := by
        rw [hl, hc, show a.length + 1 - 1 = a.reverse.length by simp, set_mid]
        simp [List.replicate_succ]
      have e1 : ∀ d, (d = C.bs ∨ d = C.del) → step cr s d next =
          { s with col := s.col - 1, occ := s.occ - 1, line := a.reverse ++ List.replicate (k + 1) [] } := by
        intro d hd
        have hdd : (d == .bs || d == .del) = true := by rcases hd with hd | hd <;> subst hd <;> rfl
        unfold step
        simp only [hdd, if_true, show s.col > 0 by omega, hg, isEmpty_false_of_ne hb, hset]
        rfl
      first
        | rw [e1 _ (Or.inl rfl)]
        | rw [e1 _ (Or.inr rfl)]
      simp only [simpleStep, hst, beq_self_eq_true, Bool.true_or, Bool.or_true, if_true,
        List.tail_cons]
      refine ⟨hout, hlead, ⟨k + 1, rfl⟩, by simp [hc], ?_, by simp [hocc, hst]⟩
      intro c hc'; exact hnb c (by rw [hst]; exact List.mem_cons_of_mem _ hc')
  | lf | cr =>
    have hend : ∀ d, (d = C.lf ∨ (d = C.cr ∧ cr = false)) → endsLine cr d next = true := by
      intro d hd; rcases hd with hd | ⟨hd, hc⟩ <;> subst hd <;> simp [endsLine, *]
    first
      | rw [step_flush rfl (hend _ (Or.inl rfl))]
      | rw [step_flush rfl (hend _ (Or.inr ⟨rfl, by simpa using hcr⟩))]
    simp only [simpleStep, beq_self_eq_true, Bool.true_or, Bool.or_true, if_true,
      Bool.or_self, Bool.false_eq_true, if_false, reduceCtorEq]
    refine ⟨?_, rfl, ⟨0, by simp⟩, rfl, by simp, rfl⟩
    simp [hout, hlead, hline, flatten_replicate_nil]
  | z i =>
    cases hst : ss.stack with
    | cons b a =>
      have hb : b ≠ [] := hnb b (by rw [hst]; exact List.mem_cons_self)
      have hc : s.col = a.length + 1 := by rw [hcol, hst]; rfl
      have hl : s.line = a.reverse ++ b :: List.replicate k [] := by rw [hline, hst]; simp
      have hg : s.line.getD (s.col - 1) [] = b := by
        rw [hl, hc, show a.length + 1 - 1 = a.reverse.length by simp]; exact getD_at_length _ _ _
      have hmod : s.line.modify (s.col - 1) (· ++ [.z i]) =
          a.reverse ++ (b ++ [.z i]) :: List.replicate k [] := by
        rw [hl, hc, show a.length + 1 - 1 = a.reverse.length by simp, modify_last_app]
      have e1 : step cr s (.z i) next =
          { s with line := a.reverse ++ (b ++ [.z i]) :: List.replicate k [] } := by
        unfold step
        simp only [endsLine, occupiesCell, show s.col > 0 by omega, hg, isEmpty_false_of_ne hb,
          hmod]
        simp
      rw [e1]
      simp only [simpleStep, occupiesCell, hst]
      simp only [reduceCtorEq, beq_iff_eq, Bool.or_self, Bool.false_eq_true, if_false,
        Bool.not_false, if_true]
      refine ⟨hout, hlead, ⟨k, by simp⟩, by simp [hc], ?_, by simp [hocc, hst]⟩
      intro c hc'
      simp at hc'
      rcases hc' with hc' | hc'
      · subst hc'; simp
      · exact hnb c (by rw [hst]; exact List.mem_cons_of_mem _ hc')
    | nil =>
      have hc0 : s.col = 0 := by rw [hcol, hst]; rfl
      have ho0 : s.occ = 0 := by rw [hocc, hst]; rfl
      have hl : s.line = List.replicate k [] := by rw [hline, hst]; simp
      simp only [simpleStep, occupiesCell, hst]
      simp only [reduceCtorEq, beq_iff_eq, Bool.or_self, Bool.false_eq_true, if_false,
        Bool.not_false, if_true]
      cases k with
      | zero =>
        have e1 : step cr s (.z i) next = { s with line := [[.z i]], occ := 1, col := 1 } := by
          unfold step; simp [endsLine, occupiesCell, hc0, ho0, hl]
        rw [e1]
        exact ⟨hout, hlead, ⟨0, by simp⟩, rfl, by simp, rfl⟩
      | succ k =>
        have e1 : step cr s (.z i) next =
            { s with line := [.z i] :: List.replicate k [], occ := 1, col := 1 } := by
          unfold step; simp [endsLine, occupiesCell, hc0, ho0, hl, List.replicate_succ]
        rw [e1]
        exact ⟨hout, hlead, ⟨k, by simp⟩, rfl, by simp, rfl⟩
  | v i | brk i =>
    have hl : s.line = ss.stack.reverse ++ List.replicate k [] := hline
    have e0 : ∀ d, occupiesCell d = true → d ≠ .bs → d ≠ .del → d ≠ .lf → d ≠ .cr →
        simpleStep ss d = { ss with stack := [d] :: ss.stack } := by
      intro d h1 h2 h3 h4 h5
      cases d <;> simp_all [simpleStep, occupiesCell]
    rw [e0 _ rfl (by simp) (by simp) (by simp) (by simp)]
    cases k with
    | zero =>
      have e1 : ∀ d, occupiesCell d = true → d ≠ .bs → d ≠ .del → d ≠ .lf → d ≠ .cr →
          step cr s d next = { s with line := s.line ++ [[d]], occ := s.occ + 1, col := s.col + 1 } := by
        intro d h1 h2 h3 h4 h5
        unfold step
        cases d <;> simp_all [endsLine, occupiesCell]
      rw [e1 _ rfl (by simp) (by simp) (by simp) (by simp)]
      refine ⟨hout, hlead, ⟨0, by simp [hl]⟩, by simp [hcol], ?_, by simp [hocc]⟩
      intro c hc'; simp at hc'; rcases hc' with hc' | hc'
      · subst hc'; simp
      · exact hnb c hc'
    | succ k =>
      have hlt : s.col < s.line.length := by rw [hl, hcol]; simp
      have hg : s.line.getD s.col [] = [] := by rw [hl, hcol, ← List.length_reverse]; exact getD_replicate_nil _ _
      have e1 : ∀ d, occupiesCell d = true → d ≠ .bs → d ≠ .del → d ≠ .lf → d ≠ .cr →
          step cr s d next = { s with line := s.line.set s.col [d], occ := s.occ + 1, col := s.col + 1 } := by
        intro d h1 h2 h3 h4 h5
        unfold step
        cases d <;> simp_all [endsLine, occupiesCell]
      rw [e1 _ rfl (by simp) (by simp) (by simp) (by simp)]
      refine ⟨hout, hlead, ⟨k, ?_⟩, by simp [hcol], ?_, by simp [hocc]⟩
      · simp only
        rw [hl, hcol, ← List.length_reverse, set_at_length_replicate]; simp
      · intro c hc'; simp at hc'; rcases hc' with hc' | hc'
        · subst hc'; simp
        · exact hnb c hc'

theorem rel_init : Rel ({} : St) ({} : SSt) :=
  ⟨rfl, rfl, ⟨0, rfl⟩, rfl, by simp, rfl⟩

theorem rel_run (cr : Bool) (rest : List C) (s : St) (ss : SSt)
    (hcr : cr = false ∨ noCR rest = true) (h : Rel s ss) :
    Rel (run cr s rest) (simpleRun ss rest) := by
  induction rest generalizing s ss with
  | nil => exact h
  | cons ch rest ih =>
    simp only [run, simpleRun]
    have hc : cr = false ∨ ch ≠ .cr := by
      rcases hcr with h | h
      · exact Or.inl h
      · right; intro e; subst e; simp [noCR] at h
    have hr : cr = false ∨ noCR rest = true := by
      rcases hcr with h | h
      · exact Or.inl h
      · right; simp [noCR] at h ⊢; exact h.2
    exact ih _ _ hr (rel_step cr s ss ch _ hc h)

theorem finish_of_rel (s : St) (ss : SSt) (h : Rel s ss) :
    finish s = ss.out ++ ss.stack.reverse.flatten := by
  obtain ⟨hout, hlead, ⟨k, hline⟩, _, _, _⟩ := h
  simp [finish, hout, hlead, hline, flatten_replicate_nil]

/-- **Without the flag, the resolver is the stack algorithm**, for every input. -/
theorem resolve_false_eq_simple (t : List C) : resolve false t = simple t := by
  rw [resolve_eq_finish, finish_of_rel _ _ (rel_run false t {} {} (Or.inl rfl) rel_init)]
  rfl

/-- **With the flag and no `CR` in the input, the resolver is the same stack algorithm.** -/
theorem resolve_true_noCR_eq_simple (t : List C) (h : noCR t = true) : resolve true t = simple t := by
  rw [resolve_eq_finish, finish_of_rel _ _ (rel_run true t {} {} (Or.inr h) rel_init)]
  rfl

/-- **With no `CR` in the input, the flag makes no difference.** -/
theorem resolve_flag_irrelevant_noCR (t : List C) (h : noCR t = true) :
    resolve true t = resolve false t := by
  rw [resolve_true_noCR_eq_simple t h, resolve_false_eq_simple]

theorem getD_replicate_any (k i : Nat) : (List.replicate k ([] : Cell)).getD i [] = [] := by
  induction k generalizing i with
  | zero => simp
  | succ k ih => cases i <;> simp [List.replicate_succ, ih]

theorem getD_right_blank (a : List Cell) (k i : Nat) (hi : a.length ≤ i) :
    (a ++ List.replicate k []).getD i [] = [] := by
  induction a generalizing i with
  | nil => simpa using getD_replicate_any k i
  | cons c a ih =>
    cases i with
    | zero => simp at hi
    | succ i =>
      simp only [List.cons_append, List.getD_cons_succ]
      exact ih i (by simp at hi; omega)

/-- **L80-83, proved.** Without a `CR`, `lead` is never used, and every cell at or right
of the cursor is blank — so `occupied > 0` at column 0 does mean a `CR` moved the cursor. -/
theorem noCR_right_of_cursor_blank (cr : Bool) (t : List C) (h : cr = false ∨ noCR t = true) :
    (run cr {} t).lead = [] ∧
    ∀ i, (run cr {} t).col ≤ i → (run cr {} t).line.getD i [] = [] := by
  obtain ⟨_, hlead, ⟨k, hline⟩, hcol, _, _⟩ := rel_run cr t {} {} h rel_init
  refine ⟨hlead, fun i hi => ?_⟩
  rw [hline]
  apply getD_right_blank
  rw [hcol] at hi; simpa using hi

/-! ## Order: without an overwriting `CR`, the output is a subsequence of the input -/

theorem simpleStep_sublist (ss : SSt) (ch : C) :
    List.Sublist ((simpleStep ss ch).out ++ (simpleStep ss ch).stack.reverse.flatten)
      (ss.out ++ ss.stack.reverse.flatten ++ [ch]) := by
  unfold simpleStep
  split
  · cases h : ss.stack with
    | nil => simp
    | cons b a =>
      simp only [List.tail_cons, List.reverse_cons, List.flatten_append]
      apply List.Sublist.trans (List.sublist_append_left _ [ch])
      simp
  split
  · simp
  split
  · split
    · rename_i top rest h
      simp [h]
    · rename_i h; simp [h]
  · simp

theorem simpleRun_sublist (rest : List C) (ss : SSt) :
    List.Sublist ((simpleRun ss rest).out ++ (simpleRun ss rest).stack.reverse.flatten)
      (ss.out ++ ss.stack.reverse.flatten ++ rest) := by
  induction rest generalizing ss with
  | nil => simp [simpleRun]
  | cons ch rest ih =>
    simp only [simpleRun]
    apply List.Sublist.trans (ih _)
    have := simpleStep_sublist ss ch
    have := this.append (List.Sublist.refl rest)
    simpa using this

/-- **No reordering without the flag**: the output is a subsequence of the input. -/
theorem resolve_false_sublist (t : List C) : List.Sublist (resolve false t) t := by
  rw [resolve_false_eq_simple]
  have := simpleRun_sublist t {}
  simpa [simple] using this

/-- **Nor with the flag, if the input has no `CR`.** -/
theorem resolve_true_noCR_sublist (t : List C) (h : noCR t = true) : List.Sublist (resolve true t) t := by
  rw [resolve_true_noCR_eq_simple t h]
  have := simpleRun_sublist t {}
  simpa [simple] using this

end Deletions
