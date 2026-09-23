import Deletions.Spec

/-!
# The repository's own test vectors, replayed on the model

Every assertion on `resolve` in the `#[cfg(test)]` module of `src/deletions.rs` and in
`tests/test_window_and_erase_boundaries.py` (class `TestEraseAfterCarriageReturn`),
checked on the model. `native_decide`: these are concrete evaluations.
-/

namespace Deletions

-- a_zero_width_at_column_zero_does_not_move_the_cursor (L185-194)
example : resolve true (enc "abc\r\u200bY") = enc "\u200bYbc" := by native_decide
example : resolve true (enc "abc\r\u0301Y") = enc "\u0301Ybc" := by native_decide
example : resolve true (enc "abc\rX\x08\u200bY") = enc "\u200bYbc" := by native_decide
example : resolve false (enc "\u200b\x08a") = enc "a" := by native_decide
example : resolve false (enc "ab\x08\x08\u200b\x08") = enc "" := by native_decide
example : resolve false (enc "ab\x08\x08\u200bY") = enc "\u200bY" := by native_decide
-- the_attack_construction_resolves_to_the_clean_word (L198-203)
example : resolve false (enc "pX\x08aX\x08yX\x08pX\x08aX\x08lX\x08") = enc "paypal" := by native_decide
example : resolve false (enc "pX\x7faX\x7fyX\x7fpX\x7faX\x7flX\x7f") = enc "paypal" := by native_decide
-- an_erase_after_a_carriage_return_removes_one_cell (L212-218)
example : resolve true (enc "abc\rX\x08") = enc "bc" := by native_decide
example : resolve true (enc "abc\rXY\x08") = enc "Xc" := by native_decide
example : resolve true (enc "abc\r\x08") = enc "abc" := by native_decide
example : resolve true (enc "abc\r\x7f") = enc "abc" := by native_decide
-- an_erase_at_the_end_of_a_line_still_pops_one_cell (L222-227)
example : resolve false (enc "abc\x08") = enc "ab" := by native_decide
example : resolve false (enc "abc\x08\x08") = enc "a" := by native_decide
example : resolve false (enc "\x08abc") = enc "abc" := by native_decide
example : resolve false (enc "ab\nc\x08") = enc "ab\n" := by native_decide
-- an_erase_does_not_shift_the_rest_of_the_line (L238-242)
example : resolve true (enc "aa\ra\x08a") = enc "aa" := by native_decide
example : resolve true (enc "ab\rX\x08Y") = enc "Yb" := by native_decide
-- a_format_character_and_a_mark_occupy_no_cell (L335-347)
example : resolve false (enc "X\u200b\x08") = enc "" := by native_decide
example : resolve false (enc "e\u0301\x08") = enc "" := by native_decide
example : resolve false (enc "ab\u200b\x08") = enc "a" := by native_decide
-- overstrike_bold_resolves_to_the_letter_every_renderer_shows (L361-364)
example : resolve false (enc "c\x08c") = enc "c" := by native_decide
example : resolve false (enc "b\x08bo\x08old") = enc "bold" := by native_decide
-- line_endings_pass_through_whatever_the_cr_flag_says (L367-381)
example : ∀ cr ∈ [false, true], resolve cr (enc "line1\r\nline2") = enc "line1\r\nline2" := by native_decide
example : ∀ cr ∈ [false, true], resolve cr (enc "trailing\r") = enc "trailing\r" := by native_decide
example : ∀ cr ∈ [false, true], resolve cr (enc "a\nb\nc") = enc "a\nb\nc" := by native_decide
-- a_lone_cr_overwrites_only_under_its_flag (L385-391)
example : resolve false (enc "abc\rxy") = enc "abc\rxy" := by native_decide
example : resolve true (enc "abc\rxy") = enc "xyc" := by native_decide
example : resolve true (enc "ZZZZZZ\rpaypal") = enc "paypal" := by native_decide
example : resolve true (enc "line1\rline2") = enc "line2" := by native_decide
-- erasing_past_the_start_of_a_line_stops_there (L394-397)
example : resolve false (enc "\x08\x08abc") = enc "abc" := by native_decide
example : resolve false (enc "a\x08\x08\x08b") = enc "b" := by native_decide
-- a_cr_that_passes_through_is_not_a_change / text_with_no_erasing_control_is_left_alone
example : ∀ cr ∈ [false, true], ∀ s ∈ ["line1\r\nline2", "trailing\r", "a\r\nb\r\nc", "no cr at all"],
    resolveInto cr (enc s) = none := by native_decide
example : (resolveInto true (enc "abc\rxy")).isSome := by native_decide
example : resolveInto false (enc "a\rb") = none := by native_decide
example : (resolveInto true (enc "a\rb")).isSome := by native_decide
-- tests/test_window_and_erase_boundaries.py, TestEraseAfterCarriageReturn
example : resolve false (enc "ab\x08\x08\u200b\x08") = resolve false (enc "\u200b\x08") := by native_decide
example : resolve false (enc "abc\x08") = enc "ab" := by native_decide
example : resolve true (enc "pX\x08aX\x08yX\x08pX\x08aX\x08lX\x08") = enc "paypal" := by native_decide

end Deletions
