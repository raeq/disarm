- **`slugify` dropped the text after a numeric entity it could not decode (fuzz finding
  1 of #1040).** A failed entity was skipped together with up to 14 bytes of the ASCII
  after it, so `slugify("Q&#A session")` gave `q`, `"Tom &#and Jerry"` gave `tom` and
  `"issue &#12 fixed"` gave `issue`. `&#` with no digit after it is now text, as it is
  in HTML (`q-a-session`), and an entity naming a control character, a surrogate or no
  character at all is dropped without what follows it (`issue-fixed`). The skip also
  stopped at a composed letter but not at its decomposition, so the two spellings of
  `"&#a\u0301"` slugified differently; a hex letter that carries a combining mark is no
  longer read as a digit, and both spellings give one slug. The digit run is no longer
  capped at ten, so leading zeros decode (`&#000000000065;` is `A`).
- **The confusable and transliteration locators report the input's character at its own
  offset (fuzz finding 2 of #1040).** `find_unmapped_confusables`, `find_confusables` and
  `find_untranslatable` look characters up on the composed form, so that a decomposed
  homoglyph is found, and reported every character of a composed cluster at the
  cluster's start: `find_untranslatable("x\ufe0f")` put U+FE0F at offset 0, where `x`
  is, and `find_unmapped_confusables("\u04aa\u0327")` put U+0327 at 0. They also
  reported the composed character itself, which the input need not contain:
  `find_confusables("\u0456\u0308")` reported U+0457, and a shin with a dagesh came back
  as U+FB49, a composition exclusion no normal form produces. Each character is now
  located at the input character it came from, and what is reported is the input's
  character there: a mark that composes with nothing at its own offset (`("\ufe0f", 1)`),
  and a decomposed homoglyph as its base, as written, with the fold of the composed
  character as `target` (`[("\u0456", 1, "i")]` for `"a\u0456\u0308"`). The same
  change reaches every binding, and `errors="strict"` names the same character.
- **`find_untranslatable` reports a compatibility character its NFKC form recovers only in
  part (fuzz finding 3 of #1040).** `transliterate("\U0001F240")` is `[?]ben[?]`: the
  character is NFKC `\u3014\u672c\u3015`, whose ideograph romanizes and whose brackets
  do not. `find_untranslatable` counted it as recovered and reported nothing, against
  "exactly the set `transliterate` would replace, drop, or preserve", and
  `errors="strict"` let it through. The recovery pass now collects what it cannot map,
  and a character whose recovery left anything unmapped is reported, and raises under
  `errors="strict"`. A compatibility character recovered whole (`\ufb01`, `\u337f`) is
  still not reported.
- **`sanitize_filename` returns a fixed point however many layers of empty extensions the
  input carries (fuzz finding 4 of #1040).** Each pass stripped trailing separators and
  then trailing dots once each, so a stem ending in both by turns lost one layer per
  pass, and the pass loop stops at eight (`MAX_PASSES`, #1026):
  `sanitize_filename("a" + ".*" * 9, preserve_extension=False)` returned `a._`, which
  sanitizes to `a`. A pass now repeats its strips until none removes anything, so that
  input gives `a` in one call, and a debug build asserts that the pass bound is never
  reached. Names a single round already settled are unchanged.
