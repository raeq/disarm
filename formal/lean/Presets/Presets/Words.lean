import Presets.Surfaces

/-!
# Word enumeration and the checkers the bounded theorems use
-/

namespace Presets

/-- Every word of length exactly `n` over `alpha`. -/
def wordsOfLen (alpha : List Nat) : Nat -> List Str
  | 0 => [[]]
  | n + 1 => (wordsOfLen alpha n).flatMap fun w => alpha.map fun c => c :: w

/-- Every word of length at most `n` over `alpha`. -/
def wordsUpTo (alpha : List Nat) (n : Nat) : List Str :=
  (List.range (n + 1)).flatMap (wordsOfLen alpha)

def idemOn (f : Str -> Str) (ws : List Str) : Bool := ws.all fun w => f (f w) == f w

/-- The words on which `f` is not idempotent. -/
def idemFailures (f : Str -> Str) (ws : List Str) : List Str := ws.filter fun w => f (f w) != f w

def agreeOn (f g : Str -> Str) (ws : List Str) : Bool := ws.all fun w => f w == g w

/-- The sub-alphabet the length-4 checks run over (the difftest's `SMALL`). -/
def small : List Nat := [0x49, 0x31, 0x7C, 0x20, 0x8, 0x0, 0x301, 0x308, 0x338, 0xFD, 0x3B0,
  0xA2, 0x3D, 0xA760, 0xA761, 0x1C1, 0x100, 0x200B, 0x34F, 0xE000, 0x61, 0x1100, 0x1161]

end Presets
