/-!
List lemmas used by the general proofs. Each is proved by induction here rather than
looked up, so the development does not depend on the names core happens to use.
-/

namespace Sanitizers.Lists

variable {α : Type}

theorem mem_of_mem_dropWhile {p : α → Bool} :
    ∀ {l : List α} {c : α}, c ∈ l.dropWhile p → c ∈ l
  | [], _, h => by simp at h
  | x :: xs, c, h => by
    simp only [List.dropWhile] at h
    cases hx : p x
    · simp only [hx] at h; exact h
    · simp only [hx] at h; exact List.mem_cons_of_mem _ (mem_of_mem_dropWhile h)

theorem head_dropWhile {p : α → Bool} :
    ∀ {l : List α} {c : α}, (l.dropWhile p).head? = some c → p c = false
  | [], _, h => by simp at h
  | x :: xs, c, h => by
    simp only [List.dropWhile] at h
    cases hx : p x
    · simp only [hx, List.head?_cons, Option.some.injEq] at h; subst h; exact hx
    · simp only [hx] at h; exact head_dropWhile h

theorem mem_of_mem_take {l : List α} {n : Nat} {c : α} (h : c ∈ l.take n) : c ∈ l :=
  List.mem_of_mem_take h

theorem length_dropWhile_le {p : α → Bool} : ∀ (l : List α), (l.dropWhile p).length ≤ l.length
  | [] => by simp
  | x :: xs => by
    simp only [List.dropWhile]
    cases p x
    · simp
    · simp only [List.length_cons]; exact Nat.le_succ_of_le (length_dropWhile_le xs)

/-- `rtrim`, generically. -/
def rtrim (p : α → Bool) (l : List α) : List α := (l.reverse.dropWhile p).reverse

theorem mem_of_mem_rtrim {p : α → Bool} {l : List α} {c : α} (h : c ∈ rtrim p l) : c ∈ l := by
  unfold rtrim at h
  rw [List.mem_reverse] at h
  exact List.mem_reverse.mp (mem_of_mem_dropWhile h)

theorem length_rtrim_le (p : α → Bool) (l : List α) : (rtrim p l).length ≤ l.length := by
  unfold rtrim
  rw [List.length_reverse]
  have := length_dropWhile_le (p := p) l.reverse
  rw [List.length_reverse] at this
  exact this

theorem getLast_rtrim {p : α → Bool} {l : List α} {c : α}
    (h : (rtrim p l).getLast? = some c) : p c = false := by
  unfold rtrim at h
  rw [List.getLast?_reverse] at h
  exact head_dropWhile h

/-- The first element survives a right trim that leaves anything. -/
theorem head_rtrim {p : α → Bool} : ∀ {l : List α} {c : α},
    (rtrim p l).head? = some c → l.head? = some c := by
  intro l c h
  unfold rtrim at h
  -- (l.reverse.dropWhile p) is a suffix of l.reverse, so its reverse is a prefix of l.
  have hs : (l.reverse.dropWhile p) <:+ l.reverse := List.dropWhile_suffix p
  have hp : (l.reverse.dropWhile p).reverse <+: l := by
    have := List.reverse_prefix.mpr hs
    simpa using this
  obtain ⟨t, ht⟩ := hp
  rw [← ht, List.head?_append, h]
  rfl

end Sanitizers.Lists
