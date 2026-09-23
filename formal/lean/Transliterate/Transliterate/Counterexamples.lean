import Transliterate.Lift

/-!
# H is necessary: context-sensitive maps defeat the per-character lift

Two concrete string functions over `Char`, each passing the *per-character*
check the exhaustive Rust tests perform, each failing the string-level
invariant — so the lift in `Lift.lean` genuinely depends on H.

* `dropXY` (idempotence). Per character it is the identity, so it passes
  per-character I1 and per-character I3 for every one of the 1,114,112 `Char`s;
  yet `dropXY (dropXY "xxy") ≠ dropXY "xxy"`.
* `sepJoin` (ASCII output). It maps every character to ASCII and inserts a
  separator between adjacent ideographs — the shape of the real engine's
  CJK word spacing (`needs_cjk_space`, src/transliterate.rs). A single
  character never has a neighbour, so **no per-character test ever sees the
  separator**. With a non-ASCII separator per-character I2 holds for every
  `Char` while `sepJoin "北京"` is not ASCII.
-/

namespace Transliterate

/-- "ASCII" on `Char`. -/
def isAscii (c : Char) : Bool := decide (c.toNat < 128)

/-! ## Idempotence: `dropXY` -/

/-- One left-to-right pass deleting every `x` that is immediately followed by
`y` *in the input*. -/
def dropXY : List Char → List Char
  | [] => []
  | c :: t => if c = 'x' ∧ t.head? = some 'y' then dropXY t else c :: dropXY t

theorem dropXY_singleton (c : Char) : dropXY [c] = [c] := by
  simp [dropXY]

/-- Per-character I3 holds for **every** `Char` (the analogue of
`exhaustive_bmp_idempotence`, but over all of `Char`, not just the BMP). -/
theorem dropXY_I3_per_char : ∀ c : Char, dropXY (dropXY [c]) = dropXY [c] := by
  intro c; simp [dropXY_singleton]

/-- Per-character I1 holds too. -/
theorem dropXY_I1_per_char : ∀ c : Char, isAscii c = true → dropXY [c] = [c] :=
  fun c _ => dropXY_singleton c

/-- …but string-level I3 fails. -/
theorem dropXY_not_idempotent :
    dropXY (dropXY "xxy".toList) ≠ dropXY "xxy".toList := by decide

/-- …and so does string-level I1 (`"xy"` is ASCII and is not fixed). -/
theorem dropXY_not_I1 : dropXY "xy".toList ≠ "xy".toList := by decide

/-- Hence `dropXY` is not a homomorphism (otherwise `lift_I3_hom` would apply). -/
theorem dropXY_not_hom : ¬ IsHom dropXY := by
  intro h
  exact dropXY_not_idempotent (lift_I3_hom h dropXY_I3_per_char _)

/-! ## ASCII output: `sepJoin` -/

/-- CJK Unified Ideographs, U+4E00–U+9FFF (`is_cjk_ideograph`). -/
def isIdeo (c : Char) : Bool := decide (0x4E00 ≤ c.toNat ∧ c.toNat ≤ 0x9FFF)

/-- A stand-in per-character table: ideographs to an ASCII syllable, ASCII to
itself, everything else dropped (`errors='ignore'`). Every value is ASCII. -/
def table (c : Char) : List Char :=
  if isIdeo c then ['x'] else if isAscii c then [c] else []

theorem table_ascii (c : Char) : AllA isAscii (table c) := by
  unfold table
  split
  · intro x hx; rw [List.mem_singleton.mp hx]; decide
  · split
    · rename_i h; exact AllA.singleton.mpr h
    · exact AllA.nil _

/-- Emit `table c` for each character, preceded by `sep` when both it and the
previous input character are ideographs. -/
def sepGo (sep : Char) : Option Char → List Char → List Char
  | _, [] => []
  | p, c :: t =>
    (if (p.map isIdeo).getD false && isIdeo c then [sep] else []) ++ table c ++ sepGo sep (some c) t

def sepJoin (sep : Char) (s : List Char) : List Char := sepGo sep none s

theorem sepJoin_singleton (sep c : Char) : sepJoin sep [c] = table c := by
  simp [sepJoin, sepGo]

/-- Per-character I2 holds for every `Char`, whatever the separator. -/
theorem sepJoin_I2_per_char (sep : Char) : ∀ c : Char, AllA isAscii (sepJoin sep [c]) := by
  intro c; rw [sepJoin_singleton]; exact table_ascii c

/-- With a non-ASCII separator (U+00B7 MIDDLE DOT) string-level I2 fails. -/
theorem sepJoin_middot_not_ascii : ¬ AllA isAscii (sepJoin '·' "北京".toList) := by
  intro h
  have : isAscii '·' = true := h '·' (by decide)
  exact absurd this (by decide)

theorem sepJoin_middot_not_hom : ¬ IsHom (sepJoin '·') := by
  intro h
  exact sepJoin_middot_not_ascii (lift_I2 h (sepJoin_I2_per_char '·') _)

/-- With an ASCII separator (the real engine pushes `' '`) the output *is*
ASCII for every string — but not by the lift, because the map is still not a
homomorphism: the proof is an induction over the emitted pieces. -/
theorem sepGo_ascii (sep : Char) (hs : isAscii sep = true) :
    ∀ (p : Option Char) (s : List Char), AllA isAscii (sepGo sep p s) := by
  intro p s
  induction s generalizing p with
  | nil => exact AllA.nil _
  | cons c t ih =>
    simp only [sepGo]
    refine AllA.append (AllA.append ?_ (table_ascii c)) (ih _)
    split
    · exact AllA.singleton.mpr hs
    · exact AllA.nil _

theorem sepJoin_space_ascii : ∀ s, AllA isAscii (sepJoin ' ' s) :=
  fun s => sepGo_ascii ' ' (by decide) none s

theorem sepJoin_space_not_hom : ¬ IsHom (sepJoin ' ') := by
  intro h
  have e := h "北".toList "京".toList
  exact absurd e (by decide)

end Transliterate
