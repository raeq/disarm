import Confusables.Props

/-! Counterexample search (`lake exe cex N`): for every property in the suite, prints
`ok` or the shortest failing string of length at most `N` over the alphabet, with what
the model computes on it. -/

open Confusables

def hexOf (s : List Char) : String :=
  " ".intercalate (s.map fun c => (String.ofList (Nat.toDigits 16 c.toNat)).toUpper)

def suite : List (String × (List Char → Bool)) :=
  let pols : List (String × Policy) := [("numeric", .numeric), ("tr39", .tr39), ("preserve", .preserve)]
  (pols.flatMap fun (n, p) =>
    [ ("fold_idempotent/" ++ n, pFoldIdem p),
      ("fold_converges/" ++ n, pFoldConverges p),
      ("fold_complete/" ++ n, pFoldComplete p),
      ("fold_nfc_eq_nfd/" ++ n, pFoldNf p),
      ("sk_idempotent/" ++ n, pSkIdem skeletonKey p),
      ("sk_nfc_eq_nfd/" ++ n, pSkNf skeletonKey p),
      ("sk_lowercase/" ++ n, pSkLower skeletonKey p),
      ("sk_not_confusable/" ++ n, pSkNotConfusable skeletonKey p),
      ("FIXED sk_idempotent/" ++ n, pSkIdem Fixes.skeletonKeyFixed p),
      ("FIXED sk_nfc_eq_nfd/" ++ n, pSkNf Fixes.skeletonKeyFixed p),
      ("FIXED sk_lowercase/" ++ n, pSkLower Fixes.skeletonKeyFixed p),
      ("FIXED sk_not_confusable/" ++ n, pSkNotConfusable Fixes.skeletonKeyFixed p) ]) ++
  [ ("HALF-FIX nfkc-in-loop only: sk_idempotent (tr39)", pSkIdem (fun p => Fixes.skeletonStepsNfkcOnly p) .tr39),
    ("HALF-FIX strip-control-first only: sk_idempotent (tr39)", pSkIdem (fun p => Fixes.skeletonStepsStripOnly p) .tr39),
    ("detect_nfc_eq_nfd", pDetectNf),
    ("detect_eq_find", pDetectFind),
    ("detect_implies_fold_changes", pDetectChanges),
    ("tr39_differs_only_on_override_rows", pTr39Scope),
    ("preserve_differs_only_on_digit_rows", pPreserveScope),
    ("find_unmapped_sound", pUnmappedSound),
    ("sk_guard_is_optimisation", pSkGuard),
    ("FIXED sk_guard_is_optimisation", pSkGuardFixed) ]

def main (args : List String) : IO Unit := do
  let n := (args.head? >>= String.toNat?).getD 3
  let filt := args.drop 1
  for (name, p) in suite do
    if !filt.isEmpty && !filt.any (fun f => (name.splitOn f).length > 1) then continue
    match firstFailure n p with
    | none => IO.println s!"ok     {name}"
    | some s =>
      IO.println s!"FAILS  {name}  [{hexOf s}]  fold={hexOf (fixedFold .numeric s)}  sk={hexOf (skeletonKey .numeric s)}  sk(sk)={hexOf (skeletonKey .numeric (skeletonKey .numeric s))}"
