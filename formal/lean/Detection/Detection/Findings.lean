import Detection.Props
import Detection.SmuggledProps
import Detection.Scripts

/-!
# The failed properties, as minimal counterexamples the kernel checks (`decide`)

Each is reproduced on the library by `repro/*.py`; the README gives the output.
-/

namespace Detection

open C

/-- All words of length at most `n` over `alpha`. -/
def words (alpha : List α) : Nat → List (List α)
  | 0 => [[]]
  | n + 1 => [] :: (words alpha n).flatMap (fun w => alpha.map (fun c => c :: w))

/-! ## Finding 1: a deletion `canonicalize` makes inside a word goes unreported -/

/-- Cleaner soundness, stated over every class: whatever `canonicalize` deletes from
between two letters is reported, unless the documentation spares it. Exactly one class
fails, the deprecated format controls. -/
theorem f1_only_fmt :
    C.all.filter (fun c => canonDeletes c && !documentedSpare c && !hasAnomalies [.a, c, .a])
      = [.fmt] := by decide

theorem f1_fixed :
    C.all.all (fun c => !canonDeletes c || documentedSpare c || hasAnomaliesFixed [.a, c, .a])
      = true := by decide

/-! ## Finding 2: a second `RLM` defeats the number-run rule -/

/-- The rule as documented: in a token that is majority-Latin or letterless, an `RLM`
immediately before a digit is reported. -/
def rlmRuleApplies (t : List C) : Bool :=
  t.all (fun c => !c.boundary) && (majLatin t || noLetters t) && anyRlmBeforeDigit t

theorem f2_counterexample :
    rlmRuleApplies [.rlm, .rlm, .d] = true ∧ classify [.rlm, .rlm, .d] = false ∧
    classify [.rlm, .d] = true ∧ classifyFixed [.rlm, .rlm, .d] = true := by decide

/-- Minimal: every token of length two or less that the rule covers is reported. -/
theorem f2_minimal :
    (words C.all 2).all (fun t => !rlmRuleApplies t || classify t) = true := by decide +kernel

/-! ## Finding 3: canonically equivalent inputs get different verdicts -/

theorem f3_isolate :
    nfc [.p, .rli] = [.p, .rli] ∧ nfd [.p, .rli] = [.a, .m, .rli] ∧
    hasAnomalies [.p, .rli] = false ∧ hasAnomalies [.a, .m, .rli] = true := by decide

theorem f3_joiner :
    hasAnomalies [.p, .nj, .p] = false ∧ hasAnomalies (nfd [.p, .nj, .p]) = true := by decide

theorem f3_rlm :
    hasAnomalies [.p, .rlm, .d] = false ∧ hasAnomalies (nfd [.p, .rlm, .d]) = true := by decide

/-- Minimal: no word of length one separates NFC from NFD. -/
theorem f3_minimal :
    (words C.all 1).all (fun t => hasAnomalies (nfc t) == hasAnomalies (nfd t)) = true := by
  decide +kernel

/-! ## Finding 6: a payload next to a carrier of its own scheme -/

/-- A variation-selector payload `hi` after an emoji that already carries `VS16`: the
selector joins the run as byte `0x0F`, so the payload has no `text` and `smuggled` does
not fire. -/
theorem f6_vs :
    decode [.x, .vsb 15, .vsb 104, .vsb 105, .x] = [⟨.variationBytes, 1, 3, [15, 104, 105]⟩] ∧
    asciiPrintable [15, 104, 105] = false := by decide

/-- A zero-width payload `hi` after one stray `U+200B`: the frame shifts by a bit and the
decoder reports the printable text `44`, which nobody encoded. -/
theorem f6_zw :
    decode (.x :: .z0 :: encZW [104, 105] ++ [.x]) = [⟨.zeroWidthBinary, 1, 17, [52, 52]⟩] ∧
    asciiPrintable [52, 52] = true := by decide

/-- ...and after a stray `U+200C` it reports no text at all. -/
theorem f6_zw_nj :
    decode (.x :: .z1 :: encZW [104, 105] ++ [.x]) = [⟨.zeroWidthBinary, 1, 17, [180, 52]⟩] := by
  decide

/-! ## Finding 5: `Script`, not `Script_Extensions` -/

theorem f5_danda : libMixed [.ch .beng, .danda] = true ∧ specScx [.ch .beng, .danda] = false := by
  decide

end Detection
