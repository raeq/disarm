import Text.Enum
import Text.Zalgo

/-!
# Bounded exhaustive checks for `is_zalgo` / `strip_zalgo` (`native_decide`)

Every word of length `≤ 7` over `a = U+0061`, `e = '='`, `A = U+0301` (class 230),
`U = U+0316` (220), `O = U+0334` (1), `N = U+0338` (1, negation), `T = U+0E31` (0):
960,800 words, each at `max_marks` 0, 1, 2 and 3. `scripts/difftest.py` runs the library on
exactly these words, and the model agrees with it on every one, so each result about the
*current* model is also a result about the built library up to this bound.

`native_decide` trusts Lean's compiler as well as its kernel.
-/

namespace Text.Zalgo

def alpha : List Ch :=
  [.base false 0, .base true 0, .mark 230 false 0, .mark 220 false 0, .mark 1 false 0,
   .mark 1 true 0, .mark 0 false 0]

abbrev N : Nat := 7

def allK (p : Nat → List Ch → Bool) : Bool :=
  Text.allUpTo alpha N (fun s => [0, 1, 2, 3].all (fun k => p k s))

def hasNeg (s : List Ch) : Bool := s.any fun c => match c with | .mark _ true _ => true | _ => false

/-! ## The current code -/

/-- The fast path is only an optimization: when the predicate is false the filtering pass
would have returned NFD(input) anyway. -/
theorem slow_eq_fast : allK (fun k s => isZalgo k s || stripSlow k s == canon s) = true := by
  native_decide

/-- Idempotence. -/
theorem strip_idem : allK (fun k s => strip k (strip k s) == strip k s) = true := by
  native_decide

/-- The cap holds, and the output is not zalgo, on every input **without** a class-0 mark and
without a negation overlay — that is, everywhere outside the shapes of Findings Z1 and Z2. -/
theorem cap_holds_elsewhere :
    allK (fun k s => !noClass0Mark s || hasNeg s ||
      (capOK k (strip k s) && !isZalgo k (strip k s))) = true := by
  native_decide

/-- Without a class-0 mark the predicate is exactly "some position carries more than `k`"
(up to the negation exemption, which only the transform makes). -/
theorem pred_is_position_count_elsewhere :
    allK (fun k s => !noClass0Mark s || hasNeg s || (isZalgo k s == (worstPosition k s > k))) = true := by
  native_decide

/-! ## The fix as proposed -/

theorem fixed_cap : allK (fun k s => capOK k (stripFixed k s)) = true := by
  native_decide

/-- The pairing #788 asked for, in both directions: the transform leaves alone what the
predicate calls ordinary, and its output is never called zalgo. -/
theorem fixed_pairing :
    allK (fun k s => (isZalgoFixed k s || stripFixed k s == canon s) &&
      !isZalgoFixed k (stripFixed k s)) = true := by
  native_decide

theorem fixed_idem : allK (fun k s => stripFixed k (stripFixed k s) == stripFixed k s) = true := by
  native_decide

/-- The fix moves nothing outside the two findings' shapes. -/
theorem fixed_agrees_elsewhere :
    allK (fun k s => !noClass0Mark s || hasNeg s ||
      (stripFixed k s == strip k s && isZalgoFixed k s == isZalgo k s)) = true := by
  native_decide

/-- Nor does it move anything for a mark count that the current code already accepts at
the positions it can see: every input the fixed predicate calls ordinary is also ordinary to
the current one. -/
theorem fixed_only_adds_detections :
    allK (fun k s => isZalgoFixed k s || !isZalgo k s || hasNeg s) = true := by
  native_decide

end Text.Zalgo
