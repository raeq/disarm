import Presets.Fixes

/-!
Differential-test driver. With the argument `names` it prints the surface names, one per
line: first every surface the model mirrors (`Presets/Surfaces.lean`), then every fixed
variant (`Presets/Fixes.lean`) under the name `fixed:<surface>`. Otherwise it reads one word
per line on stdin, as space-separated hex code points (an empty line is the empty word), and
prints, per word, one line holding every surface's output in that order, separated by
` | `, each output again as hex code points. `scripts/difftest.py` runs the same words
through the library and compares.
-/

open Presets

def hexDigit (c : Char) : Option Nat :=
  if '0' <= c && c <= '9' then some (c.toNat - '0'.toNat)
  else if 'a' <= c && c <= 'f' then some (c.toNat - 'a'.toNat + 10)
  else if 'A' <= c && c <= 'F' then some (c.toNat - 'A'.toNat + 10)
  else none

def parseHex (s : String) : Option Nat :=
  s.toList.foldl (fun acc c => do let a <- acc; let d <- hexDigit c; pure (a * 16 + d)) (some 0)

def showWord (w : Str) : String := " ".intercalate (w.map fun c => String.ofList (Nat.toDigits 16 c))

def all : List (String × (Str -> Str)) :=
  surfaces ++ fixedSurfaces.map fun (n, f) => ("fixed:" ++ n, f)

partial def loop (h : IO.FS.Stream) (o : IO.FS.Stream) : IO Unit := do
  let line <- h.getLine
  if line.isEmpty then return
  let toks := ((line.trimAscii.toString).splitOn " ").filter (· != "")
  match toks.mapM parseHex with
  | none => o.putStrLn "ERR parse"
  | some w => o.putStrLn (" | ".intercalate (all.map fun (_, f) => showWord (f w)))
  loop h o

def main (args : List String) : IO Unit := do
  if args == ["names"] then
    for (n, _) in all do IO.println n
  else
    loop (<- IO.getStdin) (<- IO.getStdout)
