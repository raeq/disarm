import Sanitizers

/-!
Differential-test driver. Reads one case per line on stdin, fields separated by TAB.
Strings are encoded as `.`-separated decimal code points (the empty string is empty), and
lists of strings as `,`-separated encoded strings, so no escaping is needed in either
direction.

    F <text> <sep> <maxLen> <u|w|p> <0|1 preserve>            sanitize_filename
    S <text> <sep> <maxLen> <wb> <saveOrder> <lower> <stops>  slugify (ASCII path)
    U <sep> <maxLen> <wb> <saveOrder> <lower> <stops> <texts> UniqueSlugifier, one instance
    L <text> <replacement> <0|1 keepTab>                      strip_log_injection
    H <text>                                                  escape_html
    P <path|segment|query|form> <text>                        percent_encode
    D <a> <b>                                                 edit_distance

Prints, per case, `<model output>` TAB `<second output>`: the fixed model's output where
there is one (F, S, U), the specification's where there is one (D: `lev`), and the model
output again otherwise. For U the outputs are `,`-joined, an error as `#M`
(`UniqueSlugMaxLengthTooSmall`) or `#A` (`UniqueSlugAttemptsExceeded`).
-/

open Sanitizers

def decodeStr (s : String) : Option (List Char) :=
  if s.isEmpty then some []
  else (s.splitOn ".").mapM (fun t => t.toNat?.map Char.ofNat)

def encodeStr (l : List Char) : String :=
  ".".intercalate (l.map (fun c => toString c.toNat))

def decodeList (s : String) : Option (List (List Char)) :=
  if s.isEmpty then some [] else (s.splitOn ",").mapM decodeStr

def platformOf : String → Option Filename.Platform
  | "u" => some .universal
  | "w" => some .windows
  | "p" => some .posix
  | _ => none

def componentOf : String → Option Enc.Component
  | "path" => some .path
  | "segment" => some .segment
  | "query" => some .query
  | "form" => some .form
  | _ => none

def encodeRes : Except Unique.Err (List Char) → String
  | .ok c => encodeStr c
  | .error .maxLengthTooSmall => "#M"
  | .error .attemptsExceeded => "#A"

def utf8 (l : List Char) : List Nat := (String.ofList l).toUTF8.toList.map (·.toNat)

def slugCfg (sep ml wb so lc stops : String) : Option Slug.Config :=
  match decodeStr sep, ml.toNat?, decodeList stops with
  | some sep, some ml, some stops =>
    some { sep, maxLen := ml, wordBoundary := wb == "1", saveOrder := so == "1",
           lowercase := lc == "1", stopwords := stops }
  | _, _, _ => none

def both (s : String) : String := s!"{s}\t{s}"

def runCase (fields : List String) : String :=
  match fields with
  | ["F", t, sep, ml, pl, pe] =>
    match decodeStr t, decodeStr sep, ml.toNat?, platformOf pl with
    | some t, some sep, some ml, some p =>
      let pe := pe == "1"
      s!"{encodeStr (Filename.sanitize t sep ml p pe)}\t{encodeStr (Filename.sanitizeFixed t sep ml p pe)}"
    | _, _, _, _ => "ERR parse"
  | ["S", t, sep, ml, wb, so, lc, stops] =>
    match decodeStr t, slugCfg sep ml wb so lc stops with
    | some t, some cfg => s!"{encodeStr (Slug.slugify cfg t)}\t{encodeStr (Slug.slugifyFixed cfg t)}"
    | _, _ => "ERR parse"
  | ["U", sep, ml, wb, so, lc, stops, texts] =>
    match slugCfg sep ml wb so lc stops, decodeList texts with
    | some cfg, some ts =>
      let cur := ",".intercalate ((Unique.run cfg 10000 ts).map encodeRes)
      let fixed := ",".intercalate ((Unique.runFixed cfg 10000 ts).map encodeRes)
      s!"{cur}\t{fixed}"
    | _, _ => "ERR parse"
  | ["L", t, rep, kt] =>
    match decodeStr t, decodeStr rep with
    | some t, some rep => both (encodeStr (Log.strip rep (kt == "1") t))
    | _, _ => "ERR parse"
  | ["H", t] =>
    match decodeStr t with
    | some t => both (encodeStr (Enc.escapeHtml t))
    | none => "ERR parse"
  | ["P", comp, t] =>
    match componentOf comp, decodeStr t with
    | some c, some t => both (encodeStr ((Enc.pctEncode c (utf8 t)).map Char.ofNat))
    | _, _ => "ERR parse"
  | ["D", a, b] =>
    match decodeStr a, decodeStr b with
    | some a, some b => s!"{Dist.dp a b}\t{Dist.lev a b}"
    | _, _ => "ERR parse"
  | _ => "ERR fields"

partial def loop (h : IO.FS.Stream) (o : IO.FS.Stream) : IO Unit := do
  let line ← h.getLine
  if line.isEmpty then return
  let fields := (String.ofList (line.toList.filter (· != (Char.ofNat 10)))).splitOn "\t"
  o.putStrLn (runCase fields)
  loop h o

def main : IO Unit := do
  let i ← IO.getStdin
  let o ← IO.getStdout
  loop i o
