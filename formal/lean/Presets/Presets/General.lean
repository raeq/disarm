/-!
# General facts about step composition

Proved by induction, for every input and every step list; nothing here uses
`native_decide`. The steps are arbitrary functions `List α -> List α`, so these apply to the
model and, read as statements about functions, to the Rust.

* `run_fixed_of_all_fixed`, `run_idem_of_image_fixed` -- the **stable-image criterion**: a
  pipeline is idempotent as soon as its output is a fixed point of every one of its steps.
  This is the shape of every idempotence argument in `src/presets.rs` ("the terminal NFC
  recomposes ... so `f(f(x)) == f(x)`").
* `run_not_idem_of` -- its contrapositive at a point, which is how the findings are read:
  a second pass differs exactly when the first output is moved by some step.
* `filter_idem`, `filter_comm`, `filter_run_comm` -- the pure strips (`strip_bidi`,
  `strip_zero_width`, `strip_control`, `strip_pua`, the comparison `strip_invisible`) are
  idempotent and commute, so their relative order never matters.
* `flatMap_idem` -- a per-character map whose images are fixed characters is idempotent
  (the case fold and a confusable pass are *not*, which is why they sit in loops).
* `comp_idem_of_comm` -- two idempotent steps that commute compose to an idempotent step.
* `fixLoop_stable` -- the bounded fixed-point loop returns a fixed point of its body
  whenever it stops before the fuel runs out.
-/

namespace Presets.General

variable {α : Type}

/-- Apply `fs` in order. -/
def run (fs : List (List α -> List α)) (x : List α) : List α := fs.foldl (fun acc f => f acc) x

theorem run_nil (x : List α) : run [] x = x := rfl

theorem run_cons (f : List α -> List α) (fs : List (List α -> List α)) (x : List α) :
    run (f :: fs) x = run fs (f x) := rfl

theorem run_append (fs gs : List (List α -> List α)) (x : List α) :
    run (fs ++ gs) x = run gs (run fs x) := by
  induction fs generalizing x with
  | nil => rfl
  | cons f fs ih => simp [run_cons, ih]

/-- If every step fixes `y`, the pipeline fixes `y`. -/
theorem run_fixed_of_all_fixed (fs : List (List α -> List α)) (y : List α)
    (h : ∀ f ∈ fs, f y = y) : run fs y = y := by
  induction fs with
  | nil => rfl
  | cons f fs ih =>
    rw [run_cons, h f (List.mem_cons_self), ih (fun g hg => h g (List.mem_cons_of_mem f hg))]

/-- **The stable-image criterion.** A pipeline whose every output is a fixed point of each of
its steps is idempotent. -/
theorem run_idem_of_image_fixed (fs : List (List α -> List α))
    (h : ∀ x, ∀ f ∈ fs, f (run fs x) = run fs x) (x : List α) :
    run fs (run fs x) = run fs x :=
  run_fixed_of_all_fixed fs (run fs x) (h x)

/-- Read the other way, at one input: if the second pass moves the output, some step moves
it. The findings name that step. -/
theorem run_not_idem_of (fs : List (List α -> List α)) (x : List α)
    (h : run fs (run fs x) ≠ run fs x) : ∃ f ∈ fs, f (run fs x) ≠ run fs x := by
  apply Classical.byContradiction
  intro hn
  apply h
  apply run_fixed_of_all_fixed
  intro f hf
  apply Classical.byContradiction
  intro hne
  exact hn ⟨f, hf, hne⟩

theorem filter_idem (p : α -> Bool) (l : List α) : (l.filter p).filter p = l.filter p := by
  induction l with
  | nil => rfl
  | cons a l ih =>
    by_cases hp : p a = true
    · simp [hp, ih]
    · simp [hp, ih]

theorem filter_comm (p q : α -> Bool) (l : List α) :
    (l.filter p).filter q = (l.filter q).filter p := by
  induction l with
  | nil => rfl
  | cons a l ih =>
    by_cases hp : p a = true <;> by_cases hq : q a = true <;> simp [hp, hq, ih]

/-- Two consecutive filters are one filter on the conjunction. -/
theorem filter_filter_and (p q : α -> Bool) (l : List α) :
    (l.filter p).filter q = l.filter (fun a => p a && q a) := by
  induction l with
  | nil => rfl
  | cons a l ih =>
    by_cases hp : p a = true <;> by_cases hq : q a = true <;> simp [hp, hq, ih]

/-- A run of filters, in any order, is the filter on the conjunction of their predicates:
the strips' relative order never matters. -/
theorem filter_run_comm (ps : List (α -> Bool)) (l : List α) :
    run (ps.map fun p => List.filter p) l = l.filter (fun a => ps.all fun p => p a) := by
  induction ps generalizing l with
  | nil =>
    exact (List.filter_eq_self.2 (by simp)).symm
  | cons p ps ih =>
    rw [List.map_cons, run_cons, ih, filter_filter_and]
    simp [List.all_cons]

/-- A per-character map whose every image character is mapped to itself is idempotent. -/
theorem flatMap_idem (f : α -> List α) (h : ∀ c, ∀ d ∈ f c, f d = [d]) (l : List α) :
    (l.flatMap f).flatMap f = l.flatMap f := by
  have hfix : ∀ m : List α, (∀ d ∈ m, f d = [d]) -> m.flatMap f = m := by
    intro m hm
    induction m with
    | nil => rfl
    | cons d m ih =>
      rw [List.flatMap_cons, hm d List.mem_cons_self,
        ih (fun e he => hm e (List.mem_cons_of_mem d he))]
      rfl
  apply hfix
  intro d hd
  rw [List.mem_flatMap] at hd
  obtain ⟨c, _, hc⟩ := hd
  exact h c d hc

/-- Two idempotent, commuting steps compose to an idempotent step. -/
theorem comp_idem_of_comm (f g : List α -> List α) (hf : ∀ x, f (f x) = f x)
    (hg : ∀ x, g (g x) = g x) (hc : ∀ x, f (g x) = g (f x)) (x : List α) :
    g (f (g (f x))) = g (f x) := by
  rw [hc (f x), hf, hg]

/-- `f` applied `k` times. -/
def iter (f : List α -> List α) : Nat -> List α -> List α
  | 0, x => x
  | k + 1, x => iter f k (f x)

/-- The bounded fixed-point loop (`Step::FixedPoint`, the confusable loops). -/
def fixLoop [DecidableEq α] (f : List α -> List α) : Nat -> List α -> List α
  | 0, cur => cur
  | n + 1, cur => if f cur = cur then cur else fixLoop f n (f cur)

/-- The loop is either at a fixed point of its body or has spent its fuel on a chain that
moved at every step. -/
theorem fixLoop_stable [DecidableEq α] (f : List α -> List α) (n : Nat) (x : List α)
    (h : ∃ k, k < n ∧ f (iter f k x) = iter f k x) : f (fixLoop f n x) = fixLoop f n x := by
  induction n generalizing x with
  | zero => obtain ⟨k, hk, _⟩ := h; exact absurd hk (Nat.not_lt_zero k)
  | succ n ih =>
    unfold fixLoop
    by_cases hx : f x = x
    · simp [hx]
    · simp only [hx, ite_false]
      apply ih
      obtain ⟨k, hk, hfk⟩ := h
      cases k with
      | zero => exact absurd hfk hx
      | succ k => exact ⟨k, by omega, hfk⟩

end Presets.General
