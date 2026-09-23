/-!
# `is_zalgo` / `strip_zalgo` (`src/zalgo.rs`)

The alphabet is split by the branches the two functions take. A scalar is either a
non-mark (`base`) or a combining mark (`mark`, General_Category `M*`, which is what
`unicode_normalization::char::is_combining_mark` answers) carrying its canonical combining
class. `neg` marks `U+0338` / `U+20D2`, the two negation overlays `is_negation_of` knows;
`sym` marks a base that `is_negation_of` accepts them on (a non-alphanumeric that survives
the pipeline, such as `=`).

Both functions walk `text.nfd()`. The characters used in the differential test do not
decompose, so NFD is only the **canonical reordering** (`canon`): each maximal run of
marks with a non-zero class is stably sorted by class. A class-0 mark is a starter for
canonical ordering, which is the whole of Finding Z1.

The library returns NFC; the differential test maps that back through NFD before comparing
with the model, whose outputs are canonically ordered and decomposed.
-/

namespace Text.Zalgo

inductive Ch where
  /-- A non-mark. `sym`: a base a negation overlay may sit on (`=`), not a letter. -/
  | base (sym : Bool) (id : Nat)
  /-- A combining mark with canonical combining class `ccc`. `neg`: `U+0338`/`U+20D2`. -/
  | mark (ccc : Nat) (neg : Bool) (id : Nat)
  deriving DecidableEq, Repr, Inhabited

def ccc : Ch → Nat
  | .base .. => 0
  | .mark c .. => c

def isMark : Ch → Bool
  | .mark .. => true
  | .base .. => false

/-! ## NFD, as canonical reordering -/

/-- Insert `x` after every element whose class is `≤` its own: repeated from the left,
this is a stable sort by class. -/
def insertCcc (x : Ch) : List Ch → List Ch
  | [] => [x]
  | y :: ys => if ccc y ≤ ccc x then y :: insertCcc x ys else x :: y :: ys

def sortRun (run : List Ch) : List Ch := run.foldl (fun acc x => insertCcc x acc) []

/-- Canonical reordering: `run` is the pending run of non-starters, in input order. -/
def canonAux (run : List Ch) : List Ch → List Ch
  | [] => sortRun run
  | c :: cs => if ccc c == 0 then sortRun run ++ c :: canonAux [] cs
               else canonAux (run ++ [c]) cs

def canon (s : List Ch) : List Ch := canonAux [] s

/-! ## `exceeds_combining_run` (L53-91) and `is_zalgo` (L102-108) -/

/-- The loop body of `exceeds_combining_run`, over the NFD stream. -/
def exceedsGo (k : Nat) : Nat → Nat → List Ch → Bool
  | _, _, [] => false
  | _, _, .base .. :: cs => exceedsGo k 0 0 cs                      -- L85-88
  | run, prev, .mark cl _ _ :: cs =>
    if cl == 0 && k > 0 then exceedsGo k 0 0 cs                          -- L75-79
    else
      let r := if cl == prev then run + 1 else 1                         -- L80
      if r > k then true else exceedsGo k r cl cs                        -- L82-84

def isZalgo (k : Nat) (s : List Ch) : Bool := exceedsGo k 0 0 (canon s)

/-! ## `strip_zalgo_into` (L196-279) -/

structure SSt where
  out : List Ch := []
  cnt : Nat := 0
  cls : Nat := 0
  base : Option Ch := none
  negKept : Bool := false
  deriving Repr

/-- `transliterate::is_negation_of`: a negation overlay on a `sym` base. -/
def isNegationOf (m : Ch) (b : Option Ch) : Bool :=
  match m, b with
  | .mark _ true _, some (.base true _) => true
  | _, _ => false

def stripStep (k : Nat) (st : SSt) (c : Ch) : SSt :=
  if isNegationOf c st.base && !st.negKept then                          -- L227-241
    { st with out := st.out ++ [c], negKept := true }
  else match c with
  | .mark cl _ _ =>
    if cl == 0 && k > 0 then                                             -- L252-255
      { st with cnt := 0, cls := 0, out := st.out ++ [c] }
    else
      let n := if cl == st.cls then st.cnt + 1 else 1                    -- L257-261
      { st with cnt := n, cls := cl, out := if n ≤ k then st.out ++ [c] else st.out }
  | .base .. =>                                                          -- L268-273
    { out := st.out ++ [c], cnt := 0, cls := 0, base := some c, negKept := false }

/-- The filtering pass (L213-275), over the NFD stream. -/
def stripSlow (k : Nat) (s : List Ch) : List Ch :=
  ((canon s).foldl (stripStep k) {}).out

/-- `strip_zalgo`, output in NFD: the fast path (L208-211) when the predicate is false. -/
def strip (k : Nat) (s : List Ch) : List Ch :=
  if isZalgo k s then stripSlow k s else canon s

/-! ## Specification: marks at one position

"Caps the number of combining marks per base character at `max_marks`" (Python
docstring), refined by #842 to "`max_marks` bounds the marks at ONE POSITION"
(`tests/test_zalgo_cap.py`): the marks of one non-zero class on one base. `perBase`
counts, for each base, the marks of each class (all classes when `k = 0`), exempting the
first negation overlay on a `sym` base, which both the cap and #749 treat as part of the
symbol. -/

/-- `(class, count)` table update. -/
def bump (cl : Nat) : List (Nat × Nat) → List (Nat × Nat)
  | [] => [(cl, 1)]
  | (c, n) :: t => if c == cl then (c, n + 1) :: t else (c, n) :: bump cl t

def lookup (cl : Nat) : List (Nat × Nat) → Nat
  | [] => 0
  | (c, n) :: t => if c == cl then n else lookup cl t

structure PSt where
  tbl : List (Nat × Nat) := []
  base : Option Ch := none
  negKept : Bool := false
  worst : Nat := 0
  deriving Repr

/-- Is this mark counted towards the cap at threshold `k`? -/
def counted (k : Nat) (cl : Nat) : Bool := cl != 0 || k == 0

def perBaseStep (k : Nat) (st : PSt) (c : Ch) : PSt :=
  if isNegationOf c st.base && !st.negKept then { st with negKept := true }
  else match c with
  | .mark cl _ _ =>
    if counted k cl then
      let t := bump cl st.tbl
      { st with tbl := t, worst := max st.worst (lookup cl t) }
    else st
  | .base .. => { st with tbl := [], base := some c, negKept := false }

/-- The largest number of marks of one class on one base (`canon` makes no difference to
it, but the library's input is NFD, so it is taken there). -/
def worstPosition (k : Nat) (s : List Ch) : Nat := ((canon s).foldl (perBaseStep k) {}).worst

/-- The documented cap: no position carries more than `k` marks. -/
def capOK (k : Nat) (s : List Ch) : Bool := worstPosition k s ≤ k

/-! ## The fix as proposed (Findings Z1, Z2)

Count per base and per class, and do not reset on a class-0 mark; exempt the first
negation overlay in the detector exactly as the stripper does. The two functions then
read one table, so they cannot disagree. -/

def isZalgoFixed (k : Nat) (s : List Ch) : Bool := worstPosition k s > k

structure FSt where
  out : List Ch := []
  tbl : List (Nat × Nat) := []
  base : Option Ch := none
  negKept : Bool := false
  deriving Repr

def stripFixedStep (k : Nat) (st : FSt) (c : Ch) : FSt :=
  if isNegationOf c st.base && !st.negKept then
    { st with out := st.out ++ [c], negKept := true }
  else match c with
  | .mark cl _ _ =>
    if counted k cl then
      let t := bump cl st.tbl
      { st with tbl := t, out := if lookup cl t ≤ k then st.out ++ [c] else st.out }
    else { st with out := st.out ++ [c] }
  | .base .. => { out := st.out ++ [c], tbl := [], base := some c, negKept := false }

def stripFixed (k : Nat) (s : List Ch) : List Ch :=
  if isZalgoFixed k s then ((canon s).foldl (stripFixedStep k) {}).out else canon s

/-! ## Small helpers used by the proofs and the checks -/

/-- The input has no class-0 mark. On such input the fix changes nothing. -/
def noClass0Mark (s : List Ch) : Bool := s.all fun c => !(isMark c && ccc c == 0)

/-- The marks of a word, in order. -/
def marks (s : List Ch) : List Ch := s.filter isMark

end Text.Zalgo
