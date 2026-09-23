- **Six text-primitive defects found by a Lean model of the primitives
  (`formal/lean/Text`, #PR).** The model covers case folding, the whitespace, control and
  invisible strips, zalgo, display width, punctuation, contractions and edit distance, and
  agreed with the library on 16,417,680 differential comparisons before any finding
  counted.

  - **A class-0 mark reset the zalgo count (Z1).** `is_zalgo`, `strip_zalgo`, the key
    builders' repeat-dropper and the `duplicate_mark` detector counted the marks of one
    class in a run, and a combining mark of class 0 ended the run. Canonical ordering
    sorts marks only between starters, and a class-0 mark is one, so
    `a` + three acutes + `U+034F` + three acutes was two runs of three: not zalgo, and
    `strip_zalgo` kept all six. 1,493 of the 1,496 class-0 marks did it, including the
    invisible `U+034F`, `U+180B`-`U+180F` and `U+17B4`/`U+17B5`, and
    `canonicalize("a" + ("\u0301" + "\u180b") * 20)` kept twenty acutes on one letter.
    The count is now per base and per class: a class-0 mark neither counts nor resets it,
    and only a non-mark starts a new base. The predicate and the cap read one table.
  - **`strip_zalgo`'s output could still be zalgo (Z2).** The cap keeps the first
    negation overlay on a symbol beyond `max_marks` (#749), and `is_zalgo` counted it, so
    `is_zalgo(strip_zalgo("=" + "\u0338" * 4))` was `True` and
    `is_zalgo("\u2260", threshold=0)` was `True` too. The predicate now skips the same
    overlay, and the output of `strip_zalgo(text, max_marks=k)` is never zalgo at `k`.
  - **A zero-width `Prepend` character hid the one after it (W1).** UAX #29 attaches
    `U+0600 ARABIC NUMBER SIGN` and the other twelve zero-width `Prepend` characters to
    the character that follows, and `grapheme_width` took the cluster's first scalar as
    its base, so `terminal_width(("\u0600" + "A") * 100)` was 0. The width now comes
    from the character the prefix attaches to: 100.
  - **A stray `U+FE0F` widened a character that is not an emoji (W2).**
    `grapheme_width("a\ufe0f")` was 2. A VS16 now takes effect only on an emoji base, as
    a stray VS15 already did, so it is 1; `\u263a\ufe0f` and the keycaps are still 2.
  - **`fold_punctuation` left members of the classes it names (D3).** `U+1680 OGHAM
    SPACE MARK`, the one space separator it skipped, now folds to a space; the
    reversed-9 quotes `U+201B`/`U+201F` to `'`/`"`; the reversed primes `U+2035`/`U+2036`
    like `U+2032`/`U+2033`; and the triple primes `U+2034`/`U+2037` to `'''`.

  `canonicalize`, `canonicalize_strict` and `sort_key` move for a repeated or stacked
  mark across a class-0 mark (Z1): 6, 1 and 6 rows of the key-stability fixture, all
  six the #862 rows that put `U+0489` between two copies of one diaeresis.
  `KEY_SCHEMA_VERSION` 10 is unreleased and records it. No other function tracked by the
  fixture moves.
