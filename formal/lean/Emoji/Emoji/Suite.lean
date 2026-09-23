import Emoji.Fixes

/-!
# The property suite, over the shipped model and over the fixed one

`suite impl` lists every property with the alphabet it is quantified over, for one
implementation of the four entry points. `shipped` is the model of `main`; `fixed` is
the same with the three fixes of `Fixes.lean`.
-/

namespace Emoji
open Tables

structure Impl where
  replace : List Char → List Char → List Char
  dIgnore : List Char → List Char
  dReplace : List Char → List Char
  dReplaceEmpty : List Char → List Char
  dPreserve : List Char → List Char
  pipe : List Char → List Char

def shipped : Impl :=
  { replace := replaceEmoji, dIgnore := demIgnore, dReplace := demReplace,
    dReplaceEmpty := demReplaceEmpty, dPreserve := demPreserve, pipe := pipelineDemojize }

def fixed : Impl :=
  { replace := replaceFix, dIgnore := demIgnoreFix, dReplace := demReplaceFix,
    dReplaceEmpty := demReplaceEmptyFix, dPreserve := demojizeFix .preserve "[?]".toList,
    pipe := pipelineFix }

structure Check where
  name : String
  alpha : List Char
  p : List Char → Bool
  f : List Char → List Char

def suite (i : Impl) : List Check :=
  let r0 := (i.replace · [])
  let r1 := (i.replace · [' '])
  let rh := (i.replace · ['#'])
  let dem : List (String × (List Char → List Char)) :=
    [("demojize ignore", i.dIgnore), ("demojize replace", i.dReplace),
     ("demojize replace_with=''", i.dReplaceEmpty), ("pipeline", i.pipe)]
  [ ⟨"replace '' leaves no emoji", full, pClean r0, r0⟩,
    ⟨"replace ' ' leaves no emoji", full, pClean r1, r1⟩,
    ⟨"replace '#' leaves no emoji", full, pClean rh, rh⟩,
    ⟨"replace '' idempotent", full, pIdem r0, r0⟩,
    ⟨"replace ' ' idempotent", full, pIdem r1, r1⟩,
    ⟨"replace '#' idempotent", full, pIdem rh, rh⟩,
    ⟨"replace '' keeps text", full, pKeeps [cX, cDot, cSP, cMK, cEU] r0, r0⟩,
    ⟨"replace '' keeps a stray keycap", full, pStrayKeycapKept r0, r0⟩,
    ⟨"replace ' ' keeps a stray keycap", full, pStrayKeycapKept r1, r1⟩,
    ⟨"replace ' ': mark stays put", full, pMarkStaysPut r1, r1⟩,
    ⟨"replace '': mark not on a name", full, pMarkNotOnName r0, r0⟩,
    ⟨"replace '': mark stays put", full, pMarkStaysPut r0, r0⟩ ] ++
  (dem.flatMap fun (n, f) =>
    [ ⟨n ++ " leaves no emoji", full, pClean f, f⟩,
      ⟨n ++ " idempotent", full, pIdem f, f⟩,
      ⟨n ++ " keeps text", full, pKeeps [cX, cDot, cSP, cC, cMK, c1, cStar] f, f⟩,
      ⟨n ++ " keeps a stray keycap", full, pStrayKeycapKept f, f⟩,
      ⟨n ++ ": name separated from next word", full, pNameSeparated f, f⟩,
      ⟨n ++ ": mark not on a name", full, pMarkNotOnName f, f⟩,
      ⟨n ++ ": mark stays put", full, pMarkStaysPut f, f⟩ ]) ++
  [ ⟨"demojize preserve: mark stays put", full, pMarkStaysPut i.dPreserve, i.dPreserve⟩,
    ⟨"demojize preserve: name separated", full, pNameSeparated i.dPreserve, i.dPreserve⟩,
    ⟨"pipeline keeps euro", full, pKeeps [cEU] i.pipe, i.pipe⟩,
    ⟨"pipeline = demojize ignore (no euro)", noEuro, (fun s => i.pipe s == i.dIgnore s), i.pipe⟩,
    ⟨"pipeline = demojize ignore (with euro)", full, (fun s => i.pipe s == i.dIgnore s), i.pipe⟩ ]

/-- Shipped-only checks: window equivalence and the provider path. -/
def shippedExtra : List Check :=
  [ ⟨"window 9 = unbounded ''", full, pWindowEq 9 [], (replaceEmoji · [])⟩,
    ⟨"window 2 = unbounded ''", grammar, pWindowEq 2 [], (replaceW 2 · [])⟩,
    ⟨"window 3 = unbounded ''", grammar, pWindowEq 3 [], (replaceW 3 · [])⟩,
    ⟨"window 3 = unbounded ' '", grammar, pWindowEq 3 [' '], (replaceW 3 · [' '])⟩,
    ⟨"window 4 = unbounded ''", grammar, pWindowEq 4 [], (replaceW 4 · [])⟩,
    ⟨"provider keeps a keycap whole", full, pProviderKeycapWhole,
      demojizePy .replace "[?]".toList (some oneProvider)⟩ ]

end Emoji
