- **`replace_emoji` cut emoji sequences at nine code points, leaving an invisible
  character behind.** The scanner matched inside a fixed window sized from
  `max_emoji_seq_len()` — the longest run the CLDR *name* table holds. That bounds naming
  correctly and replacing not at all: `presentation_len_at` follows a ZWJ chain, which
  UTS #51 does not bound, and a family of four with skin tones is eleven code points and
  RGI. Such a sequence took two replacements where one was right, and — the half that
  matters — the joiner at the seam was passed through as ordinary text, so
  `replace_emoji("👨🏻‍👩🏻‍👧🏻‍👦🏻", "")` returned a bare `U+200D`: an invisible character surviving the
  step whose purpose is removing emoji. The window now follows a sequence past its own
  edge, growing until growing stops changing the answer, and hands back everything it
  peeked at but did not consume. It grows by doubling, so following a chain of *n* code
  points costs O(*n*) rather than O(*n*²) — this is a sanitiser, and its worst case is
  somebody's input.

  A full window cannot tell a finished sequence from one it merely ran out of room for:
  the recursion breaks on a joiner with nothing after it, and "nothing after it" is
  exactly what the edge looks like. The eleven-code-point family reports 8 of 9 — one
  short of the edge and still unfinished — so completeness cannot be read off a length,
  which is what the first draft of this fix tried.

- **A backspace after a carriage return deleted the rest of the line.** `resolve_deletions`
  erased with `line.truncate(col)`, which is `pop` only while the cursor sits at the end
  of the line. That holds for every input without a `CR`, so the two agreed until #937
  added the `resolve_cr` flag that moves the cursor back. With both set,
  `"abc\rX\u{8}"` returned `""` where a terminal and a typed backspace both give `"bc"`,
  and a backspace at column 0 discarded the whole line. It now removes the one cell
  before the cursor and closes the gap, and does nothing at column 0. Losing text the
  reader can see is the risk #934 declined to take.
