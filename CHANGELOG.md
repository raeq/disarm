# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.6.0] — 2026-06-07

A hardening and bug-fix release. Two new opt-in helpers (`dedup_batch`,
`make_cached_transliterator`) make this a **minor** bump; no public API was
removed. **Several fixes change output for specific inputs** — read *Upgrade
notes* before upgrading if you cache or persist transliterator/normalizer output.

### Upgrade notes (output-affecting fixes)

Each of these was a bug; the new output is the correct one. If you store or cache
results that were keyed on the old (buggy) behaviour, regenerate them:

- **`register_replacements()` now actually applies.** It was a silent no-op — the
  registered table was never consulted. Registered replacements now take effect
  across `transliterate()` (scalar, list, and `context=True`). If you registered
  replacements and (knowingly or not) relied on them being ignored, output changes.
- **`transliterate(list, tones=True)`** now returns toned pinyin (was silently
  toneless on the list path); **`transliterate(list, target=…, tones=True)`** now
  raises `ValueError` for the forward-only parameter (was silently ignored).
- **`normalize_confusables(text, target="cyrillic")`** no longer maps characters
  onto *invisible combining marks* (28 such mappings removed).
- **`strip_obfuscation`** now folds intra-Latin ASCII homoglyphs (`þ→p`, `ſ→f`,
  `ı→i`, …) and is idempotent; **`sanitize_user_input`** is idempotent for
  control/invisible characters between combining marks; **`demojize`** no longer
  inserts a stray space after a tab/newline that precedes an emoji.
- **Context-aware transliteration (`context=True`, ar/fa/he) distribution
  changed.** The empty `arabic`/`hebrew`/`context` pip extras have been **removed**
  (they never installed anything). The ~37 MB dictionaries are no longer tracked
  in git, and are not shipped in the wheel. Context mode now loads dictionaries
  from `$TRANSLIT_DICT_DIR` (build them with `scripts/bootstrap_dicts.sh`), or use
  the `embed-dicts` Cargo feature for a self-contained build. A packaged
  pip-installable distribution is tracked in #56/#60.
- **`decode_to_utf8` default `min_confidence` changed `0.0` → `0.5`.** Low-confidence
  encoding guesses are now rejected by default instead of silently accepted; pass
  `min_confidence=0.0` to restore the old behaviour. (#66)

### Changed
- **No library-imposed input-size limit** (#80, #65). The 10 MiB input cap on
  `transliterate`, `normalize`, `fold_case`, and the preset pipelines has been
  **removed** — it was paternalistic, inconsistently applied (the ASCII fast
  path bypassed it; `slugify`/`normalize_confusables`/`strip_zalgo` never had it),
  and the threat model already disclaims DoS. All operations are linear time and
  memory; **bounding untrusted input is the caller's responsibility**, documented
  in the threat model and docstrings. The single retained size guard is the
  `register_replacements` output amplification bound (a tiny input can expand to
  an enormous string via a caller-registered value — an amplification a caller's
  own input check cannot foresee). Backward-compatible: only previously-rejected
  large inputs now succeed.
- **External wording: capability, not promise.** Security-relevant features are now
  described as mechanisms (TR39 confusable *mapping*, bidi/zalgo *stripping*, hostname
  *analysis*) rather than outcome guarantees. Package descriptions, README, and docs no
  longer claim to "prevent"/"neutralize" attacks or achieve "perfect" recovery; the XMR
  benchmark figure is always stated with its tested-pairs scope. Engineering rigor is held
  to a high internal bar (see below); the external surface promises nothing it cannot
  measure.

### Added
- **`dedup_batch(texts, …)`** — transliterate a list, processing each *distinct*
  value once and mapping back (large win for repeated/categorical data; ~146× on a
  high-locality column). Stateless — no cache to invalidate; unique values are chunked
  at the 100k batch cap. (#31)
- **`make_cached_transliterator(maxsize=…, …)`** — opt-in LRU-cached single-string
  transliterator with options fixed at construction. **Self-invalidating**: the next
  call after any `register_lang`/`register_replacements`/`remove_replacement`/
  `clear_replacements` clears the cache (via an internal table-generation counter), so
  it never serves stale results. Never enabled by default. (#31)
- **`THREAT_MODEL.md`** — defines in-scope mechanisms, explicit out-of-scope items
  (confusables outside the bundled TR39 table, whole-script and multi-character
  confusables, Unicode-version skew, semantic attacks, DoS), and a vulnerability-vs-
  known-limitation policy, grounded in the literature (Holgers 2006, Deng 2020,
  BitAbuse 2025).
- `SECURITY.md` rewritten on real footing: supported-version policy stated, triage
  scope defined, and linked to the threat model.
- **Security-invariant property tests + fuzzing.** `proptest` invariants in Rust
  (`src/presets.rs`) assert no-panic, idempotence, and "no bidi/format control
  survives" for `strip_obfuscation` / `security_clean` / `sanitize_user_input` /
  `strip_bidi` across the Unicode input space; a deterministic, CI-gating
  adversarial **attack-corpus regression** (`tests/test_attack_corpus.py`:
  homoglyph / zalgo / invisible / bidi / combined, XMR-style); and a **`cargo-fuzz`
  harness** (`fuzz/`) for continuous coverage-guided fuzzing of the defense
  pipelines.
- **Confusable coverage for intra-Latin homoglyphs of basic ASCII letters**
  (e.g. `þ→p`, `ſ→f`, `ı→i`, `ƒ→f`, `Ɩ→l`, `ꜱ→s`). The TR39 generator previously
  skipped all Latin-script sources for the Latin target, dropping ~83 genuine
  homoglyphs of A–Z/a–z; `normalize_confusables`/`strip_obfuscation` now fold
  them. Single-letter Latin confusable coverage of UTS#39 is now complete.
- Pinned `data/confusables.txt` (UTS#39 17.0.0) as the reproducible, version-
  controlled input for `scripts/gen_confusables.py` (`--download` refreshes it),
  and a `tests/test_confusable_coverage.py` gate against Unicode-version drift.

### Fixed
- **`register_replacements()` was a silent no-op** — the global table was stored
  but never consulted by `transliterate()`. It now applies as a longest-match
  pre-pass (no cascade) across the scalar, list, and `context=True` forward paths,
  including ASCII-keyed replacements that previously bypassed Rust via the Python
  fast path. (#51)
- **`tones=` on the list/batch path** was dropped: `transliterate(["北京"],
  tones=True)` returned toneless pinyin while the scalar path returned toned, and
  `transliterate([...], target=…, tones=True)` silently ignored the forward-only
  parameter instead of raising. Both now match the scalar path. (#14, #15)
- **`normalize_confusables(target="cyrillic")` emitted invisible combining marks** —
  28 mappings folded a visible character onto a combining Cyrillic-Extended mark (an
  obfuscation vector). The generator now excludes combining-mark targets. (#24)
- **`script_info("CanadianAboriginal")["context_aware"]` raised `KeyError`** — the
  entry omitted a required `ScriptMeta` field; a completeness guard now prevents
  recurrence. (#18)
- **Context path skipped `strict_iso9`/`gost7034` mutual-exclusion validation** —
  `transliterate(text, context=True, strict_iso9=True, gost7034=True)` now raises
  `ValueError` like the non-context path; the missing-dictionary error hint is now
  language-specific (`he`→`hebrew`). (#18)
- **`demojize` inserted a stray space** after a tab/newline preceding an emoji
  (`"a\t😀"` → `"a\t grinning face"`); it now checks for any whitespace. (#12)
- **Defense pipelines are now idempotent** (bugs found by the property tests):
  - `strip_obfuscation`: emoji whose CLDR name contains typographic punctuation
    (e.g. `👒` → `woman’s hat`, U+2019 `’`) weren't folded because confusables ran
    *before* demojize; a second pass folded `’`→`'`. Confusables now runs after demojize.
  - `sanitize_user_input`: an invisible *or control* character between combining
    marks (e.g. soft-hyphen, NUL) split a mark-run, so removing it *after*
    zalgo-capping merged runs that a second pass then capped differently. Bidi,
    zero-width, **and control characters** are now stripped *before* zalgo-capping.
- Build-time and doc corrections: `build.rs` now rejects malformed `\u{…}` escapes
  in TSV data; embedded-dictionary parse errors are logged (not silently dropped);
  and numerous stale docstrings/comments were corrected (`script_to_lang` returns
  ISO 639-1 *or* 639-3; `normalize()` ASCII fast-path; list single-Rust-call caveats).

### Security
- **`is_safe_hostname` now decodes IDN/`xn--` labels** (#63, high). Previously an
  `xn--` ACE label was pure ASCII → single-script → reported **safe**, so the
  on-the-wire form of the IDN homograph attack (a Cyrillic `xn--80ak6aa92e.com`
  "apple" spoof) sailed through — the exact blind spot for a library marketing
  `idn`/`anti-spoofing`. ACE labels are now UTS#46-decoded (via the `idna` crate)
  before script/confusable analysis; a malformed ACE label is treated as unsafe.
  Non-`xn--` labels are untouched (no false positives on, e.g., `my_host.local`).
- **`is_safe_hostname` fails closed** (#67.1). A confusable-check error no longer
  silently degrades to "not confusable" (`unwrap_or(false)`) → "safe"; it now
  marks the hostname unsafe.
- **Context dictionaries are no longer loaded from a CWD-relative path** (#61).
  `load_dict_from_fs` previously probed `./data/{name}_dict.bin` *first*, so a
  process whose working directory an attacker influences (or where they can drop
  `./data/`) could inject a substitute dictionary and silently change ar/fa/he
  output. Dictionaries now load only from `$TRANSLIT_DICT_DIR` (explicit opt-in)
  or the crate's own absolute `data/` path in source builds.
- **Supply-chain: corpus inputs are verified/pinned** (#62). The Tashkeela corpus
  archive is now checksum-verified before it feeds the builders (fail-closed — an
  unpinned checksum aborts unless `ALLOW_UNVERIFIED_CORPUS=1`), and the Project
  Ben Yehuda corpus is fetched at a pinned commit instead of an unpinned live HEAD.
- **`ContextDict::from_bytes` is fully bounds-checked.** A malformed or truncated
  context dictionary previously caused an out-of-bounds **panic** (the crate is
  `unsafe_code = forbid`, so a panic aborts the process). Every read is now
  bounds-checked and section offsets are validated; capacity hints are clamped.
  Added truncation/bogus-offset/`u32::MAX`-count unit tests. (#18)
- **`register_replacements` expansion is bounded.** Replacement *values* are
  caller-controlled and unbounded; a small input with a large value could expand
  past the transliterate input cap. Output is now bounded during construction and
  rejected once it would exceed `MAX_TRANSLITERATE_INPUT_BYTES`. (#51)

### Internal / tests
- **170 deterministic tests were excluded from CI.** A module-level
  `pytestmark = pytest.mark.hypothesis` in `test_filename_regressions.py` and
  `test_case_folding.py` (filename-security and case-folding regressions) deselected
  the *entire* files under CI's `-m "not hypothesis"` filter; only ~10 were actual
  property tests. The mark is now scoped to the property-test class in each file, so
  the deterministic tests run in CI. (#12)
- New tests: `register_replacements` (unit + Hypothesis property), context-dict
  parser robustness, `resolve_auto_lang` for all 18 scripts added in v0.3.0+, and a
  `SCRIPT_META` field-completeness guard.
- CI/workflow hygiene: concurrency group on secret-scan, `uv.lock` in the benchmark
  path filter, and CodeQL no longer triggered by Rust-only changes.

## [0.5.0] — 2026-06-06

### Added
- **Context-aware transliteration** for abjad scripts (Arabic, Persian, Hebrew).
  `transliterate(text, context=True)` uses dictionary-based vowel restoration
  with bigram context disambiguation to produce readable romanized text instead
  of consonant skeletons.
  - **Arabic**: Tashkeela corpus (65.7M words), 182K unigrams + 200K bigrams.
    Covers 99%+ of newspaper vocabulary.
  - **Hebrew**: Project Ben Yehuda corpus (11.4M words), 227K unigrams + 200K
    bigrams. Covers literary Hebrew.
  - **Persian**: 266 curated common words + optional Wiktionary expansion
    (14.9K entries available via harvester script).
- **`list_context_langs()`**: returns language codes that support `context=True`
  (currently `["ar", "fa", "he"]`).
- **`LangMeta.context`** field: `"full"`, `"partial"`, or `"none"` — enables
  web/WASM clients to show/hide a context toggle per language.
- **`ScriptMeta.context_aware`** field: `bool` — enables toggle per detected script.
- **Dictionary build tooling**:
  - `scripts/build_arabic_dict.py` — corpus-based Arabic dictionary builder
  - `scripts/build_hebrew_dict.py` — corpus-based Hebrew dictionary builder
  - `scripts/build_persian_dict.py` — curated vocabulary Persian builder
  - `scripts/harvest_wiktionary_persian.py` — Wiktionary Persian harvester
  - `scripts/bootstrap_dicts.sh` — reproducible bootstrap from zero with
    pinned checksums. All parameters auditable, no manual steps.
- **Abjad transliteration documentation** (`docs/user-guide/abjad-transliteration.md`)
  covering all three languages, standards used, comparison with other systems.
- **pip extras**: `pip install translit-rs[arabic]`, `[hebrew]`, `[context]`
  for optional context dictionary installation.
- Rust context engine (`src/context.rs`): binary dictionary reader, Arabic/Hebrew
  tokenizer, three-tier resolve (bigram → unigram → context-free fallback),
  lazy-loaded global singletons via `OnceLock`.
- 28 context-aware tests (8 Arabic, 14 Persian, 6 Hebrew).

### Changed
- **Repositioning (docs + metadata only — no API or coverage changes).** The project
  now leads with its differentiated, proven core: **Unicode adversarial-text defense
  and canonicalization** (TR39 visual confusable mapping), with standards-based
  Latin/Cyrillic/Greek transliteration as the supporting pillar and CJK/Indic/other
  scripts framed as best-effort, unidecode-compatible coverage.
  - Rewrote the package description, keywords, and classifiers (added `Topic :: Security`)
    across `pyproject.toml`, `Cargo.toml`, and `mkdocs.yml` to surface the security
    use case for discovery.
  - Restructured `README.md` / `docs/index.md` to lead with defense; introduced an
    explicit three-tier coverage model (core / compatibility / best-effort).
  - Added an Adversarial-Text Defense guide (`docs/security/adversarial-defense.md`)
    documenting the phonetic-vs-visual distinction, the XMR metric, and benchmark
    evidence; elevated security to a top-level docs navigation section.
  - Reframed the Unidecode migration guide: the `unidecode` alias is for romanization
    compatibility, not security (it cannot reverse homoglyph attacks).

### Fixed
- **Linux x86_64 wheels are now built as `cp39-abi3`** instead of a version-specific
  `cp38-cp38` wheel. Previously the only published x86_64 Linux wheel targeted CPython
  3.8, so `pip` fell back to a source build (requiring a Rust toolchain) on Linux
  x86_64 for Python 3.9+. The publish workflow now pins the build interpreter and
  guards against the regression. (#26)
- Documentation: corrected the built-in language-profile count (inconsistently
  reported as 64 in one place; now consistently 83), and fixed several homoglyph code
  examples whose expected output was wrong (e.g. leading-character ordering in
  `strip_obfuscation` examples). All README/doc examples are now verified against the
  built library.

### Security
- Pinned all third-party GitHub Actions to commit SHAs across the CI and release
  workflows (resolves the CodeQL `actions/unpinned-tag` findings) and added
  `.github/dependabot.yml` to keep them current. This hardens the release pipeline,
  which uses PyPI trusted publishing (`id-token: write`).
- Bumped dev/docs dependencies flagged by Dependabot:
  [Pygments → 2.20.0](https://github.com/advisories/GHSA-5239-wwwm-4pmq) and
  [pytest → 9.0.3](https://github.com/advisories/GHSA-6w46-j5rx-g56g) (the pytest
  bump applies on Python ≥ 3.10; Python 3.9 stays on pytest 8.4.2, since pytest 9
  requires ≥ 3.10). Both are development-only — the package has no runtime
  dependencies.

### Notes
- No public API, language registry, or script coverage was removed. All existing
  imports, language codes, and the pinned API surface are unchanged.

## [0.4.0] — 2026-03-29

### Added
- **`strip_obfuscation()` preset pipeline**: maximum-strength text deobfuscation
  using TR39 confusable mapping (visual similarity). Neutralizes homoglyph spoofing,
  zalgo abuse, invisible character injection, and bidi attacks. Does NOT transliterate
  — chain with `transliterate()` explicitly if romanization is also needed.
  Pipeline: NFKC → strip_zalgo(max_marks=0) → confusables → strip_bidi →
  strip_zero_width → demojize → strip_accents → fold_case → collapse_whitespace.
- **`lang_info()` and `script_info()` APIs**: return structured metadata (display
  name, script, region) for any language code or script. Backed by `LANG_META` (83
  entries) and `SCRIPT_META` (55 entries) with import-time drift assertions.
- **18 new language codes**: ban (Balinese), bax (Bamum), bug (Buginese), chr
  (Cherokee), cjm (Cham), cop (Coptic), khb (Tai Lue), lis (Lisu), mni (Meitei),
  nod (Northern Thai), nqo (N'Ko), sat (Santali), su (Sundanese), syr (Syriac),
  tdd (Tai Le), tl (Tagalog), tzm (Tamazight), vai (Vai). Total: 83 languages.
- **10 new Script enum members**: Bamum, Buginese, Cham, Lisu, MeeteiMayek, OlChiki,
  Sundanese, Tagalog, TaiTham, Tifinagh. Total: 57 scripts.
- **Transliteration provenance documentation** (`docs/provenance.md`): per-block
  audit of which formal romanization standard each Unicode block follows.
- **API surface stability tests** (`tests/test_api_stability.py`): 133 tests
  locking down function signatures, class methods, enum members, TypedDicts,
  protocol interfaces, and `__all__` exports.
- **Mutation testing survivor killers** (`tests/test_mutant_killers.py`): 92 tests
  targeting forward-only parameter validation, default parameter sensitivity,
  pipeline step tuples, and boundary checks.
- **Language consistency audit** (`scripts/audit_language_consistency.py`): checks 11
  registration points for Rust/Python/docs/test alignment. Wired into pre-push gate.
- 283 empty-string mappings for combining marks and zero-width characters in
  `translit_default.tsv` — these are now silently stripped instead of producing `[?]`.
- `docs/index.md` is now generated from `README.md` via `scripts/generate_docs_index.sh`
  — single source of truth, no more drift.

### Fixed
- **`strip_obfuscation()` homoglyph resolution**: used phonetic transliteration
  (Cyrillic р→r, с→s) instead of TR39 visual confusable mapping (р→p, с→c).
  Removed transliterate from the pipeline; confusables now handles homoglyphs.
- **Combining marks produce `[?]`**: `transliterate("n\u0303")` returned `"n[?]"`
  instead of `"n"`. Added empty-string TSV mappings for all Combining Diacritical
  Marks (U+0300–U+036F), Extended (U+1AB0–U+1AFF), Supplement (U+1DC0–U+1DFF),
  Symbols (U+20D0–U+20F0), and Half Marks (U+FE20–U+FE2F).
- **Zero-width characters produce `[?]`**: `transliterate("a\u200Bb")` returned
  `"a[?]b"`. Added empty-string mappings for ZWS, ZWNJ, ZWJ, word joiner, BOM,
  soft hyphen, bidi marks, and line/paragraph separators.
- **`TextPipeline` confusable ordering**: confusables ran before transliterate,
  creating mixed-script gibberish on Cyrillic/Greek input. Swapped execution order
  so transliterate runs first (matching `catalog_key` preset).
- **`demojize()` adjacent emoji concatenation**: `demojize("🔥🔥")` returned
  `"firefire"` instead of `"fire fire"`. Added space padding between adjacent
  emoji-to-text replacements.
- **SCRIPT_RANGES sort order**: MeeteiMayek Extensions was misplaced, breaking
  binary search for Ethiopic Extended-A. Added `test_script_ranges_sorted` invariant.
- **Tibetan incorrectly documented as Wylie**: actual mappings use Indic-phonetic
  romanization (ཅ→cha, not Wylie's ca).

### Changed
- **BREAKING: `transliterate_batch()`, `slugify_batch()`, `normalize_batch()`, and
  `strip_accents_batch()` removed.** The base functions now accept both `str` and
  `list[str]` via `@typing.overload`. Pass a list to get batch processing:
  `transliterate(["café", "naïve"])` → `["cafe", "naive"]`.
- **BREAKING: `strip_obfuscation()` no longer transliterates.** Uses TR39 confusables
  (visual mapping) instead. `lang=` parameter removed. Chain with `transliterate()`
  explicitly if romanization is also needed.
- CI restructured: lint/test on PRs only (not push-to-main), hypothesis tests
  excluded (~4s vs ~46s), CodeQL moved to workflow file with path filtering,
  benchmarks split to own workflow.
- Pinned `ruff==0.15.4` in CI and `pyproject.toml` to prevent format drift.
- Python 3.9 remains a supported runtime (`requires-python = ">=3.9"`, abi3-py39)
  but was removed from the release CI matrix; CI runs on Python 3.10+ because
  tests use PEP 604 (`X | Y`) syntax without `from __future__ import annotations`.

## [0.3.0] — 2026-03-28

### Added
- **Unicode coverage expansion**: 2,553 new codepoints across 33 Unicode blocks,
  bringing total `translit_default.tsv` entries from 6,633 to 9,186.

  **Tier 1 — Forms and extensions (~1,741 codepoints):**
  - Fullwidth ASCII (FF01–FF5E): 94 characters, mechanical offset mapping
  - Halfwidth Hangul (FFA0–FFDC): 66 characters via compatibility jamo
  - Enclosed/Circled Alphanumerics (2460–24FF): 160 characters (①→1, Ⓐ→A)
  - Superscript/Subscript (2070–209F): 29 characters mapped to base forms
  - Roman Numerals (2160–2188): 41 characters (Ⅰ→I, Ⅱ→II, ... Ⅻ→XII)
  - Modifier Letters (02B0–02FF): 80 characters (ʰ→h, ʷ→w)
  - IPA/Phonetic Extensions (0250–02AF): 96 characters (ɑ→a, ʃ→sh, ŋ→ng)
  - Greek Extended (1F00–1FFF): 233 characters (polytonic → base Greek → Latin)
  - Hangul Jamo (1100–11FF): 256 individual jamo components
  - Kangxi Radicals (2F00–2FD5): 214 radical forms → pinyin via CJK decomposition
  - CJK Compatibility Ideographs (F900–FAFF): 472 characters → pinyin via
    canonical decomposition targets

  **Tier 2 — Living scripts (~812 codepoints):**
  - Gap-filling for 7 partially-covered scripts: Balinese, Canadian Syllabics,
    Cherokee, Coptic, N'Ko, Syriac, Vai
  - 10 new abugida scripts with virama/inherent-vowel handling: Sundanese,
    Tai Tham, Cham, Batak, Buginese, Tagalog, Hanunoo, Buhid, Tagbanwa,
    Meetei Mayek
  - 4 new alphabetic/syllabic scripts: Tifinagh, Lisu, Ol Chiki, Bamum

- Unicode range constants for 12 new scripts in `src/unicode_ranges.rs`:
  `SUNDANESE`, `TAI_THAM`, `CHAM`, `BATAK`, `BUGINESE`, `TAGALOG`, `HANUNOO`,
  `BUHID`, `TAGBANWA`, `MEETEI_MAYEK`, `MEETEI_MAYEK_EXT`.
- 10 new `*_char_role()` functions in `src/transliterate.rs` for abugida
  virama handling (Sundanese, Tai Tham, Cham, Batak, Buginese, Tagalog,
  Hanunoo, Buhid, Tagbanwa, Meetei Mayek).
- `scripts/generate_unicode_expansion.py`: reproducible generator script for
  all Tier 1 and Tier 2 TSV entries (1,310 lines).
- `cargo-clippy` pre-commit hook mirroring CI `-D warnings` to catch lints
  before push.
- **Callable module**: `import translit; translit("Москва", lang="auto")` now
  works as a shorthand for `translit.transliterate(...)`. Uses in-place
  `__class__` mutation to preserve `unittest.mock.patch` compatibility.

### Fixed
- **Finnish transliteration**: removed incorrect alias `fi→sv`. Finnish ä/ö
  are independent phonemes (→a/o via default table), not ae/oe variants as
  in Swedish/German. `Hämäläinen` now correctly produces `Hamalainen`.
- **Icelandic transliteration**: removed incorrect ð→dh and Ð→Dh overrides.
  Default table already maps ð→d (ICAO/passport standard). Retained Æ→Ae
  override (differs from default AE). Icelandic override count reduced from
  6 to 2.
- clippy `manual_range_patterns` lint in `buginese_char_role`: collapsed
  `0x1A17 | 0x1A18 | 0x1A19..=0x1A1B` to `0x1A17..=0x1A1B`.
- **`errors="preserve"` dropping visible characters**: characters with explicit
  empty-string TSV mappings (e.g. U+060E Arabic Poetic Verse Sign, U+30FC
  Katakana Prolonged Sound Mark) are now preserved instead of silently dropped
  when `errors="preserve"` is set.

### Changed
- `is_indic()` and `indic_char_role()` expanded to cover all 11 new
  Brahmic/abugida script ranges.
- `lookup_lang()`: Finnish no longer dispatches to Swedish override table;
  falls through to default.
- Icelandic language TSV (`translit_lang_is.tsv`) reduced from 6 to 2 entries.
- `ml_normalize` preset: switched transliteration from `Preserve` to `Ignore`
  error mode — ML pipelines need clean ASCII output, not preserved non-ASCII.

## [0.2.0] — 2026-03-27

### Added
- **Exhaustive testing framework** — three layers of machine-verifiable assurance:
  - **Compile-time assertions** (`build.rs`): all transliteration table values asserted
    ASCII-only, entry count sanity checks (Hanzi ≥20k, BMP ≥5k, confusables ≥1k).
    Build fails if any assertion is violated.
  - **Exhaustive domain tests** (Rust): 16 tests covering all 11,172 Hangul syllables,
    full BMP (63,488 codepoints) for ASCII output and idempotence, all 20,992 CJK
    ideographs, all 51 compatibility jamo, and structural verification of 15 Indic
    script blocks. Zero sampling gaps.
  - **Stated invariant specifications** (Python): 7 stated invariants
    (I1–I7) verified via exhaustive enumeration and Hypothesis — ASCII passthrough,
    ASCII output, idempotence, no exceptions, determinism, input size bound, output
    length bound.
- **Two-tier test architecture**: formal tests gated behind `#[ignore]` (Rust) and
  `@pytest.mark.formal` (Python) so they don't slow everyday development. Run before
  release with `cargo test -- --ignored` and `pytest -m formal`.
- **CLAUDE.md**: project-level development guide for automated agents — documents
  build commands, test tiers, and code conventions.
- `list_scripts()` function for programmatic script discovery.
- `docs/formal-verification.md`: specification document for exhaustive testing methodology.
- Comprehensive overhaul of `docs/architecture/testing-guarantees.md` with exhaustive
  testing differentiator analysis and alternative library comparison.

### Changed
- `IndicRole` enum and `indic_char_role()` / script-specific char_role functions
  changed from private to `pub` for integration test access (parent modules remain
  `#[doc(hidden)]`).
- `tables::hangul` module changed from `mod` to `pub mod` for integration test access.
- Hangul const assertions added: `JUNGSEONG_COUNT`, `JONGSEONG_COUNT`, total syllable
  count, and compatibility jamo range verified at compile time.
- Total test count: 2,900+ (up from 1,678 in 0.1.5).

## [0.1.5] — 2026-03-27

### Added
- **Reverse transliteration**: `transliterate(text, target="ru")` converts Latin → native
  script for Russian, Ukrainian, and Greek. PHF tables generated at build time from
  inverted language TSV data.
- **Toned pinyin**: `transliterate("北京", tones=True)` returns `"běi jīng"` with tone
  marks. Toned readings sourced from Unihan `kMandarin` field for all 20,924 CJK
  Unified Ideographs.
- **ISO 9:1995 scholarly Cyrillic**: `transliterate(text, strict_iso9=True)` for
  scholarly romanization. GOST R 7.0.34 variant via `gost7034=True`.
- **Japanese Kunrei-shiki** (`lang="ja-kunrei"`): alternative romanization profile,
  bringing total language count to 65.
- **Ancient scripts**: Coptic, Gothic, Old Italic, Runic, Ogham transliteration tables.
- **CLI short aliases**: `t` (transliterate), `s` (slugify), `n` (normalize),
  `p` (pipeline), `d` (demojize) — e.g. `translit t "café"`.
- **CLI `--target` flag**: `translit t --target ru "Moskva"` for reverse transliteration.
- **CLI `--tones`, `--strict-iso9`, `--gost7034` flags** for transliterate subcommand.
- **CLI `--lang` flag** for slugify subcommand.
- `console_scripts` entry point: `translit` command available after `pip install translit-rs`.
- `docs/cli.md`: comprehensive CLI documentation with piping, exit codes, examples.
- Links section in README.md and docs/index.md for RTD ↔ GitHub cross-references.

### Changed
- `transliterate()` API unified: `reverse_transliterate()` merged into `transliterate()`
  via `target` parameter. Old function removed.
- `transliterate_impl` Rust signature now takes 7 arguments (added `tones: bool`).
- Updated benchmark numbers after `tones` parameter addition (15–46% regression in
  transliteration hot path due to additional branch; throughput now 450M chars/sec
  Latin, 130M chars/sec Cyrillic).
- Performance documentation updated across 4 files to reflect current benchmark results.

### Fixed
- clippy `format_push_string` lint in `build.rs` — replaced `push_str(&format!())`
  with `write!()`.
- clippy `unreadable_literal` in PHF-generated `reverse_translit_phf.rs` — suppressed
  via inner attribute in `src/reverse.rs`.
- All 219 integration test call sites updated for 7-argument `transliterate_impl`.

## [0.1.4] — 2026-03-25

### Added
- **`lang="auto"` script-based language detection**: When `lang="auto"` is passed
  to `transliterate()`, `slugify()`, `TextPipeline`, `Slugifier`, or any other
  call site, the library detects the dominant non-Latin script in the input and
  maps it to a default language code automatically. Maps 28 scripts to language
  codes (e.g. Cyrillic→`ru`, Han→`zh`, Hiragana/Katakana→`ja`, Thai→`th`).
  Zero overhead for `lang=None` or explicit lang codes.
- `LANG_AUTO` constant (`"auto"`) in `translit._enums`.
- **Georgian transliteration** (`lang="ka"`): 114 TSV entries covering Mkhedruli,
  Mtavruli, and supplement ranges. BGN/PCGN national romanization.
- **Armenian transliteration** (`lang="hy"`): 86 TSV entries covering uppercase,
  lowercase, and 5 ligatures (U+FB13–FB17). BGN/PCGN romanization.
- **Sinhala transliteration** (`lang="si"`): 90 TSV entries. Extended Indic
  Brahmic engine range from `0x0900..=0x0D7F` to `0x0900..=0x0DFF` with
  dedicated `sinhala_char_role()` function for Sinhala-specific offsets.
- **Thai transliteration** (`lang="th"`): 87 TSV entries using RTGS romanization.
  New `ScriptClass::Tai` with tone-mark stripping and cancellation handling.
- **Lao transliteration** (`lang="lo"`): 67 TSV entries using BGN/PCGN
  romanization. Shares Tai engine with Thai via offset masking.
- **Ethiopic transliteration** (`lang="am"`): 307 TSV entries for Ge'ez
  alphasyllabary (34 consonant bases × 7 vowel orders + labialized forms +
  digits). Pure data addition — no engine changes needed.
- **Myanmar transliteration** (`lang="my"`): 89 TSV entries. New
  `myanmar_char_role()` for Brahmic engine with virama (U+1039) and asat
  (U+103A) support. Medials (U+103B–103E) classified as dependent vowels.
- **Khmer transliteration** (`lang="km"`): 110 TSV entries. New
  `khmer_char_role()` for Brahmic engine with coeng (U+17D2) as virama. All
  consonants normalized to inherent 'a' regardless of series.
- **Tibetan transliteration** (`lang="bo"`): 147 TSV entries. New
  `tibetan_char_role()` for Brahmic engine with halanta (U+0F84) and subjoined
  consonants (U+0F90–0FBC).
- Unicode range constants: `TIBETAN` (0x0F00–0x0FFF), `MYANMAR` (0x1000–0x109F),
  `KHMER` (0x1780–0x17FF) in `src/unicode_ranges.rs`.
- Comprehensive test coverage: example-based tests for all 9 new scripts,
  property-based tests (hypothesis + proptest), multi-script mixture tests.
- Built-in language count: 51 → 60.

### Changed
- `is_indic()` extended to include Tibetan, Myanmar, and Khmer ranges for
  Brahmic abugida processing.
- `indic_char_role()` dispatches to script-specific functions for Sinhala,
  Tibetan, Myanmar, and Khmer codepoint ranges.

## [0.1.3] — 2026-03-25

### Added
- `strip_control` and `strip_zero_width` now work as independent pipeline steps
  without requiring `collapse_whitespace=True`. Previously they were silently
  ignored when `collapse_whitespace` was disabled.
- `strip_control_chars()` and `strip_zero_width_chars()` standalone Rust
  functions for filtering without whitespace collapsing.
- `decimal` and `hexadecimal` flags in `SlugConfig` are now functional. Setting
  `decimal=False` preserves `&#NNN;` entities; `hexadecimal=False` preserves
  `&#xHHH;` entities. Previously these flags were accepted but silently ignored.
- Rust integration tests: `tests/integration_emoji.rs` (10 tests),
  `tests/integration_slugify.rs` (20 tests),
  `tests/integration_transliterate.rs` (21 tests),
  `tests/integration_whitespace.rs` (12 tests).

### Changed
- `TextPipeline` parameters `strip_control` and `strip_zero_width` changed from
  `bool` (default `True`) to `bool | None` (default `None`). When `None`, they
  inherit from `collapse_whitespace` — `True` if `collapse_whitespace=True`,
  `False` otherwise. Set explicitly to `True` for standalone use without
  `collapse_whitespace`. This is backward compatible: existing code that passes
  `collapse_whitespace=True` gets the same behavior as before.
- `steps()` now reports `strip_control` and `strip_zero_width` as separate
  entries when active, giving full visibility into pipeline behavior.
- Pipeline step order updated: `normalize → confusables → demojize →
  strip_accents → transliterate → fold_case → strip_control →
  strip_zero_width → collapse_whitespace`.
- Migrated from `once_cell` to `std::sync::LazyLock` / `OnceLock`; MSRV bumped
  to 1.80. Removed `once_cell` dependency.
- `needs_cjk_space()` match arm tightened from wildcard `_` to explicit
  `Ideograph | Hangul | Kana` to match the call-site `is_cjk` guard.

### Fixed
- `decode_entities()` corrupting multi-byte UTF-8 characters (BUG-1). The
  function used `bytes[i] as char` which treated each continuation byte as a
  separate Latin-1 codepoint (e.g. `café` → `cafÃ©`). Now advances by full
  UTF-8 characters.
- `decode_numeric_entity_skip()` panicking on malformed `&#` followed by
  multi-byte UTF-8 (BUG-2). The skip function walked through continuation
  bytes looking for `;`, landing inside a multi-byte character. Now stops at
  the first non-ASCII byte.

### Performance
- ASCII fast-path in `demojize_impl` and `demojize_rust`: pure-ASCII text
  returns immediately without `Vec<char>` allocation or emoji scanning.
- `filter_stopwords` replaced intermediate `Vec<_>` + `.join()` with a
  pre-allocated `String` fold, removing one allocation per slugify call.

## [0.1.2] — 2026-03-25

### Added
- Python 3.14 support (classifier and CI test matrix).
- `ruff check --fix` pre-commit hook for automatic lint fixing.
- CI publish workflow using `pypa/gh-action-pypi-publish` with OIDC trusted publishers.
- Multi-platform wheel builds: Linux (x86_64, aarch64), macOS (Intel, ARM64), Windows.
- `steps()` method on `_TextPipeline` type stub.

### Changed
- Resolved all clippy pedantic warnings instead of suppressing them — reduced
  lint suppressions from 48 to 22 (remaining are genuine PyO3 constraints).
  Fixes include: combined identical match arms, replaced manual counters with
  `.enumerate()`, moved item declarations before statements, used `clone_into()`,
  merged identical branches, fixed doc comment formatting.
- Widened `stopwords` and `replacements` type stubs from strict `tuple`/`list`
  to `Sequence` for better mypy compatibility.
- Applied `ruff format` to all Python source and test files.
- Switched docs publish from deprecated `maturin upload` to
  `pypa/gh-action-pypi-publish`.
- macOS Intel wheels now cross-compiled on ARM64 runner (macos-14) instead of
  deprecated macos-13.
- CI doctests now run against installed package (not source tree) with explicit
  `shell: bash` for Windows compatibility.

### Fixed
- `TextPipeline.explain()` doctest: output format is `normalize (NFC)` not
  `normalize (form=NFC)`.
- `from __future__ import annotations` placement in test files (must follow
  module docstring, not precede it).
- Malformed HTML entity test expectation: `decode_entities("&#xyz;")` correctly
  returns `""`, not `"yz;"`.
- Rust benchmark CI: target `bench_core` binary explicitly to avoid passing
  Criterion flags to the test harness.
- Ruff lint fixes: unsorted imports in `test_encoding.py`, unused import
  `is_mixed_script` in `test_security_invariants.py`.
- Read the Docs trigger workflow: simplified curl status handling, graceful
  warning when `RTD_TOKEN` is missing.
- Removed incorrect PyPy classifier (abi3 is CPython-only).

## [0.1.1] — 2026-03-25

### Added
- `src/unicode_ranges.rs` — named constants for all Unicode codepoint ranges used
  by the library, eliminating magic numbers scattered across modules.
- `tests/test_concurrency.py` — concurrent access tests for `LANG_TABLES` and
  `HANGUL_CACHE`, plus malformed Unicode input tests.
- Code coverage reporting in CI (`pytest-cov`, XML report uploaded as artifact).
- `CLOCK$`, `KEYBD$`, `SCREEN$`, `COM0`, `LPT0` added to Windows reserved filename list.
- `casefold()` alias for `fold_case()` — matches `str.casefold()` naming.
- `remove_accents()` alias for `strip_accents()` — matches sklearn/ML ecosystem naming.
- Compatibility parameter aliases: `replacement_text`/`max_len` on `sanitize_filename()`
  (pathvalidate), `greedy`/`preferred_aliases` on `is_confusable()` (confusable_homoglyphs),
  `delimiters` on `demojize()` (emoji library).
- Complete API documentation for 19 previously undocumented exported functions:
  precompiled pipelines, grapheme clusters, encoding detection, `Text` builder,
  `is_safe_hostname`, `demojize`, `strip_bidi`, `EmojiProvider` protocol.
- Three new API reference pages: Precompiled Pipelines, Grapheme Clusters, Encoding.
- "Guides by role" section in `docs/index.md` and `README.md`.
- Performance section in `README.md` with benchmark numbers.
- `Script` enum documentation expanded from 28 to all 41 members.

### Changed
- `transliterate_impl` refactored: capacity estimation extracted to `estimate_capacity()`,
  character classification to `classify_char()`, and CJK spacing logic to
  `needs_cjk_space()`.
- All `RwLock` accesses now recover from lock poisoning using
  `.unwrap_or_else(|e| e.into_inner())` instead of silently falling through.
- Lambda closures in `_compat.py` replaced with named inner functions for clarity.
- `emoji.rs` `write!()` call no longer uses `.unwrap()` (infallible, documented with
  a `// SAFETY` comment).
- MkDocs theme switched from `material` to `readthedocs`.
- All documentation references updated from "unirust" to "translit".
- Development status promoted from Alpha to Beta.
- Package renamed from `translit` to `translit-rs` on PyPI (interim until PEP 541
  grants the `translit` name). Python import remains `import translit`.

### Fixed
- Type stub `_text.pyi` imported from wrong module name (`unirust` → `translit`).
- Type stub `_translit.pyi` missing `min_confidence` parameter on `_decode_to_utf8`.
- Type stub `_text.pyi` missing `grapheme_split`, `grapheme_truncate`, `catalog_key` methods.
- `security_clean()` pipeline step order corrected in 5+ locations: strip_bidi runs
  before collapse_whitespace (matching Rust implementation).
- `catalog_key()` step order corrected: transliterate before strip_accents.
- Stale PyO3 boundary overhead corrected from ~4µs to ~240ns in docs and code comments.

### Deprecated
- `translit._compat` awesome-slugify compatibility layer (`Slugify`, `UniqueSlugify`,
  `slugify_*` instances) — planned removal in v1.0.

## [0.1.0] — 2026-01-01

### Added
- Initial release.
- Unicode transliteration for 60 language profiles.
- Slugification, normalization, confusable detection, filename sanitization.
- Emoji demojization with ZWJ sequence support.
- Backward-compatible layers for Unidecode and awesome-slugify.
