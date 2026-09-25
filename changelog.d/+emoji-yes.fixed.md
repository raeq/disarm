- **`replace_emoji` deleted a black star, and 1,022 unassigned code points, when a
  `U+FE0F` followed (#PR).** UTS #51 defines the emoji presentation sequence for an
  `Emoji=Yes` base, and the selector arm asked `Emoji` OR `Extended_Pictographic`,
  which reserves whole blocks. `replace_emoji("a★\u{FE0F}b")` now returns its input, as
  `replace_emoji("a☆\u{FE0F}b")` always did, and `terminal_width` gives the pair the
  star's own width instead of two columns. An `Emoji=Yes` base with a selector is
  unchanged: `replace_emoji("x©\u{FE0F}y")` is still `xy`. `demojize` already dropped
  a stray selector wherever it sat, so its output does not move, and no stored key
  does. The new `emoji_yes.tsv` is generated from the pinned UCD 15.1.0 like the other
  emoji tables. Closes the part of #992 that #996 left open.
