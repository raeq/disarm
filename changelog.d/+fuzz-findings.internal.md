- **The fuzz targets assert their full properties again (#1040's findings).** Each of the
  eight findings the #1040 fuzz runs reported is reproduced through the public API in
  `tests/fuzz_findings.rs` (and `tests/test_fuzz_findings.py` where the binding reaches
  it), and the weakening each target carried for it is gone: the locators are checked
  against `s[offset..].starts_with(ch)`, `find_untranslatable` against the three
  `on_unknown` policies on every input, `sanitize_filename` for a fixed point on every
  input, and `slugify` for NFC/NFD invariance with numeric entities and for idempotence
  with an empty separator. Invariant I7 stays checked with `tones=False` only, the scope
  it is now stated in. One finding was the target's own: the `slugify` target read a
  U+24B6 that the caller's separator put in the slug as one the text kept, and now
  checks the words. Its idempotence check also assumes, with entities decoded, a
  separator without `&`, since one ending in `&#` before a word of digits spells an
  entity the next call decodes. `docs/architecture/testing-guarantees.md` lists the
  findings and how each was resolved.
