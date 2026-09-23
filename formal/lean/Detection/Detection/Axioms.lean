import Detection.Bounded

/-! The axiom audit (not in the default build): `lake env lean Detection/Axioms.lean`.
The induction results should show at most `propext`, `Quot.sound` and `Classical.choice`;
the `native_decide` results add `Lean.ofReduceBool`. -/

open Detection

#print axioms hasAnomalies_append_lf
#print axioms hasAnomalies_append_sp
#print axioms hasAnomaliesNfd_canonical
#print axioms hasAnomaliesFixed_canonical
#print axioms hasAnomaliesNfd_eq_of_no_p
#print axioms anyRlmBeforeDigit_iff
#print axioms decodeF_fuel
#print axioms decodeAt_cut
#print axioms roundtrip_tag
#print axioms roundtrip_vs
#print axioms roundtrip_zw
#print axioms f1_only_fmt
#print axioms f2_minimal
#print axioms f3_minimal
#print axioms f6_zw
#print axioms f5_danda
#print axioms isMixed_eq_spec
#print axioms fixed_cleaner_sound
