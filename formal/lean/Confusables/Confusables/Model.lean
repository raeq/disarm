import Confusables.Tables

/-!
# The model

A literal transcription of the confusable fold and its neighbours, over real `Char`s,
reading the projected tables of `Tables.lean`. Every definition names the Rust item and
the line numbers it transcribes (at the commit in `README.md`).

Strings are `List Char`. A Rust `Cow::Borrowed` is `none` and `Cow::Owned s` is `some s`
where the distinction matters (`foldPass`).

What is **not** modelled, and why that is sound for the alphabet:
* conjoining Hangul jamo (`compose.rs:127-149`, `try_compose_hangul`): no jamo is in the
  domain (the generator asserts it), so `try_compose_hangul` always returns `None`;
* `ResolveDeletions`, `StripBidi`, `StripInvisible`, `StripZeroWidth` in `skeleton_key`:
  each is the identity on a string with no BS/DEL, bidi, invisible or zero-width
  character, and the domain has none;
* byte offsets in `find_confusables` / `find_unmapped_confusables`: the model returns the
  characters and targets; offsets are checked on the library directly (`search/`).
-/

namespace Confusables
open Tables

/-! ## Unicode normalization (`unicode-normalization` 0.1.25) -/

/-- Insert a non-starter into a run already sorted by combining class, after every
element of equal class (the canonical ordering is a *stable* sort). -/
def insertByCcc (c : Char) : List Char → List Char
  | [] => [c]
  | x :: xs => if ccc c < ccc x then c :: x :: xs else x :: insertByCcc c xs

/-- Canonical ordering (`decompose.rs`: the buffer of non-starters is sorted by ccc). -/
def reorderAux : List Char → List Char → List Char
  | run, [] => run
  | run, c :: t => if ccc c == 0 then run ++ c :: reorderAux [] t else reorderAux (insertByCcc c run) t

def reorder (s : List Char) : List Char := reorderAux [] s

/-- `Recompositions::next` (`recompose.rs:67-156`), state for state: the pending
`composee`, the `buffer` of characters blocked from it, and `last_ccc`. -/
def recompose : Option Char → List Char → Option Nat → List Char → List Char
  | none, _, _, [] => []
  | some k, buf, _, [] => k :: buf
  | none, _, _, ch :: t =>
    if ccc ch != 0 then ch :: recompose none [] none t else recompose (some ch) [] none t
  | some k, buf, none, ch :: t =>
    match composePair k ch with
    | some r => recompose (some r) buf none t
    | none =>
      if ccc ch == 0 then k :: buf ++ recompose (some ch) [] none t
      else recompose (some k) (buf ++ [ch]) (some (ccc ch)) t
  | some k, buf, some l, ch :: t =>
    if l ≥ ccc ch then
      if ccc ch == 0 then k :: buf ++ recompose (some ch) [] none t
      else recompose (some k) (buf ++ [ch]) (some (ccc ch)) t
    else
      match composePair k ch with
      | some r => recompose (some r) buf (some l) t
      | none => recompose (some k) (buf ++ [ch]) (some (ccc ch)) t

def nfd (s : List Char) : List Char := reorder (s.flatMap canonDecomp)
def nfkd (s : List Char) : List Char := reorder (s.flatMap compatDecomp)
def nfc (s : List Char) : List Char := recompose none [] none (nfd s)
def nfkc (s : List Char) : List Char := recompose none [] none (nfkd s)

/-! ## `compose.rs`: compose-at-lookup -/

/-- `could_compose` (compose.rs:87-93): a combining mark or a conjoining Hangul L jamo. -/
def couldCompose (c : Char) : Bool :=
  isMark c || (0x1100 ≤ c.toNat && c.toNat ≤ 0x1112)

/-- `needs_composition` (compose.rs:71-73). -/
def needsComposition (s : List Char) : Bool := s.any couldCompose

def excludedLookup (k : List Char) : Option Char :=
  (excludedCompositions.find? (fun e => e.1 == k)).map (·.2)

/-- `excluded_prefix` (compose.rs:254-268): the longest widening-map key of at least two
characters that is a prefix of `s`. -/
def excludedPrefix (s : List Char) : Option (Char × Nat) :=
  let hits := excludedCompositions.filter (fun e => e.1.length ≥ 2 && e.1.isPrefixOf s)
  hits.foldl (fun best e => match best with
    | some (_, n) => if e.1.length > n then some (e.2, e.1.length) else best
    | none => some (e.2, e.1.length)) none

/-- The greedy loop of `recompose_excluded` (compose.rs:235-246). -/
def recomposeGreedy : Nat → List Char → List Char
  | 0, s => s
  | _ + 1, [] => []
  | fuel + 1, c :: t =>
    match excludedPrefix (c :: t) with
    | some (p, n) => p :: recomposeGreedy fuel ((c :: t).drop n)
    | none => c :: recomposeGreedy fuel t

/-- `recompose_excluded` (compose.rs:229-247). -/
def recomposeExcluded (nfcCluster : List Char) : List Char :=
  match excludedLookup nfcCluster with
  | some p => [p]
  | none => recomposeGreedy nfcCluster.length nfcCluster

theorem dropWhile_length_le (f : Char → Bool) : ∀ (l : List Char), (l.dropWhile f).length ≤ l.length
  | [] => by simp
  | a :: l => by
    simp only [List.dropWhile]
    cases f a
    · simp
    · have := dropWhile_length_le f l; simp; omega

/-- `Composed::next` (compose.rs:155-209): a character followed by a combining mark
anchors a cluster (it and the whole run of marks after it), which is NFC-composed and
passed through the widening map; any other character is yielded verbatim. -/
def composed : List Char → List Char
  | [] => []
  | [c] => [c]
  | c :: m :: t =>
    if isMark m then
      recomposeExcluded (nfc (c :: (m :: t).takeWhile isMark)) ++ composed ((m :: t).dropWhile isMark)
    else c :: composed (m :: t)
termination_by s => s.length
decreasing_by
  all_goals simp_wf
  all_goals first
    | omega
    | (have := dropWhile_length_le isMark (m :: t); simp only [List.length_cons] at *; omega)

/-! ## `confusables.rs`: the fold -/

inductive Policy where
  | numeric | tr39 | preserve
  deriving DecidableEq, Repr, BEq

/-- The single ASCII digit test of `lookup_with_policy` (confusables.rs:141):
`hit.len() == 1 && hit.as_bytes()[0].is_ascii_digit()`. -/
def isDigitValue : List Char → Bool
  | [d] => '0' ≤ d && d ≤ '9'
  | _ => false

/-- `lookup_with_policy` (confusables.rs:129-145), Latin target.
`tr39Digits` is `digit_policy == "tr39" && target_script == "latin"` (confusables.rs:216). -/
def lookup (p : Policy) (c : Char) : Option (List Char) :=
  let over := if p == .tr39 then tr39Override c else none
  match over with
  | some o => some o
  | none =>
    match latinMap c with
    | none => none
    | some hit => if p == .preserve && isDigitValue hit then none else some hit

def foldChar (p : Policy) (c : Char) : List Char := (lookup p c).getD [c]

def isAsciiStr (s : List Char) : Bool := s.all (·.toNat < 0x80)

/-- `normalize_confusables_cow` (confusables.rs:203-257): `none` is `Cow::Borrowed`. The
compose branch (230-239) always returns `Owned`, even when nothing folded. -/
def foldPass (p : Policy) (s : List Char) : Option (List Char) :=
  if !isAsciiStr s && needsComposition s then
    some ((composed s).flatMap (foldChar p))
  else if s.any (fun c => (lookup p c).isSome) then
    some (s.flatMap (foldChar p))
  else none

/-- `MAX_CONFUSABLE_PASSES` (confusables.rs:60). -/
def maxPasses : Nat := 8

/-- The loop of `normalize_confusables_fixed_cow` (confusables.rs:291-304). The `Bool` is
whether it left through a stability exit (`true`) or ran out of passes (`false`,
the `debug_assert!(false)` arm). -/
def fixedLoop (p : Policy) : Nat → List Char → List Char × Bool
  | 0, cur => (cur, false)
  | n + 1, cur =>
    match foldPass p cur with
    | none => (cur, true)
    | some next => if next == cur then (cur, true) else fixedLoop p n next

/-- `normalize_confusables_fixed_cow` (confusables.rs:281-305) with the Bool of `fixedLoop`. -/
def fixedFoldB (p : Policy) (s : List Char) : List Char × Bool :=
  match foldPass p s with
  | none => (s, true)
  | some cur => fixedLoop p maxPasses cur

/-- `normalize_confusables(text, "latin", policy)`: the public fold every binding calls. -/
def fixedFold (p : Policy) (s : List Char) : List Char := (fixedFoldB p s).1

/-- `skipped_by_detection` (confusables.rs:33-35): printable ASCII. -/
def asciiGraphic (c : Char) : Bool := 0x21 ≤ c.toNat && c.toNat ≤ 0x7E

/-- `is_confusable` (confusables.rs:480-497). -/
def isConfusable (s : List Char) : Bool :=
  (composed s).any (fun c => !asciiGraphic c && (latinMap c).isSome)

/-- `find_confusables` (confusables.rs:413-435) with no allowed scripts, offsets dropped. -/
def findConfusables (s : List Char) : List (Char × List Char) :=
  (composed s).filterMap (fun c =>
    if asciiGraphic c then none else (latinMap c).map (fun t => (c, t)))

/-- `find_unmapped_confusables` (confusables.rs:374-394), offsets dropped. -/
def findUnmapped (s : List Char) : List Char :=
  (composed s).filter (fun c => (latinMap c).isNone && upstreamSource c)

/-- `normalize_confusables_into` (confusables.rs:309-342): per character, NO composition.
This is the form `Step::ConfusablesCtx` runs inside the presets. -/
def foldInto (p : Policy) (s : List Char) : List Char := s.flatMap (foldChar p)

/-! ## `presets.rs`: `skeleton_key` -/

/-- `prototype_fold_into` (confusables.rs:922-943). -/
def prototypeFold (p : Policy) (s : List Char) : List Char :=
  s.map fun c =>
    if c == 'I' then 'l'
    else if p == .tr39 && c == '1' then 'l'
    else if p == .tr39 && c == '0' then 'O'
    else c

/-- `fold_case_into` (case_fold.rs:75-100): per character. -/
def foldCase (s : List Char) : List Char := s.flatMap caseFold

/-- `strip_control_chars_into` (whitespace.rs:117-126). -/
def stripControl (s : List Char) : List Char := s.filter (fun c => !isControl c || isFoldWs c)

/-- `collapse_whitespace_into` (whitespace.rs:33-58). -/
def collapseWs (s : List Char) : List Char :=
  let rec go : List Char → Bool → Bool → List Char
    | [], _, _ => []
    | c :: t, prevSpace, seen =>
      if isFoldWs c then
        if seen && !prevSpace then ' ' :: go t true seen else go t prevSpace seen
      else c :: go t false true
  let r := go s false false
  if r.getLast? == some ' ' then r.dropLast else r

/-- `CONFUSABLE_FIXED_POINT_ITERS` (presets.rs:28). -/
def fpIters : Nat := 8

/-- `Step::FixedPoint` (presets.rs:443-462) over an inner pass `f`. -/
def fixedPoint (f : List Char → List Char) : Nat → List Char → List Char
  | 0, cur => cur
  | n + 1, cur => let next := f cur; if next == cur then cur else fixedPoint f n next

/-- skeleton_key's step list (presets.rs:2066-2107), steps 1-6, with the identity steps
(see the module doc) left out. -/
def skeletonSteps (p : Policy) (s : List Char) : List Char :=
  let s := nfkc s                                                  -- 1. Nfkc
  let s := foldInto p s                                            -- 3. ConfusablesCtx
  let s := prototypeFold p s                                       -- 4. PrototypeFold
  let s := fixedPoint (fun x => foldInto p (foldCase x)) fpIters s -- 5. FixedPoint
  let s := stripControl s                                          -- 6. StripControl
  collapseWs s                                                     --    CollapseWs

inductive Guard where
  | inert | wsOnly | actionable
  deriving DecidableEq, Repr, BEq

/-- `classify` (presets.rs:829-891) under skeleton_key's mask. -/
def classify (s : List Char) : Guard :=
  let rec go : List Char → Bool → Bool → Bool → Guard
    | [], _, sawWs, _ => if sawWs then .wsOnly else .inert
    | c :: t, prevSpace, sawWs, first =>
      let n := c.toNat
      if n < 0x80 then
        if (n < 0x20 && !(0x09 ≤ n && n ≤ 0x0D) && !(0x1C ≤ n && n ≤ 0x1F)) || n == 0x7F then .actionable
        else if 0x41 ≤ n && n ≤ 0x5A then .actionable
        else if n == 0x22 || n == 0x60 || n == 0x7C then .actionable
        else if c == 'I' || c == '0' || c == '1' then .actionable
        else if (0x09 ≤ n && n ≤ 0x0D) || (0x1C ≤ n && n ≤ 0x1F) then go t false true false
        else if n == 0x20 then
          go t true (sawWs || first || t.isEmpty || prevSpace) false
        else go t false sawWs false
      else if guardNonAscii c then .actionable
      else go t false sawWs false
  go s false false true

/-- `skeleton_key` (presets.rs:2061-2118) through `run_static` (presets.rs:950-982): the
#458 guard runs under the default policy only. -/
def skeletonKey (p : Policy) (s : List Char) : List Char :=
  if p == .numeric then
    match classify s with
    | .inert => s
    | .wsOnly => collapseWs s
    | .actionable => skeletonSteps p s
  else skeletonSteps p s

/-! ## `collisions.rs` -/

/-- `find_key_collisions` (collisions.rs:71-125) over any reducer: groups of
`(key, distinct values, indices)` in first-appearance order, singletons dropped. -/
def findKeyCollisions (reduce : List Char → List Char) (values : List (List Char)) :
    List (List Char × List (List Char) × List Nat) :=
  let step := fun (acc : List (List Char × List (List Char) × List Nat) × List (List Char))
      (iv : Nat × List Char) =>
    let (groups, seen) := acc
    let (i, v) := iv
    let k := reduce v
    let first := !seen.contains v
    let seen := if first then seen ++ [v] else seen
    match groups.findIdx? (fun g => g.1 == k) with
    | some j =>
      (groups.modify j (fun g => (g.1, (if first then g.2.1 ++ [v] else g.2.1), g.2.2 ++ [i])), seen)
    | none => (groups ++ [(k, [v], [i])], seen)
  let (groups, _) := (values.zipIdx.map (fun (v, i) => (i, v))).foldl step ([], [])
  groups.filter (fun g => g.2.1.length > 1)

end Confusables
