import Presets.Tables

/-!
# Normalization over the model's domain

Canonical decomposition, canonical ordering and canonical composition (UAX #15), driven by
the generated tables. The composition loop follows `unicode-normalization`'s
`Recompositions` state machine, which is what every `nfc()` in `src/` runs.

Strings are lists of code points.
-/

namespace Presets

abbrev Str := List Nat

/-- Look a code point up in a generated table; off the table it maps to itself. -/
@[inline] def lk (t : Nat -> Option (List Nat)) (c : Nat) : List Nat :=
  match t c with
  | some l => l
  | none => [c]

/-- Canonical combining class. -/
def ccc (c : Nat) : Nat :=
  match cccT c with
  | some (n :: _) => n
  | _ => 0

/-- Stable insertion by combining class: `c` goes after every element whose class is not
greater than its own. -/
def insertCcc (c : Nat) : Str -> Str
  | [] => [c]
  | d :: ds => if ccc c < ccc d then c :: d :: ds else d :: insertCcc c ds

/-- Stable sort of a run of non-starters by combining class. -/
def sortRun (run : Str) : Str := run.foldl (fun acc c => insertCcc c acc) []

/-- Canonical ordering: sort every maximal run of non-starters (`run` is reversed). -/
def reorderAux : Str -> Str -> Str
  | run, [] => sortRun run.reverse
  | run, c :: cs =>
    if ccc c == 0 then sortRun run.reverse ++ c :: reorderAux [] cs
    else reorderAux (c :: run) cs

def reorder (s : Str) : Str := reorderAux [] s

def nfd (s : Str) : Str := reorder (s.flatMap (lk nfdT))
def nfkd (s : Str) : Str := reorder (s.flatMap (lk nfkdT))

/-- The recomposition state. `out` and `buf` are reversed. -/
structure CSt where
  out : Str := []
  composee : Option Nat := none
  buf : Str := []
  last : Option Nat := none
  deriving Repr

def compStep (s : CSt) (ch : Nat) : CSt :=
  let cl := ccc ch
  match s.composee with
  | none => if cl != 0 then { s with out := ch :: s.out } else { s with composee := some ch }
  | some k =>
    match s.last with
    | none =>
      match compose k ch with
      | some r => { s with composee := some r }
      | none =>
        if cl == 0 then { out := k :: s.out, composee := some ch, buf := [], last := none }
        else { s with buf := ch :: s.buf, last := some cl }
    | some l =>
      if cl <= l then
        if cl == 0 then { out := s.buf ++ k :: s.out, composee := some ch, buf := [], last := none }
        else { s with buf := ch :: s.buf, last := some cl }
      else
        match compose k ch with
        | some r => { s with composee := some r }
        | none => { s with buf := ch :: s.buf, last := some cl }

def CSt.finish (s : CSt) : Str :=
  match s.composee with
  | none => (s.buf ++ s.out).reverse
  | some k => (s.buf ++ k :: s.out).reverse

/-- Canonical composition of a canonically ordered, decomposed string. -/
def composeStr (s : Str) : Str := (s.foldl compStep {}).finish

def nfc (s : Str) : Str := composeStr (nfd s)
def nfkc (s : Str) : Str := composeStr (nfkd s)

def isAscii (s : Str) : Bool := s.all (fun c => c < 0x80)

end Presets
