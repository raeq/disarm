import Detection.Findings

/-!
# Bounded exhaustive checks (`native_decide`)

These trust Lean's compiler as well as its kernel. Each quantifies over every word up to
the stated length.
-/

namespace Detection

open C

/-! ## Scripts -/

/-- The `AugmentedState` walk **is** UTS #39 section 5.1 over `Script`: every word of
length six or less over the thirteen classes (5,229,043 words). -/
theorem isMixed_eq_spec :
    (words Sc.all 6).all (fun l => isMixed l == spec l) = true := by native_decide

/-- Per-word is never looser than whole-string: a mixed infix makes the text mixed
(`is_mixed_script(per_word=True)` implies `is_mixed_script`), over every word of length
five or less and every infix of it. -/
theorem isMixed_infix :
    (words Sc.all 5).all (fun l =>
      (List.range (l.length + 1)).all (fun i =>
        (List.range (l.length + 1 - i)).all (fun j =>
          !isMixed ((l.drop i).take j) || isMixed l))) = true := by native_decide

/-! ## Anomalies -/

/-- The three fixes move nothing else: off precomposed letters, deprecated format controls
and second `RLM`s, the fixed detector is the current one (3,368,421 words). -/
theorem fixed_agrees_elsewhere :
    (words C.all 5).all (fun t =>
      t.contains .p || t.contains .fmt || decide (1 < t.count .rlm) ||
      hasAnomaliesFixed t == hasAnomalies t) = true := by native_decide

/-- The fixed number-run rule reports every token the documentation says it covers, over
tokens of length six or less. -/
theorem fixed_rlm_rule :
    (words [.a, .p, .h, .d, .rlm, .rli, .zw, .lrm] 6).all (fun t =>
      !rlmRuleApplies t || classifyFixed t) = true := by native_decide

/-- Cleaner soundness in context, fixed detector: a zero-width, joiner, deprecated format
control, tag, override or control deleted from between two ASCII letters is reported,
whatever surrounds the word (both sides up to length two over the whole alphabet). The
bidi controls other than the override are left out on purpose: the documentation spares
them in a right-to-left majority. -/
theorem fixed_cleaner_sound :
    (words C.all 2).all (fun u => (words C.all 2).all (fun v =>
      [C.zw, .nj, .fmt, .tag, .rlo, .bel].all (fun c =>
        hasAnomaliesFixed (u ++ [.a, c, .a] ++ v)))) = true := by native_decide

/-- The same property on the current code fails only on `fmt` (Finding 1). -/
theorem current_cleaner_sound_but_fmt :
    (words C.all 2).all (fun u => (words C.all 2).all (fun v =>
      [C.zw, .nj, .tag, .rlo, .bel].all (fun c =>
        hasAnomalies (u ++ [.a, c, .a] ++ v)))) = true := by native_decide

end Detection
