/-!
# The invisible classes (`src/invisibles.rs`), `strip_bidi` (`src/presets.rs` L1017-1059)
# and the `strip_format` composition (`src/presets.rs` L1739-1766)

| Token | Rust predicate | Character in the differential test |
|---|---|---|
| `plain i` | none | `a`, `b` |
| `flag` | `FLAG_BASE` | `U+1F3F4` |
| `tagL c` | `is_tag_letter` | `U+E0061`-`U+E007A` (`c` is the letter) |
| `cancel` | `CANCEL_TAG` | `U+E007F` |
| `tagO i` | `is_tag`, not a letter or the terminator | `U+E0001`, `U+E0041`, `U+E0020` |
| `cgj` | `CGJ` | `U+034F` |
| `nonch` | `is_noncharacter` | `U+FFFE`, `U+FDD0` |
| `pua` | `is_pua` | `U+E000` |
| `vs i` | `is_variation_selector`, not VS15/VS16 | `U+FE00`, `U+E0100` |
| `vs15`, `vs16` | `U+FE0E`, `U+FE0F` | |
| `difmt` | `is_default_ignorable_format` | `U+1D173` |
| `zw` | `whitespace::is_zero_width` (not `difmt`) | `U+200B` |
| `ws i` | fold whitespace (`ws 0` is the space `collapse` writes) | space, NBSP |
| `blank` | `is_blank_render` | `U+2800` |
| `ctl` | a control that is not fold whitespace | NUL |
| `bidi` | `is_bidi_or_format` | `U+202E`, `U+00AD` |
-/

namespace Text.Invisibles

inductive I where
  | plain (i : Nat)
  | flag
  | tagL (c : Char)
  | cancel
  | tagO (i : Nat)
  | cgj
  | nonch
  | pua
  | vs (i : Nat)
  | vs15
  | vs16
  | difmt
  | zw
  | ws (i : Nat)
  | blank
  | ctl
  | bidi (i : Nat)
  deriving DecidableEq, Repr, Inhabited

def isTag : I → Bool
  | .tagL _ | .cancel | .tagO _ => true
  | _ => false

/-- `VALID_SUBDIVISION_FLAGS` (L179). The functions below take the allowlist as a
parameter defaulting to this one, so the bounded checks can use a two-letter payload and
reach the valid-flag path with short words: the code only ever compares the payload with
the list, so the structural properties do not depend on which strings are in it. -/
def realFlags : List (List Char) := ["gbeng".toList, "gbsct".toList, "gbwls".toList]

def validFlag (vf : List (List Char)) (letters : List Char) : Bool := vf.contains letters

/-- The tag letters at the head, and what follows them. -/
def takeLetters : List I → List Char × List I
  | .tagL c :: r => let (ls, rest) := takeLetters r; (c :: ls, rest)
  | r => ([], r)

/-- `consume_flag_tail` (L181-203): `some (letters, rest)` for a valid flag, where `rest`
follows the terminator; `none` with the letters consumed otherwise. -/
def flagTail (vf : List (List Char)) (r : List I) : Option (List Char) × List I :=
  let (ls, rest) := takeLetters r
  match rest with
  | .cancel :: rest' => if validFlag vf ls then (some ls, rest') else (none, rest)
  | _ => (none, rest)

/-- `whitespace::is_zero_width`, which includes the #813 formats. -/
def isZeroWidth : I → Bool
  | .zw | .difmt => true
  | _ => false

def isWs : I → Bool
  | .ws _ => true
  | _ => false

/-- `is_presentation_base` (L212-217). -/
def presBase (c : I) : Bool := !(isWs c || c == .ctl || c == .blank || isZeroWidth c)

structure Policy where
  stripPua : Bool
  keepVs : Bool
  deriving DecidableEq, Repr

def comparison : Policy := { stripPua := true, keepVs := false }
def rendering : Policy := { stripPua := false, keepVs := true }

/-- The main loop of `strip_invisible_classes_into` (L276-314) over the remaining input,
with the output so far (in order). `fuel` bounds the recursion; `stripInv` passes the
input length, and every step consumes at least one scalar. -/
def invGo (vf : List (List Char)) (pol : Policy) : Nat → List I → List I → List I
  | 0, out, _ => out
  | _ + 1, out, [] => out
  | f + 1, out, c :: r =>
    match c with
    | .flag =>
      match flagTail vf r with
      | (some ls, rest) => invGo vf pol f (out ++ .flag :: ls.map .tagL ++ [.cancel]) rest
      | (none, rest) => invGo vf pol f (out ++ [.flag]) rest
    | .tagL _ | .cancel | .tagO _ | .cgj | .nonch | .difmt => invGo vf pol f out r
    | .pua => invGo vf pol f (if pol.stripPua then out else out ++ [c]) r
    | .vs _ => invGo vf pol f out r
    | .vs15 | .vs16 =>
      let keep := pol.keepVs && (out.getLast?.map presBase == some true)
      invGo vf pol f (if keep then out ++ [c] else out) r
    | _ => invGo vf pol f (out ++ [c]) r

def stripInv (pol : Policy) (s : List I) (vf : List (List Char) := realFlags) : List I :=
  invGo vf pol (s.length + 1) [] s

/-- `strip_tags` (L221-241). -/
def tagsGo (vf : List (List Char)) : Nat → List I → List I → List I
  | 0, out, _ => out
  | _ + 1, out, [] => out
  | f + 1, out, c :: r =>
    match c with
    | .flag =>
      match flagTail vf r with
      | (some ls, rest) => tagsGo vf f (out ++ .flag :: ls.map .tagL ++ [.cancel]) rest
      | (none, rest) => tagsGo vf f (out ++ [.flag]) rest
    | _ => tagsGo vf f (if isTag c then out else out ++ [c]) r

def stripTags (s : List I) (vf : List (List Char) := realFlags) : List I :=
  tagsGo vf (s.length + 1) [] s

def stripVS (s : List I) : List I :=
  s.filter fun c => match c with | .vs _ | .vs15 | .vs16 => false | _ => true
def stripNonch (s : List I) : List I := s.filter (· != .nonch)
def stripPua (s : List I) : List I := s.filter (· != .pua)
def stripBidi (s : List I) : List I :=
  s.filter fun c => match c with | .bidi _ => false | _ => true
def stripCtl (s : List I) : List I := s.filter (· != .ctl)
def stripZW (s : List I) : List I := s.filter (fun c => !isZeroWidth c)

/-- `collapse_whitespace` over this alphabet: `ws` and `blank` fold. -/
def folds (c : I) : Bool := isWs c || c == .blank

def collapseLoop : Bool → Bool → List I → List I
  | _, _, [] => []
  | pv, sn, c :: t =>
    if folds c then (if sn && !pv then .ws 0 :: collapseLoop true sn t else collapseLoop pv sn t)
    else c :: collapseLoop false true t

def collapse (s : List I) : List I :=
  let r := collapseLoop false false s
  if r.getLast? == some (.ws 0) then r.dropLast else r

/-- `strip_format`: bidi, invisibles (rendering), control, zero-width, collapse. -/
def stripFormat (s : List I) (vf : List (List Char) := realFlags) : List I :=
  collapse (stripZW (stripCtl (stripInv rendering (stripBidi s) vf)))

/-- The same five steps with the comparison policy: the part of `canonicalize` that this
alphabet reaches (its other steps are the identity on these characters, which the
differential test confirms rather than assumes). -/
def stripCompare (s : List I) (vf : List (List Char) := realFlags) : List I :=
  collapse (stripZW (stripCtl (stripInv comparison (stripBidi s) vf)))

/-! ## Vocabulary for the properties -/

/-- Delete every well-formed valid flag sequence; what is left must hold no tag. -/
def dropValidFlags (vf : List (List Char)) : Nat → List I → List I
  | 0, _ => []
  | _ + 1, [] => []
  | f + 1, .flag :: r =>
    match flagTail vf r with
    | (some _, rest) => dropValidFlags vf f rest
    | (none, _) => .flag :: dropValidFlags vf f r
  | f + 1, c :: r => c :: dropValidFlags vf f r

/-- No tag character outside a valid subdivision flag. -/
def noStrayTags (s : List I) (vf : List (List Char) := realFlags) : Bool :=
  (dropValidFlags vf (s.length + 1) s).all (fun c => !isTag c)

/-- Every kept presentation selector directly follows a presentation base. -/
def vsWellPlaced : List I → Bool
  | [] => true
  | c :: r =>
    (match c with | .vs15 | .vs16 => false | .vs _ => false | _ => true) && vsTail c r
where
  vsTail (prev : I) : List I → Bool
    | [] => true
    | c :: r =>
      (match c with
       | .vs15 | .vs16 => presBase prev
       | .vs _ => false
       | _ => true) && vsTail c r

end Text.Invisibles
