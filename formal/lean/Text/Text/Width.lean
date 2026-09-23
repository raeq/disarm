/-!
# `grapheme_width` / `terminal_width` (`src/width.rs`)

The model does not re-implement UAX #29. `terminal_width` is modelled as the sum of
`gw` over a list of clusters, and the differential test feeds it the clusters the library
itself produced (`grapheme_split`), so it validates the width logic against the library
without depending on a second segmenter. The segmentation facts the findings rely on
(GB9b: nothing breaks after a `Prepend`) are checked against an independent UAX #29
implementation in `scripts/sweep.py`.

A scalar is described by what `grapheme_width_opts` reads from it:

* `ascii` — the L74 fast path applies to it when it is alone;
* `cls` — `width_class` (L33-46): 0 zero-width, 1 narrow, 2 wide, 3 ambiguous;
* `emo` — `is_emoji_presentation(base) || is_regional_indicator(base)` (L78-79);
* `sel` — which selector it is, if any (VS15, VS16, the keycap);
* `kb` — a keycap base `0-9 # *` (L103);
* `prep` — `Grapheme_Cluster_Break=Prepend`. The current code never reads it; the fix does.
-/

namespace Text.Width

inductive Sel where
  | none | vs15 | vs16 | keycap
  deriving DecidableEq, Repr

structure Sc where
  ascii : Bool
  cls : Nat
  emo : Bool
  sel : Sel
  kb : Bool
  prep : Bool
  deriving DecidableEq, Repr

/-- `resolve` (L52-59). -/
def resolve (cls : Nat) (amb : Bool) : Nat :=
  match cls with
  | 0 => 0
  | 2 => 2
  | 3 => if amb then 2 else 1
  | _ => 1

/-- `grapheme_width_opts` (L64-121), on a whole argument (it does not segment). -/
def gw (amb : Bool) : List Sc → Nat
  | [] => 0
  | b :: rest =>
    if b.ascii && rest.isEmpty then (if b.cls == 0 then 0 else 1)          -- L74-76
    else if b.cls == 0 && !b.emo then 0                                    -- L85-87
    else
      let vs15 := rest.any (·.sel == .vs15)
      let vs16 := rest.any (·.sel == .vs16)
      let kc := rest.any (·.sel == .keycap)
      if vs15 then (if b.emo then 1 else resolve b.cls amb)                -- L107-113
      else if vs16 || b.emo || (kc && b.kb) then 2                         -- L114-116
      else resolve b.cls amb                                               -- L120

/-- `terminal_width_opts` (L126-130), given the clusters. -/
def tw (amb : Bool) (clusters : List (List Sc)) : Nat :=
  (clusters.map (gw amb)).sum

/-! ## The fix as proposed (Finding W1)

A cluster that opens with zero-width `Prepend` scalars takes its width from the first
scalar after them: UAX #29 attaches a `Prepend` to the *following* character (GB9b), so
that character, not the prefix, is the cluster's base. -/

def dropZeroPrep : List Sc → List Sc
  | [] => []
  | b :: rest => if b.prep && b.cls == 0 then dropZeroPrep rest else b :: rest

def gwFixed (amb : Bool) (cl : List Sc) : Nat := gw amb (dropZeroPrep cl)

/-! ## Vocabulary for the properties -/

/-- A scalar a reader sees as taking a cell by itself: not zero-width and not a selector. -/
def spacing (s : Sc) : Bool := s.cls != 0 && s.sel == .none

end Text.Width
