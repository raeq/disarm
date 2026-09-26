import Presets.Steps

/-!
# Presets and profiles, as step lists in executed order

`Base` mirrors `presets::Step` (src/presets.rs L64-L143) minus `FixedPoint`, which `Step`
adds with a list of `Base` (the Rust asserts the inner list never nests one, L609-L618).
Each preset is its `static_steps!` list transcribed literally. `run` is `run_static`
(L950): the fast-path guard under `numeric`, then the steps.

`PStep` mirrors `PipelineSteps` (src/pipeline.rs L16-L127) and `stepOrder` is
`STEP_ORDER` (L140-L186); a profile is the subset its `ProfileSpec` turns on.
-/

namespace Presets

inductive InvPol
  | comparison
  | rendering
  deriving DecidableEq, Repr

inductive Base
  | resolveDeletions
  | nfkc
  | nfc
  | nfcIfNonAscii
  | stripBidi
  | stripInvisible (p : InvPol)
  | stripControl
  | stripZeroWidth
  | collapseWs
  | zalgo (cap : Nat)
  /-- Not in the Rust at `595fbda`: the step #1072 added, for the fix `Fixes.lean` models. -/
  | zalgoIfOver (cap : Nat)
  | dropRepeatedMarks
  | foldCase
  | stripAccents
  | translitPreserve
  | translitPreservingLatin
  | confusablesCtx
  | policyPreFold
  | confNfcFP
  /-- `ConfusablesMarkFixedPointCtx`: the cross-script mark strip is the identity on this
  domain (every mark in it is `Inherited`), so the outer loop exits after one round. -/
  | confMarkFP
  | prototypeFold
  | demojize
  deriving DecidableEq, Repr

inductive Step
  | base (b : Base)
  | fixedPoint (inner : List Base)
  deriving DecidableEq, Repr

def Base.apply (p : Pol) : Base -> Str -> Str
  | .resolveDeletions, s => Presets.resolveDeletions s
  | .nfkc, s => Presets.nfkc s
  | .nfc, s => Presets.nfc s
  | .nfcIfNonAscii, s => if Presets.isAscii s then s else Presets.nfc s
  | .stripBidi, s => Presets.stripBidi s
  | .stripInvisible .comparison, s => Presets.stripInvisibleCmp s
  | .stripInvisible .rendering, s => Presets.stripInvisibleRender s
  | .stripControl, s => Presets.stripControl s
  | .stripZeroWidth, s => Presets.stripZeroWidth s
  | .collapseWs, s => Presets.collapseWs s
  | .zalgo cap, s => Presets.zalgo cap s
  | .zalgoIfOver cap, s => Presets.zalgoIfOver cap s
  | .dropRepeatedMarks, s => Presets.dropRepeatedMarks s
  | .foldCase, s => Presets.foldCase s
  | .stripAccents, s => Presets.stripAccents s
  | .translitPreserve, s => Presets.translitPreserve s
  | .translitPreservingLatin, s => Presets.translitPreservingLatin s
  | .confusablesCtx, s => Presets.confPass p s
  | .policyPreFold, s => Presets.policyPreFold p s
  | .confNfcFP, s => Presets.confNfcFP p s
  | .confMarkFP, s => Presets.confNfcFP p s
  | .prototypeFold, s => Presets.prototypeFold p s
  | .demojize, s => s

def applyBases (p : Pol) (bs : List Base) (s : Str) : Str := bs.foldl (fun acc b => b.apply p acc) s

def Step.apply (p : Pol) : Step -> Str -> Str
  | .base b, s => b.apply p s
  | .fixedPoint inner, s => Presets.fixedPoint (applyBases p inner) s

def applySteps (p : Pol) (ss : List Step) (s : Str) : Str := ss.foldl (fun acc st => st.apply p acc) s

/-! ## The fast-path guard (presets.rs L500-L990) -/

structure Mask where
  controls : Bool := false
  collapseWs : Bool := false
  foldCase : Bool := false
  confusables : Bool := false
  nfkc : Bool := false
  marks : Bool := false
  stripAccents : Bool := false
  zalgoCap : Option Nat := none
  bidi : Bool := false
  zeroWidth : Bool := false
  invisible : Bool := false
  transliterate : Bool := false
  demojize : Bool := false
  prototype : Bool := false
  deriving Repr

def Mask.addBase (m : Mask) : Base -> Mask
  | .stripControl | .resolveDeletions => { m with controls := true }
  | .collapseWs => { m with collapseWs := true }
  | .foldCase => { m with foldCase := true }
  | .prototypeFold => { m with prototype := true }
  | .policyPreFold => m
  | .confusablesCtx | .confNfcFP | .confMarkFP => { m with confusables := true, marks := true }
  | .nfkc | .nfc | .nfcIfNonAscii => { m with nfkc := true, marks := true }
  | .zalgo cap | .zalgoIfOver cap => { m with marks := true, zalgoCap := some cap }
  | .dropRepeatedMarks => { m with marks := true }
  | .stripAccents => { m with marks := true, stripAccents := true }
  | .stripBidi => { m with bidi := true }
  | .stripZeroWidth => { m with zeroWidth := true }
  | .stripInvisible _ => { m with invisible := true }
  | .translitPreserve | .translitPreservingLatin => { m with transliterate := true }
  | .demojize => { m with demojize := true }

/-- `Actionable::union` (presets.rs L646), **as written**: it ORs every field except
`prototype`. -/
def Mask.union (a o : Mask) : Mask :=
  { controls := a.controls || o.controls
    collapseWs := a.collapseWs || o.collapseWs
    foldCase := a.foldCase || o.foldCase
    confusables := a.confusables || o.confusables
    nfkc := a.nfkc || o.nfkc
    marks := a.marks || o.marks
    stripAccents := a.stripAccents || o.stripAccents
    zalgoCap := match a.zalgoCap, o.zalgoCap with
      | some x, some y => some (min x y)
      | some x, none => some x
      | none, y => y
    bidi := a.bidi || o.bidi
    zeroWidth := a.zeroWidth || o.zeroWidth
    invisible := a.invisible || o.invisible
    transliterate := a.transliterate || o.transliterate
    demojize := a.demojize || o.demojize
    prototype := a.prototype }

def maskOfBases (bs : List Base) (m : Mask := {}) : Mask := bs.foldl Mask.addBase m

/-- `Actionable::for_steps` (presets.rs L531). -/
def forSteps (ss : List Step) : Mask :=
  ss.foldl (fun m st =>
    match st with
    | .base b => m.addBase b
    | .fixedPoint inner => m.union (maskOfBases inner)) {}

def isAsciiFoldWs (b : Nat) : Bool := (0x09 <= b && b <= 0x0D) || (0x1C <= b && b <= 0x20)
def isRemovedControl (b : Nat) : Bool := (b < 0x20 && !isAsciiFoldWs b) || b == 0x7F
/-- `is_ascii_confusable_latin`: the three ASCII sources of the Latin table. -/
def isAsciiConfusable (b : Nat) : Bool := b == 0x22 || b == 0x60 || b == 0x7C

def nfkcChanges (c : Nat) : Bool := nfkc [c] != [c]
def decomposesToMark (c : Nat) : Bool := (nfd [c]).any isMark
def nfdMarkRunExceeds (c : Nat) (cap : Nat) : Bool := decide (((nfd [c]).filter isMark).length > cap)

/-- `is_conjoining_jamo` (presets.rs L786). -/
def isConjoiningJamo (c : Nat) : Bool :=
  (0x1100 <= c && c <= 0x11FF) || (0xA960 <= c && c <= 0xA97F) || (0xD7B0 <= c && c <= 0xD7FF)

/-- `acts_on_nonascii` (presets.rs L732). -/
def actsOnNonascii (c : Nat) (m : Mask) : Bool :=
  m.transliterate
  || (m.marks && isMark c)
  || (m.controls && isControl c && !isFoldWs c)
  || (m.collapseWs && (isFoldWs c || isBlankRender c))
  || (m.bidi && isBidiOrFormat c)
  || (m.zeroWidth && isZeroWidth c)
  || (m.invisible && (isTag c || isVS c || isNonchar c || isPUA c || isDIF c || c == 0x34F))
  || (m.foldCase && (foldT c).isSome)
  || (m.confusables && (conf_numeric c).isSome)
  || (m.nfkc && (isConjoiningJamo c || nfkcChanges c))
  || (m.stripAccents && decomposesToMark c)
  || (match m.zalgoCap with
      | some cap => nfdMarkRunExceeds c cap
      | none => false)

inductive Guard
  | inert
  | whitespaceOnly
  | actionable
  deriving DecidableEq, Repr

/-- `classify` (presets.rs L829). -/
def classify (m : Mask) (s : Str) : Guard :=
  let n := s.length
  let r := (s.zipIdx).foldl (fun (acc : Option Guard × Bool × Bool) (b, i) =>
    let (res, prevSpace, sawWs) := acc
    match res with
    | some _ => acc
    | none =>
      if b < 0x80 then
        if (m.controls && isRemovedControl b) || (m.foldCase && 0x41 <= b && b <= 0x5A)
            || (m.confusables && isAsciiConfusable b)
            || (m.prototype && (b == 0x49 || b == 0x30 || b == 0x31)) then
          (some .actionable, prevSpace, sawWs)
        else if m.collapseWs && isAsciiFoldWs b && b != 0x20 then (none, false, true)
        else if m.collapseWs && b == 0x20 then
          (none, true, sawWs || i == 0 || i + 1 == n || prevSpace)
        else (none, false, sawWs)
      else if actsOnNonascii b m then (some .actionable, prevSpace, sawWs)
      else (none, false, sawWs)) (none, false, false)
  match r.1 with
  | some g => g
  | none => if r.2.2 then .whitespaceOnly else .inert

/-- `run_static` (presets.rs L950). The guard runs only under `numeric`. -/
def runGuarded (ss : List Step) (p : Pol) (s : Str) : Str :=
  if p == .numeric then
    match classify (forSteps ss) s with
    | .inert => s
    | .whitespaceOnly => collapseWs s
    | .actionable => applySteps p ss s
  else applySteps p ss s

/-! ## The presets, in executed order -/

def canonicalizeSteps : List Step := ([.resolveDeletions, .policyPreFold, .nfkc, .stripBidi,
  .stripInvisible .comparison, .stripControl, .stripZeroWidth, .collapseWs, .dropRepeatedMarks,
  .zalgo 3, .nfc, .confNfcFP, .dropRepeatedMarks] : List Base).map Step.base

def canonicalizeStrictSteps : List Step := ([.resolveDeletions, .policyPreFold, .nfkc, .stripBidi,
  .stripZeroWidth, .stripControl, .stripInvisible .comparison, .confMarkFP, .dropRepeatedMarks,
  .zalgo 3, .collapseWs, .nfc] : List Base).map Step.base

def stripObfuscationSteps : List Step := ([.resolveDeletions, .policyPreFold, .nfkc, .zalgo 0,
  .stripBidi, .stripZeroWidth, .stripInvisible .comparison, .confusablesCtx, .stripAccents,
  .stripControl, .collapseWs] : List Base).map Step.base

def searchKeySteps : List Step := ([.resolveDeletions, .policyPreFold, .nfkc, .stripBidi,
  .stripInvisible .comparison, .foldCase, .translitPreserve, .stripAccents, .foldCase, .stripControl,
  .stripZeroWidth, .collapseWs] : List Base).map Step.base

def catalogKeySteps : List Step :=
  [.base .resolveDeletions, .base .policyPreFold, .base .nfkc, .base .stripBidi,
   .base (Base.stripInvisible .comparison), .base .foldCase,
   .fixedPoint [.translitPreserve, .confusablesCtx, .stripAccents],
   .base .foldCase, .base .stripControl, .base .stripZeroWidth, .base .collapseWs]

def sortKeySteps : List Step := ([.resolveDeletions, .policyPreFold, .nfkc, .stripBidi,
  .stripInvisible .comparison, .foldCase, .translitPreservingLatin, .foldCase, .stripControl,
  .stripZeroWidth, .collapseWs, .dropRepeatedMarks, .zalgo 3, .nfcIfNonAscii] : List Base).map Step.base

def skeletonKeySteps : List Step :=
  [.base .resolveDeletions, .base .nfkc, .base .stripBidi, .base (Base.stripInvisible .comparison),
   .base .confusablesCtx, .base .prototypeFold, .fixedPoint [.foldCase, .confusablesCtx],
   .base .stripControl, .base .stripZeroWidth, .base .collapseWs]

def stripFormatSteps : List Step := ([.stripBidi, .stripInvisible .rendering, .stripControl,
  .stripZeroWidth, .collapseWs] : List Base).map Step.base

/-- `ml_normalize` with `lang = None` and `emoji = "cldr"`: `Transliterate` is skipped
without a language, and `Demojize` is the identity on this domain. -/
def mlNormalizeSteps (fold : Bool) : List Step :=
  (([.resolveDeletions, .nfkc, .demojize, .stripAccents, .demojize] : List Base)
    ++ (if fold then [Base.foldCase] else []) ++ [Base.stripControl, Base.stripZeroWidth, Base.collapseWs]).map Step.base

def canonicalize (p : Pol) := runGuarded canonicalizeSteps p
def canonicalizeStrict (p : Pol) := runGuarded canonicalizeStrictSteps p
def stripObfuscation (p : Pol) := runGuarded stripObfuscationSteps p
def searchKey (p : Pol) := runGuarded searchKeySteps p
def catalogKey (p : Pol) := runGuarded catalogKeySteps p
def sortKey (p : Pol) := runGuarded sortKeySteps p
def skeletonKey (p : Pol) := runGuarded skeletonKeySteps p
def stripFormat := runGuarded stripFormatSteps .numeric
def mlNormalize (fold : Bool) := runGuarded (mlNormalizeSteps fold) .numeric

/-! ## Profiles (src/pipeline.rs) -/

inductive PStep
  | resolveDeletions
  | normalize
  | stripZalgo (cap : Nat)
  | stripBidi
  | stripPlane14
  | demojize
  | stripAccents
  | transliterate
  | confusables
  | foldCase
  | confusablesPost
  | foldCasePost
  | stripControl
  | stripZeroWidth
  | stripPua
  | collapseWs
  deriving DecidableEq, Repr

/-- `STEP_ORDER`, as the rank of each step. -/
def PStep.rank : PStep -> Nat
  | .resolveDeletions => 0
  | .normalize => 1
  | .stripZalgo _ => 2
  | .stripBidi => 3
  | .stripPlane14 => 4
  | .demojize => 5
  | .stripAccents => 6
  | .transliterate => 7
  | .confusables => 8
  | .foldCase => 9
  | .confusablesPost => 10
  | .foldCasePost => 11
  | .stripControl => 12
  | .stripZeroWidth => 13
  | .stripPua => 14
  | .collapseWs => 15

/-- `apply_step_into`, for a pipeline whose normalize form is NFKC (every profile that has
one). The confusables arm is the fixed point against NFKC (pipeline.rs L553-L600). -/
def PStep.apply (p : Pol) : PStep -> Str -> Str
  | .resolveDeletions, s => Presets.resolveDeletions s
  | .normalize, s => Presets.nfkc s
  | .stripZalgo cap, s => Presets.zalgo cap s
  | .stripBidi, s => Presets.stripBidi s
  | .stripPlane14, s => s
  | .demojize, s => s
  | .stripAccents, s => Presets.stripAccents s
  | .transliterate, s => Presets.translitIgnore s
  | .confusables, s => Presets.confNormLoop Presets.nfkc p iters s false
  | .foldCase, s => Presets.foldCase s
  | .confusablesPost, s => Presets.confNormLoop Presets.nfkc p iters s false
  | .foldCasePost, s => Presets.foldCase s
  | .stripControl, s => Presets.stripControl s
  | .stripZeroWidth, s => Presets.stripZeroWidth s
  | .stripPua, s => Presets.stripPua s
  | .collapseWs, s => Presets.collapseWs s

def runProfile (p : Pol) (ss : List PStep) (s : Str) : Str := ss.foldl (fun acc st => st.apply p acc) s

def profileSteps : String -> List PStep
  | "library_catalog_key_eu" => [.normalize, .stripPlane14, .stripAccents, .transliterate, .confusables,
      .foldCase, .confusablesPost, .foldCasePost, .stripControl, .stripZeroWidth, .stripPua, .collapseWs]
  | "llm_guardrail" => [.resolveDeletions, .normalize, .stripZalgo 0, .stripBidi, .stripPlane14,
      .stripAccents, .confusables, .foldCase, .confusablesPost, .foldCasePost, .stripControl,
      .stripZeroWidth, .stripPua, .collapseWs]
  | "ml_corpus_normalize" => [.normalize, .stripPlane14, .demojize, .stripAccents, .foldCase,
      .stripControl, .stripZeroWidth, .stripPua, .collapseWs]
  | "normalize_web_input" => [.normalize, .confusables, .stripControl, .stripZeroWidth, .stripPua,
      .collapseWs]
  | "rag_ingest" => [.resolveDeletions, .normalize, .stripBidi, .stripPlane14, .stripAccents,
      .transliterate, .stripControl, .stripZeroWidth, .stripPua, .collapseWs]
  | "scholarly_cyrillic_iso9" => [.normalize, .stripPlane14, .transliterate, .foldCase, .stripControl,
      .stripZeroWidth, .stripPua, .collapseWs]
  | "search_index" => [.normalize, .stripPlane14, .stripAccents, .transliterate, .foldCase,
      .stripControl, .stripZeroWidth, .stripPua, .collapseWs]
  | "code_context" => [.stripBidi, .stripControl, .stripZeroWidth]
  | _ => []

def profileNames : List String := ["code_context", "library_catalog_key_eu", "llm_guardrail",
  "ml_corpus_normalize", "normalize_web_input", "rag_ingest", "scholarly_cyrillic_iso9",
  "search_index"]

def profile (name : String) (p : Pol := .numeric) : Str -> Str := runProfile p (profileSteps name)

end Presets
