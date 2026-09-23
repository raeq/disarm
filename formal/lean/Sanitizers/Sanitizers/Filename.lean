/-!
# Model of `sanitize_filename` (`src/filename.rs`)

The model covers the code path from the first `collapse_dot_sequences` (L210) to the
final `finalize_name` (L374), over input on which NFC normalization and transliteration
are the identity: ASCII. On that domain three steps drop out, and the model says so
rather than modelling them:

* `text.nfc()` (L207) is the identity on ASCII.
* `transliterate_impl` (L213) returns ASCII input unchanged (checked by the
  differential test, which includes the C0 controls, DEL and TAB).
* `neutralize_introduced_percent` (L231) only fires when the transliterated text holds a
  `%` the raw text does not; with transliteration the identity it never fires.

Byte length and character count coincide on ASCII, so `floor_char_boundary` is the
identity on every index the code passes it and `List.take` is `String::truncate`.

Every definition names the lines it models.
-/

namespace Sanitizers.Filename

/-- The three `platform` strings `sanitize_filename` accepts (L194-202). -/
inductive Platform where
  | universal
  | windows
  | posix
  deriving DecidableEq, Repr

/-- `UNIVERSAL_ILLEGAL` (L25). -/
def universalIllegal : List Char :=
  ['/', '\\', ':', '*', '?', '"', '<', '>', '|', Char.ofNat 0]

/-- `POSIX_ILLEGAL` (L26). -/
def posixIllegal : List Char := ['/', Char.ofNat 0]

def illegal : Platform → Char → Bool
  | .posix, c => posixIllegal.contains c
  | _, c => universalIllegal.contains c

/-- `char::is_control`: general category Cc. -/
def isControl (c : Char) : Bool :=
  c.toNat < 0x20 || (0x7F ≤ c.toNat && c.toNat ≤ 0x9F)

/-- `char::is_whitespace`: the Unicode `White_Space` property. -/
def isWs (c : Char) : Bool :=
  [9, 10, 11, 12, 13, 32, 0x85, 0xA0, 0x1680, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000].contains
      c.toNat
    || (0x2000 ≤ c.toNat && c.toNat ≤ 0x200A)

/-- The L272 / L318 test: a character that becomes the separator (stem) or is dropped
(extension). -/
def dropped (p : Platform) (c : Char) : Bool :=
  illegal p c || isControl c || isWs c

/-- Dot or space: the set `trim_end_matches(['.', ' '])` (L252), the leading/trailing
strips (L292, L304) and `finalize_name` (L170) remove. -/
def isDS (c : Char) : Bool := c == '.' || c == ' '

/-- `WINDOWS_RESERVED` (L18-22). -/
def reservedNames : List (List Char) :=
  ["CON", "PRN", "AUX", "NUL", "COM0", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7",
    "COM8", "COM9", "LPT0", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    "CLOCK$", "KEYBD$", "SCREEN$"].map String.toList

/-- `eq_ignore_ascii_case`: `Char.toUpper` folds exactly `a`-`z`. -/
def eqIgnoreAsciiCase (a b : List Char) : Bool :=
  a.map Char.toUpper == b.map Char.toUpper

/-- `is_windows_reserved` (L69-77). -/
def isReserved (stem : List Char) : Bool :=
  reservedNames.any (eqIgnoreAsciiCase stem)

/-- `collapse_dot_sequences` (L116-142): each run of one or more dots becomes one dot.
The L118 fast path returns the input when it has no `..`, which is what the loop returns
too, so the model is the loop. `run` is `dot_run >= 1`. -/
def collapseAux : List Char → Bool → List Char
  | [], run => if run then ['.'] else []
  | c :: cs, run =>
    if c == '.' then collapseAux cs true
    else if run then '.' :: c :: collapseAux cs false
    else c :: collapseAux cs false

def collapse (s : List Char) : List Char := collapseAux s false

/-- Drop the longest suffix whose characters satisfy `p`. -/
def rtrim (p : Char → Bool) (l : List Char) : List Char :=
  (l.reverse.dropWhile p).reverse

/-- Index of the last `.`, as `rfind('.')`. -/
def lastDot (l : List Char) : Option Nat :=
  match l.reverse.findIdx? (· == '.') with
  | some i => some (l.length - 1 - i)
  | none => none

/-- The L258-265 split: at the last dot, if it is not at index 0. -/
def split (preserve : Bool) (t : List Char) : List Char × Option (List Char) :=
  if preserve then
    match lastDot t with
    | some pos => if pos > 0 then (t.take pos, some (t.drop pos)) else (t, none)
    | none => (t, none)
  else (t, none)

/-- The L268-281 loop. `prev` is `prev_was_sep`; it starts `true`. -/
def stemLoop (p : Platform) (sep : List Char) : List Char → Bool → List Char
  | [], _ => []
  | c :: cs, prev =>
    if dropped p c then
      if !prev && !sep.isEmpty then sep ++ stemLoop p sep cs true
      else stemLoop p sep cs prev
    else c :: stemLoop p sep cs false

/-- L284-286: `while result.ends_with(separator) && !separator.is_empty()`. `fuel` bounds
the loop; `stripSep` passes the length, which is always enough. -/
def stripSepF (sep : List Char) : Nat → List Char → List Char
  | 0, l => l
  | n + 1, l =>
    if !sep.isEmpty && sep.isSuffixOf l then stripSepF sep n (l.take (l.length - sep.length))
    else l

def stripSep (sep l : List Char) : List Char := stripSepF sep (l.length + 1) l

/-- The L314-323 extension filter: keep the dot, drop every `dropped` character after it. -/
def cleanExt (p : Platform) (e : List Char) : List Char :=
  '.' :: (e.drop 1).filter (fun c => !dropped p c)

/-- `apply_max_length` (L85-111), with `ext` the *sanitized* extension. -/
def applyMax (name : List Char) (ext : Option (List Char)) (maxLen : Nat) (preserve : Bool) :
    List Char :=
  if maxLen == 0 || name.length ≤ maxLen then name
  else if preserve then
    match ext with
    | some e => if e.length ≥ maxLen then name.take maxLen else name.take (maxLen - e.length) ++ e
    | none => name.take maxLen
  else name.take maxLen

/-- `finalize_name` (L169-178). -/
def finalize (name : List Char) : List Char :=
  let t := rtrim isDS (name.dropWhile isDS)
  if t.isEmpty then ['_'] else t

/-- The stem the post-truncation check reads (L357-360): up to the first dot. -/
def firstDotStem (l : List Char) : List Char := l.takeWhile (· != '.')

def windowsish (p : Platform) : Bool := p != .posix

/-- The sanitized stem, L268-310. -/
def cleanStem (p : Platform) (sep stem : List Char) : List Char :=
  rtrim isDS ((stripSep sep (stemLoop p sep stem true)).dropWhile isDS)

/-- `sanitize_filename` (L180-375) on ASCII input. -/
def sanitize (text sep : List Char) (maxLen : Nat) (p : Platform) (preserve : Bool) :
    List Char :=
  let t := rtrim isDS (collapse (collapse text))
  let (stem, ext) := split preserve t
  let r := cleanStem p sep stem
  let sext := ext.map (cleanExt p)
  if windowsish p && isReserved r then
    finalize (applyMax ('_' :: (r ++ sext.getD [])) sext maxLen preserve)
  else
    let f0 := applyMax (r ++ sext.getD []) sext maxLen preserve
    let f1 :=
      if windowsish p && isReserved (firstDotStem f0) then applyMax ('_' :: f0) sext maxLen preserve
      else f0
    finalize f1

/-! ## The proposed fix

`sanitizeFixed` is `sanitize` with four changes, each aimed at one finding.

1. **An empty stem gives way to its extension** (Finding 1). When the stem sanitizes to
   nothing, the extension *is* the name: `"*.con"` has to be judged as `"con"`, which is
   what `finalize_name` turns it into. The extension's text (without its dot) becomes the
   stem before the reserved check at L326.
2. **The last reserved check reads the name Windows will see** (Finding 2): it runs after
   `finalize_name`'s trim, on the name with trailing dots and spaces removed, the part
   before the first dot, and that part's own trailing spaces removed
   (`RtlIsDosDeviceName_U`). Nothing a later step removes can then uncover a reserved
   stem.
3. **The stem's tail is trimmed of separators, dots and spaces together, before and after
   truncation** (Finding 3). L284-310 strip trailing separators *then* trailing dots and
   spaces, once each, so `"_."` or `"-.-"` leaves a separator behind; and
   `apply_max_length` can cut the stem right after a separator or a dot and nothing
   trims it. Leading separators are left alone: the reserved-name marker `_` is itself
   the default separator, and stripping it would undo the marker on the next call.
4. **The extension boundary is a dot whose extension survives cleaning** (Finding 3). An
   extension that cleans to a bare `.` (`".*"`, `"./"`) is removed by `finalize_name`,
   so the next call splits at an earlier dot: `"_.x.*"` gives `"_.x"`, then `"x"`. It is
   the #570 problem through another door: #570 trims trailing dots before the split, but
   not an extension that *becomes* a trailing dot. The stem is re-split instead.
-/

/-- Fix 4: split, and while the extension cleans to a bare dot, split the stem again. -/
def splitFixedF (p : Platform) (preserve : Bool) : Nat → List Char → List Char × Option (List Char)
  | 0, t => (t, none)
  | n + 1, t =>
    match split preserve t with
    | (stem, some e) =>
      if cleanExt p e == ['.'] then splitFixedF p preserve n (rtrim isDS stem) else (stem, some e)
    | r => r

def splitFixed (p : Platform) (preserve : Bool) (t : List Char) : List Char × Option (List Char) :=
  splitFixedF p preserve (t.length + 1) t

/-- Drop trailing dots, spaces and whole separators, in any order. -/
def trimRF (sep : List Char) : Nat → List Char → List Char
  | 0, l => l
  | n + 1, l =>
    match l.getLast? with
    | none => []
    | some c =>
      if isDS c then trimRF sep n l.dropLast
      else if !sep.isEmpty && sep.isSuffixOf l then trimRF sep n (l.take (l.length - sep.length))
      else l

/-- Fix 3: the stem, with dot runs collapsed again (an empty separator deletes the space
in `". ."`, making a `..` the L210 collapse never saw), leading dots and spaces dropped
(as L289-298), and the tail trimmed by `trimRF`. -/
def cleanStemFixed (p : Platform) (sep stem : List Char) : List Char :=
  let l := (collapse (stemLoop p sep stem true)).dropWhile isDS
  trimRF sep (l.length + 1) l

/-- What Windows compares with the device list: trailing dots and spaces of the whole name
dropped, then the part before the first dot, then its trailing spaces. -/
def winStem (l : List Char) : List Char :=
  rtrim (· == ' ') (firstDotStem (rtrim isDS l))

/-- Fix 3: truncation that trims the cut edge of the stem the same way. A cut that leaves
no stem at all falls back to cutting the whole name, as when the extension alone does not
fit: an extension with nothing before it is read as a stem by the next call. -/
def applyMaxFixed (sep : List Char) (name : List Char) (ext : Option (List Char))
    (maxLen : Nat) (preserve : Bool) : List Char :=
  if maxLen == 0 || name.length ≤ maxLen then name
  else
    let clean := fun (s : List Char) => trimRF sep (s.length + 1) s
    if preserve then
      match ext with
      | some e =>
        if e.length ≥ maxLen then clean (name.take maxLen)
        else
          let stem := clean (name.take (maxLen - e.length))
          if stem.isEmpty then clean (name.take maxLen) else stem ++ e
      | none => clean (name.take maxLen)
    else clean (name.take maxLen)

def sanitizeFixed (text sep : List Char) (maxLen : Nat) (p : Platform) (preserve : Bool) :
    List Char :=
  let t := rtrim isDS (collapse (collapse text))
  let (stem, ext) := splitFixed p preserve t
  let r0 := cleanStemFixed p sep stem
  let sext0 := ext.map (cleanExt p)
  -- fix 1
  let (r, sext) :=
    if r0.isEmpty then
      match sext0 with
      | some e => (cleanStemFixed p sep (e.drop 1), none)
      | none => (r0, sext0)
    else (r0, sext0)
  let f0 :=
    if windowsish p && isReserved r then
      applyMaxFixed sep ('_' :: (r ++ sext.getD [])) sext maxLen preserve
    else applyMaxFixed sep (r ++ sext.getD []) sext maxLen preserve
  -- fix 2: judged after the final trim, on the name Windows sees
  let f1 := finalize f0
  if windowsish p && isReserved (winStem f1) then
    finalize (applyMaxFixed sep ('_' :: f1) sext maxLen preserve)
  else f1

end Sanitizers.Filename
