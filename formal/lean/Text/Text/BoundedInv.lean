import Text.Enum
import Text.Invisibles

/-!
# Bounded exhaustive checks for the invisible strips and `strip_format` (`native_decide`)

Two alphabets, each exhaustive to length 6. The allowlist of valid subdivision-flag payloads
is `["gb"]` here instead of the three five-letter RGI payloads, so that a valid flag
(`U+1F3F4 g b U+E007F`, four scalars) fits well inside the bound; the code compares the
payload with the list and nothing else, so the structural properties checked here do not
depend on which payloads are in it. The differential test runs the real allowlist.
-/

namespace Text.Invisibles

def vfSmall : List (List Char) := ["gb".toList]

/-- Tags, flags, and the classes the invisible strip handles. -/
def alphaTags : List I :=
  [.plain 0, .flag, .tagL 'g', .tagL 'b', .cancel, .tagO 1, .cgj, .pua, .vs 0, .vs16]

/-- What `strip_format` reads: the flag machinery, a selector, and every class a later step
removes or folds. -/
def alphaFmt : List I :=
  [.plain 0, .flag, .tagL 'g', .tagL 'b', .cancel, .vs16, .difmt, .ws 0, .ctl, .bidi 0, .blank]

abbrev N : Nat := 6

def noneOf (p : I → Bool) (s : List I) : Bool := s.all (fun c => !p c)

def isVsAny : I → Bool
  | .vs _ | .vs15 | .vs16 => true
  | _ => false

/-- Whitespace in normal form: no leading, trailing or doubled fold character, and only the
ASCII space left. -/
def wsNormal (s : List I) : Bool :=
  (s.head?.map folds != some true) && (s.getLast?.map folds != some true) &&
  (s.zip s.tail).all (fun p => !(folds p.1 && folds p.2)) &&
  s.all (fun c => !folds c || c == .ws 0)

theorem tags_props :
    Text.allUpTo alphaTags N (fun s =>
      let o := stripTags s vfSmall
      stripTags o vfSmall == o && noStrayTags o vfSmall) = true := by
  native_decide

theorem inv_props :
    Text.allUpTo alphaTags N (fun s =>
      let c := stripInv comparison s vfSmall
      let r := stripInv rendering s vfSmall
      stripInv comparison c vfSmall == c && stripInv rendering r vfSmall == r &&
      noStrayTags c vfSmall && noStrayTags r vfSmall &&
      noneOf (fun x => isVsAny x || x == .pua || x == .cgj) c &&
      vsWellPlaced r) = true := by
  native_decide

/-- `strip_format` is idempotent and leaves nothing any of its steps is meant to remove. -/
theorem format_props :
    Text.allUpTo alphaFmt N (fun s =>
      let o := stripFormat s vfSmall
      stripFormat o vfSmall == o && noStrayTags o vfSmall && vsWellPlaced o && wsNormal o &&
      noneOf (fun x => x == .ctl || x == .difmt || x == .bidi 0 || x == .blank) o) = true := by
  native_decide

theorem compare_idem :
    Text.allUpTo alphaFmt N (fun s =>
      let o := stripCompare s vfSmall
      stripCompare o vfSmall == o && noneOf isVsAny o && wsNormal o) = true := by
  native_decide

end Text.Invisibles
