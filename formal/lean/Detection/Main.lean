import Detection.Anomaly
import Detection.Smuggled
import Detection.Scripts

/-!
Differential-test driver. Reads one case per line on stdin, and prints one answer line.

    A <c> <c> ...   -> "<hasAnomalies> <hasAnomaliesFixed>"   (0/1 each)
    S <s> <s> ...   -> the decoded payloads, `;`-separated: "<scheme> <start> <units> <b> <b> ..."
    M <k> <k> ...   -> "<isMixed>"                            (0/1)

`scripts/difftest.py` maps the abstract classes to concrete characters and compares with
the library.
-/

open Detection

def parseC : String → Option C
  | "a" => some .a | "p" => some .p | "m" => some .m | "h" => some .h | "d" => some .d
  | "sp" => some .sp | "zw" => some .zw | "nj" => some .nj | "fmt" => some .fmt
  | "shy" => some .shy | "vs" => some .vs | "tag" => some .tag | "pua" => some .pua
  | "rlo" => some .rlo | "rli" => some .rli | "rlm" => some .rlm | "lrm" => some .lrm
  | "cr" => some .cr | "lf" => some .lf | "bel" => some .bel
  | _ => none

/-- `z0 z1 zs x flag cancel v<n> t<n>` -/
def parseS (s : String) : Option S :=
  match s with
  | "z0" => some .z0 | "z1" => some .z1 | "zs" => some .zs | "x" => some .x
  | "flag" => some .flag | "cancel" => some .cancel
  | _ =>
    match s.toList with
    | 'v' :: n => (String.ofList n).toNat?.map S.vsb
    | 't' :: n => (String.ofList n).toNat?.map S.tagb
    | _ => none

def parseK : String → Option Sc
  | "common" => some .common | "inherited" => some .inherited | "latin" => some .latin
  | "greek" => some .greek | "cyrillic" => some .cyrillic | "hebrew" => some .hebrew
  | "han" => some .han | "hira" => some .hira | "kana" => some .kana | "hang" => some .hang
  | "bopo" => some .bopo | "deva" => some .deva | "beng" => some .beng
  | _ => none

def b2s (b : Bool) : String := if b then "1" else "0"

def showScheme : Scheme → String
  | .tagAscii => "tag_ascii"
  | .variationBytes => "variation_bytes"
  | .zeroWidthBinary => "zero_width_binary"

def showPayload (p : Payload) : String :=
  s!"{showScheme p.scheme} {p.start} {p.units}" ++
    String.join (p.bytes.map (fun b => s!" {b}"))

def answer (line : String) : String :=
  let ws := (line.trimAscii.toString.splitOn " ").filter (· ≠ "")
  match ws with
  | "A" :: toks =>
    match toks.mapM parseC with
    | some t => s!"{b2s (hasAnomalies t)} {b2s (hasAnomaliesFixed t)}"
    | none => "ERR parse"
  | "S" :: toks =>
    match toks.mapM parseS with
    | some t => "; ".intercalate ((decode t).map showPayload)
    | none => "ERR parse"
  | "M" :: toks =>
    match toks.mapM parseK with
    | some t => b2s (isMixed t)
    | none => "ERR parse"
  | _ => "ERR empty"

partial def loop (h : IO.FS.Stream) (o : IO.FS.Stream) : IO Unit := do
  let line ← h.getLine
  if line.isEmpty then return
  o.putStrLn (answer line)
  loop h o

def main : IO Unit := do
  let i ← IO.getStdin
  let o ← IO.getStdout
  loop i o
