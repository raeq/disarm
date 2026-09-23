import Text.Zalgo
import Text.Width
import Text.Whitespace
import Text.Invisibles
import Text.Punct
import Text.Utils

/-!
Differential-test driver. Reads one case per line on stdin; the first word names the
model and the rest are its tokens. Prints one answer line per case. `scripts/difftest.py`
maps tokens to concrete characters (injective tables there and here) and compares the
answers with the library.

    Z <k> <tok>...      zalgo: isZalgo | strip | isZalgoFixed | stripFixed
    W <amb> <tok>...    width: gw | gwFixed           (one cluster, or any argument)
    S <tok>...          whitespace: collapse | stripControl | stripZeroWidth
    I <tok>...          invisibles: stripTags | stripFormat | stripInv comparison | stripInv rendering | stripCompare
    P <tok>...          fold_punctuation
    E <a> <b>           edit_distance on two words (letters)
    K <word>            contraction
-/

open Text

namespace Drv

def zTok : String → Option Zalgo.Ch
  | "a" => some (.base false 0) | "b" => some (.base false 1) | "e" => some (.base true 0)
  | "A" => some (.mark 230 false 0) | "G" => some (.mark 230 false 1)
  | "U" => some (.mark 220 false 0) | "O" => some (.mark 1 false 0)
  | "N" => some (.mark 1 true 0) | "R" => some (.mark 1 true 1)
  | "T" => some (.mark 0 false 0) | "C" => some (.mark 0 false 1)
  | _ => none

def zShow : Zalgo.Ch → String
  | .base false 0 => "a" | .base false 1 => "b" | .base true 0 => "e"
  | .mark 230 false 0 => "A" | .mark 230 false 1 => "G" | .mark 220 false 0 => "U"
  | .mark 1 false 0 => "O" | .mark 1 true 0 => "N" | .mark 1 true 1 => "R"
  | .mark 0 false 0 => "T" | .mark 0 false 1 => "C"
  | _ => "?"

def sc (ascii : Bool) (cls : Nat) (emo : Bool := false) (sel : Width.Sel := .none)
    (kb : Bool := false) (prep : Bool := false) : Width.Sc :=
  { ascii, cls, emo, sel, kb, prep }

def wTok : String → Option Width.Sc
  | "a" => some (sc true 1) | "1" => some (sc true 1 (kb := true)) | "x" => some (sc true 0)
  | "m" => some (sc false 0) | "p" => some (sc false 0 (prep := true))
  | "r" => some (sc false 1 (prep := true)) | "j" => some (sc false 0)
  | "c" => some (sc false 2) | "q" => some (sc false 3)
  | "E" => some (sc false 2 true) | "F" => some (sc false 0 true) | "I" => some (sc false 1 true)
  | "h" => some (sc false 1)
  | "s" => some (sc false 0 (sel := .vs15)) | "S" => some (sc false 0 (sel := .vs16))
  | "k" => some (sc false 0 (sel := .keycap))
  | _ => none

def sTok : String → Option Whitespace.C
  | "_" => some (.ws 0) | "t" => some (.ws 1) | "n" => some (.ws 2) | "f" => some (.ws 3)
  | "B" => some (.ws 4) | "H" => some (.ws 5) | "L" => some (.ws 6) | "N" => some (.ws 7)
  | "0" => some (.ctl 0) | "D" => some (.ctl 1) | "9" => some (.ctl 2)
  | "z" => some (.zw 0) | "Z" => some (.zw 1) | "M" => some (.zw 2)
  | "a" => some (.ch 0) | "b" => some (.ch 1) | "e" => some (.ch 2)
  | _ => none

def sShow : Whitespace.C → String
  | .ws 0 => "_" | .ws 1 => "t" | .ws 2 => "n" | .ws 3 => "f" | .ws 4 => "B" | .ws 5 => "H"
  | .ws 6 => "L" | .ws 7 => "N" | .ctl 0 => "0" | .ctl 1 => "D" | .ctl 2 => "9"
  | .zw 0 => "z" | .zw 1 => "Z" | .zw 2 => "M" | .ch 0 => "a" | .ch 1 => "b" | .ch 2 => "e"
  | _ => "?"

def iTok (s : String) : Option Invisibles.I :=
  match s.toList with
  | ['a'] => some (.plain 0) | ['b'] => some (.plain 1) | ['F'] => some .flag
  | ['t', c] => some (.tagL c) | ['X'] => some .cancel
  | ['o', '1'] => some (.tagO 0) | ['o', 'A'] => some (.tagO 1) | ['o', '_'] => some (.tagO 2)
  | ['J'] => some .cgj | ['Q'] => some .nonch | ['P'] => some .pua
  | ['v', '1'] => some (.vs 0) | ['v', '1', '7'] => some (.vs 1)
  | ['V', '1', '5'] => some .vs15 | ['V', '1', '6'] => some .vs16
  | ['M'] => some .difmt | ['z'] => some .zw | ['_'] => some (.ws 0) | ['n'] => some (.ws 1)
  | ['B'] => some .blank | ['0'] => some .ctl | ['R'] => some (.bidi 0) | ['Y'] => some (.bidi 1)
  | _ => none

def iShow : Invisibles.I → String
  | .plain 0 => "a" | .plain 1 => "b" | .flag => "F" | .tagL c => "t" ++ c.toString
  | .cancel => "X" | .tagO 0 => "o1" | .tagO 1 => "oA" | .tagO 2 => "o_" | .cgj => "J"
  | .nonch => "Q" | .pua => "P" | .vs 0 => "v1" | .vs 1 => "v17" | .vs15 => "V15"
  | .vs16 => "V16" | .difmt => "M" | .zw => "z" | .ws 0 => "_" | .ws 1 => "n"
  | .blank => "B" | .ctl => "0" | .bidi 0 => "R" | .bidi 1 => "Y" | _ => "?"

def pTok (s : String) : Option Punct.P :=
  match s.toList with
  | 'A' :: n => (String.ofList n).toNat?.map (fun k => .ascii (Char.ofNat k))
  | 'd' :: n => (String.ofList n).toNat?.map .dash
  | 's' :: n => (String.ofList n).toNat?.map .squote
  | 'q' :: n => (String.ofList n).toNat?.map .dquote
  | ['E'] => some .ellipsis
  | 'n' :: n => (String.ofList n).toNat?.map .nsp
  | 'o' :: n => (String.ofList n).toNat?.map .other
  | _ => none

def pShow : Punct.P → String
  | .ascii c => s!"A{c.toNat}" | .dash n => s!"d{n}" | .squote n => s!"s{n}"
  | .dquote n => s!"q{n}" | .ellipsis => "E" | .nsp n => s!"n{n}" | .other n => s!"o{n}"

def sp (l : List String) : String := " ".intercalate l

def b2s (b : Bool) : String := if b then "1" else "0"

def answer (ws : List String) : String :=
  match ws with
  | "Z" :: k :: toks =>
    match k.toNat?, toks.mapM zTok with
    | some k, some t =>
      s!"{b2s (Zalgo.isZalgo k t)} | {sp ((Zalgo.strip k t).map zShow)} | " ++
      s!"{b2s (Zalgo.isZalgoFixed k t)} | {sp ((Zalgo.stripFixed k t).map zShow)}"
    | _, _ => "ERR"
  | "W" :: amb :: toks =>
    match toks.mapM wTok with
    | some t => s!"{Width.gw (amb == "1") t} | {Width.gwFixed (amb == "1") t}"
    | none => "ERR"
  | "S" :: toks =>
    match toks.mapM sTok with
    | some t =>
      s!"{sp ((Whitespace.collapse t).map sShow)} | {sp ((Whitespace.stripControl t).map sShow)} | " ++
      s!"{sp ((Whitespace.stripZeroWidth t).map sShow)}"
    | none => "ERR"
  | "I" :: toks =>
    match toks.mapM iTok with
    | some t =>
      s!"{sp ((Invisibles.stripTags t).map iShow)} | {sp ((Invisibles.stripFormat t).map iShow)} | " ++
      s!"{sp ((Invisibles.stripInv Invisibles.comparison t).map iShow)} | " ++
      s!"{sp ((Invisibles.stripInv Invisibles.rendering t).map iShow)} | " ++
      s!"{sp ((Invisibles.stripCompare t).map iShow)}"
    | none => "ERR"
  | "P" :: toks =>
    match toks.mapM pTok with
    | some t => sp ((Punct.foldPunct t).map pShow)
    | none => "ERR"
  | ["E", a, b] => s!"{Utils.ed (if a == "-" then [] else a.toList) (if b == "-" then [] else b.toList)}"
  | ["K", w] => String.ofList (Utils.contract Utils.rules w.toList)
  | ["K"] => ""
  | _ => "ERR"

end Drv

partial def loop (i o : IO.FS.Stream) : IO Unit := do
  let line ← i.getLine
  if line.isEmpty then return
  let ws := (line.trimAscii.toString.splitOn " ").filter (· ≠ "")
  o.putStrLn (Drv.answer ws)
  loop i o

def main : IO Unit := do
  loop (← IO.getStdin) (← IO.getStdout)
