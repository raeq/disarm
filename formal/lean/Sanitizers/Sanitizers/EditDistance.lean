/-!
# Model of `edit_distance` and `nearest_match`

`dp` is `utils::edit_distance` (`src/utils.rs` L20-34) row for row: `prev` starts as
`0..=b.len()`, and each character of `a` produces the next row. `lev` is the textbook
recursive Levenshtein distance, the specification. `nearest` is `api::nearest_match`
(`src/api/safety.rs` L1392-1415).
-/

namespace Sanitizers.Dist

/-- One row of the DP: `curr[0] = i + 1`, then
`curr[j + 1] = min(prev[j + 1] + 1, curr[j] + 1, prev[j] + cost)`. -/
def row (ca : Char) (b : List Char) (prev : List Nat) (left : Nat) : List Nat :=
  match b, prev with
  | cb :: bs, p0 :: p1 :: ps =>
    let v := min (min (p1 + 1) (left + 1)) (p0 + (if ca == cb then 0 else 1))
    v :: row ca bs (p1 :: ps) v
  | _, _ => []

def dpRows (b : List Char) : List Char → Nat → List Nat → List Nat
  | [], _, prev => prev
  | ca :: as, i, prev => dpRows b as (i + 1) ((i + 1) :: row ca b prev (i + 1))

def dp (a b : List Char) : Nat :=
  (dpRows b a 0 (List.range (b.length + 1))).getLastD 0

/-- The specification. -/
def lev : List Char → List Char → Nat
  | [], b => b.length
  | a, [] => a.length
  | x :: xs, y :: ys =>
    min (min (lev xs (y :: ys) + 1) (lev (x :: xs) ys + 1)) (lev xs ys + (if x == y then 0 else 1))

/-- `nearest_match`: the first candidate at the least distance `≤ maxD`. -/
def nearest (v : List Char) (cands : List (List Char)) (maxD : Nat) : Option (List Char × Nat) :=
  let rec go : List (List Char) → Option (List Char × Nat) → Option (List Char × Nat)
    | [], best => best
    | c :: cs, best =>
      let d := dp v c
      if d > maxD then go cs best
      else
        let best' := match best with
          | none => some (c, d)
          | some (bc, bd) => if d < bd then some (c, d) else some (bc, bd)
        if d == 0 then best' else go cs best'
  go cands none

end Sanitizers.Dist
