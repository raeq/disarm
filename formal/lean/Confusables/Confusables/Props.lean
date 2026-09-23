import Confusables.Fixes

/-!
# The properties, as decidable predicates on one input

Each `p…` is a `Bool` about one input string. `Checks.lean` quantifies them over every
string up to a length bound (closed with `native_decide`), and `Cex.lean` prints the
shortest counterexample for each that fails. The claim each one encodes is cited.
-/

namespace Confusables
open Tables

/-! ### `normalize_confusables` -/

/-- api/safety.rs:112-113, docs/user-guide/confusables.md "The result is a fixed point":
`f(f(x)) == f(x)`. -/
def pFoldIdem (p : Policy) (s : List Char) : Bool :=
  let once := fixedFold p s
  fixedFold p once == once

/-- confusables.rs:57-60: the loop leaves through a stability exit, never the cap. -/
def pFoldConverges (p : Policy) (s : List Char) : Bool := (fixedFoldB p s).2

/-- api/safety.rs:112-113, the guide: "its output is never itself confusable" — `is_confusable`
is false on the output. -/
def pFoldComplete (p : Policy) (s : List Char) : Bool := !isConfusable (fixedFold p s)

/-- api/safety.rs:106-110: "the fold is invariant to the input's normal form". -/
def pFoldNf (p : Policy) (s : List Char) : Bool := fixedFold p (nfc s) == fixedFold p (nfd s)

/-- api/safety.rs:254-257: detection "cannot be evaded by decomposing". -/
def pDetectNf (s : List Char) : Bool := isConfusable (nfc s) == isConfusable (nfd s)

/-- find_confusables is the located form of is_confusable (confusables.rs:396-435). -/
def pDetectFind (s : List Char) : Bool := isConfusable s == !(findConfusables s).isEmpty

/-- A detection means the fold changes something (the fold covers what the detector sees). -/
def pDetectChanges (s : List Char) : Bool := !isConfusable s || fixedFold .numeric s != s

/-- "The two policies differ on the tr39 rows and agree everywhere else"
(docs/user-guide/confusables.md, Digit policy). -/
def pTr39Scope (s : List Char) : Bool :=
  fixedFold .tr39 s == fixedFold .numeric s || (composed s).any (fun c => (tr39Override c).isSome)

/-- "`preserve` declines the digit rows and folds everything else as usual". -/
def pPreserveScope (s : List Char) : Bool :=
  fixedFold .preserve s == fixedFold .numeric s ||
    (composed s).any (fun c => (latinMap c).any isDigitValue)

/-- find_unmapped reports only characters the table does not fold. -/
def pUnmappedSound (s : List Char) : Bool := (findUnmapped s).all (fun c => (latinMap c).isNone)

/-! ### `skeleton_key` -/

/-- presets.rs:2085-2098, `_presets.py` skeleton_key: "a key that is not a fixed point is
not a key". -/
def pSkIdem (sk : Policy → List Char → List Char) (p : Policy) (s : List Char) : Bool :=
  let k := sk p s
  sk p k == k

/-- A key built on NFKC does not depend on the input's normal form. -/
def pSkNf (sk : Policy → List Char → List Char) (p : Policy) (s : List Char) : Bool :=
  sk p (nfc s) == sk p (nfd s)

/-- The #458 guard is an optimisation: the guarded result equals the full pipeline's. -/
def pSkGuard (s : List Char) : Bool := skeletonKey .numeric s == skeletonSteps .numeric s

def pSkGuardFixed (s : List Char) : Bool :=
  Fixes.skeletonKeyFixed .numeric s == Fixes.skeletonStepsFixed .numeric s

/-- `_presets.py`: "Returns: The skeleton, lowercased". -/
def pSkLower (sk : Policy → List Char → List Char) (p : Policy) (s : List Char) : Bool :=
  let k := sk p s
  foldCase k == k

/-- The skeleton is not itself flagged by the library's own detector. -/
def pSkNotConfusable (sk : Policy → List Char → List Char) (p : Policy) (s : List Char) : Bool :=
  !isConfusable (sk p s)

/-! ### Enumeration -/

/-- `p` holds on every string over `alphabet` of length at most `n` (built back to
front: every string is reached exactly once). -/
def allUpTo (n : Nat) (p : List Char → Bool) : Bool :=
  let rec go : Nat → List Char → Bool
    | 0, acc => p acc
    | k + 1, acc => p acc && alphabet.all (fun c => go k (c :: acc))
  go n []

/-- The shortest (then first in enumeration order) string of length at most `n` on which
`p` fails. -/
def firstFailure (n : Nat) (p : List Char → Bool) : Option (List Char) :=
  let rec strs : Nat → List (List Char)
    | 0 => [[]]
    | k + 1 => (strs k).flatMap (fun s => alphabet.map (fun c => s ++ [c]))
  (List.range (n + 1)).findSome? (fun k => (strs k).find? (fun s => !p s))

end Confusables
