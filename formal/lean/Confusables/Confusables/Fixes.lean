import Confusables.Model

/-!
# The proposed fixes, applied to a copy of the model

* **F1 / F2** (`skeleton_key` is not idempotent): the fixed point folds case, folds
  confusables and then **re-normalizes** (NFKC), so a decomposed sequence that either
  fold emits is composed and folded again inside the loop rather than on the caller's
  next call; and `StripControl` moves ahead of the first fold, so a removed control can
  no longer join a base to a mark after the last fold has run.
* **F3** (the #458 guard): a starter that composes with the starter before it (Kirat Rai
  `U+16D63`, `U+16D67`, Unicode 16) declines the fast path, as conjoining jamo already do.
-/

namespace Confusables.Fixes
open Confusables Tables

def skeletonStepsFixed (p : Policy) (s : List Char) : List Char :=
  let s := nfkc s
  let s := stripControl s                                                  -- moved up
  let s := foldInto p s
  let s := prototypeFold p s
  let s := fixedPoint (fun x => nfkc (foldInto p (foldCase x))) fpIters s  -- + NFKC
  collapseWs s

/-- Only the first half of the fix (NFKC inside the fixed point): shows the second half
is needed. -/
def skeletonStepsNfkcOnly (p : Policy) (s : List Char) : List Char :=
  let s := nfkc s
  let s := foldInto p s
  let s := prototypeFold p s
  let s := fixedPoint (fun x => nfkc (foldInto p (foldCase x))) fpIters s
  let s := stripControl s
  collapseWs s

/-- Only the second half (StripControl moved ahead of the folds). -/
def skeletonStepsStripOnly (p : Policy) (s : List Char) : List Char :=
  let s := nfkc s
  let s := stripControl s
  let s := foldInto p s
  let s := prototypeFold p s
  let s := fixedPoint (fun x => foldInto p (foldCase x)) fpIters s
  collapseWs s

/-- The guard with the Kirat Rai starters added to the jamo exception (presets.rs:780). -/
def classifyFixed (s : List Char) : Guard :=
  if s.any (fun c => c.toNat == 0x16D63 || c.toNat == 0x16D67) then .actionable else classify s

def skeletonKeyFixed (p : Policy) (s : List Char) : List Char :=
  if p == .numeric then
    match classifyFixed s with
    | .inert => s
    | .wsOnly => collapseWs s
    | .actionable => skeletonStepsFixed p s
  else skeletonStepsFixed p s

end Confusables.Fixes
