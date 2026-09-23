import Confusables.Props

/-!
# Bounded-exhaustive theorems and the findings' witnesses (`native_decide`)

`allUpTo n p` quantifies `p` over every string over the 21-letter alphabet of length at
most `n`: 4,288,306 strings at `n = 5`, 204,205 at `n = 4`. These are closed with
`native_decide`, which trusts Lean's compiler as well as its kernel.

Every failing property has a witness theorem (`F…`, the string it fails on) and a
minimality theorem (`F…_minimal`: no shorter string fails). The witnesses were then
reproduced on the library (`repro/`), which is what makes them findings.
-/

namespace Confusables
open Tables

/-! ## What holds -/

-- The fold: idempotent, convergent (never reaches the 8-pass cap), complete under
-- numeric and tr39, detection form-invariant and located by find_confusables, each
-- policy confined to its own rows. Length ≤ 5.
theorem fold_idem_numeric : allUpTo 5 (pFoldIdem .numeric) = true := by native_decide
theorem fold_idem_tr39 : allUpTo 5 (pFoldIdem .tr39) = true := by native_decide
theorem fold_idem_preserve : allUpTo 5 (pFoldIdem .preserve) = true := by native_decide
theorem fold_converges_numeric : allUpTo 5 (pFoldConverges .numeric) = true := by native_decide
theorem fold_converges_tr39 : allUpTo 5 (pFoldConverges .tr39) = true := by native_decide
theorem fold_converges_preserve : allUpTo 5 (pFoldConverges .preserve) = true := by native_decide
theorem fold_complete_numeric : allUpTo 5 (pFoldComplete .numeric) = true := by native_decide
theorem fold_complete_tr39 : allUpTo 5 (pFoldComplete .tr39) = true := by native_decide
theorem detect_nf : allUpTo 5 pDetectNf = true := by native_decide
theorem detect_changes : allUpTo 5 pDetectChanges = true := by native_decide
theorem tr39_scope : allUpTo 5 pTr39Scope = true := by native_decide
theorem preserve_scope : allUpTo 5 pPreserveScope = true := by native_decide
theorem unmapped_sound : allUpTo 5 pUnmappedSound = true := by native_decide

-- skeleton_key: case-folded output, and (tr39/preserve, which bypass the guard) form
-- invariance. Length ≤ 4.
theorem sk_lower_numeric : allUpTo 4 (pSkLower skeletonKey .numeric) = true := by native_decide
theorem sk_lower_tr39 : allUpTo 4 (pSkLower skeletonKey .tr39) = true := by native_decide
theorem sk_nf_tr39 : allUpTo 4 (pSkNf skeletonKey .tr39) = true := by native_decide
theorem sk_nf_preserve : allUpTo 4 (pSkNf skeletonKey .preserve) = true := by native_decide

-- The proposed fixes (Fixes.lean) repair every skeleton_key property, length ≤ 4.
theorem fixed_sk_idem_numeric : allUpTo 4 (pSkIdem Fixes.skeletonKeyFixed .numeric) = true := by
  native_decide
theorem fixed_sk_idem_tr39 : allUpTo 4 (pSkIdem Fixes.skeletonKeyFixed .tr39) = true := by
  native_decide
theorem fixed_sk_idem_preserve : allUpTo 4 (pSkIdem Fixes.skeletonKeyFixed .preserve) = true := by
  native_decide
theorem fixed_sk_nf_numeric : allUpTo 4 (pSkNf Fixes.skeletonKeyFixed .numeric) = true := by
  native_decide
theorem fixed_sk_not_confusable : allUpTo 4 (pSkNotConfusable Fixes.skeletonKeyFixed .numeric) = true := by
  native_decide
theorem fixed_sk_guard : allUpTo 4 pSkGuardFixed = true := by native_decide
theorem fixed_sk_lower : allUpTo 4 (pSkLower Fixes.skeletonKeyFixed .numeric) = true := by
  native_decide

/-! ## What fails: the findings -/

-- F1: skeleton_key is not idempotent. Three independent causes, one witness each.
-- (a) full case folding emits a decomposed sequence that the next call's NFKC composes.
theorem F1a_casefold_decomposes : pSkIdem skeletonKey .numeric [cIota3] = false := by native_decide
theorem F1a_minimal : allUpTo 0 (pSkIdem skeletonKey .numeric) = true := by native_decide
-- (b) the fold emits a base next to a mark it now composes with.
theorem F1b_fold_exposes_composition : pSkIdem skeletonKey .numeric [cYen, cGrave] = false := by
  native_decide
-- (c) StripControl runs after the last fold and joins a base to a mark.
theorem F1c_control_joins : pSkIdem skeletonKey .numeric [cA, cCtl, cGrave] = false := by
  native_decide
-- Each half of the fix alone leaves a failure: both halves are needed.
theorem F1_half_fix_nfkc : pSkIdem Fixes.skeletonStepsNfkcOnly .tr39 [cA, cCtl, cGrave] = false := by
  native_decide
theorem F1_half_fix_strip : pSkIdem Fixes.skeletonStepsStripOnly .tr39 [cIota3] = false := by
  native_decide
-- F1, consequence: the key is flagged by the library's own detector.
theorem F1d_key_is_confusable : pSkNotConfusable skeletonKey .numeric [cYen, cGrave] = false := by
  native_decide
theorem F1d_minimal : allUpTo 1 (pSkNotConfusable skeletonKey .numeric) = true := by native_decide

-- F2: under digit_policy="preserve" the fold's output is confusable.
theorem F2_preserve_incomplete : pFoldComplete .preserve [cDev0] = false := by native_decide
theorem F2_minimal : allUpTo 0 (pFoldComplete .preserve) = true := by native_decide

-- F3: the #458 guard skips a composition NFKC performs (Kirat Rai), so skeleton_key's
-- result depends on the normal form, and on the (digit!) policy.
theorem F3_guard : pSkGuard [cKr, cKr] = false := by native_decide
theorem F3_minimal : allUpTo 1 pSkGuard = true := by native_decide
theorem F3_nf : pSkNf skeletonKey .numeric [cKr, cKr] = false := by native_decide
theorem F3_policy : skeletonKey .numeric [cKr, cKr] ≠ skeletonKey .tr39 [cKr, cKr] := by
  native_decide

-- F4: compose-at-lookup misses the same composition, so the fold is not invariant to
-- the input's normal form (api/safety.rs:106-110).
theorem F4_fold_nf : pFoldNf .numeric [cKr, cKr] = false := by native_decide
theorem F4_minimal : allUpTo 1 (pFoldNf .numeric) = true := by native_decide

end Confusables
