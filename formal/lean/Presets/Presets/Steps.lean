import Presets.Unicode

/-!
# The steps

One function per `Step` arm of `presets::apply_into` (src/presets.rs L311-L517) and per
`PipelineSteps` arm of `Pipeline::apply_step_into` (src/pipeline.rs L480-L640), on the
model's domain. Each cites the Rust it transcribes.

Per-character maps read the generated tables. The context-sensitive steps (normalization,
the deletion resolver, the whitespace fold, the mark cap, the repeated-mark drop, the accent
strip and the fixed-point loops) are transcribed branch by branch.
-/

namespace Presets

/-- The digit policy (`confusables::DigitPolicy`). -/
inductive Pol
  | numeric
  | tr39
  | preserve
  deriving DecidableEq, Repr

/-- The raw single-pass confusable row (`lookup_with_policy`, confusables.rs L129). -/
def confT : Pol -> Nat -> Option (List Nat)
  | .numeric => conf_numeric
  | .tr39 => conf_tr39
  | .preserve => conf_preserve

/-! ## Filters -/

def stripBidi (s : Str) : Str := s.filter (fun c => !isBidiOrFormat c)
def stripZeroWidth (s : Str) : Str := s.filter (fun c => !isZeroWidth c)
/-- `strip_control_chars_into` (whitespace.rs L117): a control goes unless it folds. -/
def stripControl (s : Str) : Str := s.filter (fun c => !isControl c || isFoldWs c)
def stripPua (s : Str) : Str := s.filter (fun c => !isPUA c)

/-- `strip_invisible_classes_into` under `COMPARISON_STRIP` (invisibles.rs L276): tags,
CGJ, noncharacters, the default-ignorable formats, the PUA and every variation selector.
The flag carve-out needs `U+1F3F4`, which is not in the domain. -/
def stripInvisibleCmp (s : Str) : Str :=
  s.filter (fun c => !(isTag c || c == 0x34F || isNonchar c || isDIF c || isPUA c || isVS c))

/-- `is_presentation_base` (invisibles.rs L209). -/
def isPresentationBase (c : Nat) : Bool :=
  !isFoldWs c && !isControl c && !isBlankRender c && !isZeroWidth c

/-- `strip_invisible_classes_into` under `RENDERING_STRIP`: keep the PUA, and keep VS15/VS16
directly after a presentation base. `acc` is the output so far, reversed. -/
def stripInvisibleRenderAux : Str -> Str -> Str
  | acc, [] => acc.reverse
  | acc, c :: cs =>
    if isTag c || c == 0x34F || isNonchar c || isDIF c then stripInvisibleRenderAux acc cs
    else if isVS c then
      let keep := (c == 0xFE0E || c == 0xFE0F) &&
        (match acc with
         | d :: _ => isPresentationBase d
         | [] => false)
      if keep then stripInvisibleRenderAux (c :: acc) cs else stripInvisibleRenderAux acc cs
    else stripInvisibleRenderAux (c :: acc) cs

def stripInvisibleRender (s : Str) : Str := stripInvisibleRenderAux [] s

/-! ## Compose-at-lookup (src/compose.rs) -/

/-- Greedy longest-prefix recomposition of excluded compositions (`recompose_excluded`). -/
def widen : Nat -> Str -> Str
  | 0, s => s
  | _ + 1, [] => []
  | n + 1, c :: cs =>
    match widenKeys.find? (fun (k, _) => k.isPrefixOf (c :: cs) && k.length >= 2) with
    | some (k, v) => v :: widen n ((c :: cs).drop k.length)
    | none => c :: widen n cs

/-- Split off a cluster: the anchor and the run of marks after it. -/
def takeMarks : Str -> Str × Str
  | [] => ([], [])
  | c :: cs => if isMark c then let (m, r) := takeMarks cs; (c :: m, r) else ([], c :: cs)

/-- `try_compose_hangul` (compose.rs L117): an L jamo followed by a V jamo (and optionally a
T jamo) composes by arithmetic. -/
def hangulLV (l v : Nat) : Option Nat :=
  if 0x1100 <= l && l <= 0x1112 && 0x1161 <= v && v <= 0x1175 then
    some (0xAC00 + (l - 0x1100) * 588 + (v - 0x1161) * 28)
  else none

/-- `composed` (compose.rs L43): a conjoining L+V run composes; a character followed by a
mark anchors a cluster, which is NFC-composed and then widened; anything else is yielded
verbatim. -/
def composedLocal : Nat -> Str -> Str
  | 0, s => s
  | _ + 1, [] => []
  | n + 1, c :: cs =>
    match cs with
    | d :: rest' =>
      if let some syl := hangulLV c d then
        match rest' with
        | t :: rest'' =>
          if 0x11A8 <= t && t <= 0x11C2 then (syl + (t - 0x11A7)) :: composedLocal n rest''
          else syl :: composedLocal n rest'
        | [] => [syl]
      else if isMark d then
        let (ms, rest) := takeMarks cs
        let cl := nfc (c :: ms)
        widen (cl.length + 1) cl ++ composedLocal n rest
      else c :: composedLocal n cs
    | [] => [c]

def composed (s : Str) : Str := composedLocal (s.length + 1) s

/-! ## Per-character maps -/

def foldCase (s : Str) : Str := s.flatMap (lk foldT)
/-- `normalize_confusables_into` (confusables.rs L309): one pass, per code point. -/
def confPass (p : Pol) (s : Str) : Str := s.flatMap (lk (confT p))
/-! ## Transliteration (`transliterate_run`, transliterate.rs L640-L830)

Per code point over the composed text, plus the one context rule the domain reaches: a
space before a Hangul syllable, and before an ASCII alphanumeric after one, when the last
character written is alphanumeric (`needs_cjk_space`). -/

inductive TClass
  | none
  | latin
  | hangul
  | other
  deriving DecidableEq, Repr

def isHangulSyllable (c : Nat) : Bool := (0xAC00 <= c && c <= 0xD7A3) || (0x3130 <= c && c <= 0x318F)

def isAsciiAlnum (c : Nat) : Bool :=
  (0x30 <= c && c <= 0x39) || (0x41 <= c && c <= 0x5A) || (0x61 <= c && c <= 0x7A)

def alnumAny (c : Nat) : Bool := isAsciiAlnum c || isAlnum c

/-- No table entry and no NFKC recovery: `ignore` drops it and `preserve` keeps it. -/
def unmapped (c : Nat) : Bool := c >= 0x80 && (translitP c).isNone && translitI c == some []

structure TSt where
  out : Str := []   -- reversed
  prev : TClass := .none
  last : Option Nat := none

def tStep (preserve : Bool) (s : TSt) (ch : Nat) : TSt :=
  if ch < 0x80 then
    let sp := (s.prev == .hangul && isAsciiAlnum ch && (s.last.map alnumAny).getD false)
    { out := ch :: (if sp then 0x20 :: s.out else s.out), prev := .latin, last := some ch }
  else if unmapped ch then
    if preserve then { out := ch :: s.out, prev := .other, last := some ch }
    else { s with prev := .other }
  else
    let m := lk (if preserve then translitP else translitI) ch
    let cls := if isHangulSyllable ch then TClass.hangul else TClass.other
    let sp := cls == .hangul && s.prev != .none && (s.last.map alnumAny).getD false
    let out := m.reverse ++ (if sp then 0x20 :: s.out else s.out)
    { out := out, prev := cls, last := if m.isEmpty then (if sp then some 0x20 else s.last) else m.getLast? }

def translitWith (preserve : Bool) (s : Str) : Str :=
  ((composed s).foldl (tStep preserve) {}).out.reverse

def translitPreserve (s : Str) : Str := translitWith true s
def translitIgnore (s : Str) : Str := translitWith false s

/-- `prototype_fold_into` (confusables.rs L922). -/
def prototypeFold (p : Pol) (s : Str) : Str :=
  s.map (fun c =>
    if c == 0x49 then 0x6C
    else if p == .tr39 && c == 0x31 then 0x6C
    else if p == .tr39 && c == 0x30 then 0x4F
    else c)

/-- `transliterate_preserving_latin_into` (presets.rs L1547): transliterate maximal runs of
non-Latin, non-Common, non-Inherited characters and keep everything else. `run` is reversed. -/
def translitPreservingLatinAux : Str -> Str -> Str
  | run, [] => translitPreserve run.reverse
  | run, c :: cs =>
    if keepsScript c then translitPreserve run.reverse ++ c :: translitPreservingLatinAux [] cs
    else translitPreservingLatinAux (c :: run) cs

def translitPreservingLatin (s : Str) : Str := translitPreservingLatinAux [] s

/-! ## Whitespace -/

/-- `collapse_whitespace_into` (whitespace.rs L33). -/
def collapseWs (s : Str) : Str :=
  let st := s.foldl (fun (acc : Str × Bool × Bool) ch =>
    let (o, prevSp, seen) := acc
    if isFoldWs ch || isBlankRender ch then
      if seen && !prevSp then (0x20 :: o, true, seen) else (o, prevSp, seen)
    else (ch :: o, false, true)) ([], false, false)
  match st.1 with
  | 0x20 :: rest => rest.reverse
  | o => o.reverse

/-! ## Marks -/

/-- `is_negation_of` (transliterate.rs L1570). -/
def isNegationOf (m : Nat) (base : Option Nat) : Bool :=
  (m == 0x338 || m == 0x20D2) &&
    (match base with
     | some b => !isAlnum b && survivesNeg b
     | none => false)

/-- `exceeds_combining_run` (zalgo.rs), over the NFD. -/
def exceedsRun (thr : Nat) (s : Str) : Bool :=
  let r := (nfd s).foldl (fun (acc : Bool × Nat × Nat) ch =>
    let (hit, run, prev) := acc
    if hit then acc
    else if isMark ch then
      let cl := ccc ch
      if cl == 0 && thr > 0 then (false, 0, 0)
      else
        let run' := if cl == prev then run + 1 else 1
        (decide (run' > thr), run', cl)
    else (false, 0, 0)) (false, 0, 0)
  r.1

structure ZSt where
  out : Str := []   -- reversed
  count : Nat := 0
  cls : Nat := 0
  base : Option Nat := none
  negKept : Bool := false

/-- The body of `strip_zalgo_into`'s slow path (zalgo.rs L218-L265). -/
def zalgoStep (cap : Nat) (s : ZSt) (ch : Nat) : ZSt :=
  if isNegationOf ch s.base && !s.negKept then { s with negKept := true, out := ch :: s.out }
  else if isMark ch then
    let cl := ccc ch
    if cl == 0 && cap > 0 then { s with count := 0, cls := 0, out := ch :: s.out }
    else
      let n := if cl == s.cls then s.count + 1 else 1
      { s with count := n, cls := cl, out := if n <= cap then ch :: s.out else s.out }
  else { s with count := 0, cls := 0, negKept := false, base := some ch, out := ch :: s.out }

/-- `strip_zalgo_into` (zalgo.rs L196). -/
def zalgo (cap : Nat) (s : Str) : Str :=
  if isAscii s then s
  else if !exceedsRun cap s then nfc s
  else nfc ((nfd s).foldl (zalgoStep cap) {}).out.reverse

/-- `Step::ZalgoIfOver` (#1072, after `595fbda`): the cap, on text it would cut; any other
text unchanged, where `zalgo` would have renormalized it. The Rust also returns early from
`exceeds_combining_run` on text with no standalone mark, which gives the same answer. -/
def zalgoIfOver (cap : Nat) (s : Str) : Str :=
  if exceedsRun cap s then zalgo cap s else s

/-- `has_repeated_mark` (zalgo.rs L165). -/
def hasRepeatedMark (s : Str) : Bool :=
  let r := (nfd s).foldl (fun (acc : Bool × Option Nat) ch =>
    let (hit, prev) := acc
    if hit then acc
    else if isMark ch && ccc ch != 0 then
      if prev == some ch then (true, prev) else (false, some ch)
    else (false, none)) (false, none)
  r.1

/-- `drop_repeated_marks_into` (zalgo.rs L136): unchanged when nothing repeats, else
NFD, drop the repeat, NFC. -/
def dropRepeatedMarks (s : Str) : Str :=
  if !hasRepeatedMark s then s
  else
    let r := (nfd s).foldl (fun (acc : Str × Option Nat) ch =>
      let (o, prev) := acc
      if isMark ch && ccc ch != 0 then
        if prev == some ch then (o, prev) else (ch :: o, some ch)
      else (ch :: o, none)) ([], none)
    nfc r.1.reverse

/-- `strip_accents_into` (transliterate.rs L1603): NFD, drop every mark except one negation
overlay on a base that is not alphanumeric and survives, NFC. -/
def stripAccents (s : Str) : Str :=
  if isAscii s then s
  else
    let r := (nfd s).foldl (fun (acc : Str × Option Nat × Bool) ch =>
      let (o, base, negKept) := acc
      if isMark ch then
        if !negKept && isNegationOf ch base then (ch :: o, base, true) else (o, base, negKept)
      else (ch :: o, some ch, false)) ([], none, false)
    nfc r.1.reverse

/-! ## The deletion resolver, `cr = false` (deletions.rs L68-L166) -/

def isLineBreak (c : Nat) : Bool :=
  c == 0xA || c == 0xB || c == 0xC || c == 0xD || c == 0x85 || c == 0x2028 || c == 0x2029

def modAt (f : Str -> Str) : Nat -> List Str -> List Str
  | _, [] => []
  | 0, x :: xs => f x :: xs
  | n + 1, x :: xs => x :: modAt f n xs

structure DSt where
  out : Str := []
  line : List Str := []
  col : Nat := 0
  lead : Str := []

def delStep (s : DSt) (ch : Nat) : DSt :=
  if ch == 0x8 || ch == 0x7F then
    if s.col > 0 then { s with col := s.col - 1, line := s.line.set (s.col - 1) [] } else s
  else if isLineBreak ch then
    { out := s.out ++ s.lead ++ s.line.flatten ++ [ch], line := [], col := 0, lead := [] }
  else if !occupiesCell ch && s.col > 0 then
    { s with line := modAt (fun cell => cell ++ [ch]) (s.col - 1) s.line }
  else if !occupiesCell ch then { s with lead := s.lead ++ [ch] }
  else if s.col < s.line.length then { s with line := s.line.set s.col [ch], col := s.col + 1 }
  else { s with line := s.line ++ [[ch]], col := s.col + 1 }

def resolveDeletions (s : Str) : Str :=
  if s.any (fun c => c == 0x8 || c == 0x7F) then
    let st := s.foldl delStep {}
    st.out ++ st.lead ++ st.line.flatten
  else s

/-! ## Fixed-point loops -/

/-- `CONFUSABLE_FIXED_POINT_ITERS` and `MAX_CONFUSABLE_PASSES`. -/
def iters : Nat := 8

/-- The loop of `confusables_nfc_fixed_point_into` (presets.rs L206) and of the pipeline's
confusables arm (pipeline.rs L553), against the normalizer `norm`. -/
def confNormLoop (norm : Str -> Str) (p : Pol) : Nat -> Str -> Bool -> Str
  | 0, cur, _ => cur
  | n + 1, cur, curIsNorm =>
    let conf := confPass p cur
    if conf == cur && curIsNorm then cur
    else
      let nxt := norm conf
      if nxt == cur then cur else confNormLoop norm p n nxt true

def confNfcFP (p : Pol) (s : Str) : Str := confNormLoop nfc p iters s false

/-- `normalize_confusables_cow` (confusables.rs L203): composes at lookup when the text
carries a mark. -/
def confPublicPass (p : Pol) (s : Str) : Str :=
  if !isAscii s && s.any (fun c => isMark c || (0x1100 <= c && c <= 0x1112)) then confPass p (composed s)
  else confPass p s

/-- `normalize_confusables_fixed_cow` (confusables.rs L281). -/
def confPublicLoop (p : Pol) : Nat -> Str -> Str
  | 0, cur => cur
  | n + 1, cur =>
    let nxt := confPublicPass p cur
    if nxt == cur then cur else confPublicLoop p n nxt

def confPublic (p : Pol) (s : Str) : Str :=
  let first := confPublicPass p s
  if first == s then s else confPublicLoop p iters first

/-- `Step::PolicyPreFold` (presets.rs L413): nothing under `numeric`. -/
def policyPreFold (p : Pol) (s : Str) : Str :=
  if p == .numeric then s else confPublic p s

/-- Iterate `f` until it stops changing its input, at most `iters` times (`Step::FixedPoint`,
presets.rs L451). -/
def fixLoop (f : Str -> Str) : Nat -> Str -> Str
  | 0, cur => cur
  | n + 1, cur =>
    let nxt := f cur
    if nxt == cur then cur else fixLoop f n nxt

def fixedPoint (f : Str -> Str) (s : Str) : Str := fixLoop f iters s

end Presets
