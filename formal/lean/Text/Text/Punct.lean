import Text.Hom

/-!
# `fold_punctuation` (`src/punctuation.rs`)

`ascii_for` (L30-44) is a per-scalar table, so `fold_punctuation` is `pmap fold`. The
alphabet is split by its arms. `other` stands for everything the table does not name,
including the typographic characters it deliberately or accidentally leaves alone
(`U+3002`, `U+00B7`, `U+1680`, `U+201B`, `U+201F`, `U+2034` in the differential test).
-/

namespace Text.Punct

open Text

inductive P where
  | ascii (c : Char)
  | dash (i : Nat)
  | squote (i : Nat)
  | dquote (i : Nat)
  | ellipsis
  | nsp (i : Nat)
  | other (i : Nat)
  deriving DecidableEq, Repr

def fold : P → List P
  | .dash _ => [.ascii '-']
  | .squote _ => [.ascii '\'']
  | .dquote _ => [.ascii '"']
  | .ellipsis => [.ascii '.', .ascii '.', .ascii '.']
  | .nsp _ => [.ascii ' ']
  | c => [c]

def foldPunct (s : List P) : List P := pmap fold s

def isAscii : P → Bool
  | .ascii _ => true
  | _ => false

theorem fold_fixed (a : P) : pmap fold (fold a) = fold a := by
  cases a <;> rfl

/-- **Idempotent** (docstring: "Idempotent"), for every input. -/
theorem foldPunct_idem (s : List P) : foldPunct (foldPunct s) = foldPunct s :=
  pmap_idem fold fold_fixed s

/-- **The identity on ASCII** (docstring), for every input. -/
theorem foldPunct_ascii (s : List P) (h : s.all isAscii = true) : foldPunct s = s :=
  pmap_id_on fold isAscii (fun a ha => by cases a <;> simp_all [isAscii, fold]) s h

/-- Everything it writes is ASCII: the image of every folded class is ASCII. -/
theorem fold_image_ascii (a : P) (h : isAscii a = false ∧ ∀ i, a ≠ .other i) :
    (fold a).all isAscii = true := by
  cases a <;> simp_all [fold, isAscii]

end Text.Punct
