import Emoji.Suite

/-!
# Bounded-exhaustive theorems

Every `theorem … : allUpTo α p N = true` below says: **for every string of length ≤ N
over the alphabet α, property p holds.** They are closed by `native_decide`, which
evaluates the compiled checker (so the trusted base includes the Lean compiler; see the
README). `full` is the 21-class alphabet (all strings ≤ 5: 4,288,306 strings);
`grammar` is the 11 classes the presentation grammar branches on (≤ 7: 21,435,888).

Counterexample theorems (`…_fails`) are closed by `native_decide` on the one witness,
and each is paired with a `…_minimal` theorem showing no shorter string fails.
-/

namespace Emoji
open Tables

def r0 (s : List Char) := replaceEmoji s []
def r1 (s : List Char) := replaceEmoji s [' ']
def rh (s : List Char) := replaceEmoji s ['#']

/-! ## replace_emoji — what holds (shipped code) -/

/-- `replace_emoji(s, " ")` leaves no emoji presentation sequence. -/
theorem replace_space_clean : allUpTo full (pClean r1) 5 = true := by native_decide
/-- `replace_emoji(s, "#")` leaves no emoji presentation sequence. -/
theorem replace_hash_clean : allUpTo full (pClean rh) 5 = true := by native_decide
theorem replace_space_idem : allUpTo full (pIdem r1) 5 = true := by native_decide
theorem replace_hash_idem : allUpTo full (pIdem rh) 5 = true := by native_decide
/-- No `x . space U+0301 €` is ever removed. -/
theorem replace_keeps_text : allUpTo full (pKeeps [cX, cDot, cSP, cMK, cEU] r0) 5 = true := by
  native_decide
/-- A stray keycap survives when nothing in the input could bind it (#996). -/
theorem replace_keeps_stray_keycap :
    allUpTo full (pStrayKeycapKept r0) 5 = true ∧ allUpTo full (pStrayKeycapKept r1) 5 = true := by
  constructor <;> native_decide
theorem replace_space_mark_stays_put : allUpTo full (pMarkStaysPut r1) 5 = true := by native_decide

/-! ## CharWindow is an optimisation (with the general `grow_stop_sound`, `General.lean`) -/

/-- The shipped window (9) equals the unbounded scanner on every string ≤ 5 over the full
alphabet (the ASCII fast path, the window fill and the seam are all exercised). -/
theorem window9_eq_unbounded : allUpTo full (pWindowEq 9 []) 5 = true := by native_decide
/-- A window of 4 already equals the unbounded scanner on every grammar string ≤ 7 —
strings up to 3 over the window, so the growth path, doubling, and pushback are
exercised. -/
theorem window4_eq_unbounded : allUpTo grammar (pWindowEq 4 []) 7 = true := by native_decide
theorem window4_eq_unbounded_space : allUpTo grammar (pWindowEq 4 [' ']) 6 = true := by
  native_decide
/-- …and 3 is not enough: the growth loop's stop rule needs `before ≥ 4`
(`grow_stop_sound`), so `MAX_WINDOW ≥ 4` is a real, currently unasserted, precondition. -/
theorem window3_is_not_enough :
    pWindowEq 3 [] [cM, cV15, cV15, cZ, c1, cV16, cKC] = false := by native_decide

/-! ## demojize — what holds (shipped code) -/

theorem demojize_keeps_text :
    allUpTo full (pKeeps [cX, cDot, cSP, cC, cMK, c1, cStar] demIgnore) 5 = true ∧
    allUpTo full (pKeeps [cX, cDot, cSP, cC, cMK, c1, cStar, cEU] pipelineDemojize) 5 = true := by
  constructor <;> native_decide
theorem demojize_keeps_stray_keycap :
    allUpTo full (pStrayKeycapKept demIgnore) 5 = true ∧
    allUpTo full (pStrayKeycapKept demReplace) 5 = true ∧
    allUpTo full (pStrayKeycapKept pipelineDemojize) 5 = true := by
  refine ⟨?_, ?_, ?_⟩ <;> native_decide
/-- With `errors="replace"` (a visible token is written for a dropped emoji) the #996 and
#200 rules hold. -/
theorem demojize_replace_separates :
    allUpTo full (pNameSeparated demReplace) 5 = true ∧
    allUpTo full (pMarkStaysPut demReplace) 5 = true := by
  constructor <;> native_decide
theorem demojize_preserve_separates :
    allUpTo full (pNameSeparated demPreserve) 5 = true ∧
    allUpTo full (pMarkStaysPut demPreserve) 5 = true := by
  constructor <;> native_decide
/-- `TextPipeline(demojize=True)` = `demojize(errors="ignore")` on every string without
`€` (the #757 class). -/
theorem pipeline_eq_demojize_ignore : allUpTo noEuro pPipelineAgrees 5 = true := by
  native_decide
/-- #1006: a provider claiming the digit alone still takes the whole keycap. -/
theorem provider_keycap_whole : allUpTo full pProviderKeycapWhole 5 = true := by native_decide

/-! ## Counterexamples (shipped code), each minimal -/

/-- F1: `replace_emoji("1️😀⃣", "")` = `"1️⃣"`, a keycap emoji. -/
theorem F1_replace_manufactures_keycap :
    r0 [c1, cV16, cE, cKC] = [c1, cV16, cKC] ∧ pClean r0 [c1, cV16, cE, cKC] = false ∧
    pIdem r0 [c1, cV16, cE, cKC] = false := by native_decide
theorem F1_minimal : allUpTo full (pClean r0) 3 = true ∧ allUpTo full (pIdem r0) 3 = true := by
  constructor <;> native_decide

/-- F2: `demojize("1︎⃣")` = `"1⃣"` (and the pipeline): a keycap, named on
a second pass. -/
theorem F2_demojize_manufactures_keycap :
    demIgnore [c1, cV15, cKC] = [c1, cKC] ∧ demReplace [c1, cV15, cKC] = [c1, cKC] ∧
    pipelineDemojize [c1, cV15, cKC] = [c1, cKC] ∧
    demIgnore [c1, cKC] = "keycap: 1".toList := by native_decide
theorem F2_minimal : allUpTo full (pClean demIgnore) 2 = true := by native_decide

/-- F3: after a dropped unnamed emoji the separator state is lost: `😀🇦x` →
`grinning facex`, and `😀🇦◌́` → `grinning facé`. -/
theorem F3_name_glued :
    pipelineDemojize [cE, cRA, cX] = "grinning facex".toList ∧
    demIgnore [cE, cRA, cX] = "grinning facex".toList ∧
    demReplaceEmpty [cE, cRA, cX] = "grinning facex".toList ∧
    pipelineDemojize [cE, cRA, cMK] = "grinning face".toList ++ [cMK] := by native_decide
theorem F3_minimal :
    allUpTo full (pNameSeparated pipelineDemojize) 2 = true ∧
    allUpTo full (pMarkNotOnName pipelineDemojize) 2 = true := by
  constructor <;> native_decide

/-- F4: a mark on a removed emoji moves onto the preceding letter. -/
theorem F4_mark_moves :
    r0 [cX, cE, cMK] = [cX, cMK] ∧ demIgnore [cX, cRA, cMK] = [cX, cMK] := by native_decide

/-- #757 (documented): the pipeline leaves `€` for the confusable fold. -/
theorem euro_documented : pipelineDemojize [cEU] = [cEU] ∧ demIgnore [cEU] = "euro".toList := by
  native_decide

/-! ## The fixes close F1-F3 (and open nothing on the properties that held) -/

/-- Every property of the suite except the strong mark rule (F4, a design question) and
the `€` agreement (#757, intended) holds for the fixed model on every string ≤ 5. -/
theorem fixed_model_holds :
    ((suite fixed).filter fun c =>
      (c.name.splitOn "mark stays put").length ≤ 1 && (c.name.splitOn "with euro").length ≤ 1
      ).all (fun c => allUpTo c.alpha c.p 5) = true := by
  native_decide

end Emoji
