import Presets.Fixes

/-!
# Bounded exhaustive checks (`native_decide`)

`W3` is every word of length at most 3 over the 38-letter input alphabet (56,355 words), the
same words `scripts/difftest.py --exhaustive 3` sends through the library, on which the model
and the library agree exactly. So each result here about the *current* model is also a
result about the built library on those words.

`S4` is every word of length exactly 4 over the 23-letter sub-alphabet that carries the
findings (279,841 words), used for the headline properties.
-/

namespace Presets.Bounded

open Presets

def W3 : List Str := wordsUpTo inputAlphabet 3
def S4 : List Str := wordsOfLen small 4

theorem W3_size : W3.length = 56355 := by native_decide

/-! ## Idempotence that holds

Each property is a `Bool` over a word list, stated for `W3` and again for `S4`. -/

def holdIdem (ws : List Str) : Bool :=
  [Pol.numeric, .tr39, .preserve].all (fun p =>
    idemOn (canonicalize p) ws && idemOn (canonicalizeStrict p) ws && idemOn (catalogKey p) ws)
  && idemOn (searchKey .numeric) ws && idemOn (sortKey .numeric) ws && idemOn stripFormat ws
  && ["code_context", "library_catalog_key_eu", "rag_ingest", "scholarly_cyrillic_iso9",
      "search_index"].all (fun n => idemOn (profile n .numeric) ws)
  && idemOn (profile "library_catalog_key_eu" .tr39) ws

/-- `canonicalize`, `canonicalize_strict` and `catalog_key` under all three policies,
`search_key` and `sort_key` under the default, `strip_format`, and five of the eight
profiles are fixed points on every word of `W3`. -/
theorem idem_W3 : holdIdem W3 := by native_decide
/-- ... and on every word of `S4`. -/
theorem idem_S4 : holdIdem S4 := by native_decide

/-! ## Idempotence that fails: how often, on `W3` -/

theorem skeleton_key_failures :
    (idemFailures (skeletonKey .numeric) W3).length = 5092 ∧
    (idemFailures (skeletonKey .tr39) W3).length = 5174 ∧
    (idemFailures (skeletonKey .preserve) W3).length = 5092 := by native_decide
theorem search_key_policy_failures :
    (idemFailures (searchKey .tr39) W3).length = 8206 ∧
    (idemFailures (searchKey .preserve) W3).length = 8206 := by native_decide
theorem sort_key_policy_failures :
    (idemFailures (sortKey .tr39) W3).length = 8206 ∧
    (idemFailures (sortKey .preserve) W3).length = 8206 := by native_decide
theorem strip_obfuscation_failures :
    (idemFailures (stripObfuscation .numeric) W3).length = 1 := by native_decide
theorem ml_normalize_failures : (idemFailures (mlNormalize true) W3).length = 2 := by native_decide
theorem profile_failures :
    (idemFailures (profile "llm_guardrail" .numeric) W3).length = 331 ∧
    (idemFailures (profile "ml_corpus_normalize" .numeric) W3).length = 80 ∧
    (idemFailures (profile "normalize_web_input" .numeric) W3).length = 112 := by native_decide

/-! ## The fast-path guard is sound for every shipped preset, on `W3`

`run_static`'s guard (`classify`) never returns a borrow, or a lone whitespace fold, where
the full step list would produce something else. -/

def guardSound (ws : List Str) : Bool :=
  [canonicalizeSteps, canonicalizeStrictSteps, stripObfuscationSteps, searchKeySteps,
    catalogKeySteps, sortKeySteps, skeletonKeySteps, stripFormatSteps, mlNormalizeSteps true,
    mlNormalizeSteps false].all fun ss => agreeOn (runGuarded ss .numeric) (applySteps .numeric ss) ws

theorem guard_sound_W3 : guardSound W3 := by native_decide
theorem guard_sound_S4 : guardSound S4 := by native_decide

/-! ## The proposed fixes are fixed points -/

def fixesIdem (ws : List Str) : Bool :=
  [Pol.numeric, .tr39, .preserve].all (fun p =>
    idemOn (skeletonKeyFixed p) ws && idemOn (searchKeyFixed p) ws && idemOn (sortKeyFixed p) ws
    && idemOn (stripObfuscationFixed p) ws)
  && idemOn (mlNormalizeFixed true) ws && idemOn (mlNormalizeFixed false) ws
  && profileNames.all (fun n => idemOn (profileFixed n .numeric) ws && idemOn (profileFixed n .tr39) ws)

theorem fixes_idem_W3 : fixesIdem W3 := by native_decide
theorem fixes_idem_S4 : fixesIdem S4 := by native_decide

/-- The fixed skeleton is also NFC on every word, which the current one is not. -/
theorem skeleton_fixed_nfc :
    W3.all (fun w => nfc (skeletonKeyFixed .numeric w) == skeletonKeyFixed .numeric w) &&
    S4.all (fun w => nfc (skeletonKeyFixed .numeric w) == skeletonKeyFixed .numeric w) := by
  native_decide

/-- The targeted profile fix (one more mark strip, strips ahead of NORMALIZE) is not enough
for `normalize_web_input`: a PUA code point still separates a composition. -/
theorem targeted_insufficient :
    (idemFailures (profileTargeted "normalize_web_input" .numeric) W3).length = 28 := by native_decide

end Presets.Bounded
