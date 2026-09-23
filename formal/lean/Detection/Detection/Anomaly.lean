/-!
# A model of `has_anomalies` (`src/anomalies.rs`)

The alphabet is split by the branches `classify` takes. Every class is one concrete code
point in the differential test (`scripts/difftest.py`, table `ANOMALY`), so the model is
compared with the library character for character.

| Class | Concrete | What the code sees |
|---|---|---|
| `a`   | `e`       | ASCII letter, Latin, strong L |
| `p`   | `U+00E9`  | Latin letter, alphabetic, **not** ASCII; NFD is `a m` |
| `m`   | `U+0301`  | combining mark, class 230, not alphabetic, Inherited |
| `h`   | `U+05D0`  | Hebrew letter, alphabetic, strong R |
| `d`   | `1`       | ASCII digit |
| `sp`  | space     | token boundary |
| `zw`  | `U+200B`  | `is_invisible_in_word`, not a joiner, zero-width carrier |
| `nj`  | `U+200C`  | `is_invisible_in_word`, a joiner, zero-width carrier |
| `fmt` | `U+206A`  | deprecated format control: none of the detector's predicates |
| `shy` | `U+00AD`  | soft hyphen: zero-width *run* carrier only |
| `vs`  | `U+FE01`  | variation selector carrier (run floor 2) |
| `tag` | `U+E0061` | tag carrier (run floor 1) |
| `pua` | `U+E000`  | Private Use Area carrier (run floor 4) |
| `rlo` | `U+202E`  | bidi override |
| `rli` | `U+2067`  | bidi isolate |
| `rlm` | `U+200F`  | right-to-left mark |
| `lrm` | `U+200E`  | left-to-right mark |
| `cr`, `lf` | `CR`, `LF` | line breaks, token boundaries |
| `bel` | `U+0007`  | non-whitespace control |

With an empty lexicon (the default, `lexicon=None`), the `leet` and `segmentation`
branches cannot fire: both end in a lexicon lookup. On this alphabet `mixed_numbers`,
`enclosing_mark`, `compat_fold` and `confusable` never fire either (no second digit
system, no `Me` mark, and no class folds to ASCII); the differential test is what
establishes that, not an argument.
-/

namespace Detection

inductive C where
  | a | p | m | h | d | sp | zw | nj | fmt | shy | vs | tag | pua | rlo | rli | rlm | lrm | cr | lf | bel
  deriving DecidableEq, Repr, Inhabited

namespace C

def all : List C :=
  [a, p, m, h, d, sp, zw, nj, fmt, shy, vs, tag, pua, rlo, rli, rlm, lrm, cr, lf, bel]

/-- `char::is_ascii`. -/
def isAscii : C → Bool
  | a | d | sp | cr | lf | bel => true
  | _ => false

/-- `char::is_alphabetic`. -/
def alpha : C → Bool
  | a | p | h => true
  | _ => false

/-- `char::is_ascii_alphabetic`. -/
def asciiAlpha : C → Bool
  | a => true
  | _ => false

/-- `is_invisible_in_word` (L47-55): zero-width, fillers, the twelve default-ignorable `Cf`. -/
def invisibleInWord : C → Bool
  | zw | nj => true
  | _ => false

/-- `c == '\u{200C}' || c == '\u{200D}'` (L1193). -/
def joiner : C → Bool
  | nj => true
  | _ => false

/-- `is_token_boundary` (L1523-1525). -/
def boundary : C → Bool
  | sp | cr | lf => true
  | _ => false

/-- `is_line_break` (L627-632), restricted to the alphabet. -/
def lineBreak : C → Bool
  | cr | lf => true
  | _ => false

/-- `c.is_control() && !is_fold_whitespace(c)` (L1154-1156). -/
def control : C → Bool
  | bel => true
  | _ => false

/-- A letter with strong direction L / R (`has_bidi_letter_conflict`). -/
def ltrLetter : C → Bool
  | a | p => true
  | _ => false

def rtlLetter : C → Bool
  | h => true
  | _ => false

end C

open C

/-! ## The carrier-run rule (`Carrier`, L91-125; `carrier_run`, L1091-1123) -/

inductive Carrier where
  | tag | vs | zw | pua
  deriving DecidableEq, Repr

def carrierOf : C → Option Carrier
  | .tag => some .tag
  | .vs => some .vs
  | .zw | .nj | .shy => some .zw
  | .pua => some .pua
  | _ => none

def Carrier.threshold : Carrier → Nat
  | .tag => 1
  | .vs => 2
  | .zw => 8
  | .pua => 4

/-- Closing a run of class `cur` and length `n`: does it reach its floor? -/
def closes : Option Carrier → Nat → Bool
  | none, _ => false
  | some k, n => decide (k.threshold ≤ n)

/-- `carrier_run`: some maximal run of one class reaches that class's threshold. -/
def runAux : Option Carrier → Nat → List C → Bool
  | cur, n, [] => closes cur n
  | cur, n, c :: rest =>
    match carrierOf c with
    | none => closes cur n || runAux none 0 rest
    | some k =>
      if cur = some k then runAux cur (n + 1) rest
      else closes cur n || runAux (some k) 1 rest

def carrierRun (t : List C) : Bool := runAux none 0 t

/-! ## The neighbour rule (L1186-1215) -/

/-- `pre` is the part of the token before position `i`, reversed; `c :: post` starts at `i`. -/
def neighbourAux : List C → List C → Bool
  | _, [] => false
  | pre, c :: post =>
    (c.invisibleInWord &&
      (if c.joiner then pre.any asciiAlpha && post.any asciiAlpha
       else pre.any alpha || post.any alpha))
    || neighbourAux (c :: pre) post

def neighbour (t : List C) : Bool := neighbourAux [] t

/-! ## The bidi rules (L1225-1253) -/

/-- `is_majority_latin` (L711-724): counts **ASCII** letters, not Latin ones. -/
def majLatin (t : List C) : Bool :=
  let letters := t.countP alpha
  let ascii := t.countP (fun c => c.alpha && c.isAscii)
  letters != 0 && decide (letters ≤ 2 * ascii)

def noLetters (t : List C) : Bool := !t.any alpha

/-- L1247-1251: the **first** RTL mark in the token, and whether a digit follows it. -/
def firstRlmBeforeDigit (t : List C) : Bool :=
  match t.dropWhile (· != .rlm) with
  | .rlm :: .d :: _ => true
  | _ => false

def bidiRule (t : List C) : Bool :=
  t.any (· == .rlo) ||
  ((majLatin t || noLetters t) && (t.any (· == .rli) || firstRlmBeforeDigit t))

/-! ## Marks and scripts -/

/-- NFD on this alphabet: only `p` decomposes. -/
def nfdChar : C → List C
  | .p => [.a, .m]
  | c => [c]

def nfd (t : List C) : List C := t.flatMap nfdChar

/-- Two copies of the one stacking mark, adjacent in NFD (`duplicate_stacking_mark`,
L851-866). With a single mark class this also covers every `is_zalgo` hit, which needs
four marks of one class in a row. -/
def adjMM : List C → Bool
  | .m :: .m :: _ => true
  | _ :: rest => adjMM rest
  | [] => false

def dupMark (t : List C) : Bool := adjMM (nfd t)

/-- `has_bidi_letter_conflict` on the (single) word part, and the Latin-plus-other rule. -/
def mixed (t : List C) : Bool := t.any ltrLetter && t.any rtlLetter

/-- `classify` (L1125-1504), as a verdict. -/
def classify (t : List C) : Bool :=
  t.any control ||
  (!t.all isAscii &&
    (neighbour t || carrierRun t || bidiRule t || dupMark t || mixed t))

/-! ## Text level -/

/-- `split_tokens` (L1567-1583). `cur` is the token in progress, reversed. -/
def flush (cur : List C) : List (List C) := if cur.isEmpty then [] else [cur.reverse]

def splitAux : List C → List C → List (List C)
  | cur, [] => flush cur
  | cur, c :: rest =>
    if c.boundary then flush cur ++ splitAux [] rest else splitAux (c :: cur) rest

def splitTokens (t : List C) : List (List C) := splitAux [] t

/-- `overwriting_cr` (L665-680). `seen`: a character since the last line break. -/
def crAux : Bool → List C → Bool
  | _, [] => false
  | seen, c :: rest =>
    if c = .cr then
      (seen && (match rest with
                | [] => false
                | n :: _ => n != .lf))
      || crAux false rest
    else if c.lineBreak then crAux false rest
    else crAux true rest

def overwritingCR (t : List C) : Bool := crAux false t

/-- `has_anomalies` with an empty lexicon. The `decoded_payloads` disjunct is omitted: on
this alphabet every decoding run is also a carrier run over its floor (a tag run always,
a zero-width run only from 8 bits up, and `U+FE01` bytes are never printable), which the
differential test confirms. -/
def hasAnomalies (t : List C) : Bool :=
  overwritingCR t || (splitTokens t).any classify

/-! ## The cleaners, restricted to the alphabet -/

/-- What `canonicalize` deletes from inside a word (`strip_format`'s classes, the
zero-width strip, the control strip), measured on the library by
`scripts/sweep_cleaners.py`. -/
def canonDeletes : C → Bool
  | .zw | .nj | .fmt | .shy | .vs | .tag | .pua | .rlo | .rli | .rlm | .lrm | .bel => true
  | _ => false

/-- The deletions the detector documents as deliberate: the soft hyphen (a run carrier
only), a lone variation selector, a lone Private Use Area code point, `LRM`, and `RLM`
outside a number run (`docs/user-guide/anomaly-detection.md`, the "Spared" column). -/
def documentedSpare : C → Bool
  | .shy | .vs | .pua | .lrm | .rlm => true
  | _ => false

/-! ## Proposed fixes -/

/-- Finding 3's fix: evaluate the token's ASCII tests on its NFD, as `duplicate_mark`
already does. The simplest form is to classify the NFD. -/
def hasAnomaliesNfd (t : List C) : Bool := hasAnomalies (nfd t)

/-- Finding 2's fix: any RTL mark directly before a digit, not only the first one. -/
def anyRlmBeforeDigit : List C → Bool
  | .rlm :: .d :: _ => true
  | _ :: rest => anyRlmBeforeDigit rest
  | [] => false

def bidiRuleFixed (t : List C) : Bool :=
  t.any (· == .rlo) ||
  ((majLatin t || noLetters t) && (t.any (· == .rli) || anyRlmBeforeDigit t))

/-- Finding 1's fix: `fmt` joins `is_invisible_in_word`. -/
def invisibleInWordFixed : C → Bool
  | .zw | .nj | .fmt => true
  | _ => false

def neighbourAuxFixed : List C → List C → Bool
  | _, [] => false
  | pre, c :: post =>
    (invisibleInWordFixed c &&
      (if c.joiner then pre.any asciiAlpha && post.any asciiAlpha
       else pre.any alpha || post.any alpha))
    || neighbourAuxFixed (c :: pre) post

def classifyFixed (t : List C) : Bool :=
  t.any control ||
  (!t.all isAscii &&
    (neighbourAuxFixed [] t || carrierRun t || bidiRuleFixed t || dupMark t || mixed t))

/-- All three fixes together. -/
def hasAnomaliesFixed (t : List C) : Bool :=
  let u := nfd t
  overwritingCR u || (splitTokens u).any classifyFixed

end Detection
