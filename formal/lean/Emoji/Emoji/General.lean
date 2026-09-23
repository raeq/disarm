import Emoji.Model

set_option linter.unusedSimpArgs false

/-!
# General theorems (proved by induction, for all inputs over all of `Char`)

None of these proofs unfolds a table predicate (`isEmojiPresentation`,
`isEmojiProperty`, …): they hold for any tables, so they hold for the full UCD/CLDR
tables and not only the alphabet projection.
-/

namespace Emoji

/-- `HEAD_LOOKAHEAD = 3` is enough (emoji.rs:544, and the Rust test
`head_lookahead_is_enough`, which checks it exhaustively over an 11-char alphabet up to
length 5): a `None` from `head_len_at` on at least three characters is final, whatever
follows. -/
theorem headLen_none_stable (w e : List Char) (hw : 3 ≤ w.length)
    (h : headLen w = none) : headLen (w ++ e) = none := by
  match w, hw with
  | a :: b :: c :: r, _ =>
    dsimp only [headLen, List.cons_append, List.head?_cons] at h ⊢
    by_cases hRI : isRI a
    · simp [hRI] at h
    · by_cases hK : isKeycapBase a
      · simp only [hRI, hK, Bool.false_eq_true, ite_false, ite_true] at h ⊢
        by_cases hb : b = VS16 <;> simp_all
      · simp only [hRI, hK, Bool.false_eq_true, ite_false] at h ⊢
        by_cases hO : (opensEmojiPresentation a || (some b == some VS16 && Tables.isEmojiProperty a)) = true
        · simp only [hO, Bool.not_true, Bool.not_false, Bool.false_eq_true, ite_true, ite_false, reduceCtorEq, Option.some.injEq] at h
        · simp only [Bool.not_eq_true] at hO
          simp only [hO, Bool.not_true, Bool.not_false, Bool.false_eq_true, ite_true, ite_false, reduceCtorEq, Option.some.injEq]

/-- A `Some` from `head_len_at` that stops short of the end of its slice is final. -/
theorem headLen_some_stable (x e : List Char) (j : Nat) (h : headLen x = some j)
    (hj : j < x.length) : headLen (x ++ e) = some j := by
  match x with
  | [] => simp [headLen] at h
  | [a] =>
    dsimp only [headLen, List.head?_nil] at h
    by_cases hRI : isRI a
    · simp [hRI] at h; simp at hj; omega
    · by_cases hK : isKeycapBase a
      · simp [hRI, hK] at h
      · simp only [hRI, hK, Bool.false_eq_true, ite_false] at h
        by_cases hO : (opensEmojiPresentation a || (none == some VS16 && Tables.isEmojiProperty a)) = true
        · simp only [hO, Bool.not_true, Bool.false_eq_true, ite_false, Option.some.injEq] at h
          simp at h hj; omega
        · simp only [Bool.not_eq_true] at hO
          simp only [hO, Bool.not_true, Bool.not_false, Bool.false_eq_true, ite_true, ite_false, reduceCtorEq, Option.some.injEq] at h
  | a :: b :: r =>
    dsimp only [headLen, List.cons_append, List.head?_cons] at h ⊢
    by_cases hRI : isRI a
    · simp only [hRI, ite_true] at h ⊢; exact h
    · by_cases hK : isKeycapBase a
      · simp only [hRI, hK, Bool.false_eq_true, ite_false, ite_true] at h ⊢
        by_cases hb : b = VS16
        · subst hb
          simp only [beq_self_eq_true, ite_true] at h ⊢
          cases r with
          | nil => simp at h
          | cons c r => simp_all
        · have : (b == VS16) = false := by simp [hb]
          simp_all
      · simp only [hRI, hK, Bool.false_eq_true, ite_false] at h ⊢
        by_cases hO : (opensEmojiPresentation a || (some b == some VS16 && Tables.isEmojiProperty a)) = false
        · simp only [hO, Bool.not_true, Bool.not_false, Bool.false_eq_true, ite_true, ite_false, reduceCtorEq, Option.some.injEq] at h
        · simp only [Bool.not_eq_false] at hO
          simp only [hO, Bool.not_true, Bool.false_eq_true, ite_false] at h ⊢
          simp only [Option.some.injEq] at h ⊢
          -- the takeWhile stopped inside `b :: r`
          have hlt : (List.takeWhile isHeadMod (b :: r)).length < (b :: r).length := by
            simp at hj; simp; omega
          have key : List.takeWhile isHeadMod (b :: r ++ e) = List.takeWhile isHeadMod (b :: r) := by
            clear h hj hRI hK
            generalize b :: r = l at hlt ⊢
            induction l with
            | nil => simp at hlt
            | cons y ys ih =>
              by_cases hy : isHeadMod y
              · simp [hy] at hlt ⊢
                exact ih hlt
              · simp [hy]
          simp only [List.cons_append] at key
          rw [key]; exact h

/-- A head is never empty. -/
theorem headLen_pos (w : List Char) (l : Nat) (h : headLen w = some l) : 1 ≤ l := by
  match w with
  | [] => simp [headLen] at h
  | a :: r =>
    simp only [headLen] at h
    by_cases hRI : isRI a
    · simp only [hRI, ite_true, Option.some.injEq] at h
      by_cases hb : (r.head?.map isRI).getD false = true
      · simp only [hb, ite_true] at h; omega
      · simp only [hb, Bool.false_eq_true, ite_false] at h; omega
    · by_cases hK : isKeycapBase a
      · simp only [hRI, hK, Bool.false_eq_true, ite_false, ite_true] at h
        simp at h
        obtain ⟨_, h2⟩ := h
        rw [← h2]; omega
      · simp only [hRI, hK, Bool.false_eq_true, ite_false] at h
        by_cases hO : (opensEmojiPresentation a || (r.head? == some VS16 && Tables.isEmojiProperty a)) = true
        · simp only [hO, Bool.not_true, Bool.false_eq_true, ite_false, Option.some.injEq] at h; omega
        · simp only [Bool.not_eq_true] at hO
          simp only [hO, Bool.not_true, Bool.not_false, Bool.false_eq_true, ite_true, ite_false, reduceCtorEq, Option.some.injEq] at h

/-- The chain loop never returns less than it started with. -/
theorem chainLoop_ge (w : List Char) (fuel len : Nat) : len ≤ chainLoop w fuel len := by
  induction fuel generalizing len with
  | zero => simp [chainLoop]
  | succ k ih =>
    simp only [chainLoop]
    split
    · rename_i c _
      split
      · exact Nat.le_trans (Nat.le_succ _) (ih _)
      · split
        · split
          · rename_i j _
            exact Nat.le_trans (by omega) (ih (len + 1 + j))
          · exact Nat.le_refl _
        · exact Nat.le_refl _
    · exact Nat.le_refl _

/-- The chain loop's answer on `p` carries over to `p ++ e` when it stopped inside `p` at
a point that more input cannot move: at a character that is neither a modifier nor a
joiner, or at a joiner with at least `HEAD_LOOKAHEAD` characters after it. -/
theorem chainLoop_stable (p e : List Char) :
    ∀ (fuel fuel' len : Nat), fuel ≤ fuel' → p.length + 1 ≤ len + fuel →
    let r := chainLoop p fuel len
    r < p.length → (p[r]? ≠ some ZWJ ∨ 3 ≤ p.length - (r + 1)) →
    chainLoop (p ++ e) fuel' len = r := by
  intro fuel
  induction fuel with
  | zero =>
    intro fuel' len _ hinv
    simp only [chainLoop]
    intro hr; omega
  | succ k ih =>
    intro fuel' len hle hinv
    obtain ⟨k', rfl⟩ : ∃ k', fuel' = k' + 1 := ⟨fuel' - 1, by omega⟩
    intro r hr hjudged
    have hlenr : len ≤ r := chainLoop_ge p (k + 1) len
    have hlen : len < p.length := by omega
    have hget : p[len]? = some p[len] := by simp [hlen]
    have hget' : (p ++ e)[len]? = some p[len] := by
      rw [List.getElem?_append_left hlen]; exact hget
    simp only [r, chainLoop, hget, hget'] at hr hjudged ⊢
    by_cases hm : isHeadMod p[len]
    · simp only [hm, ite_true] at hr hjudged ⊢
      exact ih k' (len + 1) (by omega) (by omega) hr hjudged
    · simp only [hm, Bool.false_eq_true, ite_false] at hr hjudged ⊢
      by_cases hz : (p[len] == ZWJ) = true
      · simp only [hz, ite_true] at hr hjudged ⊢
        have hdrop : (p ++ e).drop (len + 1) = p.drop (len + 1) ++ e := by
          simp [List.drop_append_of_le_length (show len + 1 ≤ p.length by omega)]
        rw [hdrop]
        cases hh : headLen (p.drop (len + 1)) with
        | none =>
          simp only [hh] at hr hjudged ⊢
          -- stopped at this joiner: it must have been judged
          have hZ : p[len]? = some ZWJ := by
            rw [hget]; simp at hz; rw [hz]
          have h3 : 3 ≤ p.length - (len + 1) := by
            rcases hjudged with h | h
            · exact absurd hZ h
            · exact h
          have hn := headLen_none_stable (p.drop (len + 1)) e (by simp; omega) hh
          simp [hn]
        | some j =>
          simp only [hh] at hr hjudged ⊢
          have hr' := chainLoop_ge p k (len + 1 + j)
          have hj : j < (p.drop (len + 1)).length := by simp; omega
          have hs := headLen_some_stable (p.drop (len + 1)) e j hh hj
          simp only [hs]
          exact ih k' (len + 1 + j) (by omega) (by omega) hr hjudged
      · simp only [hz, Bool.false_eq_true, ite_false] at hr hjudged ⊢

/-- **The window fast path is sound** (emoji.rs:335). If `presentation_len_at` on a
prefix `p` of the input returns `len` short of the prefix's end, and the character at
`len` is not a joiner — or is a joiner with at least `HEAD_LOOKAHEAD` characters after it
— then the whole input gives the same answer. This is exactly the condition under which
`CharWindow::presentation_len` returns without reading ahead. -/
theorem presLen_prefix_stable (p e : List Char) (len : Nat)
    (h : presLen p = some len) (hlt : len < p.length)
    (hjudged : p[len]? ≠ some ZWJ ∨ 3 ≤ p.length - (len + 1)) :
    presLen (p ++ e) = some len := by
  match p, h with
  | first :: rest, h =>
    simp only [presLen, List.cons_append] at h ⊢
    cases hh : headLen (first :: rest) with
    | none => simp [hh] at h
    | some l =>
      simp only [hh] at h
      have hl : l ≤ len := by
        split at h
        · simp at h; omega
        · simp only [Option.some.injEq] at h; rw [← h]; exact chainLoop_ge _ _ _
      have hs := headLen_some_stable (first :: rest) e l hh (by omega)
      simp only [List.cons_append] at hs
      rw [hs]
      split at h
      · simp_all
      · rename_i hnot
        simp only [Bool.not_eq_true] at hnot
        simp only [hnot, Bool.false_eq_true, ite_false, Option.some.injEq] at h ⊢
        have hl1 : 1 ≤ l := headLen_pos _ _ hh
        have := chainLoop_stable (first :: rest) e ((first :: rest).length)
          ((first :: rest ++ e).length) l (by simp) (by simp; omega)
        simp only [List.cons_append] at this
        rw [← h] at hlt hjudged ⊢
        exact this hlt hjudged

/-- The fast path of `CharWindow::presentation_len` (emoji.rs:319-337) returns the same
answer as `presentation_len_at` over the whole remaining input `buf ++ pushback ++ rest`
(the window's invariant: the three are the unread input, in order). -/
theorem window_fastPath_sound (w : Win) (len : Nat)
    (h : presLen w.buf = some len) (hlt : len < w.buf.length)
    (hjudged : w.buf[len]? ≠ some ZWJ ∨ 3 ≤ w.buf.length - (len + 1)) :
    presLen (w.buf ++ w.pb ++ w.rest) = some len := by
  rw [List.append_assoc]
  exact presLen_prefix_stable w.buf (w.pb ++ w.rest) len h hlt hjudged

/-- The growth loop's stop rule (emoji.rs:357-360) is sound once the scan it grew from
held at least four characters: if doubling a scan of `before` characters leaves the
answer `len ≤ before` unchanged, more input cannot change it either. `CharWindow` starts
the loop from a full window of `MAX_WINDOW = 9`, so every scan it judges has
`before ≥ 9`. The bound is tight: at a window of 3 the model finds
`👨 U+FE0E U+FE0E ZWJ 1 U+FE0F U+20E3`, where the doubled scan ends one character short
of the keycap that completes the chain (`Checks.lean`, `window3_is_not_enough`). -/
theorem grow_stop_sound (scan e : List Char) (len before : Nat)
    (h : presLen scan = some len) (hle : len ≤ before) (hgrown : 2 * before ≤ scan.length)
    (h4 : 4 ≤ before) :
    presLen (scan ++ e) = some len :=
  presLen_prefix_stable scan e len h (by omega) (Or.inr (by omega))

end Emoji
