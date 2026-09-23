import Text

/-!
The axiom audit, not part of the default build: `lake env lean Text/Axioms.lean`.
The general theorems should show only `propext`, `Quot.sound` and `Classical.choice`;
the `Bounded*` ones add the auxiliary axiom `native_decide` introduces (trust in the
compiler). The `Findings` counterexamples use `decide` and need no extra axiom.
-/

#print axioms Text.CaseFold.stable_correct
#print axioms Text.pmap_idem
#print axioms Text.Whitespace.collapse_eq_cs
#print axioms Text.Whitespace.collapse_idem
#print axioms Text.Whitespace.collapse_nf
#print axioms Text.Whitespace.collapse_keeps_non_ws
#print axioms Text.Zalgo.strip_sublist
#print axioms Text.Zalgo.strip_keeps_protected
#print axioms Text.Zalgo.strip_zero_only_negation
#print axioms Text.Width.tw_le
#print axioms Text.Width.gwFixed_spacing
#print axioms Text.Punct.foldPunct_idem
#print axioms Text.Findings.z1_minimal
#print axioms Text.Findings.w1
#print axioms Text.Zalgo.fixed_pairing
#print axioms Text.Invisibles.format_props
