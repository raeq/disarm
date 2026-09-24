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
