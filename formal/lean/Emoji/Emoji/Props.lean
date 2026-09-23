import Emoji.Model

/-!
# The properties, as decidable predicates on one input

Each `p…` is a `Bool` about a single input string. `Checks.lean` quantifies them over
every string up to a length bound (by enumeration, closed with `native_decide`), and
`Cex.lean`'s executable prints the shortest counterexample for each that fails.
-/

namespace Emoji
open Tables

def count (c : Char) (s : List Char) : Nat := s.countP (· == c)

/-- Occurrences of the adjacent pair `a b` in `s`. -/
def countPair (a b : Char) : List Char → Nat
  | x :: y :: t => (if x == a && y == b then 1 else 0) + countPair a b (y :: t)
  | _ => 0

/-! ### replace_emoji -/

/-- "A removal manufactures no emoji": no suffix of the output starts an emoji
presentation sequence. -/
def pReplaceClean (repl : List Char) (s : List Char) : Bool :=
  !hasPresentation (replaceEmoji s repl)

def pReplaceIdem (repl : List Char) (s : List Char) : Bool :=
  let once := replaceEmoji s repl
  replaceEmoji once repl == once

/-- `CharWindow` is an optimisation only: the windowed scanner (window `W`) equals the
unbounded one. -/
def pWindowEq (W : Nat) (repl : List Char) (s : List Char) : Bool :=
  replaceW W s repl == replaceU s repl

/-! ### demojize -/

def demIgnore (s : List Char) : List Char := demojizePy .ignore "[?]".toList none s
def demReplace (s : List Char) : List Char := demojizePy .replace "[?]".toList none s
def demReplaceEmpty (s : List Char) : List Char := demojizePy .replace [] none s
def demPreserve (s : List Char) : List Char := demojizePy .preserve "[?]".toList none s

def pClean (f : List Char → List Char) (s : List Char) : Bool := !hasPresentation (f s)
def pIdem (f : List Char → List Char) (s : List Char) : Bool := f (f s) == f s

/-- Nothing in `keep` is lost: every such character occurs at least as often in the
output as in the input. -/
def pKeeps (keep : List Char) (f : List Char → List Char) (s : List Char) : Bool :=
  let out := f s
  keep.all fun c => count c out ≥ count c s

/-- A stray keycap survives when nothing in the input could bind it (no keycap base). -/
def pStrayKeycapKept (f : List Char → List Char) (s : List Char) : Bool :=
  s.any isKeycapBase || count KEYCAP (f s) == count KEYCAP s

/-- Characters a combining mark extends through to reach its base: UAX #29
`Grapheme_Cluster_Break=Extend` restricted to the alphabet (the marks, including the two
selectors and the keycap; skin tones; tags) plus ZWJ, which rule GB9 also attaches. -/
def isExtend (c : Char) : Bool := isCombiningMark c || c == ZWJ || isSkinTone c || isTag c

/-- For each `U+0301` in `s`, the character it attaches to: the nearest preceding
non-`Extend` character (`none` at the start of the string). -/
def markBases (s : List Char) : List (Option Char) :=
  let rec go : List Char → Option Char → List (Option Char)
    | [], _ => []
    | c :: t, base =>
      if c == cMK then base :: go t base
      else if isExtend c then go t base
      else go t (some c)
  go s none

def countBase (a : Char) (s : List Char) : Nat := (markBases s).countP (· == some a)

/-- #996, stated strongly: a combining mark does not end up on an alphanumeric it was not
attached to in the input — for every alphanumeric `a`, no more marks sit on an `a` in the
output than in the input. -/
def pMarkStaysPut (f : List Char → List Char) (s : List Char) : Bool :=
  let out := f s
  (markBases out).all fun
    | some a => !isAlphanumeric a || countBase a out ≤ countBase a s
    | none => true

/-- #996, the weaker form the changelog states: a mark never lands on an emoji **name**.
Names are the only source of ASCII letters other than `x` (the alphabet's one letter,
which occurs in no name), so a mark whose base is such a letter is on a name. -/
def pMarkNotOnName (f : List Char → List Char) (s : List Char) : Bool :=
  (markBases (f s)).all fun
    | some a => !(a.isAlpha && a != 'x')
    | none => true

/-- #200: a name is not glued to the word after it. No output position has a name's
last letter (an ASCII letter other than `x`, see `pMarkNotOnName`) directly followed by
an input character that `needs_separator_after_a_name` separates (`x`, `1`, `€`). -/
def pNameSeparated (f : List Char → List Char) (s : List Char) : Bool :=
  let rec go : List Char → Bool
    | a :: b :: t => !(a.isAlpha && a != 'x' && (b == cX || b == c1 || b == cEU)) && go (b :: t)
    | _ => true
  go (f s)

/-- `demojize(errors="ignore")` and `TextPipeline(demojize=True)` agree. -/
def pPipelineAgrees (s : List Char) : Bool := pipelineDemojize s == demIgnore s

/-- The provider path keeps a keycap whole (#1006): with a provider that claims the
digit alone, no `U+20E3` is left after a digit in the output. -/
def oneProvider : Provider := fun seq => if seq == ['1'] then some "ONE" else none
def pProviderKeycapWhole (s : List Char) : Bool :=
  countPair '1' KEYCAP (demojizePy .replace "[?]".toList (some oneProvider) s) == 0

/-! ### enumeration -/

/-- Does `p` hold on every string over `alpha` of length exactly `n`? Enumerated
depth-first without materialising the list of strings. -/
def allOfLen (alpha : List Char) (p : List Char → Bool) : Nat → List Char → Bool
  | 0, acc => p acc
  | n + 1, acc => alpha.all fun c => allOfLen alpha p n (c :: acc)

/-- Does `p` hold on every string over `alpha` of length ≤ `n`? -/
def allUpTo (alpha : List Char) (p : List Char → Bool) (n : Nat) : Bool :=
  (List.range (n + 1)).all fun k => allOfLen alpha p k []

/-- The first counterexample in length-then-lexicographic order, if any. -/
def firstCex (alpha : List Char) (p : List Char → Bool) (n : Nat) : Option (List Char) :=
  let rec ofLen : Nat → List Char → Option (List Char)
    | 0, acc => if p acc then none else some acc
    | k + 1, acc => alpha.findSome? fun c => ofLen k (acc ++ [c])
  (List.range (n + 1)).findSome? fun k => ofLen k []

/-! ### alphabets -/

/-- The whole model alphabet (21 classes). -/
def full : List Char := alphabet

/-- `full` without `€`, the one class the pipeline's `NamePolicy` treats differently (#757). -/
def noEuro : List Char := alphabet.filter (· != cEU)

/-- The classes the presentation grammar and the window branch on (11). -/
def grammar : List Char := [cM, cH, cC, c1, cKC, cV15, cV16, cZ, cT, cG, cRA]

end Emoji
