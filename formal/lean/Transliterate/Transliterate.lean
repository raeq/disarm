import Transliterate.Lift
import Transliterate.Counterexamples
import Transliterate.Engine

/-! Axiom audit: none of the results below may depend on `sorryAx`.
`lake build` prints the axiom set of each. -/

#print axioms Transliterate.lift_I1
#print axioms Transliterate.lift_I2
#print axioms Transliterate.lift_I3_hom
#print axioms Transliterate.lift_I3_via_I1_I2
#print axioms Transliterate.I3_of_I1_I2
#print axioms Transliterate.dropXY_not_idempotent
#print axioms Transliterate.dropXY_not_hom
#print axioms Transliterate.sepJoin_middot_not_ascii
#print axioms Transliterate.sepJoin_space_ascii
#print axioms Transliterate.sepJoin_space_not_hom
#print axioms Transliterate.translit_I2
#print axioms Transliterate.translit_I3
#print axioms Transliterate.not_I2_of_emit
#print axioms Transliterate.ctxShipped_not_I2
#print axioms Transliterate.ctxFixed_I3
