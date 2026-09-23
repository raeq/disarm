import Deletions.Model

/-!
Differential-test driver. Reads one case per line on stdin:

    <flag> <tok> <tok> ...

where `<flag>` is `0` (`cr = false`) or `1` (`cr = true`) and each token is `B` (BS),
`D` (DEL), `R` (CR), `L` (LF), `v<n>`, `z<n>` or `n<n>` (a `brk`). Prints, per case, the
model's output of `resolve` and of `resolveFixed`, as tokens, separated by ` | `.
`scripts/difftest.py` maps both sides to concrete characters and compares with the real
library.
-/

open Deletions

def parseTok (s : String) : Option C :=
  match s.toList with
  | ['B'] => some .bs
  | ['D'] => some .del
  | ['R'] => some .cr
  | ['L'] => some .lf
  | 'v' :: n => (String.ofList n).toNat?.map C.v
  | 'z' :: n => (String.ofList n).toNat?.map C.z
  | 'n' :: n => (String.ofList n).toNat?.map C.brk
  | _ => none

def showTok : C → String
  | .bs => "B"
  | .del => "D"
  | .cr => "R"
  | .lf => "L"
  | .v n => s!"v{n}"
  | .z n => s!"z{n}"
  | .brk n => s!"n{n}"

def showList (l : List C) : String := " ".intercalate (l.map showTok)

partial def loop (h : IO.FS.Stream) (o : IO.FS.Stream) : IO Unit := do
  let line ← h.getLine
  if line.isEmpty then return
  let ws := (line.trimAscii.toString.splitOn " ").filter (· ≠ "")
  match ws with
  | [] => o.putStrLn "ERR empty"
  | f :: toks =>
    let cr := f == "1"
    match toks.mapM parseTok with
    | none => o.putStrLn "ERR parse"
    | some t =>
      o.putStrLn s!"{showList (resolve cr t)} | {showList (resolveFixed cr t)}"
  loop h o

def main : IO Unit := do
  let i ← IO.getStdin
  let o ← IO.getStdout
  loop i o
