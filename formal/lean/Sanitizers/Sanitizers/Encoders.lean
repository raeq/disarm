/-!
# Models of `escape_html` and `percent_encode` (`src/encoders.rs`), and of their decoders

`escapeHtml` is `escape_html_str` (L21-40) over characters; `pctEncode` is
`percent_encode_into` (L85-97) over the UTF-8 bytes, as the Rust code iterates
`text.as_bytes()`. The decoders are the parts of `html.unescape` and
`urllib.parse.unquote` / `unquote_plus` that can fire on these encoders' output: the five
entities, and `%XX` / `+`. The differential test checks the library's output against
the model *and* against Python's real decoders.
-/

namespace Sanitizers.Enc

/-! ## `escape_html` -/

def amp : List Char := "&amp;".toList
def lt : List Char := "&lt;".toList
def gt : List Char := "&gt;".toList
def quot : List Char := "&quot;".toList
def apos : List Char := "&#x27;".toList

/-- `escape_html_str` (L21-40). -/
def escapeHtml : List Char → List Char
  | [] => []
  | c :: cs =>
    (if c == '&' then amp
     else if c == '<' then lt
     else if c == '>' then gt
     else if c == '"' then quot
     else if c == '\'' then apos
     else [c]) ++ escapeHtml cs

/-- The five-entity decoder: what `html.unescape` does to text whose only `&` start one of
these five entities. Anything else is copied. -/
def unescapeHtml : List Char → List Char
  | [] => []
  | '&' :: 'a' :: 'm' :: 'p' :: ';' :: r => '&' :: unescapeHtml r
  | '&' :: 'l' :: 't' :: ';' :: r => '<' :: unescapeHtml r
  | '&' :: 'g' :: 't' :: ';' :: r => '>' :: unescapeHtml r
  | '&' :: 'q' :: 'u' :: 'o' :: 't' :: ';' :: r => '"' :: unescapeHtml r
  | '&' :: '#' :: 'x' :: '2' :: '7' :: ';' :: r => '\'' :: unescapeHtml r
  | c :: r => c :: unescapeHtml r

def isMeta (c : Char) : Bool := c == '&' || c == '<' || c == '>' || c == '"' || c == '\''

/-! ## `percent_encode` -/

inductive Component where
  | path
  | segment
  | query
  | form
  deriving DecidableEq, Repr

def isAlnumB (b : Nat) : Bool :=
  (48 ≤ b && b ≤ 57) || (65 ≤ b && b ≤ 90) || (97 ≤ b && b ≤ 122)

/-- `is_unreserved` (L45-47). -/
def unreserved (b : Nat) : Bool := isAlnumB b || [45, 46, 95, 126].contains b

/-- `keep_segment` (L52-70): unreserved, sub-delims, `:` and `@`. -/
def keepSegment (b : Nat) : Bool :=
  unreserved b || [33, 36, 38, 39, 40, 41, 42, 43, 44, 59, 61, 58, 64].contains b

def keep : Component → Nat → Bool
  | .path, b => keepSegment b || b == 47
  | .segment, b => keepSegment b
  | .query, b => unreserved b
  | .form, b => unreserved b

def plus : Component → Bool
  | .form => true
  | _ => false

/-- `UPPER_HEX`. -/
def hexDigit (n : Nat) : Nat := if n < 10 then 48 + n else 55 + n

/-- `percent_encode_into` (L85-97), byte by byte. -/
def pctEncode (comp : Component) : List Nat → List Nat
  | [] => []
  | b :: bs =>
    (if plus comp && b == 32 then [43]
     else if keep comp b then [b]
     else [37, hexDigit (b / 16), hexDigit (b % 16)]) ++ pctEncode comp bs

def hexVal (d : Nat) : Option Nat :=
  if 48 ≤ d && d ≤ 57 then some (d - 48)
  else if 65 ≤ d && d ≤ 70 then some (d - 55)
  else if 97 ≤ d && d ≤ 102 then some (d - 87)
  else none

/-- `unquote_to_bytes` (and `+` to space for `unquote_plus`). -/
def pctDecode (plusSpace : Bool) : List Nat → List Nat
  | [] => []
  | 37 :: h :: l :: r =>
    match hexVal h, hexVal l with
    | some a, some b => (16 * a + b) :: pctDecode plusSpace r
    | _, _ => 37 :: pctDecode plusSpace (h :: l :: r)
  | b :: r => (if plusSpace && b == 43 then 32 else b) :: pctDecode plusSpace r

end Sanitizers.Enc
