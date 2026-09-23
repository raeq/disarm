- **Script detection gave a script to 50 Common code points and never found Bopomofo, and
  `decode_smuggled` misread a payload beside a carrier of its own scheme.** Found by the
  Lean model of the detectors in `formal/lean/Detection` (Findings 5 and 6).
  `detect_char_script` reads a table of block ranges, so the byte order mark was Arabic,
  the dandas `U+0964`-`U+0965` Devanagari, the Arabic comma, question mark and tatweel
  Arabic, `U+00D7` and `U+00F7` Latin: `is_mixed_script("\ufeffhello")` was `True`, a
  Bengali or Tamil sentence ending in a danda was mixed, and
  `inspect_anomalies("\u03b1\u00d7\u03b2")` reported `mixed_script`. The UCD calls all
  50 `Script=Common`; they are now carved out by `script_common_carveouts.tsv`, generated
  from the bundled `data/Scripts.txt` by `scripts/gen_script_common_carveouts.py`.
  Transliteration still groups runs by block, so `sort_key`, `search_key` and
  `catalog_key` do not move. Bopomofo (`U+3105`-`U+312F`, `U+31A0`-`U+31BF`, and the
  two tone marks `U+02EA`-`U+02EB`) had no range at all, so `a\u3105` read as
  single-script and the Han + Bopomofo augmented set was unreachable; it is now detected
  and `Script.BOPOMOFO` names it. `Script_Extensions`, which UTS #39 section 5.1 actually
  reads, is still not bundled: `docs/limitations.md` lists what that leaves.
  In `decode_smuggled`, a variation-selector payload after a fully qualified emoji
  (`\u2764\ufe0f`) decoded as `b'\x0fhi'` with no text, because the emoji's own `VS16`
  was read as its first byte; that selector is now left out when the rest decodes as
  text. After one stray `U+200B`, a zero-width payload spelling `hi` was reported as the
  text `44`, a decode nobody encoded: when a run's bit count is not a multiple of 8,
  both byte frames are tried and `text` is set only when exactly one is printable.
