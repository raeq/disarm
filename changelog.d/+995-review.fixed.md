- **`replace_emoji` no longer builds an emoji out of what a removal leaves behind, and a
  zero-width character after a carriage return no longer overwrites visible text (#995
  follow-up).** A keycap or presentation selector after an emoji is not part of it
  (#996), so removing the emoji left it in place — and when the character before could
  take it, the two became an emoji the input never had: `replace_emoji("1😀\u20e3", "")`
  returned `1\u20e3`, a keycap, and a second pass removed it with the caller's digit. A
  mark that would bind to the character before the seam is now dropped with the emoji, so
  that input gives `1`; one that binds to nothing is still kept, so the `" "` replacement
  gives `1 \u20e3` as before.

  With `resolve_deletions=True, resolve_cr=True`, a character that occupies no cell — a
  zero-width space, a combining mark — met at column 0 after a `CR` took cell 0 and moved
  the cursor, so the next letter overwrote the `b` in `"abc\r\u200bY"` and gave
  `"\u200bYc"`. It now takes no cell and moves nothing, and is kept ahead of the line:
  `"\u200bYbc"`. No key builder resolves a `CR`, so no stored key moves.
