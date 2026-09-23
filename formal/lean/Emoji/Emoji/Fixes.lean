import Emoji.Props

/-!
# The proposed fixes, applied to the model

Each finding in the README comes with a minimal fix. Each fix is applied here to a copy
of the model, and `Checks.lean` re-runs the failing property against the copy, so the
fix is shown to close the counterexample class (to the same bound) without opening
another one on the properties that held.

* **Fix 1 — the seam looks back two characters** (finding F1). `drop_marks_the_seam_would_bind`
  builds its seam from the *last* output character only. A keycap head is up to three
  characters (base, `U+FE0F`, keycap), so when the output ends in `1 U+FE0F` the seam
  sees only `U+FE0F` and lets a following keycap through. The fix asks the question for
  the last one *and* the last two output characters.
* **Fix 2 — the loop-top skip closes the seam** (finding F2). Both demojize scanners
  drop every `VS15`/`VS16`/`ZWJ` at the top of the loop; that drop is a removal like any
  other, and `1 U+FE0E U+20E3` became `1 U+20E3`. The fix runs the same seam rule after
  the skip.
* **Fix 3 — a drop that writes nothing leaves the separator state alone** (findings F3,
  F4). After dropping an unnamed emoji (pure scanner; `errors="ignore"`, or `"replace"`
  with `replace_with=""`), `last_was_emoji` is reset to `false`, so what follows is
  glued to a *name* written before the drop: `😀🇦x` → `grinning facex`,
  `😀🇦◌́` → `grinning facé`. Nothing was written, so the flags should stay as they were.
-/

namespace Emoji
open Tables

/-- Fix 1: `drop_marks_the_seam_would_bind` with a two-character look-back. `accRev` is
the reversed output so far. -/
def seamDrop2 (accRev : List Char) (s : List Char) : List Char :=
  match accRev with
  | [] => s
  | b :: bs =>
    let binds (m : List Char) : Bool :=
      (match headLen (b :: m.take 2) with | some l => l ≥ 2 | none => false) ||
      (match bs.head? with
       | some a => match headLen (a :: b :: m.take 1) with | some l => l ≥ 3 | none => false
       | none => false)
    let rec go : List Char → List Char
      | [] => []
      | mark :: t =>
        if !(mark == VS15 || mark == VS16 || mark == KEYCAP) then mark :: t
        else if binds (mark :: t) then go t else mark :: t
    go s

def replaceLoopFix (repl : List Char) : Nat → List Char → List Char → List Char
  | 0, _, acc => acc
  | _, [], acc => acc
  | fuel + 1, s@(c :: t), acc =>
    match presLen s with
    | some n =>
      let acc' := repl.reverse ++ acc
      replaceLoopFix repl fuel (seamDrop2 acc' (s.drop n)) acc'
    | none => replaceLoopFix repl fuel t (c :: acc)

/-- `replace_emoji` with Fix 1 (unbounded form; the window is an optimisation, shown
separately). -/
def replaceFix (s repl : List Char) : List Char :=
  if isAscii s then s else (replaceLoopFix repl (s.length + 1) s []).reverse

/-- pyo3 `demojize_impl` with Fixes 1-3. `fix2`/`fix3` select which are applied. -/
def pyLoopFix (fix2 fix3 : Bool) (mode : ErrorMode) (replaceWith : List Char) :
    Nat → List Char → List Char → Bool → Bool → List Char
  | 0, _, acc, _, _ => acc
  | _, [], acc, _, _ => acc
  | fuel + 1, s@(ch :: t), acc, lastWasEmoji, lastWasRaw =>
    if ch == VS16 || ch == VS15 || ch == ZWJ then
      let t := if fix2 then seamDrop2 acc t else t
      pyLoopFix fix2 fix3 mode replaceWith fuel t acc lastWasEmoji lastWasRaw
    else
    let win := s.take maxWindow
    match matchAt win with
    | some (name, consumed) =>
      let acc := pad acc name
      pyLoopFix fix2 fix3 mode replaceWith fuel (sweep (s.drop consumed)) acc true false
    | none =>
    match unnamedLen win with
    | some consumed =>
      let acc' := match mode with
        | .replace => replaceWith.reverse ++ acc
        | .ignore => acc
        | .preserve => (win.take consumed).reverse ++ acc
      let wrote := match mode with
        | .preserve => true
        | .replace => !replaceWith.isEmpty
        | .ignore => false
      let lwe := if fix3 && !wrote then lastWasEmoji else wrote
      let lwr := if fix3 && !wrote then lastWasRaw else mode == .preserve
      let rest := s.drop consumed
      let rest := if !wrote then seamDrop2 acc' rest else rest
      pyLoopFix fix2 fix3 mode replaceWith fuel rest acc' lwe lwr
    | none =>
      let separate := if lastWasRaw then isAlphanumeric ch else needsSep ch
      let acc := if lastWasEmoji && separate then ' ' :: acc else acc
      pyLoopFix fix2 fix3 mode replaceWith fuel t (ch :: acc) false false

def demojizeFix (mode : ErrorMode) (replaceWith : List Char) (s : List Char) : List Char :=
  if isAscii s then s
  else (pyLoopFix true true mode replaceWith (s.length + 1) s [] false false).reverse

/-- The pure-Rust scanner with Fixes 1-3 (`TextPipeline(demojize=True)`). -/
def demojizeLoopFix (skipNonEmoji : Bool) : Nat → List Char → List Char → Bool → List Char
  | 0, _, acc, _ => acc
  | _, [], acc, _ => acc
  | fuel + 1, s@(ch :: t), acc, lastWasEmoji =>
    if ch == VS16 || ch == VS15 || ch == ZWJ then
      demojizeLoopFix skipNonEmoji fuel (seamDrop2 acc t) acc lastWasEmoji
    else if policySkips skipNonEmoji ch then
      let acc := if lastWasEmoji && needsSep ch then ' ' :: acc else acc
      demojizeLoopFix skipNonEmoji fuel t (ch :: acc) false
    else
      let win := s.take maxWindow
      match matchAt win with
      | some (name, consumed) =>
        demojizeLoopFix skipNonEmoji fuel (sweep (s.drop consumed)) (pad acc name) true
      | none =>
        match unnamedLen win with
        | some consumed =>
          demojizeLoopFix skipNonEmoji fuel (seamDrop2 acc (s.drop consumed)) acc lastWasEmoji
        | none =>
          let acc := if lastWasEmoji && needsSep ch then ' ' :: acc else acc
          demojizeLoopFix skipNonEmoji fuel t (ch :: acc) false

def pipelineFix (s : List Char) : List Char :=
  if isAscii s then s else (demojizeLoopFix true (s.length + 1) s [] false).reverse

def demIgnoreFix := demojizeFix .ignore "[?]".toList
def demReplaceFix := demojizeFix .replace "[?]".toList
def demReplaceEmptyFix := demojizeFix .replace []

end Emoji
