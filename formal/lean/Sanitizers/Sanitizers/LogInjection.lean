/-!
# Model of `strip_log_injection` (`src/log_injection.rs`)

Character-level and stateless, so the model is the code: `isNeut` is
`is_log_injection_char` (L34-44) and `strip` is `strip_log_injection_str` (L57-75). The
`Cow::Borrowed` fast path (L62-64) returns the input exactly when no character is
neutralized, which is what the loop returns too, so the model is the loop.
-/

namespace Sanitizers.Log

/-- `is_log_injection_char` (L34-44). -/
def isNeut (keepTab : Bool) (c : Char) : Bool :=
  if c.toNat == 9 then !keepTab
  else c.toNat ≤ 0x1F || c.toNat == 0x7F || (0x80 ≤ c.toNat && c.toNat ≤ 0x9F)
    || c.toNat == 0x2028 || c.toNat == 0x2029

/-- `strip_log_injection_str` (L57-75). -/
def strip (rep : List Char) (keepTab : Bool) : List Char → List Char
  | [] => []
  | c :: cs => (if isNeut keepTab c then rep else [c]) ++ strip rep keepTab cs

/-- `validate_log_replacement` (L80-93): `true` when the call is accepted. -/
def validRep (rep : List Char) (keepTab : Bool) : Bool :=
  rep.all (fun c => !isNeut keepTab c)

end Sanitizers.Log
