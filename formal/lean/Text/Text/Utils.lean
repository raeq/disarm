/-!
# `edit_distance` (`src/utils.rs` L20-34) and `contract` (`src/contraction.rs`)

`ed` is the two-row dynamic programme exactly as written (stream `a`, keep `prev` and
`curr` rows over `b`); `lev` is the textbook recursive definition of Levenshtein distance.
`Bounded.lean` checks they agree and that `ed` is a metric.

`contract` is the leftmost-longest rewrite `aho_corasick` performs with
`MatchKind::LeftmostLongest` over the three rules of `confusables_contractions.tsv`.
-/

namespace Text.Utils

/-- The textbook definition. -/
def lev {α : Type} [DecidableEq α] : List α → List α → Nat
  | [], b => b.length
  | a, [] => a.length
  | x :: xs, y :: ys =>
    min (min (lev xs (y :: ys) + 1) (lev (x :: xs) ys + 1)) (lev xs ys + if x = y then 0 else 1)
termination_by a b => a.length + b.length

/-- One row of the programme: `curr[0] = i + 1`, then
`curr[j+1] = min(prev[j+1] + 1, curr[j] + 1, prev[j] + cost)` (L26-30). -/
def row {α : Type} [DecidableEq α] (ca : α) (i : Nat) (b : List α) (prev : List Nat) : List Nat :=
  let rec go (j : Nat) (left : Nat) (bs : List α) (acc : List Nat) : List Nat :=
    match bs with
    | [] => acc.reverse
    | cb :: bs' =>
      let cost := if ca = cb then 0 else 1
      let v := min (min (prev.getD (j + 1) 0 + 1) (left + 1)) (prev.getD j 0 + cost)
      go (j + 1) v bs' (v :: acc)
  go 0 (i + 1) b [i + 1]

/-- `edit_distance`. -/
def ed {α : Type} [DecidableEq α] (a b : List α) : Nat :=
  let init := (List.range (b.length + 1))
  let (_, last) := a.foldl (fun (st : Nat × List Nat) ca => (st.1 + 1, row ca st.1 b st.2)) (0, init)
  last.getD b.length 0

/-! ## Contraction -/

/-- The rules of `confusables_contractions.tsv`. -/
def rules : List (List Char × Char) :=
  [("rn".toList, 'm'), ("vv".toList, 'w'), ("cl".toList, 'd')]

/-- The longest rule whose source is a prefix of `s`. -/
def longestAt (rs : List (List Char × Char)) (s : List Char) : Option (List Char × Char) :=
  rs.foldl (fun best r =>
    if r.1.isPrefixOf s then
      match best with
      | some b => if r.1.length > b.1.length then some r else best
      | none => some r
    else best) none

/-- Leftmost-longest, non-overlapping replacement (fuel = input length). -/
def contractGo (rs : List (List Char × Char)) : Nat → List Char → List Char
  | 0, s => s
  | _ + 1, [] => []
  | f + 1, c :: s =>
    match longestAt rs (c :: s) with
    | some r => r.2 :: contractGo rs f ((c :: s).drop r.1.length)
    | none => c :: contractGo rs f s

def contract (rs : List (List Char × Char)) (s : List Char) : List Char :=
  contractGo rs (s.length + 1) s

end Text.Utils
