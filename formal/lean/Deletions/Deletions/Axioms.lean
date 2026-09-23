import Deletions.Invariants
import Deletions.Output
import Deletions.Simple
import Deletions.Findings

/-!
# Axiom audit

The general theorems depend only on Lean's standard axioms (`propext`, `Quot.sound`,
`Classical.choice`) — no `sorry`, no `native_decide` (`Lean.ofReduceBool`). Build this
file and read the output; `Bounded.lean`, `Vectors.lean` and the string-level findings
use `native_decide` and so also list `Lean.ofReduceBool`, by design.
-/

open Deletions

#print axioms wf_step
#print axioms no_panic
#print axioms l128_dead
#print axioms resolve_eq_finish
#print axioms resolve_clean
#print axioms resolve_no_erase
#print axioms resolve_idem
#print axioms resolve_count_le
#print axioms resolve_lf
#print axioms resolve_crlf_nocr
#print axioms resolve_false_eq_simple
#print axioms resolve_true_noCR_eq_simple
#print axioms resolve_flag_irrelevant_noCR
#print axioms noCR_right_of_cursor_blank
#print axioms resolve_false_sublist
#print axioms resolve_true_noCR_sublist
#print axioms fixed_z_keeps_cursor
#print axioms z_moves_cursor
#print axioms seen_depends_on_z
#print axioms detector_silent
#print axioms resolver_eats_break
#print axioms bs_erases_break
