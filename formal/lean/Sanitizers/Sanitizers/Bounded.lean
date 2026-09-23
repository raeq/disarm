import Sanitizers.Enumerate

/-!
# Bounded exhaustive checks (`native_decide`)

Each theorem evaluates a Boolean predicate from `Enumerate.lean` over every case of a
grid, with `native_decide`: it trusts Lean's compiler as well as its kernel. The filename
and slug grids are the ones `scripts/difftest.py` runs against the library, so a statement
about the *current* model here is also a statement about the library on those words.
`lake exe explore 5` prints, for each grid, how many cases fail and the first one; it is
how the failing properties were cut down.

| Theorem | Grid (cases) | Result |
|---|---|---|
| `current_filename_default_sep` | words ≤ 5 over `. space / * _ c o n x` × separators `_`, empty, `-`, space × `max_length` 0-6, 8 × universal, POSIX × both `preserve_extension` (8,503,040) | with separator `_` and no truncation, P1-P8 fail **only** through Finding 1 |
| `fixed_filename_safe` | the same | the fixed model meets P1-P8 |
| `fixed_filename_idem` | the same | without truncation (`max_length = 0`) the fixed model is idempotent (P9); the current model fails P9 on 3,872 of those cases |
| `current_slug_shape_single_char` | words ≤ 5 over `a B 1 space - !` × separators `-` `.` × `max_length` 0-6 × both flags × four stopword lists (2,090,144) | S2 and S5 hold for one-character separators |
| `fixed_slug_shape` | the same, separators `-` `.` `--` `-_` (4,180,288) | the fixed model meets S2 for every separator |
| `fixed_slug_stopwords` | the same | without truncation, the fixed model leaves no stopword (case-insensitive; with `save_order`, at either end) |
| `unique_hint_is_sound` | every call sequence of length ≤ 4 over five texts × separators `-` `--` × `max_length` 0-6 (10,934) | the per-base hint changes no output |
| `fixed_unique_shape` | the same | every non-empty slug the fixed model returns meets S2 and S3 |
| `dp_eq_lev` | every pair of words ≤ 4 over `a b c` (14,641) | `edit_distance`'s row DP is the Levenshtein distance |
-/

namespace Sanitizers

theorem current_filename_default_sep :
    (Filename.grid 5).all Filename.curSafeDefault = true := by native_decide

theorem fixed_filename_safe : (Filename.grid 5).all Filename.fixedSafe = true := by native_decide

theorem fixed_filename_idem : (Filename.grid 5).all Filename.fixedIdemNoTrunc = true := by
  native_decide

theorem current_slug_shape_single_char :
    (Slug.grid 5 Slug.singleSeps).all Slug.curShape = true := by native_decide

theorem fixed_slug_shape : (Slug.grid 5 Slug.allSeps).all Slug.fixedShape = true := by native_decide

theorem fixed_slug_stopwords : (Slug.grid 5 Slug.allSeps).all Slug.fixedStops = true := by
  native_decide

theorem unique_hint_is_sound : Unique.grid.all Unique.hintSound = true := by native_decide

theorem fixed_unique_shape : Unique.grid.all Unique.fixedShape = true := by native_decide

theorem dp_eq_lev : Dist.pairs.all Dist.dpIsLev = true := by native_decide

end Sanitizers
