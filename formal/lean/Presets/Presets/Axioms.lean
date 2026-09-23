import Presets.Bounded
import Presets.Findings

/-!
The axiom audit. Not part of the default build: run it with
`lake env lean Presets/Axioms.lean`.

The general theorems and the findings (checked by `decide`) rest on the kernel alone, plus
`propext`/`Quot.sound`/`Classical.choice` where a proof uses them. The bounded checks also
list a `..._native.native_decide.ax_...` axiom: they trust the compiler `native_decide` runs.
-/

#print axioms Presets.General.run_idem_of_image_fixed
#print axioms Presets.General.run_not_idem_of
#print axioms Presets.General.filter_run_comm
#print axioms Presets.General.flatMap_idem
#print axioms Presets.General.comp_idem_of_comm
#print axioms Presets.General.fixLoop_stable
#print axioms Presets.Findings.skeleton_not_idem
#print axioms Presets.Findings.skeleton_misses_pair
#print axioms Presets.Findings.search_vy2
#print axioms Presets.Findings.guard_cent2
#print axioms Presets.Findings.obf_jamo2
#print axioms Presets.Findings.applySteps_eq_run
#print axioms Presets.Findings.guard_skips
#print axioms Presets.Bounded.idem_S4
#print axioms Presets.Bounded.guard_sound_S4
#print axioms Presets.Bounded.fixes_idem_S4
