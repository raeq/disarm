import Deletions.Model

/-!
# Vocabulary for the bounded checks and the findings
-/

namespace Deletions

/-- `anomalies::is_line_break` (src/anomalies.rs L627-632): every UAX #14 mandatory
break. -/
def isLineBreak : C → Bool
  | .lf => true
  | .cr => true
  | .brk _ => true
  | _ => false

/-- `anomalies::overwriting_cr` (src/anomalies.rs L665-679), as a Boolean: is there a `CR`
followed by something other than `LF`, with text between it and the start of its line?
`atStart` is `i == line_start`. -/
def detGo : Bool → List C → Bool
  | _, [] => false
  | atStart, c :: r =>
    (c == .cr && r.head?.any (· != .lf) && !atStart) || detGo (isLineBreak c) r

/-- The `deletion` detector's `CR` rule fires on `t`. -/
def detectsCR (t : List C) : Bool := detGo true t

/-- The characters the Rust test `an_erase_costs_at_most_one_cell` counts as text cells:
`occupies_cell(c) && !matches!(c, BS | DEL | CR | LF)`. -/
def textCell : C → Bool
  | .v _ => true
  | .brk _ => true
  | _ => false

/-- What a reader sees drawn: the text cells, and the `LF`s between lines. `CR` is left
out: whether one survives is a line-ending question the other theorems settle, and here
the question is only which *text* is on screen. -/
def seen (t : List C) : List C := t.filter (fun c => textCell c || c == .lf)

def countCells (t : List C) : Nat := (t.filter textCell).length

def hasErase (t : List C) : Bool := t.any (fun c => c == .bs || c == .del)

/-- Every word over `alpha` of length exactly `n`. -/
def words (alpha : List C) : Nat → List (List C)
  | 0 => [[]]
  | n + 1 => (words alpha n).flatMap (fun w => alpha.map (fun c => c :: w))

/-- Every word over `alpha` of length at most `n`. -/
def wordsUpTo (alpha : List C) (n : Nat) : List (List C) :=
  (List.range (n + 1)).flatMap (words alpha)

/-- The bounded-check alphabet: every class, two distinct cell characters so overwrites
and erases are observable, one no-cell character, one non-`LF` mandatory break. -/
def alpha : List C := [.bs, .del, .cr, .lf, .v 0, .v 1, .z 0, .brk 0]

/-- Readable test vectors: a `String` in the concrete alphabet the differential test
uses, mapped onto the abstract one. -/
def enc (s : String) : List C :=
  s.toList.map fun ch =>
    if ch = '\x08' then .bs
    else if ch = '\x7f' then .del
    else if ch = '\r' then .cr
    else if ch = '\n' then .lf
    else if ch = '\x0b' ∨ ch = '\x0c' ∨ ch = '\u0085' ∨ ch = '\u2028' ∨ ch = '\u2029' then
      .brk ch.toNat
    else if ch = '\u200b' ∨ ch = '\u0301' ∨ ch = '\u200d' ∨ ch = '\u2060' then .z ch.toNat
    else .v ch.toNat

end Deletions
