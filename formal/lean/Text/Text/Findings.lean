import Text.Zalgo
import Text.Width
import Text.Whitespace

/-!
# The failed properties, as minimal counterexamples checked by the kernel (`decide`)

Each one was reproduced on the library (README, `scripts/repro.py`). The names follow the
README's findings.
-/

namespace Text.Findings

section Z
open Text.Zalgo

/-- `a`, `U+0301`, `U+0E31` (a class-0 mark), `=`, `U+0338`. -/
def a : Ch := .base false 0
def eq : Ch := .base true 0
def acute : Ch := .mark 230 false 0
def thai : Ch := .mark 0 false 0
def cgj : Ch := .mark 0 false 1
def neg : Ch := .mark 1 true 0

/-- **Z1, minimal** (`max_marks = 1`): two acutes on one base, split by a class-0 mark. The
predicate is false, so the transform keeps both, and the cap of one mark per position is
exceeded. -/
theorem z1_minimal :
    isZalgo 1 [a, acute, thai, acute] = false ∧
    strip 1 [a, acute, thai, acute] = [a, acute, thai, acute] ∧
    worstPosition 1 (strip 1 [a, acute, thai, acute]) = 2 := by decide

/-- **Z1 at the default** (`max_marks = 3`): four acutes on one base. -/
theorem z1_default :
    isZalgo 3 [a, acute, acute, acute, thai, acute] = false ∧
    capOK 3 (strip 3 [a, acute, acute, acute, thai, acute]) = false := by decide

/-- The same with `U+034F COMBINING GRAPHEME JOINER`, which renders as nothing: the
separator does not have to be visible. -/
theorem z1_cgj :
    isZalgo 3 [a, acute, acute, acute, cgj, acute, acute, acute] = false ∧
    worstPosition 3 (strip 3 [a, acute, acute, acute, cgj, acute, acute, acute]) = 6 := by decide

/-- The fix catches both and caps them. -/
theorem z1_fixed :
    isZalgoFixed 1 [a, acute, thai, acute] = true ∧
    capOK 1 (stripFixed 1 [a, acute, thai, acute]) = true ∧
    stripFixed 1 [a, acute, thai, acute] = [a, acute, thai] := by decide

/-- **Z2**: the transform keeps one negation overlay beyond the cap, and the predicate
counts it, so the output of `strip_zalgo` is still zalgo at the same threshold. At
`max_marks = 0` the output is `U+2260` itself. -/
theorem z2_default :
    strip 3 [eq, neg, neg, neg, neg] = [eq, neg, neg, neg, neg] ∧
    isZalgo 3 (strip 3 [eq, neg, neg, neg, neg]) = true := by decide

theorem z2_zero : strip 0 [eq, neg] = [eq, neg] ∧ isZalgo 0 (strip 0 [eq, neg]) = true := by
  decide

theorem z2_fixed :
    isZalgoFixed 3 (stripFixed 3 [eq, neg, neg, neg, neg]) = false ∧
    isZalgoFixed 0 (stripFixed 0 [eq, neg]) = false := by decide

end Z

section W
open Text.Width

def w (ascii : Bool) (cls : Nat) (sel : Sel := .none) (prep : Bool := false) (emo : Bool := false) :
    Sc := { ascii, cls, emo, sel, kb := false, prep }

/-- `U+0600 ARABIC NUMBER SIGN`: `Cf`, zero-width in the table, `Grapheme_Cluster_Break=Prepend`. -/
def numberSign : Sc := w false 0 (prep := true)
def letterA : Sc := w true 1
def vs15 : Sc := w false 0 .vs15
def vs16 : Sc := w false 0 .vs16

/-- **W1**: a cluster that opens with a zero-width `Prepend` measures 0, whatever follows it;
`U+0600` + `a` is one cluster by GB9b and measures 0 while `a` alone measures 1. -/
theorem w1 : gw false [numberSign, letterA] = 0 ∧ gw false [letterA] = 1 ∧
    gwFixed false [numberSign, letterA] = 1 := by decide

/-- **W2**: a stray VS15 on a non-emoji base is ignored, a stray VS16 is not. -/
theorem w2 : gw false [letterA, vs15] = gw false [letterA] ∧
    gw false [letterA, vs16] = 2 := by decide

end W

open Text.Whitespace in
/-- Checked and documented (review D-8): a strip run *after* the collapse can leave two
spaces, which is why the presets always collapse last. -/
theorem d8_order_matters :
    nf (stripControl (collapse [.ch 0, .ws 0, .ctl 0, .ws 0, .ch 1])) = false ∧
    nf (collapse (stripControl [.ch 0, .ws 0, .ctl 0, .ws 0, .ch 1])) = true := by decide

end Text.Findings
