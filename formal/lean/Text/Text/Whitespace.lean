import Text.Hom

/-!
# `collapse_whitespace`, `strip_control_chars`, `strip_zero_width_chars` (`src/whitespace.rs`)

The alphabet is split by the three predicates the functions read:

| Class | Rust | Characters in the differential test |
|---|---|---|
| `ws i` | `is_fold_whitespace(ch) \|\| is_blank_render(ch)` (L41) | space (`ws 0`), TAB, NBSP, `U+001C`, `U+2800`, `U+3164`, `U+2028`, NEL |
| `ctl i` | `is_control() && !is_fold_whitespace` (L124) | NUL, DEL, `U+009B` |
| `zw i` | `is_zero_width` (L153-178) | `U+200B`, `U+FEFF`, `U+1D173` |
| `ch i` | anything else | `a`, `b`, `U+00E9` |

`loop` is the `for` loop of `collapse_whitespace_into` (L40-51) and `collapse` adds the
trailing truncate (L55-57). `cs` is a second, lazier formulation (a space is owed, and paid
only when a non-space follows); `collapse_eq_cs` proves the two equal for every input, and
the properties are proved about `cs`.
-/

namespace Text.Whitespace

inductive C where
  | ws (i : Nat)
  | ctl (i : Nat)
  | zw (i : Nat)
  | ch (i : Nat)
  deriving DecidableEq, Repr, Inhabited

/-- ASCII space, which is itself whitespace. -/
def sp : C := .ws 0

def isWs : C → Bool
  | .ws _ => true
  | _ => false

/-- The loop, as written: `pv` is `prev_was_space`, `sn` is `seen_non_ws`. -/
def loop : Bool → Bool → List C → List C
  | _, _, [] => []
  | pv, sn, c :: t =>
    if isWs c then (if sn && !pv then sp :: loop true sn t else loop pv sn t)
    else c :: loop false true t

def dropTrailingSp (l : List C) : List C :=
  if l.getLast? == some sp then l.dropLast else l

/-- `collapse_whitespace`. -/
def collapse (s : List C) : List C := dropTrailingSp (loop false false s)

/-- The lazy formulation: `p` = a space is owed. -/
def cs : Bool → Bool → List C → List C
  | _, _, [] => []
  | p, sn, c :: t =>
    if isWs c then cs sn sn t
    else if p then sp :: c :: cs false true t else c :: cs false true t

/-- Whether the loop ends having just emitted a space. -/
def lastPrev : Bool → Bool → List C → Bool
  | pv, _, [] => pv
  | pv, sn, c :: t =>
    if isWs c then (if sn && !pv then lastPrev true sn t else lastPrev pv sn t)
    else lastPrev false true t

theorem loop_cs : ∀ (t : List C) (pv sn : Bool), (pv = true → sn = true) →
    (if pv then [sp] else []) ++ loop pv sn t
      = cs pv sn t ++ (if lastPrev pv sn t then [sp] else []) := by
  intro t
  induction t with
  | nil => intro pv sn _; cases pv <;> simp [loop, cs, lastPrev]
  | cons c t ih =>
    intro pv sn hps
    by_cases hc : isWs c = true
    · cases pv with
      | true =>
        have hsn := hps rfl
        subst hsn
        have := ih true true (fun _ => rfl)
        simpa [loop, cs, lastPrev, hc] using this
      | false =>
        cases sn with
        | true =>
          have := ih true true (fun _ => rfl)
          simpa [loop, cs, lastPrev, hc] using this
        | false =>
          have := ih false false (fun h => h)
          simpa [loop, cs, lastPrev, hc] using this
    · have hc' : isWs c = false := by simpa using hc
      have := ih false true (fun h => by simp at h)
      cases pv <;> simp [loop, cs, lastPrev, hc'] at this ⊢ <;> simpa using this

/-! ## The normal form -/

/-- After the first character: single spaces, each followed by a non-space. -/
def nfTail : List C → Bool
  | [] => true
  | c :: r =>
    if isWs c then (c == sp && match r with
                              | [] => false
                              | d :: r' => !isWs d && nfTail r')
    else nfTail r

/-- **The normal form**: empty, or starts with a non-space, and then `nfTail`. It says at
once: no leading space, no trailing space, no two spaces in a row, and the only whitespace
left is ASCII space. -/
def nf : List C → Bool
  | [] => true
  | c :: r => !isWs c && nfTail r

@[simp] theorem isWs_sp : isWs sp = true := rfl

theorem cs_ws (p sn : Bool) (c : C) (t : List C) (hc : isWs c = true) :
    cs p sn (c :: t) = cs sn sn t := by simp [cs, hc]

theorem cs_nonws (p sn : Bool) (c : C) (t : List C) (hc : isWs c = false) :
    cs p sn (c :: t) = if p then sp :: c :: cs false true t else c :: cs false true t := by
  simp [cs, hc]

theorem nfTail_nonws (c : C) (r : List C) (hc : isWs c = false) : nfTail (c :: r) = nfTail r := by
  rw [nfTail.eq_def]; simp [hc]

theorem nfTail_sp (d : C) (r : List C) (hd : isWs d = false) :
    nfTail (sp :: d :: r) = nfTail r := by
  simp [nfTail, hd]

theorem cs_shapes : ∀ t : List C,
    nfTail (cs false true t) = true ∧
    (cs true true t = [] ∨ ∃ d r, cs true true t = sp :: d :: r ∧ isWs d = false ∧ nfTail r = true) := by
  intro t
  induction t with
  | nil => simp [cs, nfTail]
  | cons c t ih =>
    obtain ⟨ih1, ih2⟩ := ih
    cases hc : isWs c
    · rw [cs_nonws _ _ _ _ hc, cs_nonws _ _ _ _ hc]
      simp only [Bool.false_eq_true, ↓reduceIte]
      exact ⟨by rw [nfTail_nonws _ _ hc]; exact ih1, Or.inr ⟨c, _, rfl, hc, ih1⟩⟩
    · rw [cs_ws _ _ _ _ hc, cs_ws _ _ _ _ hc]
      refine ⟨?_, ih2⟩
      rcases ih2 with h | ⟨d, r, h, hd, hr⟩
      · rw [h]; rfl
      · rw [h, nfTail_sp _ _ hd]; exact hr

theorem cs_nf : ∀ t : List C, nf (cs false false t) = true := by
  intro t
  induction t with
  | nil => rfl
  | cons c t ih =>
    cases hc : isWs c
    · rw [cs_nonws _ _ _ _ hc]
      simp [nf, hc, (cs_shapes t).1]
    · rw [cs_ws _ _ _ _ hc]; exact ih

theorem cs_fix_tail : ∀ l : List C, nfTail l = true → cs false true l = l
  | [], _ => rfl
  | [c], h => by
    cases hc : isWs c
    · rw [cs_nonws _ _ _ _ hc]; rfl
    · simp [nfTail, hc] at h
  | c :: d :: r', h => by
    cases hc : isWs c
    · rw [cs_nonws _ _ _ _ hc, nfTail_nonws _ _ hc] at *
      simp only [Bool.false_eq_true, ↓reduceIte]
      rw [cs_fix_tail (d :: r') h]
    · simp only [nfTail, hc, ↓reduceIte, Bool.and_eq_true, beq_iff_eq, Bool.not_eq_true'] at h
      obtain ⟨hsp, hd, hr⟩ := h
      rw [cs_ws _ _ _ _ hc, cs_nonws _ _ _ _ hd]
      simp only [↓reduceIte]
      rw [cs_fix_tail r' hr, hsp]

theorem cs_fix : ∀ l : List C, nf l = true → cs false false l = l
  | [], _ => rfl
  | c :: r, h => by
    simp only [nf, Bool.and_eq_true, Bool.not_eq_true'] at h
    rw [cs_nonws _ _ _ _ h.1]
    simp only [Bool.false_eq_true, ↓reduceIte]
    rw [cs_fix_tail r h.2]

/-- The last character of a normal-form tail is not a space. -/
theorem nfTail_last : ∀ l : List C, nfTail l = true → ∀ x, l.getLast? = some x → isWs x = false
  | [], _, x, hx => by simp at hx
  | [c], h, x, hx => by
    simp at hx; subst hx
    cases hc : isWs c
    · rfl
    · simp [nfTail, hc] at h
  | c :: d :: r', h, x, hx => by
    rw [List.getLast?_cons_cons] at hx
    cases hc : isWs c
    · rw [nfTail_nonws _ _ hc] at h
      exact nfTail_last (d :: r') h x hx
    · simp only [nfTail, hc, ↓reduceIte, Bool.and_eq_true, beq_iff_eq, Bool.not_eq_true'] at h
      obtain ⟨_, hd, hr⟩ := h
      cases r' with
      | nil => simp at hx; subst hx; exact hd
      | cons e r'' =>
        rw [List.getLast?_cons_cons] at hx
        exact nfTail_last (e :: r'') hr x hx

theorem nf_last (l : List C) (h : nf l = true) : l.getLast? ≠ some sp := by
  intro hl
  match l, h with
  | [], _ => simp at hl
  | [c], h =>
    simp at hl; subst hl; simp [nf] at h
  | c :: d :: r, h =>
    simp only [nf, Bool.and_eq_true, Bool.not_eq_true'] at h
    rw [List.getLast?_cons_cons] at hl
    have := nfTail_last (d :: r) h.2 sp hl
    simp at this

theorem collapse_eq_cs (s : List C) : collapse s = cs false false s := by
  have h := loop_cs s false false (fun h => h)
  simp only [Bool.false_eq_true, ↓reduceIte, List.nil_append] at h
  unfold collapse dropTrailingSp
  rw [h]
  have hn := nf_last _ (cs_nf s)
  cases hlp : lastPrev false false s
  · simp only [Bool.false_eq_true, ↓reduceIte, List.append_nil]
    split
    · rename_i hx; simp at hx; exact absurd hx hn
    · rfl
  · simp

/-! ## The claims -/

/-- **Normal form**: no leading, trailing or doubled space, and only ASCII space remains. -/
theorem collapse_nf (s : List C) : nf (collapse s) = true := by
  rw [collapse_eq_cs]; exact cs_nf s

/-- **Idempotence** (`collapse_whitespace_idempotent`, the #433 acceptance criterion). -/
theorem collapse_idem (s : List C) : collapse (collapse s) = collapse s := by
  rw [collapse_eq_cs s, collapse_eq_cs, cs_fix _ (cs_nf s)]

/-- **Folds whitespace only.** Every non-whitespace character survives, in order, and
nothing else is added: controls and zero-width characters are not deleted (L14-15). -/
theorem collapse_keeps_non_ws (s : List C) :
    (collapse s).filter (fun c => !isWs c) = s.filter (fun c => !isWs c) := by
  rw [collapse_eq_cs]
  suffices ∀ p sn (t : List C), (cs p sn t).filter (fun c => !isWs c) = t.filter (fun c => !isWs c) from
    this false false s
  intro p sn t
  induction t generalizing p sn with
  | nil => rfl
  | cons c t ih =>
    cases hc : isWs c
    · rw [cs_nonws _ _ _ _ hc]
      cases p <;> simp [hc, ih]
    · rw [cs_ws _ _ _ _ hc, ih]; simp [hc]

/-- A whitespace-free input is returned unchanged. -/
theorem collapse_id_of_no_ws (s : List C) (h : s.all (fun c => !isWs c) = true) :
    collapse s = s := by
  rw [collapse_eq_cs]
  suffices ∀ sn (t : List C), t.all (fun c => !isWs c) = true → cs false sn t = t from this false s h
  intro sn t
  induction t generalizing sn with
  | nil => intro _; rfl
  | cons c t ih =>
    intro ht
    simp only [List.all_cons, Bool.and_eq_true, Bool.not_eq_true'] at ht
    rw [cs_nonws _ _ _ _ ht.1]
    simp [ih true ht.2]

/-! ## The two strips are filters -/

def isCtl : C → Bool
  | .ctl _ => true
  | _ => false

def isZw : C → Bool
  | .zw _ => true
  | _ => false

def stripControl (s : List C) : List C := s.filter (fun c => !isCtl c)
def stripZeroWidth (s : List C) : List C := s.filter (fun c => !isZw c)

theorem stripControl_idem (s : List C) : stripControl (stripControl s) = stripControl s :=
  Text.filter_idem _ s

theorem stripZeroWidth_idem (s : List C) :
    stripZeroWidth (stripZeroWidth s) = stripZeroWidth s := Text.filter_idem _ s

/-- The two strips commute with each other. -/
theorem strips_commute (s : List C) :
    stripControl (stripZeroWidth s) = stripZeroWidth (stripControl s) := Text.filter_comm _ _ s

/-- Strips after the collapse: the order the presets use makes the result a normal form
too, since deleting a non-space from a normal form keeps it one **only** if the deletion
does not expose two spaces. It does not: `a NUL b` style inputs are the counterexamples
(`Bounded.lean`, `strip_after_collapse_breaks_nf`), which is why the presets collapse last
(review D-8, L19-24). -/
def stripsThenCollapse (s : List C) : List C := collapse (stripZeroWidth (stripControl s))

theorem stripsThenCollapse_nf (s : List C) : nf (stripsThenCollapse s) = true := collapse_nf _

end Text.Whitespace
