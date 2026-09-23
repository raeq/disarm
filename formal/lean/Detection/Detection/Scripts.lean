/-!
# A model of `is_mixed_script` (`src/scripts.rs`, L24-137)

Characters are abstracted to the script `detect_char_script` gives them. `isMixed` is the
`AugmentedState` walk, early exit included; `spec` is UTS #39 section 5.1 read literally:
intersect the augmented script sets of every character (Common and Inherited are every
set) and call the text mixed when the intersection is empty.

| Class | Concrete | |
|---|---|---|
| `common` | `1` | |
| `inherited` | `U+0301` | |
| `latin` .. `deva` | `a`, `U+03B1`, `U+0430`, `U+05D0`, `U+4E00`, `U+3042`, `U+30A2`, `U+AC00`, `U+3105`, `U+0915` | |
| `beng` | `U+0995` | |
-/

namespace Detection

inductive Sc where
  | common | inherited | latin | greek | cyrillic | hebrew | han | hira | kana | hang | bopo
  | deva | beng
  deriving DecidableEq, Repr, Inhabited

namespace Sc
def all : List Sc :=
  [common, inherited, latin, greek, cyrillic, hebrew, han, hira, kana, hang, bopo, deva, beng]
end Sc

/-! ## The code: `augmented_set` and `AugmentedState::accept` -/

def JPAN : Nat := 1
def KORE : Nat := 2
def HANB : Nat := 4
def HANI : Nat := 8

def augMask : Sc → Option Nat
  | .han => some (HANI ||| JPAN ||| KORE ||| HANB)
  | .hira | .kana => some JPAN
  | .hang => some KORE
  | .bopo => some HANB
  | _ => none

structure St where
  mask : Nat := 255
  sawCjk : Bool := false
  other : Option Sc := none
  deriving DecidableEq, Repr

/-- `accept`: the new state, and `false` once the answer is settled as mixed. -/
def accept (st : St) (s : Sc) : St × Bool :=
  if s = .common ∨ s = .inherited then (st, true)
  else match augMask s with
    | some set =>
      let st' := { st with sawCjk := true, mask := st.mask &&& set }
      if st'.mask = 0 then (st', false)
      else (st', !(st'.sawCjk && st'.other.isSome))
    | none =>
      match st.other with
      | none =>
        let st' := { st with other := some s }
        (st', !(st'.sawCjk && st'.other.isSome))
      | some o =>
        if o ≠ s then (st, false)
        else (st, !(st.sawCjk && st.other.isSome))

def mixedAux : St → List Sc → Bool
  | _, [] => false
  | st, s :: rest =>
    let r := accept st s
    if r.2 then mixedAux r.1 rest else true

/-- `is_mixed_script` (L133-136): `!text.chars().all(accept)`. -/
def isMixed (l : List Sc) : Bool := mixedAux {} l

/-! ## The specification: UTS #39 section 5.1 augmented sets, as bitmasks -/

def bit (i : Nat) : Nat := 2 ^ i

/-- Writing systems: Latn Grek Cyrl Hebr Hani Hira Kana Hang Bopo Hanb Jpan Kore Deva Beng. -/
def wLatn := bit 0
def wGrek := bit 1
def wCyrl := bit 2
def wHebr := bit 3
def wHani := bit 4
def wHira := bit 5
def wKana := bit 6
def wHang := bit 7
def wBopo := bit 8
def wHanb := bit 9
def wJpan := bit 10
def wKore := bit 11
def wDeva := bit 12
def wBeng := bit 13
def wAll : Nat := bit 14 - 1

/-- The augmented set of one character's `Script` value. -/
def aug : Sc → Nat
  | .common | .inherited => wAll
  | .latin => wLatn
  | .greek => wGrek
  | .cyrillic => wCyrl
  | .hebrew => wHebr
  | .han => wHani ||| wHanb ||| wJpan ||| wKore
  | .hira => wHira ||| wJpan
  | .kana => wKana ||| wJpan
  | .hang => wHang ||| wKore
  | .bopo => wBopo ||| wHanb
  | .deva => wDeva
  | .beng => wBeng

def resolved (sets : List Nat) : Nat := sets.foldl (· &&& ·) wAll

def spec (l : List Sc) : Bool := resolved (l.map aug) == 0

/-! ## Script_Extensions

UTS #39 section 5.1 resolves a character through its `Script_Extensions`, not its `Script`.
The library keys on a block table (`SCRIPT_RANGES`, L180-420), which gives `U+0964
DEVANAGARI DANDA` the script `Devanagari`; the UCD gives it `Script=Common` and
`Script_Extensions` of twenty-one Indic scripts, Bengali among them. -/

inductive X where
  | ch (s : Sc)
  /-- `U+0964`: the library says `deva`; `scx` = {Beng, Deva, ...}. -/
  | danda
  deriving DecidableEq, Repr

def X.libScript : X → Sc
  | .ch s => s
  | .danda => .deva

def X.scx : X → Nat
  | .ch s => aug s
  | .danda => wDeva ||| wBeng

def specScx (l : List X) : Bool := resolved (l.map X.scx) == 0

def libMixed (l : List X) : Bool := isMixed (l.map X.libScript)

end Detection
