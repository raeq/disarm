import Confusables

/-! Differential-test driver (`lake exe confmodel`). Reads one input per line on stdin —
code points in hex, space separated — and prints the model's outputs, separated by `|`,
in the order of `modes` below (scripts/difftest.py holds the matching list). A string
output is space-separated hex; a `Bool` is `0`/`1`; a `find_confusables` hit is
`C=T.T`, the source then its target's code points.

With the argument `fixed`, the three `skeleton_key` modes run the proposed fix
(`Confusables/Fixes.lean`) instead: the harness should then DISAGREE with the library,
and only on the finding classes. -/

open Confusables

def hex (c : Char) : String := (String.ofList (Nat.toDigits 16 c.toNat)).toUpper

def hexOf (s : List Char) : String := " ".intercalate (s.map hex)

def parseHex (w : String) : Char :=
  Char.ofNat (w.foldl (fun n d =>
    n * 16 + (if d.isDigit then d.toNat - '0'.toNat
              else d.toLower.toNat - 'a'.toNat + 10)) 0)

def showFind (l : List (Char × List Char)) : String :=
  " ".intercalate (l.map fun (c, t) => hex c ++ "=" ++ ".".intercalate (t.map hex))

def modes (fixed : Bool) (s : List Char) : List String :=
  let sk := fun p => if fixed then Fixes.skeletonKeyFixed p s else skeletonKey p s
  [ hexOf (fixedFold .numeric s),
    hexOf (fixedFold .tr39 s),
    hexOf (fixedFold .preserve s),
    if isConfusable s then "1" else "0",
    showFind (findConfusables s),
    hexOf (findUnmapped s),
    hexOf (sk .numeric),
    hexOf (sk .tr39),
    hexOf (sk .preserve),
    hexOf (nfc s),
    hexOf (nfd s),
    hexOf (nfkc s),
    hexOf (foldCase s) ]

partial def loop (fixed : Bool) (h : IO.FS.Stream) (o : IO.FS.Stream) : IO Unit := do
  let line ← h.getLine
  if line.isEmpty then return
  let ws := (line.trimAscii.toString.splitOn " ").filter (· ≠ "")
  let s := ws.map parseHex
  o.putStrLn ("|".intercalate (modes fixed s))
  loop fixed h o

def main (args : List String) : IO Unit := do
  loop (args.contains "fixed") (← IO.getStdin) (← IO.getStdout)
