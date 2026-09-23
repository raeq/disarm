- **The deletion resolver disagreed with the detector about line breaks, and a leading
  zero-width character still took a cell.** Both found by a Lean model of
  `resolve_deletions` (`formal/lean/Deletions`), which proves the resolver idempotent,
  panic-free and never inventing text, and checks it against the library on 5.39 million
  inputs. VT, FF, NEL, LS and PS start a line for `has_anomalies` but were ordinary cells
  to the resolver: with `resolve_cr=True` a carriage return after one overwrote the line
  above it while the detector reported nothing, and without it a backspace erased the
  break and joined two lines, so `canonicalize("pay\x85\bpal")` gave `paypal` where the
  `LF` form gives `pay pal`. They now end a line, as `LF` does. And #1005's rule that a
  character taking no cell moves nothing held only with visible text to its right: on an
  empty line a U+200B took cell 0, so every overwrite after a later carriage return landed
  a column off, and `"​ZZZZZZ\rpaypal"` resolved to `paypalZ`. It now never takes a
  cell; the consequence, as in a terminal, is that a backspace at column 0 has nothing to
  erase and the zero-width character is kept for `strip_zero_width` to decide on.
