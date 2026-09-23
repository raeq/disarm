import Sanitizers.Filename
import Sanitizers.Slug
import Sanitizers.Unique
import Sanitizers.EditDistance

/-!
The grids the bounded checks (`Bounded.lean`) quantify over, and the predicates they
check, as named functions: `Bounded.lean` is then only statements, and `lake exe explore`
prints the first case of each grid that fails its predicate.
-/

namespace Sanitizers

/-- Every word of length exactly `n` over `alpha`. -/
def wordsExactly (alpha : List Char) : Nat → List (List Char)
  | 0 => [[]]
  | n + 1 => (wordsExactly alpha n).flatMap (fun w => alpha.map (fun c => c :: w))

/-- Every word of length at most `n` over `alpha`. -/
def wordsUpTo (alpha : List Char) (n : Nat) : List (List Char) :=
  (List.range (n + 1)).flatMap (wordsExactly alpha)

namespace Filename

/-- The alphabet of the bounded checks and of the exhaustive half of the differential
test (`F_ALPHA` in `scripts/difftest.py`): one character per branch the code takes, plus
the letters of `con` and a letter that is none of them. -/
def alpha : List Char := ['.', ' ', '/', '*', '_', 'c', 'o', 'n', 'x']

structure Case where
  w : List Char
  sep : List Char
  ml : Nat
  p : Platform
  pe : Bool
  deriving Repr

def grid (n : Nat) : List Case :=
  (wordsUpTo alpha n).flatMap fun w =>
    [['_'], [], ['-'], [' ']].flatMap fun sep => [0, 1, 2, 3, 4, 5, 6, 8].flatMap fun ml =>
      [Platform.universal, .posix].flatMap fun p => [false, true].map fun pe => ⟨w, sep, ml, p, pe⟩

/-- Not a reserved name, as Windows reads it (`winStem`). -/
def safeWin (p : Platform) (out : List Char) : Bool :=
  !(windowsish p && isReserved (winStem out))

/-- P1, P2, P6, P7, P8, and the characters (`sanitize_chars`). -/
def outOK (c : Case) (out : List Char) : Bool :=
  !out.isEmpty && out != ['.'] && out != ['.', '.']
    && !(out.head?.any isDS) && !(out.getLast?.any isDS)
    && (c.ml == 0 || out.length ≤ c.ml)
    && safeWin c.p out
    && out.all (fun ch => c.sep.contains ch || !dropped c.p ch)

def cur (c : Case) : List Char := sanitize c.w c.sep c.ml c.p c.pe
def fixed (c : Case) : List Char := sanitizeFixed c.w c.sep c.ml c.p c.pe

def fixedSafe (c : Case) : Bool := outOK c (fixed c)

def fixedIdem (c : Case) : Bool :=
  sanitizeFixed (fixed c) c.sep c.ml c.p c.pe == fixed c

def curIdem (c : Case) : Bool :=
  sanitize (cur c) c.sep c.ml c.p c.pe == cur c

/-- P9 without truncation (`max_length = 0`, and every case whose name already fits). -/
def fixedIdemNoTrunc (c : Case) : Bool := c.ml != 0 || fixedIdem c

/-- Finding 1's precondition: the extension split off, and the stem sanitized to nothing. -/
def emptyStem (c : Case) : Bool :=
  let sp := split c.pe (rtrim isDS (collapse (collapse c.w)))
  sp.2.isSome && (cleanStem c.p c.sep sp.1).isEmpty

/-- With the default separator and no truncation, the current model meets P1-P8 unless
the stem sanitized to nothing (Finding 1). -/
def curSafeDefault (c : Case) : Bool :=
  c.sep != ['_'] || c.ml != 0 || outOK c (cur c) || emptyStem c

end Filename

namespace Slug

def alpha : List Char := ['a', 'B', '1', ' ', '-', '!']

/-- No empty word (so no leading, trailing or doubled separator) and no trailing proper
prefix of the separator. -/
def shapeOK (sep out : List Char) : Bool :=
  out.isEmpty || sep.isEmpty ||
    ((split sep out).all (fun w => !w.isEmpty)
      && (List.range sep.length).all (fun k => k == 0 || !(sep.take k).isSuffixOf out))

def grid (n : Nat) (seps : List (List Char)) : List (Config × List Char) :=
  (wordsUpTo alpha n).flatMap fun w =>
    seps.flatMap fun sep => [0, 1, 2, 3, 4, 5, 6].flatMap fun ml =>
      [false, true].flatMap fun wb => [false, true].flatMap fun so =>
        [[], [['a']], [['A'], ['b', '1']], [['b']]].map fun st =>
          ({ sep, lowercase := true, maxLen := ml, wordBoundary := wb, saveOrder := so,
             stopwords := st }, w)

def singleSeps : List (List Char) := [['-'], ['.']]
def allSeps : List (List Char) := [['-'], ['.'], ['-', '-'], ['-', '_']]

def curShape (x : Config × List Char) : Bool :=
  let o := slugify x.1 x.2
  shapeOK x.1.sep o && o.all (fun c => !c.isUpper)

def fixedShape (x : Config × List Char) : Bool := shapeOK x.1.sep (slugifyFixed x.1 x.2)

/-- Without truncation, no word of the fixed model's output is a stopword, compared
case-insensitively. (Truncation can cut a word down to a stopword; python-slugify's
`smart_truncate` does the same, so that is not claimed.) -/
def fixedStops (x : Config × List Char) : Bool :=
  let isStop := fun (t : List Char) => x.1.stopwords.any (fun s => s.map Char.toLower == t)
  let o := slugifyFixed x.1 x.2
  let ws := split x.1.sep o
  x.1.maxLen != 0 || x.1.sep.isEmpty || o.isEmpty ||
    (if x.1.saveOrder then !(ws.head?.any isStop) && !(ws.getLast?.any isStop)
     else ws.all (fun t => !isStop t))

end Slug

namespace Unique

def texts : List (List Char) := ["ab cd", "ab", "ab-1", "!!!", "x"].map String.toList

/-- Every call sequence of length at most 4 over `texts`. -/
def seqs : List (List (List Char)) :=
  (List.range 5).flatMap (fun n => (List.replicate n texts).foldr
    (fun opts acc => opts.flatMap (fun t => acc.map (t :: ·))) [[]])

def cfgs : List Slug.Config :=
  [['-'], ['-', '-']].flatMap fun sep => (List.range 7).map fun ml =>
    { sep, lowercase := true, maxLen := ml, wordBoundary := false, saveOrder := false,
      stopwords := [] }

def grid : List (Slug.Config × List (List Char)) :=
  seqs.flatMap fun ts => cfgs.map fun cfg => (cfg, ts)

def resEq : Except Err (List Char) → Except Err (List Char) → Bool
  | .ok a, .ok b => a == b
  | .error a, .error b => a == b
  | _, _ => false

def hintSound (x : Slug.Config × List (List Char)) : Bool :=
  let a := run x.1 12 x.2
  let b := runNoHint x.1 12 x.2
  a.length == b.length && (a.zip b).all (fun p => resEq p.1 p.2)

def slugShape (cfg : Slug.Config) : Except Err (List Char) → Bool
  | .ok c => c.isEmpty || (Slug.shapeOK cfg.sep c && (cfg.maxLen == 0 || c.length ≤ cfg.maxLen))
  | .error _ => true

def fixedShape (x : Slug.Config × List (List Char)) : Bool :=
  (runFixed x.1 12 x.2).all (slugShape x.1)

def curShape (x : Slug.Config × List (List Char)) : Bool :=
  (run x.1 12 x.2).all (slugShape x.1)

end Unique

namespace Dist

def pairs : List (List Char × List Char) :=
  (wordsUpTo ['a', 'b', 'c'] 4).flatMap fun a => (wordsUpTo ['a', 'b', 'c'] 4).map fun b => (a, b)

def dpIsLev (x : List Char × List Char) : Bool := dp x.1 x.2 == lev x.1 x.2

end Dist

end Sanitizers
