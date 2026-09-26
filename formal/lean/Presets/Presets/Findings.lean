import Presets.Fixes
import Presets.General

/-!
# The findings, as minimal counterexamples

Each is a closed statement about the model on one short word, checked by the kernel
(`decide`), and each word is reproduced on the library by `repro/*.py`. Next to each: the
same word through the fixed variant from `Fixes.lean`.

Code points are hex; the README spells each word out.
-/

namespace Presets.Findings

open Presets

/-! ## Finding 1: `skeleton_key` is not a fixed point, and misses a confusable pair -/

/-- U+03B0 case-folds to three code points (upsilon, diaeresis, acute); the fold maps the
upsilon to `u`, and nothing recomposes what is left. -/
theorem skeleton_once : skeletonKey .numeric [0x3B0] = [0x75, 0x308, 0x301] := by decide
theorem skeleton_twice : skeletonKey .numeric [0x75, 0x308, 0x301] = [0x1D8] := by decide
theorem skeleton_not_idem :
    skeletonKey .numeric (skeletonKey .numeric [0x3B0]) ≠ skeletonKey .numeric [0x3B0] := by decide

/-- A yen sign with an acute renders as a capital Y with an acute. The fold turns the yen
sign into `Y` after NFKC has already run, so the key keeps a decomposed `y` + acute while
the precomposed capital keys to U+00FD. -/
theorem skeleton_yen_acute : skeletonKey .numeric [0xA5, 0x301] = [0x79, 0x301] := by decide
theorem skeleton_Y_acute : skeletonKey .numeric [0xDD] = [0xFD] := by decide
theorem skeleton_misses_pair : skeletonKey .numeric [0xA5, 0x301] ≠ skeletonKey .numeric [0xDD] := by
  decide

/-- The CGJ is stripped after NFKC and nothing recomposes the pair it separated. -/
theorem skeleton_cgj : skeletonKey .numeric [0x65, 0x34F, 0x301] = [0x65, 0x301] := by decide

theorem skeleton_fixed_once : skeletonKeyFixed .numeric [0x3B0] = [0x1D8] := by decide
theorem skeleton_fixed_pair :
    skeletonKeyFixed .numeric [0xA5, 0x301] = skeletonKeyFixed .numeric [0xDD] := by decide

/-! ## Finding 2: `search_key` and `sort_key` are not fixed points under a digit policy -/

/-- The pre-fold runs on the raw text, before the case fold; the capital has no row and its
lowercase does. -/
theorem search_vy : searchKey .tr39 [0xA760] = [0xA761] := by decide
theorem search_vy2 : searchKey .tr39 [0xA761] = [0x77] := by decide
/-- Transliteration emits `|`, a confusable source, after the only fold has run. -/
theorem search_click : searchKey .preserve [0x1C1] = [0x7C, 0x7C] := by decide
theorem search_click2 : searchKey .preserve [0x7C, 0x7C] = [0x6C, 0x6C] := by decide
/-- `A` with macron case-folds to `a` with macron, whose tr39 row is `a` with tilde. -/
theorem sort_macron : sortKey .tr39 [0x100] = [0x101] := by decide
theorem sort_macron2 : sortKey .tr39 [0x101] = [0xE3] := by decide
/-- Under the default the same words are fixed points: the policy is what breaks it. -/
theorem search_vy_numeric : searchKey .numeric [0xA760] = [0xA761] ∧
    searchKey .numeric [0xA761] = [0xA761] := by decide

theorem search_fixed_vy : searchKeyFixed .tr39 [0xA760] = [0x77] := by decide
theorem sort_fixed_macron : sortKeyFixed .tr39 [0x100] = [0xE3] := by decide

/-! ## Finding 3: `llm_guardrail` and `ml_corpus_normalize` keep an overlay they then orphan -/

/-- The cent sign is a symbol, so its U+0338 survives the mark strip as a negation; the fold
then makes it the letter `c`, and on the second pass the overlay is strikethrough. -/
theorem guard_cent : profile "llm_guardrail" .numeric [0xA2, 0x338] = [0x63, 0x338] := by decide
theorem guard_cent2 : profile "llm_guardrail" .numeric [0x63, 0x338] = [0x63] := by decide
/-- A PUA base survives the mark strip and is removed by `strip_pua` afterwards. -/
theorem corpus_pua : profile "ml_corpus_normalize" .numeric [0xE000, 0x338] = [0x338] := by decide
theorem corpus_pua2 : profile "ml_corpus_normalize" .numeric [0x338] = [] := by decide

theorem guard_fixed : profileFixed "llm_guardrail" .numeric [0xA2, 0x338] = [0x63] := by decide

/-! ## Finding 4: a removed character between two that compose -/

/-- `strip_obfuscation` strips NUL after its last normalization. -/
theorem obf_jamo : stripObfuscation .numeric [0x1100, 0x0, 0x1161] = [0x1100, 0x1161] := by decide
theorem obf_jamo2 : stripObfuscation .numeric [0x1100, 0x1161] = [0xAC00] := by decide
/-- `ml_normalize` strips ZWSP after its last normalization. -/
theorem ml_jamo : mlNormalize true [0x1100, 0x200B, 0x1161] = [0x1100, 0x1161] := by decide
theorem ml_jamo2 : mlNormalize true [0x1100, 0x1161] = [0xAC00] := by decide
/-- `llm_guardrail` strips zero-width characters after `NORMALIZE`. -/
theorem guard_jamo : profile "llm_guardrail" .numeric [0x1100, 0x200B, 0x1161] = [0x1100, 0x1161] := by
  decide
theorem guard_jamo2 : profile "llm_guardrail" .numeric [0x1100, 0x1161] = [0xAC00] := by decide
/-- `normalize_web_input` does not resolve deletions, so a BS is only stripped, at the end. -/
theorem web_bs : profile "normalize_web_input" .numeric [0x65, 0x8, 0x301] = [0x65, 0x301] := by decide
theorem web_bs2 : profile "normalize_web_input" .numeric [0x65, 0x301] = [0xE9] := by decide
/-- And a PUA code point, which `strip_pua` removes after the fold. The targeted fix
(strips ahead of `NORMALIZE`) cannot reach this one. -/
theorem web_pua : profileTargeted "normalize_web_input" .numeric [0x49, 0xE000, 0x301] = [0x49, 0x301] := by
  decide

theorem obf_fixed : stripObfuscationFixed .numeric [0x1100, 0x0, 0x1161] = [0xAC00] := by decide
theorem web_fixed : profileFixed "normalize_web_input" .numeric [0x65, 0x8, 0x301] = [0xE9] := by decide

/-! ## Finding 8: the fold moves a mark past `canonicalize`'s cap (#1072)

The cap (three marks of one class on a base) runs before the fold. `ģ` keeps its cedilla
below the letter (class 202) and the three marks above (class 230) are within the cap; the
fold then turns `ģ` into `ġ`, whose dot is a fourth mark above, and the next call cuts
one. Under `tr39` and `preserve` the pre-fold folds before the cap, so only `numeric`
moves. Found in the library by the `presets` fuzz target, after the model: its alphabet
had no fold that moves a mark, and this word needs one. -/

theorem canon_gcedilla_once :
    canonicalize .numeric [0x123, 0x301, 0x308, 0x303] = [0x121, 0x301, 0x308, 0x303] := by decide
theorem canon_gcedilla_twice :
    canonicalize .numeric [0x121, 0x301, 0x308, 0x303] = [0x121, 0x301, 0x308] := by decide
theorem canon_gcedilla_tr39 :
    canonicalize .tr39 [0x123, 0x301, 0x308, 0x303] = [0x121, 0x301, 0x308] := by decide

theorem canon_fixed_gcedilla :
    canonicalizeFixed .numeric [0x123, 0x301, 0x308, 0x303] = [0x121, 0x301, 0x308] := by decide

/-! ## Which step moves the output

`General.run_not_idem_of`: when a second pass differs, some step of the list moves the first
output. `applySteps_eq_run` puts the presets in that form; these name the step, and in every
case it is a normalizer or a fold that runs *before* a step which re-opens its work. -/

theorem applySteps_eq_run (p : Pol) (ss : List Step) (s : Str) :
    applySteps p ss s = General.run (ss.map (Step.apply p)) s := by
  unfold applySteps General.run
  induction ss generalizing s with
  | nil => rfl
  | cons st ss ih => simp only [List.foldl_cons, List.map_cons]; exact ih _

theorem skeleton_moved_by_nfkc :
    Base.apply .numeric .nfkc (skeletonKey .numeric [0x3B0]) ≠ skeletonKey .numeric [0x3B0] := by decide
theorem search_moved_by_prefold :
    Base.apply .tr39 .policyPreFold (searchKey .tr39 [0xA760]) ≠ searchKey .tr39 [0xA760] := by decide
theorem guard_moved_by_mark_strip :
    PStep.apply .numeric (.stripZalgo 0) (profile "llm_guardrail" .numeric [0xA2, 0x338]) ≠
      profile "llm_guardrail" .numeric [0xA2, 0x338] := by decide
theorem canon_moved_by_zalgo :
    Base.apply .numeric (.zalgo 3) (canonicalize .numeric [0x123, 0x301, 0x308, 0x303]) ≠
      canonicalize .numeric [0x123, 0x301, 0x308, 0x303] := by decide
theorem obf_moved_by_nfkc :
    Base.apply .numeric .nfkc (stripObfuscation .numeric [0x1100, 0x0, 0x1161]) ≠
      stripObfuscation .numeric [0x1100, 0x0, 0x1161] := by decide

/-! ## A digit policy folds letters on the builders with no fold of their own

`search_key` and `sort_key` document no confusable step, and `digit_policy` as folding
"digit variants". Under `tr39` or `preserve` the pre-fold is the whole Latin table. -/

theorem search_er_numeric : searchKey .numeric [0x440] = [0x72] := by decide
theorem search_er_preserve : searchKey .preserve [0x440] = [0x70] := by decide
theorem sort_er_preserve : sortKey .preserve [0x440] = [0x70] := by decide

/-! ## The fast-path guard's `union` drops `prototype` (latent)

No shipped preset puts `PrototypeFold` inside a `FixedPoint`, so this is not reachable
through the library. The model shows what would happen if one did. -/

def hypothetical : List Step := [.fixedPoint [.prototypeFold]]

theorem union_drops_prototype : (forSteps hypothetical).prototype = false := by decide
theorem guard_skips : runGuarded hypothetical .numeric [0x49] = [0x49] := by decide
theorem steps_change : applySteps .numeric hypothetical [0x49] = [0x6C] := by decide

end Presets.Findings
