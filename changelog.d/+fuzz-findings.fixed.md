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
