import Sanitizers
import Sanitizers.Findings
import Sanitizers.Vectors

/-!
The axiom audit, not part of the default build: `lake env lean Sanitizers/Axioms.lean`.
The general theorems and the findings should show at most `propext`, `Quot.sound` and
`Classical.choice`; the bounded ones add one auxiliary axiom per `native_decide` call
(`..._native.native_decide.ax_1_1`), which is how Lean 4.34 records trust in the compiler.
-/

#print axioms Sanitizers.Filename.sanitize_ne_nil
#print axioms Sanitizers.Filename.sanitize_not_dotdot
#print axioms Sanitizers.Filename.sanitize_no_leading_dot_space
#print axioms Sanitizers.Filename.sanitize_no_trailing_dot_space
#print axioms Sanitizers.Filename.sanitize_legal
#print axioms Sanitizers.Filename.sanitize_length
#print axioms Sanitizers.Slug.slugify_chars
#print axioms Sanitizers.Slug.slugify_length
#print axioms Sanitizers.Unique.run_nodup
#print axioms Sanitizers.Unique.runFixed_nodup
#print axioms Sanitizers.Enc.unescape_escape
#print axioms Sanitizers.Enc.pctDecode_pctEncode
#print axioms Sanitizers.Enc.pctEncode_safe
#print axioms Sanitizers.Log.strip_clean
#print axioms Sanitizers.Log.strip_idem
#print axioms Sanitizers.Findings.f1_reserved_universal
#print axioms Sanitizers.Findings.f9_doubled_separator
#print axioms Sanitizers.fixed_filename_safe
