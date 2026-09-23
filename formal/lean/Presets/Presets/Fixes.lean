import Presets.Words

/-!
# The proposed fixes, as model variants

Each finding's minimal fix, written against the model so `Bounded.lean` can check it and
`scripts/difftest.py` can count how many outputs it moves on the library's side.

* **F1 `skeleton_key`.** Strip the controls and zero-width characters before the fold
  rather than after it, fold with the NFC-sandwiched fixed point that `canonicalize` uses,
  and close the case-fold loop with NFC: `fixedPoint [foldCase, confusables, nfc]`.
* **F2 key builders under a digit policy.** Under any policy but `numeric`, iterate the
  builder to a fixed point, the way `Step::FixedPoint` iterates `catalog_key`'s core.
* **F3/F4 profiles.** Iterate `Pipeline::process` to a fixed point, as F2 does for the
  builders. `profileTargeted` is the targeted alternative -- the mark strip once more after
  the PUA strip, and the control / zero-width strips ahead of `NORMALIZE` -- and
  `Bounded.lean` shows it is not enough: a PUA code point between a base and a mark still
  separates a composition the fold then misses (`normalize_web_input`).
* **F4 presets.** Recompose at the end of `strip_obfuscation` and `ml_normalize`
  (`NfcIfNonAscii`, as `sort_key` does).
-/

namespace Presets

/-! ## F1 -/

def skeletonKeyFixedSteps : List Step :=
  [.base .resolveDeletions, .base .nfkc, .base .stripBidi, .base (Base.stripInvisible .comparison),
   .base .stripControl, .base .stripZeroWidth, .base .confNfcFP, .base .prototypeFold,
   .fixedPoint [.foldCase, .confusablesCtx, .nfc], .base .collapseWs]

def skeletonKeyFixed (p : Pol) := runGuarded skeletonKeyFixedSteps p

/-! ## F2 -/

def runPolicyFixed (ss : List Step) (p : Pol) (s : Str) : Str :=
  if p == .numeric then runGuarded ss p s else fixedPoint (applySteps p ss) s

def searchKeyFixed (p : Pol) := runPolicyFixed searchKeySteps p
def sortKeyFixed (p : Pol) := runPolicyFixed sortKeySteps p

/-! ## F3 and F4, for the profiles -/

/-- The mark strip a profile runs: `strip_zalgo(0)` for `llm_guardrail`, `strip_accents`
otherwise; both keep one negation overlay on a surviving base. -/
def profileStripsMarks (ss : List PStep) : Bool :=
  ss.contains .stripAccents || ss.contains (.stripZalgo 0)

/-- The targeted alternative: `STRIP_ACCENTS_POST` after `STRIP_PUA`, and the strips ahead of
`NORMALIZE`. -/
def profileStepsTargeted (ss : List PStep) : List PStep :=
  let early := ss.filter fun st => st == .stripControl || st == .stripZeroWidth
  let rest := ss.filter fun st => !(st == .stripControl || st == .stripZeroWidth)
  let (pre, post) := rest.span fun st => st == .resolveDeletions
  let body := pre ++ early ++ post
  if profileStripsMarks ss then
    let (a, b) := body.span fun st => st != .collapseWs
    a ++ [.stripAccents] ++ b
  else body

def profileTargeted (name : String) (p : Pol := .numeric) : Str -> Str :=
  runProfile p (profileStepsTargeted (profileSteps name))

/-- F3/F4 as proposed: the profile iterated to a fixed point. -/
def profileFixed (name : String) (p : Pol := .numeric) : Str -> Str :=
  fixedPoint (runProfile p (profileSteps name))

/-! ## F4, for the presets -/

def stripObfuscationFixed (p : Pol) :=
  runGuarded (stripObfuscationSteps ++ [.base .nfcIfNonAscii]) p

def mlNormalizeFixed (fold : Bool) :=
  runGuarded (mlNormalizeSteps fold ++ [.base .nfcIfNonAscii]) .numeric

/-- Every surface with its fixed variant, for the difftest and the bounded checks. -/
def fixedSurfaces : List (String × (Str -> Str)) :=
  (pols.flatMap fun (n, p) =>
    [ ("skeleton_key@" ++ n, skeletonKeyFixed p),
      ("search_key@" ++ n, searchKeyFixed p),
      ("sort_key@" ++ n, sortKeyFixed p),
      ("strip_obfuscation@" ++ n, stripObfuscationFixed p) ]) ++
  [ ("ml_normalize", mlNormalizeFixed true), ("ml_normalize@nofold", mlNormalizeFixed false) ] ++
  (profileNames.map fun n => ("profile:" ++ n, profileFixed n)) ++
  [ ("profile:llm_guardrail@tr39", profileFixed "llm_guardrail" .tr39),
    ("profile:normalize_web_input@tr39", profileFixed "normalize_web_input" .tr39),
    ("profile:library_catalog_key_eu@tr39", profileFixed "library_catalog_key_eu" .tr39) ]

end Presets
