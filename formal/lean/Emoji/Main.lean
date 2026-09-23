import Emoji

/-! With the argument `fixed`, the modes run the fixed model of `Emoji/Fixes.lean`
instead: the differential test should then DISAGREE with the library exactly on the
finding classes (a sensitivity check for the harness itself). -/

/-! Differential-test driver. Reads one input per line on stdin — code points in hex,
space separated — and prints the model's outputs, each as space-separated hex,
separated by `|`, in the order of `modes` below (scripts/difftest.py). -/

open Emoji

def hexOf (s : List Char) : String :=
  " ".intercalate (s.map fun c => (String.ofList (Nat.toDigits 16 c.toNat)).toUpper)

def parseHex (w : String) : Char :=
  Char.ofNat (w.foldl (fun n d =>
    n * 16 + (if d.isDigit then d.toNat - '0'.toNat
              else d.toLower.toNat - 'a'.toNat + 10)) 0)

/-- The provider the differential test registers (difftest.py `PROVIDER`). -/
def testProvider : Provider := fun seq =>
  if seq == ['1'] then some "ONE"
  else if seq == [Tables.cE] then some "GRIN"
  else if seq == [Tables.cRA] then some "LETTER A"
  else if seq == [Tables.cM, Tables.cT] then some "PALE MAN"
  else none

def modes (fixedModel : Bool) (s : List Char) : List (List Char) :=
  if fixedModel then
    [ replaceFix s [], replaceFix s [' '], replaceFix s ['#'], replaceFix s [],
      demojizeFix .replace "[?]".toList s, demojizeFix .ignore "[?]".toList s,
      demojizeFix .preserve "[?]".toList s, pipelineFix s,
      demojizePy .replace "[?]".toList (some testProvider) s, demojizeFix .replace [] s ]
  else
  [ replaceEmoji s [],
    replaceEmoji s [' '],
    replaceEmoji s ['#'],
    replaceU s [],
    demojizePy .replace "[?]".toList none s,
    demojizePy .ignore "[?]".toList none s,
    demojizePy .preserve "[?]".toList none s,
    pipelineDemojize s,
    demojizePy .replace "[?]".toList (some testProvider) s,
    demojizePy .replace [] none s ]

partial def loop (fixedModel : Bool) (h : IO.FS.Stream) (o : IO.FS.Stream) : IO Unit := do
  let line ← h.getLine
  if line.isEmpty then return
  let ws := (line.trimAscii.toString.splitOn " ").filter (· ≠ "")
  let s := ws.map parseHex
  o.putStrLn ("|".intercalate ((modes fixedModel s).map hexOf))
  loop fixedModel h o

def main (args : List String) : IO Unit := do
  loop (args.contains "fixed") (← IO.getStdin) (← IO.getStdout)
