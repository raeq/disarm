import Sanitizers.Enumerate

/-!
`lake exe explore`: for each bounded check, the number of grid cases that fail its
predicate and the first one. Every check `Bounded.lean` proves prints `0`; the checks it
does not prove (the current model's failures) print their first counterexample.
-/

open Sanitizers

def str (l : List Char) : String := (repr (String.ofList l)).pretty

def report {α : Type} (name : String) (xs : List α) (p : α → Bool) (show_ : α → String) : IO Unit := do
  let bad := xs.filter (fun x => !p x)
  IO.println s!"{name}: {bad.length} of {xs.length} fail"
  match bad.head? with
  | some x => IO.println s!"    first: {show_ x}"
  | none => pure ()

def showF (c : Filename.Case) : String :=
  s!"text={str c.w} sep={str c.sep} max_length={c.ml} platform={repr c.p} preserve={c.pe} -> current {str (Filename.cur c)}, fixed {str (Filename.fixed c)}, fixed again {str (Filename.sanitizeFixed (Filename.fixed c) c.sep c.ml c.p c.pe)}"

def showS (x : Slug.Config × List Char) : String :=
  s!"text={str x.2} sep={str x.1.sep} max_length={x.1.maxLen} wb={x.1.wordBoundary} so={x.1.saveOrder} stop={x.1.stopwords.map str} -> current {str (Slug.slugify x.1 x.2)}, fixed {str (Slug.slugifyFixed x.1 x.2)}"

def showRes : Except Unique.Err (List Char) → String
  | .ok c => str c
  | .error e => (repr e).pretty

def showU (x : Slug.Config × List (List Char)) : String :=
  s!"texts={x.2.map str} sep={str x.1.sep} max_length={x.1.maxLen} -> current {(Unique.run x.1 12 x.2).map showRes}, no hint {(Unique.runNoHint x.1 12 x.2).map showRes}, fixed {(Unique.runFixed x.1 12 x.2).map showRes}"

def main (args : List String) : IO Unit := do
  let n := (args.head? >>= String.toNat?).getD 5
  let fg := Filename.grid n
  report "filename fixed P1-P8" fg Filename.fixedSafe showF
  report "filename fixed P9" fg Filename.fixedIdem showF
  report "filename current P1-P8 (sep _, no truncation, stem non-empty)" fg Filename.curSafeDefault showF
  report "filename current P1-P8" fg (fun c => Filename.outOK c (Filename.cur c)) showF
  report "filename current P9" fg Filename.curIdem showF
  report "filename current P9, max_length = 0" fg (fun c => c.ml != 0 || Filename.curIdem c) showF
  report "filename fixed P9, max_length = 0" fg Filename.fixedIdemNoTrunc showF
  if args.length > 1 then return
  let sg1 := Slug.grid n Slug.singleSeps
  let sg := Slug.grid n Slug.allSeps
  report "slug current S2 (one-char separators)" sg1 Slug.curShape showS
  report "slug current S2 (all separators)" sg Slug.curShape showS
  report "slug fixed S2" sg Slug.fixedShape showS
  report "slug fixed stopwords" sg Slug.fixedStops showS
  report "unique hint sound" Unique.grid Unique.hintSound showU
  report "unique current S2/S3" Unique.grid Unique.curShape showU
  report "unique fixed S2/S3" Unique.grid Unique.fixedShape showU
  report "dp = lev" Dist.pairs Dist.dpIsLev (fun x => s!"{str x.1} {str x.2}")
