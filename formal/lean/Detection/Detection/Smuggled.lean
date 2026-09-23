/-!
# A model of the smuggled-payload decoder (`src/smuggled.rs`)

`decode` mirrors `decode(text, with_percent)` (L117-156) for the three invisible carriers.
The percent scheme is left out: nothing in this alphabet is a `%`, so `decode_smuggled` and
`decode_carriers` agree on every input here.

| Class | Concrete | |
|---|---|---|
| `z0`, `z1` | `U+200B`, `U+200C` | a zero-width bit |
| `zs` | `U+200D` | a zero-width separator (carries no bit) |
| `vsb n` | `U+FE00+n` (n < 16), `U+E0100+n-16` | a variation selector, byte `n` |
| `tagb n` | `U+E0000+n` | a tag character; a *tag byte* when `0x20 <= n <= 0x7E` |
| `cancel` | `U+E007F` | `CANCEL TAG` |
| `flag` | `U+1F3F4` | the subdivision-flag base |
| `x` | `x` | anything else |
-/

namespace Detection

inductive S where
  | z0 | z1 | zs | x | flag | cancel
  | vsb (n : Nat)
  | tagb (n : Nat)
  deriving DecidableEq, Repr, Inhabited

inductive Scheme where
  | tagAscii | variationBytes | zeroWidthBinary
  deriving DecidableEq, Repr

structure Payload where
  scheme : Scheme
  start : Nat      -- index of the first carrier, in characters
  units : Nat      -- characters consumed
  bytes : List Nat
  deriving DecidableEq, Repr

namespace S

/-- `is_tag_byte` (L215-217). -/
def isTagByte : S → Bool
  | tagb n => decide (0x20 ≤ n ∧ n ≤ 0x7E)
  | _ => false

def tagByte : S → Nat
  | tagb n => n
  | _ => 0

/-- Tag *letters* `U+E0061..U+E007A` (`invisibles::is_tag_letter`). -/
def isTagLetter : S → Bool
  | tagb n => decide (0x61 ≤ n ∧ n ≤ 0x7A)
  | _ => false

def isVS : S → Bool
  | vsb n => decide (n < 256)
  | _ => false

def vsByte : S → Nat
  | vsb n => n
  | _ => 0

def isZWStart : S → Bool
  | z0 | z1 => true
  | _ => false

def isZW : S → Bool
  | z0 | z1 | zs => true
  | _ => false

end S

open S

/-! ## The subdivision-flag allowlist (`invisibles::subdivision_flag_len`, L138-155) -/

def gbeng : List Nat := [0x67, 0x62, 0x65, 0x6E, 0x67]
def gbsct : List Nat := [0x67, 0x62, 0x73, 0x63, 0x74]
def gbwls : List Nat := [0x67, 0x62, 0x77, 0x6C, 0x73]

def validFlag (acc : List Nat) : Bool := acc == gbeng || acc == gbsct || acc == gbwls

/-- Reading after the flag base: `k` characters consumed so far (the base counts). -/
def flagScan : List S → List Nat → Nat → Option Nat
  | [], _, _ => none
  | c :: rest, acc, k =>
    if c.isTagLetter then flagScan rest (acc ++ [c.tagByte]) (k + 1)
    else if c = .cancel then (if validFlag acc then some (k + 1) else none)
    else none

def flagLen : List S → Option Nat
  | .flag :: rest => flagScan rest [] 1
  | _ => none

/-! ## The three runs -/

/-- `(bytes, count)` of the maximal prefix satisfying `p`. -/
def run (p : S → Bool) (f : S → Nat) : List S → List Nat × Nat
  | [] => ([], 0)
  | c :: rest =>
    if p c then
      let r := run p f rest
      (f c :: r.1, r.2 + 1)
    else ([], 0)

def zwBit : S → List Nat
  | .z0 => [0]
  | .z1 => [1]
  | _ => []

/-- The bits of the maximal zero-width prefix, and its length in characters. -/
def zwRun : List S → List Nat × Nat
  | [] => ([], 0)
  | c :: rest =>
    if c.isZW then
      let r := zwRun rest
      (zwBit c ++ r.1, r.2 + 1)
    else ([], 0)

/-- MSB-first, whole bytes only; a trailing partial byte is dropped (L353-359). -/
def toBytes : List Nat → List Nat
  | b0 :: b1 :: b2 :: b3 :: b4 :: b5 :: b6 :: b7 :: rest =>
    (((((((b0 * 2 + b1) * 2 + b2) * 2 + b3) * 2 + b4) * 2 + b5) * 2 + b6) * 2 + b7) :: toBytes rest
  | _ => []

def headIs (c : S) : List S → Bool
  | d :: _ => d == c
  | [] => false

/-- One step of the scanner at the head of `l`: the payload found there (start 0) and how
many characters to advance. -/
def step (l : List S) : Option Payload × Nat :=
  match l with
  | [] => (none, 1)
  | c :: _ =>
    match flagLen l with
    | some k => (none, k)
    | none =>
      if c.isTagByte then
        let r := run isTagByte tagByte l
        let k := r.2 + (if headIs .cancel (l.drop r.2) then 1 else 0)
        (some ⟨.tagAscii, 0, k, r.1⟩, k)
      else if c.isVS then
        let r := run isVS vsByte l
        if 2 ≤ r.2 then (some ⟨.variationBytes, 0, r.2, r.1⟩, r.2) else (none, 1)
      else if c.isZWStart then
        let r := zwRun l
        let bs := toBytes r.1
        if bs = [] then (none, r.2) else (some ⟨.zeroWidthBinary, 0, r.2, bs⟩, r.2)
      else (none, 1)

def shift (pos : Nat) (p : Payload) : Payload := { p with start := p.start + pos }

/-- The scan loop, with fuel. Every step consumes at least one character, so `l.length`
fuel is always enough (`decodeF_fuel` in `SmuggledProps.lean`); fuel rather than
well-founded recursion keeps the definition reducible, so the kernel can check the
counterexamples in `Findings.lean` by `decide`. -/
def decodeF : Nat → Nat → List S → List Payload
  | 0, _, _ => []
  | _ + 1, _, [] => []
  | n + 1, pos, c :: rest =>
    let r := step (c :: rest)
    (r.1.map (shift pos)).toList ++ decodeF n (pos + max 1 r.2) ((c :: rest).drop (max 1 r.2))

def decodeAt (pos : Nat) (l : List S) : List Payload := decodeF l.length pos l

def decode (l : List S) : List Payload := decodeAt 0 l

/-! ## The encoders the documentation describes -/

/-- `tag_ascii`: one tag character per byte (`docs/api/predicates.md`, `decode_smuggled`). -/
def encTag (bs : List Nat) : List S := bs.map S.tagb

/-- `variation_bytes`: `U+FE00`-`U+FE0F` for 0-15, `U+E0100`-`U+E01EF` for 16-255. -/
def encVS (bs : List Nat) : List S := bs.map S.vsb

/-- `zero_width_binary`: `U+200B` = 0, `U+200C` = 1, MSB first. -/
def bits8 (b : Nat) : List Nat :=
  [b / 128 % 2, b / 64 % 2, b / 32 % 2, b / 16 % 2, b / 8 % 2, b / 4 % 2, b / 2 % 2, b % 2]

def bitChar (bit : Nat) : S := if bit = 1 then .z1 else .z0

def encZW (bs : List Nat) : List S := bs.flatMap (fun b => (bits8 b).map bitChar)

/-- What `Payload.text` is on an ASCII payload: printable exactly when every byte is in
`0x20..0x7E` (`printable`, L188-195; a C0 control or `DEL` is not visible). -/
def asciiPrintable (bs : List Nat) : Bool :=
  !bs.isEmpty && bs.all (fun b => decide (0x20 ≤ b ∧ b ≤ 0x7E))

end Detection
