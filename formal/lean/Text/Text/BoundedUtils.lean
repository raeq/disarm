import Text.Enum
import Text.Utils

/-!
# Bounded exhaustive checks for `edit_distance` and `contract` (`native_decide`)
-/

namespace Text.Utils

/-- All words of length `≤ n` over `alpha`, materialized (small bounds only). -/
def wordList {α : Type} (alpha : List α) : Nat → List (List α)
  | 0 => [[]]
  | n + 1 => [] :: (wordList alpha n).flatMap (fun w => alpha.map (· :: w))

/-- `p` occurs in `s` as a contiguous block. -/
def hasInfix (p : List Char) : List Char → Bool
  | [] => p.isEmpty
  | c :: t => p.isPrefixOf (c :: t) || hasInfix p t

def xyz : List Char := ['x', 'y', 'z']

/-- The two-row programme computes the textbook distance: every pair of words of length
`≤ 4` over three letters (14,641 pairs, after de-duplicating the word list). -/
theorem ed_eq_lev :
    let ws := (wordList xyz 4).eraseDups
    ws.all (fun a => ws.all (fun b => ed a b == lev a b)) = true := by
  native_decide

/-- It is a metric: zero exactly on equal words, symmetric, and the triangle inequality,
on every triple of words of length `≤ 4` over two letters. -/
theorem ed_metric :
    let ws := (wordList ['x', 'y'] 4).eraseDups
    ws.all (fun a => ws.all (fun b =>
      ((ed a b == 0) == (a == b)) && ed a b == ed b a &&
      ws.all (fun c => ed a c ≤ ed a b + ed b c))) = true := by
  native_decide

/-- Contraction is idempotent, and one pass leaves no rule source behind, on every word of
length `≤ 7` over the rule letters and two outsiders (960,800 words). -/
theorem contract_idem :
    Text.allUpTo ['r', 'n', 'v', 'c', 'l', 'm', 'x'] 7 (fun s =>
      let o := contract rules s
      contract rules o == o &&
      rules.all (fun r => !(hasInfix r.1 o))) = true := by
  native_decide

end Text.Utils
