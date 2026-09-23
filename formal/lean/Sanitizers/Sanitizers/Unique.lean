import Sanitizers.Slug

/-!
# Model of `UniqueSlugifier` (`src/py/slugify.rs` L268-486)

`_UniqueSlugifier::slugify` without a `check` callback (the path the per-base hint is
used on), over the ASCII slug model. `seen` and `next_counter` are association lists.
`MAX_UNIQUE_ATTEMPTS` is a parameter (`src/limits.rs` L30 sets it to 10,000) so the
bounded checks can use a small one.
-/

namespace Sanitizers.Unique

open Sanitizers.Slug

/-- Decimal digits of `n`, as `format!("{counter}")`. -/
def digits (n : Nat) : List Char := (toString n).toList

/-- `build_unique_candidate` (L295-327), ASCII: `floor_char_boundary` is the identity.
Returns the candidate and the `lossy` flag. -/
def candidate (sep base : List Char) (maxLen counter : Nat) : List Char × Bool :=
  if counter == 0 then (base, false)
  else
    let suffix := sep ++ digits counter
    let c := base ++ suffix
    if maxLen > 0 && c.length > maxLen then
      if suffix.length ≥ maxLen then (suffix.take maxLen, maxLen < suffix.length)
      else (base.take (maxLen - suffix.length) ++ suffix, false)
    else (c, false)

inductive Err where
  | maxLengthTooSmall
  | attemptsExceeded
  deriving DecidableEq, Repr

instance : DecidableEq (Except Err (List Char)) := fun a b =>
  match a, b with
  | .ok x, .ok y =>
    if h : x = y then isTrue (h ▸ rfl) else isFalse (by intro e; cases e; exact h rfl)
  | .error x, .error y =>
    if h : x = y then isTrue (h ▸ rfl) else isFalse (by intro e; cases e; exact h rfl)
  | .ok _, .error _ => isFalse (by intro e; cases e)
  | .error _, .ok _ => isFalse (by intro e; cases e)

structure St where
  seen : List (List Char)
  hint : List (List Char × Nat)
  deriving Repr

def St.empty : St := ⟨[], []⟩

def hintOf (h : List (List Char × Nat)) (b : List Char) : Nat :=
  match h.find? (fun p => p.1 == b) with
  | some p => p.2
  | none => 0

def setHint (h : List (List Char × Nat)) (b : List Char) (n : Nat) : List (List Char × Nat) :=
  (b, n) :: h.filter (fun p => p.1 != b)

/-- The L416-479 loop from `counter`, with `fuel` steps left. Returns the counter that
was consumed and the candidate, or the error. -/
def walk (sep base : List Char) (maxLen maxAttempts : Nat) (seen : List (List Char)) :
    Nat → Nat → Bool → Except Err (Nat × List Char)
  | 0, _, _ => .error .attemptsExceeded
  | fuel + 1, counter, sawLossy =>
    if counter > maxAttempts then
      .error (if sawLossy then .maxLengthTooSmall else .attemptsExceeded)
    else if counter ≥ 1 && maxLen > 0 && maxLen < sep.length + 1 then
      .error .maxLengthTooSmall
    else
      let (cand, lossy) := candidate sep base maxLen counter
      if !seen.contains cand then .ok (counter, cand)
      else walk sep base maxLen maxAttempts seen fuel (counter + 1) (sawLossy || lossy)

/-- One call: `slugify` then the walk from the hint. -/
def step (cfg : Config) (maxAttempts : Nat) (st : St) (text : List Char) :
    Except Err (List Char) × St :=
  let base := slugify cfg text
  let h := hintOf st.hint base
  match walk cfg.sep base cfg.maxLen maxAttempts st.seen (maxAttempts + 2) h false with
  | .ok (k, c) => (.ok c, ⟨c :: st.seen, setHint st.hint base (k + 1)⟩)
  | .error e => (.error e, st)

/-- The same call without the hint: the walk always starts at counter 0. This is the
path taken when `check` is set (L404-409, `use_hint`), and what the hint claims to be equivalent to. -/
def stepNoHint (cfg : Config) (maxAttempts : Nat) (st : St) (text : List Char) :
    Except Err (List Char) × St :=
  let base := slugify cfg text
  match walk cfg.sep base cfg.maxLen maxAttempts st.seen (maxAttempts + 2) 0 false with
  | .ok (k, c) => (.ok c, ⟨c :: st.seen, setHint st.hint base (k + 1)⟩)
  | .error e => (.error e, st)

def runAll (step : St → List Char → Except Err (List Char) × St) :
    St → List (List Char) → List (Except Err (List Char))
  | _, [] => []
  | st, t :: ts =>
    let (r, st') := step st t
    r :: runAll step st' ts

def run (cfg : Config) (maxAttempts : Nat) (ts : List (List Char)) : List (Except Err (List Char)) :=
  runAll (step cfg maxAttempts) St.empty ts

def runNoHint (cfg : Config) (maxAttempts : Nat) (ts : List (List Char)) :
    List (Except Err (List Char)) :=
  runAll (stepNoHint cfg maxAttempts) St.empty ts

/-! ## The proposed fix (Finding 9)

A suffixed candidate is built from the base the way the slug itself is truncated: the
head is cut, then stripped of a trailing separator prefix (so `ab-` + `-1` cannot give
`ab--1`), and a candidate is never the suffix alone. When the budget leaves no room for
at least one base character, the call fails with `UniqueSlugMaxLengthTooSmall` instead of
returning `-1`; `min_unique_len` becomes `sep.len() + 2`. An empty base is not suffixed at
all: the empty slug is returned as the (documented) empty result every time, as
`slugify` does, rather than becoming `-1`, `-2`, ... . -/

def candidateFixed (sep base : List Char) (maxLen counter : Nat) : Option (List Char) :=
  if counter == 0 then some base
  else if base.isEmpty then none
  else
    let suffix := sep ++ digits counter
    let c := base ++ suffix
    if maxLen > 0 && c.length > maxLen then
      if suffix.length + 1 > maxLen then none
      else
        let head := stripPartial sep (base.take (maxLen - suffix.length))
        if head.isEmpty then none else some (head ++ suffix)
    else some c

def walkFixed (sep base : List Char) (maxLen maxAttempts : Nat) (seen : List (List Char)) :
    Nat → Nat → Except Err (Nat × List Char)
  | 0, _ => .error .attemptsExceeded
  | fuel + 1, counter =>
    if counter > maxAttempts then .error .attemptsExceeded
    else
      match candidateFixed sep base maxLen counter with
      | none => if counter == 0 then .ok (0, base) else .error .maxLengthTooSmall
      | some cand =>
        if base.isEmpty then .ok (0, base)
        else if !seen.contains cand then .ok (counter, cand)
        else walkFixed sep base maxLen maxAttempts seen fuel (counter + 1)

def stepFixed (cfg : Config) (maxAttempts : Nat) (st : St) (text : List Char) :
    Except Err (List Char) × St :=
  -- the base is the fixed slug (Finding 5), so it does not end in a partial separator
  let base := slugifyFixed cfg text
  let h := hintOf st.hint base
  match walkFixed cfg.sep base cfg.maxLen maxAttempts st.seen (maxAttempts + 2) h with
  | .ok (k, c) =>
    if c.isEmpty then (.ok c, st) else (.ok c, ⟨c :: st.seen, setHint st.hint base (k + 1)⟩)
  | .error e => (.error e, st)

def runFixed (cfg : Config) (maxAttempts : Nat) (ts : List (List Char)) :
    List (Except Err (List Char)) :=
  runAll (stepFixed cfg maxAttempts) St.empty ts

end Sanitizers.Unique
