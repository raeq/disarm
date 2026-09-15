- **`demojize` ate a keycap that belonged to no emoji, then let what survived attach to
  the name (#992).** After naming an emoji the scanner swept trailing modifiers with
  `is_emoji_modifier`, which includes `U+20E3 COMBINING ENCLOSING KEYCAP`. That character
  makes a keycap sequence only after a digit, `#` or `*` — `head_len_at` has no keycap arm
  and says why, ten lines from where the sweep ran — so the *naming* half of the scanner
  did exactly what the *replacing* half refuses to, and `demojize("😀⃣")` returned
  `'grinning face'` with an assigned character silently gone. The sweep is now one
  function shared by all three call sites, covering what the match's own definition
  covers, and the two halves agree.

  A joiner stays swept, which #992 proposed dropping along with the keycap. It cannot be:
  between two separately named emoji the joiner is structural, and leaving it puts an
  invisible character into prose — `demojize("👨‍👨")` would read `man ‍man`. That is the
  failure this scanner exists to prevent, so the narrowing stops at the keycap.

- **A combining mark after an emoji landed on the emoji's name.** Found while fixing the
  above, and the same defect one class wider. `demojize("😀́")` returned `'grinning facé'`
  — an accent the input put on an emoji, moved onto a word the input never contained. The
  scanner already guarded the narrow version of this (`"woman's hat"` + `U+20AC` became
  `"woman's hate"` once `confusables` folded the euro sign to `e`), but the guard sat at
  one of the two places a character is emitted, and the mark arrived at the other. There
  is now one `needs_separator_after_a_name`, asked by both, and by the pyo3 scanner as
  well — which had a third copy of the narrow test, and is why `demojize` and
  `TextPipeline(demojize=True)` could disagree.
