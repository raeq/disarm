/-!
# A statement-by-statement model of `resolve_deletions_into` (src/deletions.rs)

Characters are abstracted into the classes the Rust code distinguishes. Every class but
the four controls carries an identity (`Nat`), so two outputs can be compared character
for character and "which input character is this" is a question the model can answer.

Line numbers in the comments are those of `src/deletions.rs` at the commit this model was
written against (main @ bec93cf).
-/

namespace Deletions

/-- The alphabet, by the branch of the Rust loop each class takes. -/
inductive C where
  /-- `U+0008` BACKSPACE (`BS`, L49). -/
  | bs
  /-- `U+007F` DELETE (`DEL`, L50). -/
  | del
  /-- `U+000D` CARRIAGE RETURN (`CR`, L51). -/
  | cr
  /-- `U+000A` LINE FEED (`LF`, L52). -/
  | lf
  /-- A UAX #14 mandatory break other than `CR`/`LF` — `VT`, `FF`, `NEL`, `LS`, `PS`.
  `anomalies::is_line_break` treats these as line starts; `resolve_deletions_into` does
  not, and `occupies_cell` answers `true` for them, so in the model of the current code
  they behave exactly like `v`. They are a separate class only so that the *fixed* model
  (`stepFixed` below) can treat them differently. -/
  | brk (i : Nat)
  /-- A character for which `occupies_cell` is `true` (L40): a letter, a rendering `Cf`
  such as `U+0605`, a `TAB`, any other control. -/
  | v (i : Nat)
  /-- A character for which `occupies_cell` is `false`: a combining mark, a zero-width
  character, a variation selector, a default-ignorable format character, a tag, a bidi
  control (L41-46). -/
  | z (i : Nat)
  deriving DecidableEq, Repr, Inhabited

/-- `occupies_cell` (L40-47), on the abstract alphabet. The Rust function also answers
`true` for `BS`, `DEL`, `CR`, `LF`; the loop consumes those before it asks (L88, L114,
L123), so the model's answer for them is never consulted. -/
def occupiesCell : C → Bool
  | .z _ => false
  | _ => true

/-- A cell: a base character plus whatever attaches to it (L28, L73). `[]` is a blank. -/
abbrev Cell := List C

/-- The loop state: `out` (the `&mut String`), `line` (L76), `col` (L77), `lead` (L84),
`occupied` (L85). -/
structure St where
  out : List C := []
  line : List Cell := []
  col : Nat := 0
  lead : List C := []
  occ : Nat := 0
  deriving DecidableEq, Repr, Inhabited

/-- The line-ending test of L114:
`ch == LF || (ch == CR && (!cr || chars.peek().is_none_or(|&n| n == LF)))`.
`next` is `chars.peek()`. -/
def endsLine (cr : Bool) (ch : C) (next : Option C) : Bool :=
  ch == .lf || (ch == .cr && (!cr || next.all (· == .lf)))

/-- One iteration of the `while let Some(ch) = chars.next()` loop (L87-155). -/
def step (cr : Bool) (s : St) (ch : C) (next : Option C) : St :=
  if ch == .bs || ch == .del then                                      -- L88
    if s.col > 0 then                                                  -- L101
      let c := s.col - 1                                               -- L102
      -- L109-111: `if !line[col].is_empty() { occupied -= 1; }`
      let occ := if (s.line.getD c []).isEmpty then s.occ else s.occ - 1
      { s with col := c, occ := occ, line := s.line.set c [] }         -- L112 `clear()`
    else s                                                             -- col == 0: nothing
  else if endsLine cr ch next then                                     -- L114
    { out := s.out ++ s.lead ++ s.line.flatten ++ [ch]                 -- L115, L117-119, L120
      lead := []                                                       -- L116
      line := []                                                       -- L117 `drain(..)`
      col := 0                                                         -- L121
      occ := 0 }                                                       -- L122
  else if ch == .cr then                                               -- L123
    { s with col := 0 }                                                -- L125
  else if !occupiesCell ch && s.col > 0 then                           -- L126
    -- L127-129: `if line[col - 1].is_empty() { occupied += 1; }`
    { s with occ := if (s.line.getD (s.col - 1) []).isEmpty then s.occ + 1 else s.occ
             line := s.line.modify (s.col - 1) (· ++ [ch]) }           -- L130
  else if !occupiesCell ch && s.occ > 0 then                           -- L131
    { s with lead := s.lead ++ [ch] }                                  -- L143
  else if s.col < s.line.length then                                   -- L144
    -- L145-147: `if line[col].is_empty() { occupied += 1; }`
    { s with occ := if (s.line.getD s.col []).isEmpty then s.occ + 1 else s.occ
             line := s.line.set s.col [ch]                             -- L148
             col := s.col + 1 }                                        -- L149
  else
    { s with line := s.line ++ [[ch]]                                  -- L151
             occ := s.occ + 1                                          -- L152
             col := s.col + 1 }                                        -- L153

/-- The loop (L86-155). `rest.head?` is `chars.peek()`. -/
def run (cr : Bool) : St → List C → St
  | s, [] => s
  | s, ch :: rest => run cr (step cr s ch rest.head?) rest

/-- The tail after the loop (L156-159): the pending `lead`, then the line's cells. -/
def finish (s : St) : List C := s.out ++ s.lead ++ s.line.flatten

/-- The early return of L68: nothing to do unless an erasing control is present. -/
def needsScan (cr : Bool) (t : List C) : Bool :=
  t.any (fun c => c == .bs || c == .del || (cr && c == .cr))

/-- `resolve_deletions_into` itself: `some out` for `true` (changed), `none` for `false`
(L68-70, L165). -/
def resolveInto (cr : Bool) (t : List C) : Option (List C) :=
  if !needsScan cr t then none
  else
    let o := finish (run cr {} t)
    if o != t then some o else none

/-- What a caller sees: on `false` it keeps its input (L56-57; `pipeline.rs` L619-624,
the `resolve` helper in the Rust tests L172-179). -/
def resolve (cr : Bool) (t : List C) : List C := (resolveInto cr t).getD t

/-! ## The proposed fix, modelled for comparison

Two changes, each one line in the Rust:

1. L131: `!occupies_cell(ch) && col == 0` instead of `&& occupied > 0`. A character that
   takes no cell never takes one, at column 0 of an empty or blank line included.
2. L114: every UAX #14 mandatory break ends the line, as `anomalies::is_line_break`
   already says, not only `LF`.
-/

def endsLineFixed (cr : Bool) (ch : C) (next : Option C) : Bool :=
  match ch with
  | .brk _ => true
  | _ => endsLine cr ch next

def stepFixed (cr : Bool) (s : St) (ch : C) (next : Option C) : St :=
  if ch == .bs || ch == .del then
    if s.col > 0 then
      let c := s.col - 1
      let occ := if (s.line.getD c []).isEmpty then s.occ else s.occ - 1
      { s with col := c, occ := occ, line := s.line.set c [] }
    else s
  else if endsLineFixed cr ch next then                                -- fix 2
    { out := s.out ++ s.lead ++ s.line.flatten ++ [ch]
      lead := [], line := [], col := 0, occ := 0 }
  else if ch == .cr then
    { s with col := 0 }
  else if !occupiesCell ch && s.col > 0 then
    { s with occ := if (s.line.getD (s.col - 1) []).isEmpty then s.occ + 1 else s.occ
             line := s.line.modify (s.col - 1) (· ++ [ch]) }
  else if !occupiesCell ch then                                        -- fix 1 (col == 0)
    { s with lead := s.lead ++ [ch] }
  else if s.col < s.line.length then
    { s with occ := if (s.line.getD s.col []).isEmpty then s.occ + 1 else s.occ
             line := s.line.set s.col [ch]
             col := s.col + 1 }
  else
    { s with line := s.line ++ [[ch]], occ := s.occ + 1, col := s.col + 1 }

def runFixed (cr : Bool) : St → List C → St
  | s, [] => s
  | s, ch :: rest => runFixed cr (stepFixed cr s ch rest.head?) rest

def resolveFixed (cr : Bool) (t : List C) : List C :=
  if !needsScan cr t then t else finish (runFixed cr {} t)

/-! ## Vocabulary for the properties -/

/-- The characters a reader sees drawn: everything but the four controls and the
no-cell class. -/
def visible : C → Bool
  | .v _ => true
  | .brk _ => true
  | _ => false

/-- The input with every no-cell character removed. -/
def dropZ (t : List C) : List C := t.filter (fun c => occupiesCell c)

/-- No `CR` at all. -/
def noCR (t : List C) : Bool := !t.contains .cr

/-- The shape an output must have to be a fixed point: no `BS`/`DEL`, and under `cr`
every `CR` is followed by `LF` or ends the text. -/
def Clean (cr : Bool) : List C → Bool
  | [] => true
  | c :: r => c != .bs && c != .del && (!cr || c != .cr || r.head?.all (· == .lf)) && Clean cr r

/-- The simpler no-`CR` algorithm the docs describe: a stack of cells. An erase pops the
top cell; a no-cell character joins the top cell, or starts one when there is none;
`LF` (and `CR`, which without the flag is a line ending) flushes. The stack is held top
first, so the line reads as `stack.reverse`. -/
structure SSt where
  out : List C := []
  stack : List Cell := []
  deriving DecidableEq, Repr

def simpleStep (s : SSt) (ch : C) : SSt :=
  if ch == .bs || ch == .del then { s with stack := s.stack.tail }
  else if ch == .lf || ch == .cr then { out := s.out ++ s.stack.reverse.flatten ++ [ch], stack := [] }
  else if !occupiesCell ch then
    match s.stack with
    | top :: rest => { s with stack := (top ++ [ch]) :: rest }
    | [] => { s with stack := [[ch]] }
  else { s with stack := [ch] :: s.stack }

def simpleRun : SSt → List C → SSt
  | s, [] => s
  | s, ch :: rest => simpleRun (simpleStep s ch) rest

def simple (t : List C) : List C :=
  let s := simpleRun {} t
  s.out ++ s.stack.reverse.flatten

end Deletions
