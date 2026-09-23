import Sanitizers.Filename
import Sanitizers.Slug
import Sanitizers.Unique

/-!
# The failed properties, as minimal counterexamples checked by the kernel

Each `theorem` evaluates the model on one input with `decide`, so it rests on the kernel
alone. Every input here was also run on the built library (`scripts/repro.py`), which
returns the same value: the counterexample is a fact about disarm, not only about the
model. The fixed model's answer on the same input follows each one.

Strings are written as character lists; `s!"..."` would need the kernel to decode UTF-8.
-/

namespace Sanitizers.Findings

open Filename

/-! ## Finding 1: a stem that sanitizes to nothing leaves a reserved extension as the name -/

/-- `sanitize_filename("_.con") == "con"`, on both Windows-aware platforms. -/
theorem f1_reserved_universal :
    sanitize ['_', '.', 'c', 'o', 'n'] ['_'] 255 .universal true = ['c', 'o', 'n'] ∧
      isReserved ['c', 'o', 'n'] = true := by decide

theorem f1_reserved_windows :
    sanitize ['*', '.', 'N', 'U', 'L'] ['_'] 255 .windows true = ['N', 'U', 'L'] := by decide

/-- ... and the output is not a fixed point: the second call does prefix it. -/
theorem f1_not_idempotent :
    sanitize ['c', 'o', 'n'] ['_'] 255 .universal true = ['_', 'c', 'o', 'n'] := by decide

theorem f1_fixed :
    sanitizeFixed ['_', '.', 'c', 'o', 'n'] ['_'] 255 .universal true = ['_', 'c', 'o', 'n'] := by
  decide

/-! ## Finding 2: the separator is not validated -/

/-- `sanitize_filename("con _", separator=" ", max_length=4, preserve_extension=False)`
is `"con"`: the post-truncation check reads `"con "` and `finalize_name` then trims it. -/
theorem f2_space_separator_truncation :
    sanitize ['c', 'o', 'n', ' ', '_'] [' '] 4 .universal false = ['c', 'o', 'n'] := by decide

/-- `sanitize_filename("AUX .txt", separator=" ", preserve_extension=False)` keeps
`"AUX .txt"`: the check compares `"AUX "` with the device list, Windows compares `"AUX"`. -/
theorem f2_space_separator_stem :
    sanitize ['A', 'U', 'X', ' ', '.', 't', 'x', 't'] [' '] 255 .universal false =
        ['A', 'U', 'X', ' ', '.', 't', 'x', 't'] ∧
      isReserved (firstDotStem ['A', 'U', 'X', ' ', '.', 't', 'x', 't']) = false ∧
      isReserved (winStem ['A', 'U', 'X', ' ', '.', 't', 'x', 't']) = true := by decide

/-- `sanitize_filename("../etc/passwd", separator="/")` is `"/etc/passwd"`. -/
theorem f2_slash_separator :
    sanitize ['.', '.', '/', 'e', 't', 'c', '/', 'p', 'w'] ['/'] 255 .universal true =
      ['/', 'e', 't', 'c', '/', 'p', 'w'] := by decide

/-- `sanitize_filename("a b", separator="\x00")` contains NUL. -/
theorem f2_nul_separator :
    sanitize ['a', ' ', 'b'] [Char.ofNat 0] 255 .universal true = ['a', Char.ofNat 0, 'b'] := by
  decide

theorem f2_fixed :
    sanitizeFixed ['c', 'o', 'n', ' ', '_'] [' '] 4 .universal false = ['_', 'c', 'o', 'n'] ∧
      sanitizeFixed ['A', 'U', 'X', ' ', '.', 't', 'x', 't'] [' '] 255 .universal false =
        ['_', 'A', 'U', 'X', ' ', '.', 't', 'x', 't'] := by decide

/-! ## Finding 3: outputs that are not fixed points -/

/-- `sanitize_filename("_.x.*")` is `"_.x"`, and `"_.x"` gives `"x"`: the extension `.*`
cleans to a bare dot, `finalize_name` drops it, and the next call splits at the earlier
dot. -/
theorem f3_ext_cleans_to_dot :
    sanitize ['_', '.', 'x', '.', '*'] ['_'] 255 .universal true = ['_', '.', 'x'] ∧
      sanitize ['_', '.', 'x'] ['_'] 255 .universal true = ['x'] := by decide

/-- `sanitize_filename("ab_cd", max_length=3, preserve_extension=False)` ends in the
separator: truncation runs after the trailing-separator strip. -/
theorem f3_truncation_leaves_separator :
    sanitize ['a', 'b', '_', 'c', 'd'] ['_'] 3 .universal false = ['a', 'b', '_'] ∧
      sanitize ['a', 'b', '_'] ['_'] 3 .universal false = ['a', 'b'] := by decide

/-- `sanitize_filename("a.bcd.txt", max_length=6)` is `"a..txt"`. -/
theorem f3_truncation_leaves_dotdot :
    sanitize ['a', '.', 'b', 'c', 'd', '.', 't', 'x', 't'] ['_'] 6 .universal true =
      ['a', '.', '.', 't', 'x', 't'] := by decide

theorem f3_fixed :
    sanitizeFixed ['_', '.', 'x', '.', '*'] ['_'] 255 .universal true = ['x'] ∧
      sanitizeFixed ['a', 'b', '_', 'c', 'd'] ['_'] 3 .universal false = ['a', 'b'] ∧
      sanitizeFixed ['a', '.', 'b', 'c', 'd', '.', 't', 'x', 't'] ['_'] 6 .universal true =
        ['a', '.', 't', 'x', 't'] := by decide

/-! ## Slugs -/

open Slug

def cfg (sep : List Char) (ml : Nat) (wb : Bool) (stop : List (List Char)) : Config :=
  { sep, lowercase := true, maxLen := ml, wordBoundary := wb, saveOrder := false, stopwords := stop }

/-- Finding 5: `slugify("a b", separator="-_", max_length=2)` is `"a-"`; with
`word_boundary=True` it is `"a"`. -/
theorem f5_partial_separator :
    slugify (cfg ['-', '_'] 2 false []) ['a', ' ', 'b'] = ['a', '-'] ∧
      slugify (cfg ['-', '_'] 2 true []) ['a', ' ', 'b'] = ['a'] ∧
      slugifyFixed (cfg ['-', '_'] 2 false []) ['a', ' ', 'b'] = ['a'] := by decide

/-- Finding 6: `slugify("ab cd ef", max_length=5, word_boundary=True)` is `"ab"`, although
`"ab-cd"` is five bytes and ends on a word (python-slugify returns `"ab-cd"`). -/
theorem f6_word_boundary_not_maximal :
    slugify (cfg ['-'] 5 true []) ['a', 'b', ' ', 'c', 'd', ' ', 'e', 'f'] = ['a', 'b'] ∧
      slugifyFixed (cfg ['-'] 5 true []) ['a', 'b', ' ', 'c', 'd', ' ', 'e', 'f'] =
        ['a', 'b', '-', 'c', 'd'] := by decide

/-- Finding 7: `slugify("The Fox", stopwords=["The"])` is `"the-fox"`. -/
theorem f7_stopwords_case_sensitive :
    slugify (cfg ['-'] 0 false [['T', 'h', 'e']]) ['T', 'h', 'e', ' ', 'F', 'o', 'x'] =
        ['t', 'h', 'e', '-', 'f', 'o', 'x'] ∧
      slugifyFixed (cfg ['-'] 0 false [['T', 'h', 'e']]) ['T', 'h', 'e', ' ', 'F', 'o', 'x'] =
        ['f', 'o', 'x'] := by decide

/-- Finding 8: `slugify("abc", separator="", stopwords=["b"])` is `"ac"`: with an empty
separator, `str::split("")` yields single characters, and each is tested as a word. -/
theorem f8_empty_separator_stopwords :
    slugify (cfg [] 0 false [['b']]) ['a', 'b', 'c'] = ['a', 'c'] ∧
      slugifyFixed (cfg [] 0 false [['b']]) ['a', 'b', 'c'] = ['a', 'b', 'c'] := by decide

/-! ## Finding 9: `UniqueSlugifier` suffixes that break the slug's own shape -/

open Unique

/-- `UniqueSlugifier(max_length=5)` on `"ab cd"` three times: `ab-cd`, `ab--1`, `ab--2`. -/
theorem f9_doubled_separator :
    run (cfg ['-'] 5 false []) 10000 [['a', 'b', ' ', 'c', 'd'], ['a', 'b', ' ', 'c', 'd'],
        ['a', 'b', ' ', 'c', 'd']] =
      [.ok ['a', 'b', '-', 'c', 'd'], .ok ['a', 'b', '-', '-', '1'], .ok ['a', 'b', '-', '-', '2']] := by
  decide

/-- `UniqueSlugifier(max_length=2)` on `"ab"` twice: `ab`, then `-1`, the suffix alone. -/
theorem f9_suffix_alone :
    run (cfg ['-'] 2 false []) 10000 [['a', 'b'], ['a', 'b']] = [.ok ['a', 'b'], .ok ['-', '1']] := by
  decide

/-- `UniqueSlugifier()` on `"!!!"` twice: the empty slug, then `-1`. -/
theorem f9_empty_base :
    run (cfg ['-'] 0 false []) 10000 [['!'], ['!']] = [.ok [], .ok ['-', '1']] := by decide

theorem f9_fixed :
    runFixed (cfg ['-'] 5 false []) 10000 [['a', 'b', ' ', 'c', 'd'], ['a', 'b', ' ', 'c', 'd']] =
        [.ok ['a', 'b', '-', 'c', 'd'], .ok ['a', 'b', '-', '1']] ∧
      runFixed (cfg ['-'] 2 false []) 10000 [['a', 'b'], ['a', 'b']] =
        [.ok ['a', 'b'], .error .maxLengthTooSmall] ∧
      runFixed (cfg ['-'] 0 false []) 10000 [['!'], ['!']] = [.ok [], .ok []] := by decide

end Sanitizers.Findings
