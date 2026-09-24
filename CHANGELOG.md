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

Releases before 0.15.0 are archived verbatim, one page per minor series, in `docs/changelog/`.

<!-- towncrier release notes start -->

## [0.16.0] — 2026-09-06

### Upgrade notes

**`KEY_SCHEMA_VERSION` goes 3 → 9 in this release.** Six changes each moved a stored
output. Each carries its own note under *Added* or *Changed (breaking)*, and this is the one
place they are listed together. If you persist any output named in the third column,
recompute it once against 0.16.0; `disarm.KEY_SCHEMA_VERSION` reads `9`.

| step | change | what moves, and what does not |
|---|---|---|
| 3 → 4 | single-letter Latin small capitals fold to their letter (#815) | `catalog_key` for seven code points; `search_key` and `sort_key` unchanged |
| 4 → 5 | six confusable rows become reachable from every preset (#833) | `canonicalize`, `canonicalize_strict`, `strip_obfuscation`, `normalize_confusables`, including Greek prose with a final sigma; the three key builders unchanged |
| 5 → 6 | the 54 negative enclosed letters fold to their letter (#815) | `catalog_key` for all 54; `search_key` and `sort_key` unchanged |
| 6 → 7 | `llm_guardrail` and `strip_obfuscation` stop naming emoji (#910) | `strip_obfuscation` for any input containing emoji; `llm_guardrail` output also changes, and is not a stored key |
| 7 → 8 | the deletion class is resolved, not only reported (#937) | `canonicalize`, `canonicalize_strict`, `strip_obfuscation`, `search_key`, `catalog_key`, `sort_key`, `skeleton_key`, `ml_normalize`, `llm_guardrail` and `rag_ingest`, for input containing `BS` or `DEL`; `strip_format` and `code_context` unchanged |
| 8 → 9 | two measured-visual confusable rows admitted by multi-font agreement (#738) | `canonicalize`, `canonicalize_strict`, `strip_obfuscation`, `normalize_confusables` for text containing either code point; `search_key`, `catalog_key` and `sort_key` unchanged |

**Two surfaces change behaviour without moving a key.** `llm_guardrail` and
`strip_obfuscation` now leave a visible emoji in place where they used to replace it with
its English name (#910). Removing one is a separate, opt-in step: `replace_emoji` (#972).

### Added

- **The meta-benchmark's prompt-hygiene composition replaces emoji with nothing (#972).**
  `disarm-composed:prompt-hygiene` declared `demojize=False` because naming hands an attacker
  words (#910) and nothing else was composable. With `TextPipeline(demojize="")` it now
  closes the Emoji Attack split: `aa🔥bb` comes back as `aabb` where it stayed split before,
  and the composition rejoins 1,192 of the 1,219 `Emoji_Presentation` code points on
  `emoji-delimiter-segmentation` instead of 0. The shipped `llm_guardrail` still keeps the
  emoji by #910's measured decision, so the bare `disarm` subject does not move; the two are
  scored side by side, which is what the composed subjects are for. A build whose `demojize`
  is bool-only rejects the declaration and the subject skips with the reason.

- **`replace_emoji` — removing an emoji, on all seven surfaces (#972).** An emoji
  inserted inside a word splits it for a subword tokenizer (Emoji Attack,
  arXiv:2411.01077). disarm could **name** an emoji or keep it, and removal was reachable
  only as a side effect of `transliterate` — so no composable step closed the split.
  `replace_emoji(text, replacement)` does, and `TextPipeline(demojize=...)` now takes
  `bool | str`: `True` names as before, a string replaces, `False` omits the step.
  `demojize(text, replacement=...)` is the same operation under the function that owns
  the emoji scanner.

  **Naming and replacing are separate functions because they read different tables.**
  Naming asks what CLDR calls a character, over a table wider than the emoji — CLDR
  annotates `U+2122`, so `demojize("x™y")` is `x trade mark y`. Replacing asks whether
  the UCD calls it an emoji, over the emoji-presentation set: `Emoji_Presentation=Yes`,
  an `Emoji=Yes` base carrying `U+FE0F`, and the ZWJ, modifier, keycap and flag sequences
  on those. So `™` and `©` stay where naming would have written a word over them, and a
  build that only replaces links neither the CLDR name trie nor the 182 KB behind it —
  **19 KB of wasm against 643 KB**, asserted by a new `demojize_replace` surface in the
  #695 coupling gate.

  The replacement is inserted verbatim, with no padding and no whitespace collapse,
  because the two useful values want opposite things and neither can be a default: `""`
  closes an intra-word split (`aa🔥bb` → `aabb`) and `" "` keeps two words apart
  (`stop🛑now` → `stop now`). One sequence takes one replacement however many code points
  it is written with, so a flag, a ZWJ family and a keycap each become a single space.

  **No shipped default moves.** `llm_guardrail` keeps a visible emoji on #910's
  measurement — naming writes attacker-chosen English into screened text, and removal
  fused `stop<emoji>now` into `stopnow` 144 times out of 144 — and `canonicalize` and
  `strip_obfuscation` are unchanged, so no stored key moves. The parameter is how a
  caller whose emoji sit *inside* words says so.

- **The keycap sequence people actually type is now one emoji (#972).** CLDR keys the
  keycap without its variation selector (`0031_20E3`), so `demojize("x1️⃣y")` returned
  `x1⃣y`: the selector dropped and the combining keycap left on the digit. Both spellings
  now name as `keycap: 1`, and both are removed as one emoji under a replacement.

- **`TextPipeline.purpose`: every profile says what it is *for*, in one sentence (#860).**
  `list_profiles()` returned names and the step list said what a pipeline *does*; neither said
  what it is for, which made the profiles the one part of the public surface a reader could not
  evaluate without leaving the REPL. It matters most where two profiles look alike and are not:
  `rag_ingest` has no confusables step — its recovery is transliteration, so `раураl` romanizes
  to `raural` — where `llm_guardrail` folds the same input to `paypal`. Choosing wrong there
  fails silently and in the unsafe direction. Additive, so nothing breaks and `list_profiles()`
  keeps returning strings; the list-with-purposes case is one line,
  `{p: get_pipeline(p).purpose for p in list_profiles()}`, and is in that function's docstring.
  Rust `api::Pipeline::purpose`, Python, Node, Ruby and Java — every surface with a pipeline
  handle; the C ABI has none, so it is not owed one. A hand-built `TextPipeline` returns `None`:
  the caller composed it and knows why. **The sentence is gated**, because two copies of one
  sentence in this repository have parted company before: every purpose must appear verbatim on
  `docs/policy-templates.md`, which also gained sections for `code_context`, `llm_guardrail`
  and `rag_ingest` — three of the eight profiles were undocumented.
- **`is_canonical` reaches every binding (#730 §5).** The verification-path predicate
  shipped in Rust and Python and stopped there, so five surfaces could ask disarm to
  normalize text and not to check whether it already was. Ruby `canonical?`, Node
  `isCanonical`, Java and Kotlin `isCanonical`, and on the C ABI `disarm_is_canonical`
  returning a **tri-state** — `1` canonical, `0` not, `-1` unknown preset — because every
  other predicate there is infallible and this one takes a name that can be wrong, where
  answering `0` would report "not canonical" for a question that was never asked. It joins
  the parity floor complete on all seven. Each binding's test pins the asymmetry the
  predicate exists for: `U+FA10` is reported clean by the detector and is not its own
  canonical form.
- **`confusable_coverage` — the per-script denominator, on all seven surfaces (#963,
  #884).** `unmapped_confusables` measures one bundled table against the whole
  6,565-source population. For a target disarm ships that is the right question; asked
  about a script it does not, the answer is dominated by the absence — Greek reports
  almost the entire population unmapped, and the number means only "there is no Greek
  table". A count determined by a table's absence is a blind spot with a number in front
  of it, which is worse than the exception it replaced, because it looks like data. The
  new entry point reports, per script, how many TR39 sources have a prototype in that
  script and how many of those disarm reaches: Greek **71 of 159**, Han **0 of 1,393**,
  Latin **1,833 of 1,985**. `folded` counts sources any bundled table reaches, not
  sources folded *toward* that script, which is why Greek is not zero — 71 of its
  sources are Greek letters the Latin table folds. The census is generated by
  `scripts/gen_confusable_census.py` from `data/confusables.txt` and a newly vendored
  `data/Scripts.txt` (UCD 17.0.0), and a test re-runs the generator to prove the shipped
  table is what its inputs produce. The grouping uses the **UCD's** script property
  rather than disarm's curated block table, because that table has no range for 207 of
  the prototypes and they are not all `Common` — Yi and Siddham letters are among them,
  and filing them under `Common` would move a coverage gap into a bucket labelled
  punctuation. Nineteen scripts disarm's own enum does not name are therefore
  addressable here, as are `Common` (893 sources) and `Inherited` (143), which
  `script_info` refuses outright — 16% of the population that two more `ScriptMeta`
  fields could not have reached. A script disarm knows that TR39 never uses as a
  prototype returns `0` of `0`, which is a different statement from "no such script" and
  is answered as one.

- **`data/confusables_vision.tsv`: measured-visual confusable rows admitted by multi-font
  agreement, and the rule that admits them (#738).** The supplement pins one confusable-vision
  tranche by its `danger` weight, and that file has not moved since the pin, so the stated
  threshold admits nothing new; the four further sets that shipped carry a mean SSIM per pair
  and a font count, not a weight, so they take a fourth file with an admission rule of their
  own: at least five fonts, mean SSIM at least 0.85, a letter or letter-number source, one
  ASCII letter as target, not an accented form of it, and not already covered. Coverage is
  measured through `canonicalize`, because every preset runs NFKC before the fold and 96 of the
  793 novel pairs are covered by that alone — the bare fold would call them gaps. Under the
  rule the two published sets admit two rows, `U+4E28 CJK UNIFIED IDEOGRAPH-4E28` (ten fonts)
  and `U+3021 HANGZHOU NUMERAL ONE` (six), both absent from TR39 and so outside the
  `unmapped_confusables()` denominator, which now says which population it enumerates. The
  rule leaves out, on purpose, the single-font hits at the top of the set, the Indic fraction
  symbols that agree in nine fonts (a numeral folded to a letter is what `digit_policy`
  refuses), and the accented `l`s that agree in fifty to ninety (letters, not confusables).
  `scripts/measure_confusable_vision.py` regenerates the rows and the band table the file's
  header quotes; the RaySpace superset and the IDN-filtered subset are not published at this
  revision and remain #738's open threshold decision. THREAT_MODEL.md now claims what was an
  unclaimed strength: detection is script-agnostic, and the fold is Latin- and
  Cyrillic-targeted by design.

  **Upgrade note — `KEY_SCHEMA_VERSION` goes 8 → 9.** `canonicalize`, `canonicalize_strict`,
  `strip_obfuscation` and `normalize_confusables` move for text containing either code point:
  `canonicalize("丨")` was `丨` and is now `l`. `search_key`, `catalog_key` and `sort_key`
  are byte-identical — they transliterate before the fold, and `丨` romanizes to `gun` on
  that path as it did before. The fixture corpus carries both characters.

- **`digit_policy` on the six key builders, `skeleton_key`, `edit_distance` and
  `nearest_match` reach Node, Ruby, Java, Kotlin and the C ABI, and a pipeline handle takes
  `withDigitPolicy` (#894, #896).** The binding half of the two 0.15.0 deferrals, in one
  change so the parity rows are touched once. Each binding takes the policy the way it
  already took it on `normalize_confusables`: a trailing options object on Node, a keyword
  on Ruby, an overload with the `DigitPolicy` enum on Java and a default argument on
  Kotlin, and on the C ABI a separate `_opts` symbol per builder so the existing entry
  points keep their ABI. `skeleton_key` (#650) was in no binding at all. `nearest_match`
  follows each binding's result convention — an object on Node, a `{ value:, distance: }`
  hash on Ruby, a `NearestMatch` record on Java, a JSON object or the JSON `null` on the C
  ABI, where a malformed candidate list is an error rather than "nothing close". Node,
  Ruby and Java pipeline handles gain the profile setter from #646; the C ABI has no handle
  family to put it on. `skeleton_key`, `edit_distance` and `nearest_match` join the parity
  floor, complete on all seven surfaces.

- **`digit_policy` reaches the six key builders through the core, and the Rust API gains
  `canonicalize_with`, `canonicalize_strict_with`, `strip_obfuscation_with`,
  `search_key_with`, `sort_key_with` and `catalog_key_with` (#896).** #885 shipped the setting
  as a Python pre-pass, so the Rust API and every other binding could not express it. It is
  now a step at the head of each builder's list — a no-op under the default, so every default
  key is byte-identical (the fixture gate proves it) — and the builder's own fold runs under
  the same policy. The port was measured before it was written: over 290,889 probes, `tr39`
  output is identical to the pre-pass on all six builders. Two things that sweep found are
  pinned: the pre-fold is the *fixed-point* fold, which composes between passes, so a
  decomposed base + mark reaches the row keyed on its composed form; and the inert fast path
  is the default's only, since its confusable-source set is generated for the default and a
  `tr39`-only row (`ā` → `ã`) was invisible to it. The Python pre-pass is gone.

- **`fold_punctuation`: typographic punctuation folded to its ASCII spelling (#703).** The
  dash family and the minus sign to `-`, the curly and low-9 quotes and the primes to `'` /
  `"`, the ellipsis to `...`, the non-standard spaces to a space. Nothing else did this as a
  stated purpose, and the two functions that came closest disagreed: `canonicalize` folds
  five dashes and skips the em dash and the horizontal bar, `transliterate` folds those two
  and rejects the other four, so a key built from `canonicalize` treated `a—b` and `a-b` as
  distinct while treating `a–b` and `a-b` as the same. A separate primitive rather than a
  change to either, because `canonicalize` is a security fold entitled to map `“` to `''`.
  CJK and Arabic punctuation, the Catalan middle dot and the bullet are left alone on
  purpose, and spaces fold rather than delete. Named for the operation, per the naming rule:
  the issue proposed `ascii_punctuation`, which names the outcome. Rust and Python; the
  other bindings follow with the next parity pass.

- **`disarm scan --sarif`, `--baseline` and `--write-baseline`, and a fingerprint that
  survives an edit (#705).** SARIF is the small half: a 2.1.0 document so findings land in
  GitHub's Security tab and as annotations on the pull request that introduced them, with
  the disarm fingerprint in `partialFingerprints` so a consumer that baselines on its own
  keys on the same identity.

  The fingerprint rule is the part worth having even if SARIF never shipped: **the file,
  what was found, and which occurrence of it this is — never the line.** The naive
  identity breaks on the first commit that inserts a paragraph, because every finding
  below it looks new; keyed on the occurrence index, inserting text above a finding raises
  no second alert. The honest limit is documented beside it and asserted: inserting a
  *second* occurrence above a recorded first accepts the new one and reports the old — the
  count stays right, nothing is dropped, but which occurrence is named can swap.

  A baseline is what lets the check go on at all. A repository with years of history is
  not clean on its first scan, and requiring it to be clean first is the order that stops
  adoption. `--write-baseline` records what exists today; `--baseline` suppresses it
  (counted, not shown) and fails only on what arrives afterwards. A baselined finding that
  no longer exists is reported as **stale** rather than quietly kept, so the file shrinks
  as the tree is cleaned. The file is versioned, and a version the reader does not know is
  refused rather than matched against nothing.

  The SARIF level map lives in the writer, not on `AnomalyKind`: #705 item 4 says a
  severity on the enum is a public API addition and its own change, so that is filed
  separately, and a test reads the kinds from the Rust source and asserts the map covers
  every one — it cannot fall behind the enum. `smuggled` is the one `error`, the one
  finding that needs no threshold to interpret; the rest are `warning`.

  `docs/cli.md` carries the GitHub Actions snippet, including the detail that decides
  whether it works: the upload step has to run before any failing exit, or the findings
  that caused the failure are the ones nobody sees.

- **`get_pipeline(profile, digit_policy=...)` and `TextPipeline(digit_policy=...)`: a
  profile takes the fold's digit policy at construction (#646).** Eight profiles shipped
  and none could express `digit_policy`, so a caller following the CVE page to
  `llm_guardrail` got the `numeric` side of the trade with no way to ask for the other and
  no signal that a choice had been made: `get_pipeline("llm_guardrail")("g੦ogle")` is
  `g0ogle` while `normalize_confusables("g੦ogle", digit_policy="tr39")` is `google`. The
  policy is fixed when the profile is built, on the call that resolves the steps — the
  position it holds on the key builders — and reported through `steps()` only when it is
  not the default, so every profile's default output is byte-identical. A pipeline with no
  confusables step refuses a non-default policy at construction rather than keeping a
  setting that would never run; `rag_ingest` recovers by transliteration, not by a fold.
  Rust: `api::Pipeline::with_digit_policy`. `docs/architecture/prototype-policy.md`
  records the decision as §4. Refs #896 for the Rust API and binding reach of the key
  builders.

- **`disarm scan PATH...` — the one API built for scanning, pointed at files (#704).**
  `inspect_anomalies` has always returned everything a scanner needs — a kind, a span,
  evidence and a plain-language reason — and there was no way to run it over a file. Every
  CLI subcommand took text from an argument or stdin; none took a path. That single absence
  is most of why third-party tools in this space exist as separate projects: the detection
  is the hard part and disarm has it, while the file plumbing is the easy part and disarm
  had none of it.

  Python rather than a Rust binary, which is #704's own recommendation: plumbing over an
  API that already exists ships now and can be measured against real repositories before
  anyone commits to a binary per tag.

  The four rules #704 takes from `juriku/untrace`, each asserted:

  - **git's ignore rules, all three sources.** `.gitignore` in the scanned directory *and
    every parent*, `.git/info/exclude`, and `core.excludesFile`. A scanner reading only
    the nearest file makes `scan src/` and `scan .` disagree on one tree, which users
    report as flakiness. Delegated to `git check-ignore` rather than reimplemented, so the
    two cannot disagree; `--no-gitignore` turns it off.
  - **A defensible skip list.** `node_modules`, `__pycache__`, `.venv`, `.terraform` and
    the like are skipped. `build`, `dist`, `out`, `target`, `bin` and `vendor` are **not**:
    hand-written in some projects, and a scanner that skips them by name reports clean on
    a tree it never read.
  - **Symlinks are never followed**, directory or file, so a scan stays inside the tree.
  - **An exit-code contract.** `0` clean or found-without-`--fail`, `1` found with
    `--fail`, `3` a path could not be read. `2` stays argparse's. A missing path and an
    unlistable subdirectory both surface as `3` — the first version swallowed both and
    reported clean, because `os.walk` yields nothing and raises nothing for either.

  `--json` converts the library's byte spans to 1-based line and **character** column,
  which is what an editor's gutter shows; pinned with a non-ASCII prefix where the two
  diverge. Binary, non-UTF-8 and oversize files are skipped without error. Inline
  suppression is deliberately not here (#704 item 5): there is nothing to suppress until
  there is a scanner.
- **`percent_escape`, the fourth scheme on `decode_smuggled` (#727).** disarm ships
  `percent_encode` and shipped no decoder, so every detector reported clean on a
  percent-encoded value: `has_anomalies("ad\u200bmin")` is `True` and
  `has_anomalies("ad%E2%80%8Bmin")` is `False`, for every detector and every row of #727's
  table. A caller whose value arrives encoded — a query parameter, a stored key, a
  `Content-Disposition` filename — could not reach the starting point the ordering
  invariant in `THREAT_MODEL.md` requires.

  A fourth scheme on #701's `Payload` rather than a `percent_decode`, which is the shape
  #727 itself preferred and the decision #902's R14 recorded: a decode-for-inspection
  primitive returns what the escapes *spelled*, as evidence, where a substituting decoder
  hands back a string some callers will re-emit — and repeated decoding is its own
  vulnerability class. Decoded exactly once: `%25%32%45` spells `%2E`, and that `text` is
  the evidence of double-encoding, not a prompt to decode again.

  The error contract, each answer pinned: `%FF` is not UTF-8 and comes back as bytes with
  no `text`, through the same printable rule as the other three schemes; `%` with fewer
  than two hex digits is malformed, is not consumed, and ends a run; a single `%20` is an
  escaped space, not a payload — the same two-unit floor as variation selectors, for the
  same reason.

  **Deliberately not fed to the anomaly detector.** Unlike the three invisible carriers, a
  percent run spelling readable text is ordinary in any URL; reporting it as `smuggled`
  would fire on every escaped query string. `decode_smuggled` reports it and
  `inspect_anomalies` does not, and a test asserts both halves.

  `THREAT_MODEL.md` now states the blindness beside the ordering invariant, and
  `percent_encode`'s docstring says a value that arrives encoded is opaque to the rest of
  the library until it is decoded.

- **`per_word=True` on `is_mixed_script` and `has_bidi_conflict` (#901).** Both answer a
  question about the whole string, and both docstrings were accurate about that. The
  trouble is what a caller does with them: they look like standalone detectors, so callers
  compose them, and `is_mixed_script(x) or has_bidi_conflict(x) or find_confusables(x)`
  rejects every bilingual user. Measured, that rule turned away **all six** rows of #901's
  table — the two spoofs and the four ordinary bilingual strings alike.

  `has_anomalies` has told them apart since it was written. `per_word=True` is that
  distinction on its own, so the rule can be built from parts: with it, and with #900's
  `allowed_scripts` for the third primitive, only `hellо` and `שלוםworld` are rejected.

  **Words, not whitespace tokens.** #901 proposed splitting on whitespace; measured, that
  fires on `IT-специалист`, `email:почта`, `user@почта.рф`, `Tokyo/東京` and `ru_текст` —
  five ordinary shapes, every one of which `has_anomalies` calls clean. The parameter uses
  the detector's own word splitter instead, borrowed rather than restated, and a test
  asserts the two agree on every row of the table.

  Rust gets `api::is_mixed_script_per_word` and `api::has_bidi_conflict_per_word`; the
  existing functions are unchanged.
- **`on_empty` on the four key builders, and the empty-key census in nine docstrings
  (#728).** Every preset and key builder maps some non-empty input to `""`, so a value
  that was entirely stripped is indistinguishable from one that was never there.
  `sanitize_filename` was the only surface that guarded it, with the `_` sentinel from
  #485.

  Measured at Unicode 15.0.0, the oldest version CI runs: `search_key` takes **139,870**
  single characters to `""` (2,402 excluding the PUA), `slugify` 243,399, `canonicalize`
  137,955.
  The version is stated because the census is not one number — a 16.0.0 host counts the
  16.0 additions each surface takes to `""`, and the first version of the gate, measured
  on one, failed CI by exactly those. The gate now compares exactly on the pinned version
  and asserts a lower bound on any newer one, so neither branch is a skip.
  A caller storing `search_key(username)` as a uniqueness key has all of them, every
  string built from them, **and** "no username" competing for one slot.

  This is not the homoglyph collision the key builders exist to produce — `аdmin` and
  `admin` *should* meet. It collapses absence onto a value, which arXiv:2608.06508v1 §2.2
  calls code-side semantic collapse and §7.5 says is fixed by moving the sentinel outside
  the value range rather than by normalizing harder.

  `on_empty` applies **only when the input was non-empty**, which is the whole point:
  substituting for an empty input too would put absence and a stripped value back in one
  slot. `search_key("")` is `""` with or without it; `search_key("\u200b")` is the
  sentinel. The three stripped values still share a key, and that is correct — they are
  all *input that reduced to nothing*.

  The census is frozen by `tests/test_empty_key.py`, so a strip class that widens becomes
  a diff somebody reads rather than a silent change to nine documented numbers.

  Python-only for now, as `digit_policy` was in #885: it is a post-pass on the output, and
  the Rust and binding half belongs with #896 rather than beside it.

- **`decode_smuggled(text)` and the `smuggled` anomaly kind — decode what a hidden run
  *spells* (#701).** disarm strips the three ASCII-smuggling carriers and, since #700,
  reports that invisible characters are present. Neither answer tells the caller that the
  run reads `tracked-by:acct-99213`.

  Presence and decode are different strengths of evidence. An invisible character can
  arrive by accident — a copy-paste artefact, a BOM, an editor quirk. A run that decodes to
  readable text cannot: random damage does not spell words. So a decode needs no threshold
  and no policy to interpret, which is why it is a kind of its own rather than a longer
  `invisible` detail.

  Three schemes, all arithmetic on code point values with **no table**, which matters under
  #695: `tag_ascii` (`U+E0020`–`U+E007E`), `variation_bytes` (`U+FE00`–`U+FE0F` and
  `U+E0100`–`U+E01EF`) and `zero_width_binary` (`U+200B` = 0, `U+200C` = 1, MSB first).

  Two rules keep the output honest. `Payload.text` is populated only when the bytes are
  valid UTF-8 and wholly printable, so a run of arbitrary selectors is reported as *n*
  bytes with no string rather than as a bogus decode. And a well-formed emoji subdivision
  flag is not a payload — the allowlist is the stripper's own rather than a second copy of
  it, which is the drift #700 was about.

  In `inspect_anomalies` the decode **outranks every other kind for the same span**, as
  #701 asks — implemented by ordering rather than suppression, so the run is still reported
  as `invisible` too and a caller already matching on that kind keeps working.
- **`resolve_deletions` and `resolve_cr` on `TextPipeline`, the profiles and the CLI
  (#937).** The step runs **first** in `STEP_ORDER`, before `normalize` rather than merely
  before `strip_control`, because the renderer saw the code points as written and every
  later step changes what the preceding cell is: `ﬁ` + `BS` erases to nothing and to `f`
  once NFKC has split the ligature; `щ` + `BS` erases to nothing and to `sh` once
  transliteration has produced `shc`.

  A cursor over **cells**, not a stack over code points — the two branches a stack gets
  wrong are `X` + `ZWSP` + `BS` and `e` + `U+0301` + `BS`, where a terminal erases the
  whole cell and a pop leaves the base. The format half of that rule reuses disarm's own
  predicates rather than a blanket `Cf` test, which is narrower and more correct: a `Cf`
  that renders, like `U+0605`, does occupy a cell.

  `resolve_cr` is a *parameter* of that step rather than a step of its own, the way
  `zalgo_max_marks` parameterises `strip_zalgo`, and is reported through `steps()` as the
  step's parameter so it stays visible.

- **`skeleton_key(text, *, digit_policy="numeric")` — the prototype classes disarm's table
  keeps apart (#650).** TR39 puts `I`, `l` and `1` in one equivalence class and `O`/`0` in
  another; disarm's table folds the whole capital-I family to `I` and stops there, so
  `paypaI` survives every shipped surface intact. This closes it, as a **spoof key**: the
  output is never for display, and it is more destructive than any preset that forwards
  text.

  **A separate builder rather than a flag, for a measured reason.** The letter half costs
  six collision groups in the 235,976 entries of `/usr/share/dict/words` — `Ione`/`lone`
  is the only ordinary-word merge among them. That price holds *only on cased text*: after
  a case fold, `I ≡ l` becomes `i ≡ l` and the same class costs 264 groups of ordinary
  vocabulary (`boiling`/`bolling`, `doit`/`dolt`, `ail`/`all`). A factor of 44. No existing
  key builder runs a confusable fold before folding case, and `catalog_key` cannot be
  reordered to — fold-before-transliterate is required for idempotency (#419).

  `digit_policy="tr39"` adds the digit half, `1 ≡ l` and `0 ≡ O`. That is what an
  identifier skeleton wants and what a deduplication key must not have: `SKU-100`,
  `SKU-1O0`, `SKU-IOO` and `SKU-l00` all become one key, as do `v1.0.1`, `vI.O.I` and
  `vl.o.l`. Opt-in, never a default.

  The digit policy rides on `PresetCtx` rather than on the step, which is a **third option**
  beside the two #646 §2 weighed: it neither triples the step lists nor defeats the
  #695/#868 monomorphisation, because the mask is still computed at compile time from a
  single list. `scripts/perf_lint.sh` and the wasm coupling gate are unchanged. That
  mechanism is what #896 needs to reach the other key builders from Rust.
- **`find_confusables(..., allowed_scripts=[...])` — say what legitimate input looks like
  (#900).** With the default `target_script="latin"` the function asks *"could this
  character imitate a Latin letter"*, one character at a time, with no reference to the
  string around it. The docstring was accurate; the trouble is that this is the function
  callers reach for as a spoof detector, and used that way it reports every Russian word.
  `find_confusables("Москва")` is six findings out of six letters, so a registry gating on
  `bool(find_confusables(name))` rejects its own users' language. `confusable-bench.v1`
  cannot see it: all 140 rows target English brands and all 20 benign rows are Latin.

  A character belonging to a declared script is no longer reported; everything else still
  is. Two properties hold **by construction**, which is what keeps this from costing
  recall the way "no Latin in the string, so nothing to imitate" would:

  - A whole-script substitution survives it. Declaring `Latin` does not exempt Cyrillic,
    so `аррӏе` is still five findings.
  - `Common` and `Inherited` are never allowed, whatever the caller passes. `ℐ`, `Ⅰ`, `𝐈`
    and the mathematical alphanumerics belong to no script, so declaring every script
    disarm knows still reports them.

  Rust gets `api::find_confusables_with`, following the `normalize_confusables_with`
  precedent — the existing `find_confusables` is unchanged and still infallible. Names are
  the ones `detect_scripts` returns and are matched case-insensitively, so the lowercase
  spelling `target_script` uses also works.

- **`deletion`: a lone carriage return that overwrites text (#739).** Boucher et al.,
  *Bad Characters* (IEEE S&P 2022) §IV-G names four classes of imperceptible
  perturbation; `tests/test_attack_corpus.py` cites that taxonomy as its source and
  generated three of them. The fourth is deletions — "the backspace (BS) and delete
  (DEL) characters… there is also the carriage return (CR)". `ZZZZZZ\rpaypal` renders as
  `paypal` on any terminal and **nothing reported it**: a lone `CR` is whitespace, so it
  splits the tokens either side of it and both halves are clean on their own. No
  per-token rule could ever see it, so the check is text-level and shared by
  `has_anomalies` and `inspect_anomalies` rather than stated twice.

  Its own kind rather than a `control` finding, because the kind names the treatment
  path: `BS`/`DEL` are non-whitespace controls that `strip_control_chars` removes and
  `control` already reported, while `CR` is whitespace-class and `collapse_whitespace`
  deliberately folds it to a space — which *surfaces* the overwritten prefix instead of
  reproducing the rendering. It fires only where a `CR` can overwrite something: not
  before an `LF`, not at end of text, not at the start of a line. Its known false
  positive is a classic Mac OS file, documented rather than fixed, since the two are
  indistinguishable from the bytes.

- **`is_canonical(text, *, preset="canonicalize")` — the verification-path predicate
  (#730).** Every other normalization surface here is generation path: text in,
  normalized text out. There was no counterpart for the question a caller has about
  bytes that arrive already bound to a decision — a signed payload, a primary key with
  rows pointing at it — where quietly re-normalizing defends the comparison and leaves
  the second representation in circulation. `has_anomalies` looks like that predicate
  and is a strict under-approximation of it: over every assigned code point, 142,760
  (5,292 excluding the Private Use Area) are reported clean and are not their own
  canonical form, while **zero** go the other way. So the obvious accept gate — reject
  if `has_anomalies`, else take the bytes — admits CJK compatibility ideographs, Arabic
  presentation forms, Kangxi radicals and all of fullwidth Latin. Widening the detector
  is not the fix (`ＮＨＫ` is ordinary Japanese text; that was #633 and #907), so this is
  a second question with its own answer. Defined as `preset(text) == text`, but it does
  not build the normalized copy to return a boolean and takes the `Guard::Inert` fast
  path when the input is untouched. `preset` accepts any preset or policy-profile name.

- **The Latin-shape exposure set is published and gated (#815).**
  `tests/fixtures/latin_shape_exposure.tsv` lists the **299** non-ASCII code points that
  read as a Latin letter and reach ASCII on no surface, with a per-block gate so a table
  refresh cannot widen it quietly. An exposure set, not a bug list: Latin Extended-D's
  medievalist letters have no sensible ASCII fold.

  The number was 401 in the issue, and wrong in both directions. Its selector matched
  names *starting with* `LATIN `, `MODIFIER LETTER ` or `TURNED `, or containing
  `SMALL CAPITAL` — so `NEGATIVE CIRCLED LATIN CAPITAL LETTER A` and 51 siblings were
  outside the count entirely. Widening it by hand then went wrong three more ways, each
  found by reading the output rather than by reasoning: 53 **combining marks**, which are
  `strip_accents`' business; 52 **TAG characters**, which are *stripped* rather than folded
  (#413) and so read as unhandled to a naive test; and names that merely *contain* LATIN,
  where `LATIN CROSS` is a symbol and `LATINATE MYSLITE` is Glagolitic.

  The selector is now a word-bounded `LATIN [CAPITAL|SMALL] LETTER` plus a category of
  letter or symbol, which excludes marks and format characters by construction.

  One caveat the census cannot express, recorded on the page beside it: it counts
  *unfolded* code points, so one that folds to the **wrong** letter is invisible to it.
  That is #916.

- **`strip_plane14` — the TAG block is a composable step, not a side effect (#914).**
  Removing U+E0000–U+E007F was reachable only by enabling `demojize` or `transliterate`.
  Neither belongs in a screening pipeline, so a composed `TextPipeline` could not remove
  the concealment carrier behind #700, #701, #812 and #748 without also glossing emoji
  into words or romanizing the text:

  ```python
  screening = dict(normalize="NFKC", strip_bidi=True, strip_zero_width=True,
                   strip_control=True, strip_pua=True, confusables=True, ...)

  TextPipeline(**screening)(concealed)                      # payload intact
  TextPipeline(**screening, strip_plane14=True)(concealed)  # 'formats code neatly.'
  ```

  A real `PipelineSteps` flag in `STEP_ORDER`, taken by `Pipeline::new` so every
  construction site has to decide — the shape #911 gave `strip_pua`. It runs **before**
  `demojize`: a concealment carrier should be removed before any step can gloss it into
  words, and that order also keeps the six profiles that strip it today byte-identical.

  Named for the Unicode region, like `strip_pua`. `strip_tags` reads as markup.

  A valid emoji subdivision flag survives — `invisibles::strip_tags` already draws that
  line for `canonicalize` (#413) and the step reuses it rather than inventing a second
  rule that could disagree.

  Default `false`; the six profiles that already stripped it set it explicitly, so no
  shipped profile moves. `code_context` keeps its input by design. **`normalize_web_input`
  never stripped the carrier and still does not** — recorded in a test rather than changed,
  because whether a profile named for screening web input should pass a concealment
  channel is a separate call from adding the capability.

  This unblocks #910: turning `demojize` off no longer silently disables TAG stripping,
  so a text-injection primitive is no longer traded for a concealment channel.

- **Six confusable rows were unreachable from every preset (#833).** `STEP_ORDER` runs
  `normalize` at position 1 and `confusables` at position 7, so a preset folds the NFKC
  *image* of the input, never the input. When the image had no row of its own, the row
  that existed for the source could never fire:

  ```python
  get_pipeline("llm_guardrail")("ϲecure")  # was 'oecure', now 'cecure'
  ```

  `ϲ` U+03F2 normalises to `ς` U+03C2, which had no row; the case fold then made it `σ`,
  which folds to `o`. Three steps to the wrong answer, and the `c` the table already
  carried was never reachable.

  #245 diagnosed exactly this for U+2502 and fixed it with one literal in
  `CUSTOM_LATIN_OVERRIDES` — Latin only, by that dict's own name, which is why the
  Cyrillic half stayed open. The generator derives the rows now, so the next class that
  routes through an unmapped image is covered without an edit: `ς` → `c`/`с`, `Ɛ` → `E`,
  `ȷ` → `j`, `Σ` → `С`, `│` → `ӏ`.

  Latin and Cyrillic only, deliberately. The RTL tables are built by inverting equivalence
  classes, so a source there is often an Arabic *mathematical* variant whose NFKC image is
  the ordinary letter; propagating those rows would fold the base letter and turn `ث` into
  `ى`. That is #848's intra-script case and needs its own analysis.

  The order-dependent count drops from 68 to 65 for Latin and 8 to 5 for Cyrillic, and
  #834's "actionable set" is now empty. The rows that remain diverge because both readings
  are defensible, which is what that documentation is about.

  **Upgrade note — `KEY_SCHEMA_VERSION` goes 4 → 5.** `canonicalize`,
  `canonicalize_strict`, `strip_obfuscation` and `normalize_confusables` move; the three
  key builders are byte-identical, having no confusable step on this path. Greek prose
  containing a final sigma changes, though `canonicalize` already rewrote Greek before
  this — `κόσμος` was `koouoς` and is now `koouoc`.
- **The 54 negative enclosed letters fold to their letter (#815).** `🅐` and `🅰` folded on
  no surface. Their positive counterparts `ⓐ` and `🄰` do, because NFKC decomposes those
  and leaves these alone — two neighbouring blocks, opposite outcomes, and a "fancy text"
  generator offers both side by side, so one style was neutralised and the other passed
  through untouched.

  Derived from the UCD name and filtered to what NFKC does not already handle, so the set
  is exactly the 54 that need it: NEGATIVE CIRCLED (26), NEGATIVE SQUARED (26), CROSSED
  NEGATIVE SQUARED and one stray SQUARED. Two families that match the same name pattern
  are excluded because both are already handled correctly: **Tags** are stripped as a
  smuggling class (#413), and **combining letters** are category `Mn`, which is
  `strip_accents`' business.

  Four of them are dual-purpose. `🅰` is NEGATIVE SQUARED LATIN CAPITAL LETTER A *and* the
  blood-type A button, so it now folds under `canonicalize`, following #614 — inside a
  comparison preset the fold wins over the name, or a spoof and its target stop being
  equal. `llm_guardrail` still names it, because demojize runs before the fold there;
  that divergence is #918's subject. The `build.rs` gate on the emoji/confusable overlap
  moves 50 → 54 and caught this, which is what it exists for.

  **Upgrade note — `KEY_SCHEMA_VERSION` goes 5 → 6.** `catalog_key` moves for all 54.
  `search_key` and `sort_key` do not. The key-stability corpus contained none of these,
  which is the **third** time this cycle the fixture stayed green through a key change
  because its corpus did not sample the class being fixed; 58 rows added with it.

- **`scripts/watch_pr.py` — a PR watcher whose decision logic is tested.** Shepherding
  loops kept being written by hand, and four bugs kept coming back:

  1. **A reviewer comment waited on CI.** Threads polled after checks meant a comment
     sat through an entire run before anyone noticed.
  2. **A running check was reported as a failure.** GitHub gives an in-flight check
     `conclusion: ""`, not `null`; a loop waiting for `null` to clear exits early and
     then prints the running jobs as failures.
  3. **A structurally blocked PR was slept on.** `BLOCKED` with nothing pending and
     nothing unresolved means a required review or a protection rule. Waiting cannot
     fix it, so it is now a stop condition.
  4. **A mergeable PR was held.** `UNSTABLE` and `HAS_HOOKS` are mergeable; gating on
     "every check COMPLETED" waits on jobs that never gate the merge. #912 merged with
     a check still in flight.

  `decide()` is a pure function of a snapshot, so `tests/test_watch_pr.py` covers all
  four without a network, and each bug was re-introduced to confirm the matching test
  fails. Exit codes: `0` merged, `1` closed or unconfirmed, `2` a human is needed,
  `3` gave up.
- **Single-letter Latin small capitals fold to their letter (#815).** `ᴀ` `ᴅ` `ᴊ` `ᴘ` `ᴛ`
  `ꜰ` `ꞯ` reached ASCII on no surface, because TR39 lists them only as *destinations*.
  `ASCII_FOLD` (#341) resolves a small capital when it is a row's target — which is why
  `ᴍ` folded, U+1D0D being a TR39 source as well — but a glyph nothing points at has no
  row to resolve. The result was a half-conversion, which is worse than a clean miss:

  ```python
  canonicalize("ᴄᴀɴ ʏᴏᴜ ᴜɴᴅᴇʀsᴛᴀɴᴅ ᴍᴇ")  # was 'cᴀn you unᴅersᴛᴀnᴅ me', now 'can you understand me'
  ```

  A mangling matches neither the attack nor the target, and `llm_guardrail` handed it to
  the model in that state. Seven rows, derived from the UCD name rather than enumerated,
  so a future small capital is covered without an edit. The digraph and barred forms
  (`ᴁ`, `ᴃ`, `ᴆ`) are deliberately left: folding those is a visual judgment, which is the
  open policy question in #815 rather than something this decides.

  **Upgrade note — `catalog_key` output moves for these seven code points.**
  `KEY_SCHEMA_VERSION` goes 3 → 4. `search_key` and `sort_key` do not move; they carry no
  confusable step. Reindex if you persist `catalog_key` values containing small capitals.

  The key-stability corpus contained **zero** small capitals in 22,977 rows, which is why
  the fixture stayed green through a key change. 75 rows added, and
  `tests/test_small_capital_folds.py` asserts the class derivationally.

- **`TextPipeline(strip_pua=...)` — the one `ProfileSpec` field composition could not
  express (#911).** `strip_pua` was set post-hoc inside `ProfileSpec::build` rather than
  taken by `Pipeline::new`, so it was reachable from named profiles and from nowhere
  else. A caller compiling their own pipeline silently kept all **137,468** Private Use
  Area code points that #814 strips in every screening profile:

  ```python
  probe = "a\ue000b"
  get_pipeline("llm_guardrail")(probe)          # 'ab'
  TextPipeline(normalize="NFKC", ...)(probe)    # 'a\ue000b' — every PUA code point kept
  ```

  `Pipeline::new` takes it as a parameter now, so every construction site has to decide
  and none can forget. The default is `False`, so no existing pipeline moves. Plain
  `bool` rather than the `Option<bool>` the issue proposed: `strip_control` and
  `strip_zero_width` use `None` to *derive* from `collapse_whitespace`, and `strip_pua`
  has no such rule, so `None` would be a third state meaning exactly what `False` means.

  Four of the seven `strip_pua` profiles never showed the gap, which is why it survived:
  they set `transliterate`, and transliteration already drops PUA. That masking is
  incidental rather than protection — the three that do not transliterate
  (`llm_guardrail`, `normalize_web_input`, `ml_corpus_normalize`) lost the whole area.

- **`strict_iso9` and `gost7034` are reachable from `disarm pipeline --steps` (#911).**
  Found by the new composability gate. Both were on `TextPipeline` and absent from the
  CLI allowlist, the same way `strip_bidi` had been before #250. `lang` stays out
  deliberately: it takes a value, so it needs its own flag rather than a step name.

- **`benchmarks/adversarial_eval` scores a named surface (#903).** `metrics.py` imported
  `strip_obfuscation` at module level and applied it to both the perturbed text and the
  clean target, so the harness measured one surface in one role. It could not answer "how
  does `canonicalize` recover this corpus compared with `strip_obfuscation`", and it
  scored the wrong surface for any consumer whose declared sanitise entry point is not
  `strip_obfuscation`.

  `evaluate(..., transform="disarm.canonicalize")` and `--transform` on the CLI. A dotted
  **string** rather than a callable, because the scan runs across a process pool: a
  function object cannot cross that boundary and a name can. It is resolved inside each
  worker beside the confusables table, and once up front so a bad name fails before the
  pool starts rather than inside the initializer.

  `EvalResult.transform` and the report header record which surface produced the numbers,
  so a report can never be read as a `strip_obfuscation` figure when it is not.

  **The default is unchanged**, deliberately: every committed report and the pre-release
  BitAbuse cadence are `strip_obfuscation` figures, and a default that moved would
  silently reinterpret all of them. No metric changed.


### Changed

- **The meta-benchmark scores disarm's prompt-hygiene job through the composed pipeline,
  not the `llm_guardrail` preset (#972).** The preset keeps a visible emoji in place by #910's
  measured decision and takes no `demojize` override, so the parameter #973 added could not
  reach the bare `disarm` subject and the Emoji Attack split stayed open on the job's own
  benchmark. The job now answers with `ComposedPromptHygiene.STEPS`, the same declaration
  scored as `disarm-composed:prompt-hygiene`, so there is one pipeline named twice rather
  than one built for a benchmark. On `emoji-delimiter-segmentation` the bare subject rejoins
  1,192 of 1,219 `Emoji_Presentation` code points where it rejoined 0. A build that rejects
  the declaration falls back to the preset under its own predicate name, so a 0.14.1 build
  still has a prompt-hygiene surface and the report says which one answered.

### Changed (breaking)

- **The deletion class is now resolved, not only reported — and `KEY_SCHEMA_VERSION` is
  8 (#937).** `BS` and `DEL` erase the preceding *cell* before any other step runs, so
  `canonicalize` on a run that renders as `paypal` returns `paypal` where it returned
  `pXaXyXpXaXlX`. This **reverses the out-of-scope call #934 recorded**, on measurement:
  0 of 51 surface/form pairs recovered any of the three forms, and the cell model recovers
  all of them while changing none of the clean inputs it was checked against.

  #934's reason was that the class is renderer-dependent, so resolution risked losing text
  a reader can see. What an erase removes is the cell *before* the control, and in every
  row of the paper's released corpus that cell is the attacker's insertion — dropping it
  is the direction `strip_zero_width` already takes. The detector is untouched, so a
  reader who saw a control picture is still told.

  Affected: `canonicalize`, `canonicalize_strict`, `strip_obfuscation`, `search_key`,
  `catalog_key`, `sort_key`, `skeleton_key`, `ml_normalize`, and the `llm_guardrail` and
  `rag_ingest` profiles. **Unchanged by design:** `strip_format`, whose contract is
  display-preserving, and `code_context`, where a literal `\b` in source is data.

  **A lone `CR` is still resolved by nothing.** It is byte-identical to a classic Mac OS
  line ending, so `TextPipeline(resolve_deletions=True, resolve_cr=True)` is the only way
  to get it, and turning it on means `line1<CR>line2` becomes `line2`.

  Stored keys move only for input containing `BS` or `DEL`. The fixture was green through
  the change — the fourth time in this cycle that its corpus did not sample the class
  being fixed — so 34 rows were added covering every shape the model has a rule for.

- **`llm_guardrail` and `strip_obfuscation` no longer name emoji (#910).** Both converted
  an attacker-chosen emoji into attacker-chosen English *inside the text being screened*:

  ```python
  get_pipeline("llm_guardrail")("ignore😀 previous")
  # was 'ignore grinning face previous', now 'ignore😀 previous'
  ```

  Measured over `Emoji_Presentation`, 1,180 of 1,219 code points reached a name, together
  spanning **1,272 distinct English words** — including `stop`, `end`, `new`, `key` and
  `no` — with up to eight words from a single code point. The emoji was always visible, so
  this was never concealment: the sanitiser was the thing writing new words.

  This is the third time naming won over neutralizing, and the first where no table was at
  fault. #614 narrowed *what* was named (the TR39-claimed rows), #757 narrowed it again
  (the non-emoji rows); neither could reach the case where the naming is correct and a
  security surface should not be doing it.

  **The emoji is left in place, not removed.** Removal fuses the words either side —
  `stop🛑now` becomes `stopnow` — 144 times out of 144 measured, while leaving keeps them
  apart 144 out of 144. Removal does not close a split word; it creates a joined one.

  Only these two move. `ml_normalize` and `ml_corpus_normalize` keep naming, because
  glossing is the point of an ML-corpus surface and neither is a security preset.

  **Naming is a relocation, not a removal:** `demojize()` and `TextPipeline(demojize=True)`.

  Two side effects worth knowing. `llm_guardrail` now *folds* the dual-purpose enclosed
  letters instead of naming them, so `🅿AYPAL` reaches `paypal` rather than
  `p buttonaypal` — the #918/#920 tension for those four resolves itself. And
  `strip_obfuscation` no longer links the CLDR name table into a wasm build, which the
  #695 coupling gate caught the moment the step came out.

  **Upgrade note — `KEY_SCHEMA_VERSION` goes 6 → 7.** `strip_obfuscation` is a
  key-stability column and its output moves for any input containing emoji. Reindex if you
  persist it. This one the fixture *did* catch: its corpus carries 54 emoji, unlike the
  three classes earlier in this cycle that it could not see.

### Fixed

- **Every preset linked every table again, and had since #951 (#974).** `presets::apply_into`
  is an `#[inline(always)]` match over a `const` `Step`, and the inlining is the whole
  tree-shaking mechanism: it lets each call site fold the match to its one arm, so a
  preset links only the tables its own steps reach (#695). #951 added two arms that
  re-entered `apply_into` to resolve the digit policy — reasonably, since it kept one copy
  of each fixed-point loop — and that made the function self-recursive. LLVM will not
  `alwaysinline` a recursive function, so the attribute was dropped, the match stopped
  folding, and the Hanzi pinyin and CLDR emoji tables came back into presets that reach
  neither. **`strip_format` measured 662,087 bytes against 27,490**, and `canonicalize`,
  `canonicalize_strict` and `strip_obfuscation` were red with it.

  Nothing failed. Output was byte-identical, no key moved, and every test stayed green —
  because the gate that measures this is `slow`-marked, `addopts` deselects `slow`, and no
  workflow runs it. It caught #926 only because someone ran it by hand.

  The two loops are free functions now, called by both the step arm and nothing else, so
  the loop still lives once and no arm re-enters the dispatch. With the recursion gone the
  two policy-carrying `Step` variants had no constructor left and are removed, taking the
  match from 24 arms to 22. All six gated surfaces are green, and `strip_format` is back
  to 27,490 bytes.

  `tests/test_preset_step_dispatch.py` is the half that can run on every PR: it reads the
  source for the one mechanism known to break the inlining, in milliseconds, and fails on
  the exact shape #951 introduced. The wasm gate stays for the causes nobody has thought
  of yet.

- **The meta-benchmark's `weaponizing-unicode` suite no longer rewards saying yes (#977).** Its
  one directed key, `flagged_by_a_detector`, scored a detector for flagging any of 7,402
  model-predicted lookalikes fed one code point at a time — 7,277 of which are not UTS #39
  sources, and 547 of the rest have a multi-code-point prototype in their own script, so a
  lone Hangul jamo counted as coverage. That key is now a census. Two censuses read from the
  normative `confusables.txt` give the context (`uts39_sources` 586 of 7,402,
  `uts39_prototype_sources` 35 of 586), and the one directed measurement,
  `uts39_prototype_detected`, scores the 35 candidates whose prototype is a single code point
  in another script and names the misses: disarm 17 of 35, with Gurmukhi→Devanagari,
  Kannada→Telugu, Malayalam→Tamil, Myanmar→Malayalam, Georgian→Malayalam, Coptic→Greek and
  four combining marks unflagged, the disagreement the suite was registered to surface.

- **The leaderboard no longer scores a tool for having been asked more questions, and a
  detector's silence on plain ASCII is no longer a failure (#970).** Two independent faults,
  both in the harness rather than in any subject, and together they put `disarm` fifth of nine
  on `mcp-tag-block-concealment` while it gave the best answer in the field to every question
  that suite asks.

  **A plain-text control is a false-positive check.** T1 there is the concealed instruction
  written out in printable ASCII — the paper quotes it beside T7 precisely because the two
  differ only in encoding. `detected_t1_plain` was directed higher-is-better, so a detector
  that correctly stayed silent scored zero, and `confusable-homoglyphs` earned the point with
  `is_confusable(T1) == True` on pure ASCII: a false positive counted as coverage, the shape
  #957 had just removed from disarm's own detector. The key is now directed lower-is-better.
  The recorded number still means "a detector fired", as the key name says; only the direction
  moves, which is the orientation `controls_false_positive` already used on the
  invisible-carrier comparator. A sweep of the other `detected_*` keys found no second case —
  `flagged_by_a_detector` on the benign-prompt corpus is already an undirected census.

  **Parcels are formed per cohort of subjects, not per suite.** Thirteen subjects answer that
  suite's transform key; the two with a detector answer detection keys as well. Averaging both
  into one parcel put a detector's *mean over its answers* against a transliterator's *single
  answer*, and the mean cannot win: a key answered by two subjects is standardised on a sample
  of two, where the sample standard deviation caps |z| at 0.707 — below what a thirteen-subject
  key reaches. The completeness check already judged a subject against its peer cohort; the
  score did not. Measurements are now grouped by which subjects answered them, and each group
  is its own axis, so a detector is ranked against detectors and a transform against
  transforms, and a tool answering both appears on both. Re-scoring the committed baseline:
  `disarm` moves from 5th of 9 on that suite (z +0.185) to joint 1st of 8 on the transform
  axis (+0.808) and 1st of 2 on the detection axis (+0.707).

  **Coverage is counted in benchmarks, not axes.** Splitting a parcel adds an axis a
  transform-only tool has no surface to answer, and counting axes would have marked every such
  tool "partial coverage" — the exclusion error the peer-cohort rule exists to prevent,
  arriving one step later in the pipeline. `Standing.suites` records what the fraction is taken
  over.

  **A control no longer sets the scale inside a parcel.** Longstanding, and found while
  reviewing the above: `parcel` passed the full subject list as the standardisation basis,
  which overrode `standardize`'s own control exclusion. `null-baseline` deletes all input and
  so sits several standard deviations out, and fitting on it compressed every real tool into a
  narrow band — *before* the members were averaged, so it reweighted the parcel. Two tools that
  should separate by 1.414 landed 0.017 apart. Controls are placed on a parcel's scale now,
  never fitted to it, which is what the module has said about every other scale here since it
  was written. It moves recorded composites: on the committed baseline `anyascii` and `disarm`
  exchange first and second place, which is the honest consequence of no longer measuring
  distance from a strawman.

  **`per_benchmark()` is keyed by axis.** Keyed by suite, a second axis from the same suite
  overwrote the first — a dict assignment, so the detection ranking would simply never have
  appeared in the report. Both halves of a split suite are named, never just the smaller one:
  a bare suite name silently meaning "the transform half" would be the same omission in the
  report as in the score. The recorded baseline is unchanged either way — it stores
  measurements, not parcels, and no measured value moves.

- **The meta-benchmark's three composed subjects no longer strip every diacritic (#958).**
  Each passed `strip_zalgo=0` to `TextPipeline`, reading `0` as off; in disarm `0` is a cap
  of zero combining marks and off is `None`. The `review-display` composition, declared to
  change nothing a reader can see, turned `Čeština` into `Cestina` and altered 88 of 100
  JailbreakBench prompts. All three now pass `None`; a test runs each over
  `Čeština, naïve café` and lets accents go only where `strip_accents` is declared, and a
  second refuses a `0` cap in any composition. The committed baseline never held composed
  rows, so there was nothing to re-record.

- **`is_confusable` and `find_confusables` no longer report printable ASCII (#957).** `"`,
  `` ` `` and `|` are TR39 confusable *sources* — the table folds them to `''`, `'` and `l` —
  so the detector returned `True` for any quoted sentence or JSON document: 588 of the 1,342
  pure-ASCII lines of this repository's own prose, and every one of the 100 JailbreakBench
  prompts the meta-benchmark runs. The rows stay in the fold, because #725's contract for the
  transforming surfaces is deliberate and unchanged; they stop counting as detections. Both
  halves are tested, so deleting the rows instead would fail. The rule is the whole
  `U+0021`–`U+007E` range rather than those three code points, swept in Rust and Python, so a
  row added later cannot quietly turn punctuation into a detection. `has_anomalies` was never
  affected and does not move. **Faster, not slower:** the range check runs before the table
  probe, so a pure-ASCII document costs 2.57 µs where it cost 5.62 µs — 54% off
  `is_confusable` and 55% off `find_confusables` — and a homoglyph document is unchanged.
  `benchmarks/meta`'s `jailbreakbench::flagged_by_a_detector` census moves 100 → 99: the one
  prompt that changes is the only pure-ASCII one, and the other 99 carry CJK or accented Latin
  that other kinds report.

- **`digit_policy="preserve"` now holds on `canonicalize`, `canonicalize_strict` and
  `strip_obfuscation` (#949).** The pre-pass kept the numeral and the preset's own fold then
  folded it under the default, so the documented setting did nothing on six of the seven
  builders. With the policy threaded through the core (#896) the three builders that own a
  fold keep `amount-١` as written. On `search_key`, `catalog_key` and `sort_key` the numeral
  is romanized by transliteration, not by the fold — a key that maps every script to Latin
  cannot keep one — and that is now stated on each, both halves asserted.

- **The attack corpus was testing the recoverable half of the reordering class (#740).**
  `bidi()` builds `RLO + t[:mid] + RLM + t[mid:] + PDF`, whose *logical* order is already
  the clean word — the one direction in which strip and resolve give the same answer, so
  XMR passed 10/10. Reversed so the *rendering* is the clean word, as the paper's
  generator does, the same assertion is 0/10. Both constructions are now asserted, the
  second as a negative, with an independent render model pinning the premise.

- **A `control` finding for `BS`/`DEL` now names the character it erases (#739).**
  `detail` was `U+0008` and the reason said only that the token contained a control, so
  nothing said *what* vanished or that the token had a deletion structure at all. The
  kind and `detail` are unchanged — this is the reason string, which is plain-language
  prose by contract.

- **The detector went silent exactly when the disguise was complete (#815).**
  `inspect_anomalies` reported a `confusable` only when a word also carried an ASCII
  letter — #633's gate, and the thing that keeps ordinary Cyrillic and Greek prose from
  firing. It inverted:

  ```
  1/12 converted   has_anomalies True
  7/12 converted   has_anomalies True
  12/12 converted  has_anomalies False   <- the finished attack
  ```

  A token is now also reported when every character folds to an ASCII letter, there are at
  least four, and its script is Latin or none. The script condition is the whole
  separation: every letter of `Москва` folds to ASCII too, and it is a Russian word rather
  than Latin letters in disguise.

  Three of #722's seven spared blocks stay spared, because a whole token written in them
  is ordinary text that nothing else spells — Halfwidth and Fullwidth Forms, CJK
  Compatibility, Letterlike Symbols. `ＮＨＫ` does not fire and neither does `ｐａｙｐａｌ`;
  that trade is #633's and is unchanged. Phonetic Extensions and Enclosed Alphanumeric
  Supplement are **not** spared here, because those are the blocks that spell `ᴘᴀꜱꜱᴡᴏʀᴅ`
  and `🅟🅐🅨🅟🅐🅛` — sparing a block because it *can* hold ordinary text is what let the
  finished attack through.

  The false positive this risks is IPA, answered by the four-character floor: a
  transcription short enough to be wholly non-ASCII is shorter than that. Measured at
  **0 hits across 235,976 dictionary words** and 4 across the 23,135-row key-stability
  corpus, every one an attack string.

- **A `TextPipeline` built from a profile's own `ProfileSpec` behaved differently (#918).**
  `ProfileSpec::build` set `emoji_name_policy` and `Pipeline::new` left it at
  `NAME_EVERYTHING`, so the two profiles that set `demojize` without `transliterate`
  diverged from their own transcription on **413 code points each** — every one *named*
  by the composed pipeline where the profile *folds* it:

  ```python
  get_pipeline("llm_guardrail")("aa‑bb")  # 'aa-bb'
  TextPipeline(**that_profile_s_flags)("aa‑bb")  # was 'aa hyphen bb', now 'aa-bb'
  ```

  That is #614's failure mode on the composed surface: a spoof and its target stop being
  equal rather than become equal, so every downstream equality check is wrong in the
  direction the CVE describes. Worse than a missing capability, because the composed
  pipeline reported no failure — it returned plausible text that was not the profile's.

  The old reasoning was that a caller writing `demojize` asked for the step by name. It
  does not survive its own evidence: #757 measured `ml_normalize` turning `film’s` into
  `film right apostrophe s`, and a hand-built pipeline aimed at a tokenizer meets that
  identically. Asking for `demojize` is asking to name **emoji**.

  One `NamePolicy::PRESET` constant now, used by presets, profiles and hand-built
  pipelines alike — spelling the value out at each construction site is how the two came
  to disagree. **Standalone `demojize()` still names every row**, which is the one place
  "the caller asked by name" holds: one function, nothing downstream to fold.

  All eight profiles now reproduce exactly across the whole assigned code space, up from
  six. `tests/test_pipeline_composability.py` asserts it per profile, with the exhaustive
  sweep in the `slow` tier. The presets were checked too and do not have this divergence —
  #803 closed it for `PRESETS`; they name 0 of 5 of #918's sample.

- **The allocation gate was stochastic (#905).** `tests/preset_alloc_count.rs` blocked
  merges on a `stats_alloc` counter that measures the whole process, with a bound of
  `measured + 1`. It failed #904 — a pull request that changes no Rust — reporting
  `search_key` at 7 against a bound of 4, and passed on re-run of the same commit.

  The file's own header shows how: it crams every measurement into one `#[test]` so no
  concurrent *test* thread pollutes the counters. That is half the hazard. A process-wide
  counter is moved by anything in the process, and being the only test in a binary does
  not make the process single-threaded.

  `allocs_for` now takes the **minimum** over nine runs. The noise is one-sided — another
  thread can only add allocations, never remove them — so the minimum is the tightest
  true observation and a transient disturbance no longer decides the verdict.

  It does not make a process-wide counter safe against *sustained* interference, and
  nothing can: measured with a thread allocating continuously, the minimum over nine runs
  still read 39 against a true 3. That is why the one-test premise now fails as an
  assertion rather than resting on a comment — a second `#[test]` in that binary runs
  concurrently and recreates exactly that condition.

- **The Tier 3 release gate ran four times, independently, on one artifact.**
  `publish.yml`, `publish-node.yml`, `publish-ruby.yml` and `publish-java.yml` each
  called the reusable `tier3.yml`, described as gating "on the SAME reusable workflow".
  True of the definition, false of the execution: `uses:` instantiates a fresh job per
  caller, and Tier 3 contains proptests, which draw random inputs.

  Four stochastic gates on one artifact are atomic only by luck. A seed that fails in
  one workflow and passes in three publishes a subset of the bindings — and the three
  green ones look verified. Cutting `v0.15.0` hit the benign version: all four failed
  on the same proptest input, so nothing published and nothing diverged.

  Tier 3 now runs in `publish.yml` alone. The bindings inherit it transitively — each
  waits for the core on crates.io, and the core cannot get there unless that gate
  passed — so nothing is left ungated. `tests/test_workflow_baselines.py` asserts the
  single caller and the transitive wait.

### Documentation

- **Three descendants of arXiv:2405.14490, written down where each lands (#816).**
  `THREAT_MODEL.md` gains malicious font injection (Xiong et al., arXiv:2505.16957) as an
  out-of-scope row: it reads as a homoglyph attack from the reader's side, and it is not
  one — every code point is innocent and the substitution happens in the glyph table,
  below the character layer, so no character-level tool can see it.
  `docs/user-guide/llm-pipelines.md` gains a *when NOT to use disarm* row for the classes
  a table-driven fold cannot reach — Braille, turned letters, small capitals — where an
  LLM-based normalizer (Cooper et al., ACL Findings 2025) is the honest alternative at a
  per-call cost disarm does not have. And `docs/limitations.md` now names the
  detect-versus-transform gap as a published result rather than an observation about this
  library: Wang et al. (The Web Conference 2026) describe a **"success interval"** where a
  perturbation bypasses guardrail detection yet stays interpretable to the model, which is
  the argument for *clean unconditionally* over *detect, then clean*.

- **Canonical links and sitemap entries name the URL that serves them (#694).**
  `use_directory_urls: false` makes MkDocs write `.html` into every `rel=canonical` and every
  sitemap `<loc>`, and Cloudflare Pages answers the extensionless form with 200 while 308ing
  the `.html` form to it — so both of the signals telling a search engine where the content
  lives pointed at redirects: 78 canonicals, 78 sitemap entries and the 78 `og:url` tags the
  theme override emits from the same `page.canonical_url`. A build hook now rewrites them, and
  **nothing moves**: the `.html` files are still built, still deployed and still reachable, so
  every existing link keeps working and no indexed URL changes. That is what separates this
  from `use_directory_urls: true`, which would relocate all 78 and needs a preview deploy to
  confirm Pages does not redirect the directory form in turn. The hook checks its own work:
  a canonical or sitemap entry still ending in `.html` fails the build, and `sitemap.xml.gz`
  is regenerated so a stale copy cannot serve the old entries. The three transforms were
  measured against the live site before the hook was written.
- **The two spellings of a script, and the member that bridges them (#884).** `list_scripts()`
  returns `"Arabic"`, the confusable surfaces take `"arabic"` and `script_info` takes
  `"Arabic"`, so the obvious loop over `list_scripts()` raises on every script — which #884
  reads as a defect. It is half a defect: #767 decided the bridge deliberately, and an enum
  **member** is already translated at every surface, so `unmapped_confusables(target_script=
  Script.ARABIC)` works and `Script("Arabic")` converts a name from `list_scripts()`. A raw
  string stays strict at each surface on purpose, so a caller who hard-coded the wrong one
  still finds out; making the strings interchangeable would have overturned that in passing.
  The `unmapped_confusables` docstring now shows the loop written correctly, and states the
  distinction the issue is really about: four target tables against 61 identifiable scripts
  are different questions. The fair per-script denominator is #963.
- **Three limits weighed and kept, written down (#848, #836, #742).** Each was decided
  against changing the library, and each reads as an oversight until it is stated.
  **The fold is cross-script by construction:** `gen_confusables.py` drops a TR39 class whose
  members are all one script, so Persian keheh and Arabic kaf stay apart. 2,772 Arabic pairs,
  678 outside the presentation forms NFKC already removes — declined because which of them is
  the same letter is a language question and the fold takes a target script, not a language,
  with no registry judgement attached where #831's Latin pairs had ICANN's. **The fold keys on
  single code points:** a base plus a combining mark cannot be a source, leaving six Latin
  pairs where a tilde and a macron disagree about precomposition; the key builders merge all
  six by stripping accents and `canonicalize` merges none, and both halves are now asserted.
  **The chat-template sink is out of scope,** recorded beside the injection item in
  `THREAT_MODEL.md` — its metacharacters are a model vocabulary and disarm bundles Unicode
  data — with the artefact disowned: 11 of 26 delimiters survive `canonicalize`, and the split
  is TR39 row `U+007C` folding `|` to `l`, not a control. Both drop sites in the generator now
  say the rule is deliberate, and `tests/test_declined_fold_limits.py` pins the behaviour so
  the pages cannot describe a library that changed underneath them.
- **`strip_zalgo`'s off switch is `None`, and `0` is the opposite of off (#958 §4).**
  Every other `TextPipeline` step is switched with a boolean; this one takes a cap on
  combining marks per base character, so the falsy-looking `0` permits none and removes
  every diacritic in the text. A caller in this repository read `0` as off and built three
  pipelines with it, one of them declared to change nothing a reader can see, and every
  accented word they touched came out unaccented (#959 fixed that caller). The
  `TextPipeline` docstring and
  `docs/api/classes.md` now state the three settings with worked output, and
  `docs/api/pipelines.md` notes that the same literal reads the other way in `PRESETS`,
  where `("strip_zalgo", None)` is a live step at its default cap.

- **`confusable-bench.v1`: the three surfaces the meta-benchmark suite predated, and the
  identifier-validation recipe it produces (#736).** The corpus was already registered as the
  `confusable-bench-v1` suite under `benchmarks/meta`, so this scores the surfaces the suite
  could not see rather than re-deriving it: `skeleton_key` (#650), `skeleton_key` under
  `tr39`, `nearest_match` (#894), and the two-call composition. Re-measured, the issue's
  picture has moved — `nearest_match` at one edit reaches 0.942 recall alone where the best
  single call was 0.550, and `is_confusable` **or** `nearest_match` reaches 1.000, two calls
  rather than three, at precision 1.000 on every policy. The suite's `finding` is left exactly
  as it was: that field records what the 0.15.0 cycle measured, and the distance between it
  and a fresh run is the report's most useful column. The docs gap the issue is actually about
  is closed on the CVE page beside *If you only make one call*: the recipe, with the
  non-obvious half named (the protected list is `inspect_anomalies`'s lexicon) and the two
  ASCII rows the issue pinned as residual misses now reported at distance 1 while staying
  no-ops for every Unicode transform. The corpus's 31 NFKC/TR39-divergence rows are
  cross-referenced from the prototype-policy decision they answer.
- **`docs/security/derived-identifiers.md`: the map for derived deterministic identifiers (#731).** Idempotency keys, cache keys, dedup-on-insert and canonical-request signing all normalize, hash and keep the digest, and the caller never sees two values side by side — so under-normalizing (a retry runs twice) and over-normalizing (a real second request is suppressed) are both silent. No key builder is clean for it: `search_key` and `catalog_key` merge every distinct value in the matrix, `canonicalize` is closest and its three failures all change the value of a number, and `skeleton_key` is a spoof key by design. The page carries a variance-class × key matrix that `tests/test_derived_identifiers.py` renders from its registry and fails on when the page drifts, and a recipe: split the key by field, put code-like fields on `fold_case` or nothing and screen them with `has_anomalies`, and use `is_canonical` as the write-time check (#730). Measuring it found #949: `digit_policy="preserve"` is a no-op on six of the seven builders.

- **`strip_bidi` keeps the *logical* order, and now says so (#740).** It is a pure
  filter: the UAX #9 controls are deleted and the code-point order is untouched, so every
  preset, profile and key builder returns the byte order rather than the order a reader
  saw. `"\u202e" + "paypal"[::-1] + "\u202c"` renders as `paypal` and canonicalizes to
  `lapyap` on all 15 surfaces, `llm_guardrail` and `rag_ingest` included. Detection is
  10/10 on kind `bidi`, so this is a recovery gap, not a blindness.

  The distinction was written down nowhere — `grep -rin "logical order|visual order|
  display order|reading order"` over `docs/`, `THREAT_MODEL.md` and `src/` returned
  nothing. It is now named in three places a reader can meet it: the `strip_bidi` row in
  `THREAT_MODEL.md`, the `strip_bidi` docstring, and a new section in
  `docs/limitations.md` stating which consumer wants which order. A compiler, a
  filesystem and an identifier comparison read logical order, and disarm is correct for
  them — that is the Trojan Source direction, CVE-2021-42574. A search index, an NLP
  model and content moderation want the display order, and no surface returns it.

  A `resolve_bidi` is deliberately not built. Display order needs a paragraph direction
  disarm does not model, the UAX #9 implementation is a Unicode-data dependency the crate
  does not carry today, and it must not become a step inside `canonicalize`, since
  reordering before a denylist check is its own hazard.

- **The deletion class is named in `THREAT_MODEL.md` (#739).** It appeared in neither
  *In scope* nor *Out of scope*, so *Vulnerability vs. known limitation* could not answer
  a report about it either way. The entry states what disarm does (detects the whole
  class, resolves none of it), and why resolving `BS`/`DEL` is the wrong answer rather
  than merely unimplemented: the paper says in the same section that the class is
  renderer-dependent, so reproducing one renderer's behaviour would *lose* text another
  reader can see.
- **Boucher et al., *Bad Characters* is cited in *Background and evidence* (#739).** The
  taxonomy the CI-gating corpus is built on, and the source of the Exact Match Recovery
  measure that corpus asserts, was the one reference missing from the section.

- **The generation path and the verification path are named and distinguished
  (#730).** `docs/api/predicates.md` gains the two-path table, the measured
  clean-but-not-canonical census, and why the answer is a new predicate rather than a
  wider detector. `has_anomalies` and `inspect_anomalies` now say in their own
  docstrings that a clean result is not a claim of canonicity.
- **`THREAT_MODEL.md` lists reversal beside ROT-n (#917).** The textual-encoding
  obfuscation exclusion enumerated base64, hex, ROT-n, binary, Morse and
  percent-encoding but not writing the payload backwards, which is the same class and
  equally untouched.

- **`docs/security/adversarial-corpora.md` — the CVE page's counterpart for published
  adversarial corpora (#732).** `cve-validation.md` answers "which published CVEs does
  disarm handle?" with every row asserted; there was no equivalent for the corpora, and
  the CVE set cannot reach them — a CVE is a defect in one implementation, a paper
  releases a generator that emits a whole family.

  27 vectors over four families, all perturbing one prompt so the family is the only
  variable:

  | family | neutralized | detected |
  |---|---|---|
  | Unicode control | 8/8 | 8/8 |
  | Homoglyph | 5/5 | 4/5 |
  | Structural | 3/7 | 1/7 |
  | Encoding | 0/7 | 0/7 |

  **Reconstructed in-repo, not cloned.** CI does not depend on a third-party repository
  staying put, and the released generator has three defects that would score as *passes*
  if its output were trusted: `script_mixing/mathematical` emits nothing (a duplicated
  dict key means the paper's headline U+1D400 subtype is never exercised by the shipped
  code), `invisible_payload/steganographic` returns its input, and
  `targeted_word/target_system` substitutes `"system"` for `"system"`. 28 of 591 rows are
  no-ops. Every vector here is asserted to differ from the base prompt first.

  **The table is parsed and checked**, which is #732 item 5: every other doc gate in this
  repo reads fenced code blocks and none read a markdown table, which is how a
  `grapheme_len` cell stayed wrong through #708. Mutation-checked — flipping one cell and
  deleting one row each fail.

  The two columns stay apart, as on the CVE page. `fullwidth` is neutralized and
  undetected, deliberately: #633 spared the block because `ＮＨＫ` is ordinary text, so a
  caller who screens without rewriting gets nothing for that row. Out-of-scope rows are
  asserted as negatives so a limitation cannot drift into a claim.

- **The confusable fold has an orientation assumption, and rotated text inverts it
  (#916).** TR39 pairs a glyph with the letter it resembles *upright*. An "upside-down
  text" generator substitutes each letter for the glyph that looks like it rotated 180°
  and then reverses the string, so in that text a glyph means its *rotated* form — the
  opposite reading. Five glyphs fold to a different letter than such a generator meant,
  and `ɯ`/`ʍ` are a swapped pair, so `gap` flipped and canonicalized reads back as `bad`.

  **Upright wins, and that is a decision.** Recovering rotated text needs the string
  reversed, and no disarm surface reverses anything — reversal is out of scope by the
  rule that excludes ROT-n and base64 (#917). Pointing the fold the other way would leave
  the output reversed and unreadable while giving up the upright spoofs the table exists
  for: `canonicalize("ʍicrosoft")` is `microsoft`. No behaviour changes here.

  `docs/limitations.md` states the assumption, lists the five, and says the observable
  consequence: on rotated text the output is a *different plausible word* rather than a
  partial result, so it is not evidence about text that may have been rotated. Ask
  `has_anomalies` instead, which fires on the mixed-script shape.

  `tests/test_turned_letter_orientation.py` pins the decision from both sides, including
  a guard that fails if any surface ever starts reversing — the premise the decision
  rests on — and the three-way split (1 agrees, 5 fold elsewhere, 9 unfolded). That split
  is #916's scope item 3 in durable form: #815's census asks only whether a code point
  reaches ASCII on *some* surface, so it scores all five as covered, and a number that
  cannot separate "folds to the wrong letter" from "folds correctly" reads as coverage it
  does not have.

- **The confusable fold is not a romanization, and the docstrings now say so (#907).**
  `canonicalize("Москва")` is `Mockba`, where `search_key` and `catalog_key` give
  `moskva`. Three surfaces, three answers, and nothing said which was which. `Mockba` is
  not a spelling of anything: it is the confusable table applied to letters no
  transliteration step has handled, and `catalog_key`'s own step list records the rule
  it departs from — transliterate first, so non-Latin scripts are romanized before
  confusables.

  The order is a decision, not an omission. The collapse is the point — an attacker's
  Latin `Mockba` and a Cyrillic `Москва` are meant to meet, and the romanizing surfaces
  cannot make them: `find_key_collisions(["Москва", "Mockba"], key="search_key")` is
  empty. What was missing was the sentence telling a caller to pick by what they need,
  and that `normalize` applies Unicode normalization and nothing else, so the script
  survives it. That is not the same as leaving the string alone: NFC still recomposes.

- **`target_script` folds toward a script; it does not protect one (#907).**
  `normalize_confusables` was the only surface exposing the parameter and the only one
  whose docstring never described this class of effect at all. Passing a third script
  rewrites the word into it — `normalize_confusables("Москва", target_script="arabic")`
  puts an ARABIC LETTER HEH where the Cyrillic о was. There is also no Greek target, so
  Greek text has no value that preserves it by design. Declaring which scripts a caller
  considers legitimate is a different question, tracked as `allowed_scripts` in #900.

  No behaviour changed in either case. `tests/test_fold_is_not_romanization.py` pins the
  three-way split, both halves of the collapse trade, and — because nothing in this repo
  runs Python docstrings as doctests — that the value quoted for the Arabic target is the
  one the function returns.

- **`canonicalize_strict` said it "preserves the original script"; it does not (#907).**
  Found while adding the paragraph above, four lines below it. The parenthesis — "(no
  transliteration)" — was the true half: there is no romanization step, so the output
  never reaches `moskva`. The claim around it was false for every non-Latin input with a
  Latin lookalike, which is the whole population the sentence was about: `Москва` folds
  to `Mockba`, `Ελλάδα` to `Eλλάda`, `שלום` to `שלlם`. Reworded to the half that is true.

## [0.15.0] — 2026-09-01

### Upgrade notes

**Stored `strip_obfuscation` output moves for 90 Cyrillic rows (#723).** A fold target
that was itself a source is now resolved in the data, so the single-pass callers reach
the fixed point the iterating ones already did: `Apy6ƅi` becomes `Apy6bi`. If you persist
`strip_obfuscation` output as a comparison value, reindex. `canonicalize`,
`normalize_confusables`, `search_key`, `catalog_key` and `sort_key` are byte-identical —
they iterate, and were already returning the resolved form.

**The key builders now collapse a nonspacing mark repeated on one base (#835).** `a`
followed by two identical acutes renders exactly like `a` followed by one, so the two
spellings now produce the same key: `canonicalize`, `canonicalize_strict` and `sort_key`
moved on 11, 13 and 11 of the 22,977 key-stability rows. `search_key`, `catalog_key`,
`strip_obfuscation`, `normalize_confusables` and `fold_case` are byte-identical, and no
row grew. `KEY_SCHEMA_VERSION` is now `3`, which covers #723's `strip_obfuscation`
movement above as well as this one.

If you have stored keys, recompute them. The change only merges rows that a reader could
never have told apart in the first place — every moved row lost a repeat of a mark it
still carries.

`strip_zalgo` is deliberately unchanged. It is the cap, #788 pairs it with `is_zalgo`, and
two identical acutes are ordinary by that threshold — so `strip_zalgo("Z" + acute × 8)`
still keeps three marks while `canonicalize` of the same input now keeps one.

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

- **`edit_distance` and `nearest_match`, for the class the confusable tables correctly
  do not reach (#883).** `paypa1`, `g1thub`, `adm1n`, `supp0rt` are ASCII substitutions.
  Every key reducer misses all twelve such rows in `confusable-bench.v1`, and so does
  `find_confusables` — **correctly**, because no confusable table should fold ASCII `1`
  onto `l` without wrecking ordinary text. So the one class disarm does not model in
  Unicode was also the one whose existing answer was unreachable from Python, though
  `utils::edit_distance` has been compiled into the wheel all along.

  All twelve are **distance 1** from the name they imitate, so a reserved list needs only
  `nearest_match(candidate, RESERVED, max_distance=1)`.

  `nearest_match` rather than exposing the internal `closest_match`, and the difference is
  deliberate. That helper exists for *"did you mean …?"* hints on language codes: it
  **skips exact matches**, because its caller has already rejected the input — so a
  registry asking about a name it protects verbatim would have been told nothing — and its
  threshold is two edits plus a minority-of-the-longer-string rule tuned for two-letter
  codes. `nearest_match` reports exact matches with distance 0, takes the threshold from
  the caller, and returns the distance so the policy stays the caller's, which is the
  precedent `find_key_collisions` set.

  It returns a named `NearestMatch` with `value` and `distance` — exported from the
  package root, like `KeyCollision` and `Finding`, so it can be annotated and
  `isinstance`-checked — not a tuple — the repo's
  `api_surface_contract` gate caught the tuple, and it is right that `(str, int)` at a
  call site does not say which number is which.

  Ties go to the first candidate at the lowest distance, so the caller's ordering decides;
  documented, and tested in both directions.

  **Python only in this release.** The other five bindings are tracked separately.

- **`digit_policy` is reachable from the six key builders, in Python (#885).** It was
  accepted by
  `normalize_confusables` and by nothing else — not a preset, not a profile, not a key
  builder — so a caller who reached for `canonicalize`, the README's first example, could
  not express the better answer for this class. `canonicalize`, `canonicalize_strict`,
  `search_key`, `catalog_key`, `sort_key` and `strip_obfuscation` now take it **on the
  Python surface**; the Rust API and the other five bindings are tracked separately, as
  the equivalent split was made for #883.

  Over `confusable-bench.v1` the union of the six goes from **72 of 120** malicious rows
  to **92** under `"tr39"`.

  **The default does not move, and the issue's case for moving it does not survive
  measurement.** #885 reported `"tr39"` at "zero false-positive cost". TR39's digit
  mappings are not the styled Latin variants — they cover every non-Latin numeral system.
  Arabic-Indic zero folds to `.`, one to `l`, five to `o`:

  | input | `numeric` | `tr39` |
  |---|---|---|
  | Arabic year `٢٠٢٤` | `٢0٢٤` | `٢.٢٤` |
  | Persian `۱۴۰۳` | `1۴0۳` | `l۴.۳` |

  The 20 benign controls that measured that cost contain **no non-Latin digits at all**
  (`café`, `naïve`, `jalapeño`, `résumé`), so the population that pays was never sampled.
  Making `"tr39"` the default would have destroyed the numeric reading of Arabic, Persian,
  Indic and Thai text in every key — in the release that added Arabic and Hebrew targets
  for those readers.

  `"numeric"` is therefore a **genuine no-op**: passing it is byte-identical to not
  passing it, pinned over the BMP for all six builders. Pre-folding under it would still
  have moved output — 78 rows collide rather than 72, because folding both sides before
  reducing is a different operation from reducing alone — and no stored key moves for a
  parameter nobody asked for.

- **`duplicate_mark`: the same nonspacing mark twice on one base (#835).** UTS #39 §5.4
  lists a sequence of the same nonspacing mark as an optional detection, and `disarm`
  implemented none of it. `a` + two acutes reports clean at every surface: it is two
  marks, so no zalgo threshold reaches it, and it is one script, so `mixed_script` does
  not see it — while rendering indistinguishably from `a` + one acute. The kind reports
  after `zalgo` rather than before it, because a heavy stack is usually also a repeat and
  `zalgo` is the louder fact about that token. Class-0 marks are out of scope: those are
  positioned rather than stacked, so a doubled Devanagari matra is an orthography
  question rather than this one.

- **A meta-benchmark that runs `n` of `m` externally produced benchmarks
  (`benchmarks/meta`).** The 0.15.0 cycle found and verified defects against roughly
  thirty outside artifacts — corpora released with papers, public spam and phishing
  datasets, normative Unicode/IETF/ICANN tables, published CVEs, released tokenizers and
  a third-party labelled benchmark — and each measurement lived in its own script. This
  consolidates the selection, the provenance record, the scoring protocol and the report
  into one harness. It is not collected by `pytest` and runs on demand:

  ```bash
  python -m benchmarks.meta --list                    # show m, and what is runnable
  python -m benchmarks.meta --run --only-available    # run what the machine has
  python -m benchmarks.meta --run --select 'uts39-*' --report out.md
  ```

  The harness supplies the runner and supplies no vectors. `Provenance.external` marks
  the bias boundary, the report renders external and introspective results separately,
  and a test asserts that no external suite is scored against a file disarm generated —
  `data/confusables_lgr.tsv` is the trap, since the shipped fold was built from it.

  A suite whose artifact is absent reports `SKIPPED` with the variable to set, never a
  pass. Results are compared against a committed baseline keyed by subject, suite *and*
  population; a moved number is reported and never fails a run.

  **Other tools are scored on the same benchmarks.** `--subject` runs the suites against
  the pinned comparator environment in `requirements/bench.txt` — ftfy, unidecode,
  text-unidecode, anyascii, decancer — plus CPython's own normalization as the floor. A
  suite that measures a disarm-specific surface skips the other subjects rather than
  scoring them zero.

  **Two subjects are controls, not candidates.** `null-baseline` deletes all input and
  `identity` returns it unchanged. The first scored 100% on every coverage metric in the
  registry until collisions were made to require a *non-empty* shared form — deleting
  both sides of a comparison is not resolving it. They stay in the roster because a
  control that is meant to fail is the only thing that proves a metric can fail.

  **Coverage is never reported without its cost.** The new `corruption-cost` suite
  measures what a tool does to text that needed nothing: code points destroyed,
  characters retained, injectivity, and alteration of pure ASCII. Labelled corpora get
  the same axis from their own `clean` column. Both ends are always reported with the
  names of the surfaces at each end, and key builders are scored separately — `sort_key`
  and `catalog_key` are many-to-one by contract, and counting that as damage would rank
  a tool with no key builder as the safer one.

  **Every run records its method**: subject and version, domain and size, the predicates
  invoked, every parameter that moves a result, the sha256 of the artifact read, and the
  Unicode/UCD versions in force.

  **Each suite reproduces the published script its finding came from**, pinned to the
  value that script printed at v0.14.1. The suites generalise their issues — the gist
  probed seven cases, the suite sweeps the domain — so the two numbers answer different
  questions, and only a matching reproduction licenses reading them as a before/after.
  Pins come from executing the script on a reference build rather than from its own
  docstring: the segmentation census header says `total=36` and running it says `37`.

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

- **`mixed_numbers` — UTS #39 §5.3 Mixed Numbers (#777).** An identifier should not carry
  digits from more than one decimal numbering system. Nothing checked it, and the reason
  the gap survived is worth stating: **digits carry the script of nothing**, so
  `is_mixed_script` sees one script for a token that is mostly ASCII with one substituted
  digit.

  | input | before | now |
  |---|---|---|
  | `12٣` — ASCII + Arabic-Indic | clean at **every** surface | `mixed_numbers` |
  | `1٢۳４२` — five systems | `is_mixed_script` only, by accident | `mixed_numbers` |
  | `٢٠٢٤` — one system | clean | clean |
  | `२०२४` — one system | clean | clean |

  `1٢۳४५` was caught only because five systems happened to be five *scripts*. `12٣` —
  the shape an attacker would use — was `anomalous=False` with no kinds. A single system
  is never flagged however unusual it looks: `٢٠٢٤` is a year.

  UCD 17.0.0 has **77** numbering systems, not the 76 UTS #39 and the issue quote — that
  figure is UCD 16.0.0. Each is a complete run of ten code points from its zero, so
  `src/tables/data/decimal_digit_zeros.tsv` is one row per system and membership is
  `cp - decimal_value`. build.rs asserts the rows are sorted and at least ten apart, which
  is the model the lookup depends on.

  Reported by `inspect_anomalies` and `has_anomalies` on every surface — the kind flows
  through an entry point all six already export, so no new binding functions were needed.

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

- **A repeated mark no longer survives the key builders (#835).** See *Upgrade notes*
  for the movement. The collapse is its own pipeline step rather than part of the zalgo
  cap, and it runs *before* the cap so the cap counts marks a reader can distinguish:
  `a` + five acutes + five graves capped first keeps three acutes and drops the grave
  entirely, while deduplicating first keeps one of each.

  In `canonicalize` it runs a **second** time, after the confusable fold, because the fold
  can *create* a repeat rather than merely reveal one: `U+1EF3` (y with grave) folds to
  `U+00FD` (y with acute), whose NFD is `y` + acute. So `U+1EF3` followed by a combining
  acute became a base carrying the same mark twice, manufactured by a step downstream of
  the one that removes them, and `canonicalize` was not idempotent on 16 such pairs.
  `canonicalize_strict` and `sort_key` need no second pass and have none — #862 already
  put their cap after the fold. Every idempotence sweep in the repository walked single
  code points; this class needs a base *and* a mark, so the sweeps are now over pairs.

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

- **A negation overlay outlived a base that did not survive (#749 follow-up).**
  `is_negation_of` kept `U+0338` / `U+20D2` whenever the base was `!is_alphanumeric()`,
  because the 45 composed negations all sit on `Sm`/`So` and std exposes no
  general-category API. That also admitted every base the pipeline *deletes*: the overlay
  was kept because it had a base, the base was stripped by a later step, and the orphan
  went on the next pass.

  ```
  ml_normalize("\u0000\u0338")  ->  "\u0338"  ->  ""
  ```

  **141 (base, overlay) pairs**, across `ml_normalize` and `strip_obfuscation`. They share
  no general category — `U+0000` (Cc), `U+0020` (Zs), `U+00A8` (Sk, which NFKC-decomposes
  to space + diaeresis), `U+2017` (Po, likewise), `U+2800` (So, removed as a blank render).
  What they share is that **none of them survives**, so the fix asks about survival rather
  than category.

  Both halves of #749 still hold: `≠`, `∄` and `∉` keep their overlay, and `H̸a̸t̸e̸` still
  comes back as `Hate`.

  Found by `exhaustive_preset_idempotency` in the publish workflow while cutting the
  release — after the same suite passed locally on the same commit with a different draw.
  That non-determinism is why Tier 3 no longer runs in four publish workflows at once
  (#898).

- **The key-fixture digest moved on every version bump (#887 follow-up).** `#887` added
  `KEY_FIXTURE_SHA256` so that regenerating the fixture without bumping
  `KEY_SCHEMA_VERSION` fails a gate. It hashed the whole file — and the fixture header
  stamps `disarm.__version__`, so the digest moved on any release whether or not a key
  did. Caught preparing this one: the only difference was
  `# generated against disarm 0.14.1` becoming `0.15.0`, with all 22,977 rows
  byte-identical.

  Now hashed over the rows, header excluded, so the digest carries one meaning: a key
  moved. The 0.15.0 regeneration is the proof — the stamp changed and the digest did not.

  The rows are found by splitting on the `# columns:` delimiter rather than by filtering
  `#`-leading lines. A TSV row begins with the *escaped input*, so a corpus entry starting
  with `#` looks exactly like a header line and a prefix filter would have placed it
  outside the digest — silently, in the one gate that exists to notice a key moving. No
  such row exists today, which is why this is a mechanism test rather than a fix.

- **`normalize_web_input` was not a fixed point on 6,410 (base, mark) pairs (#886).**
  Its steps are `normalize` → `confusables` → strips, and nothing normalized after the
  fold — so the fold emitted a decomposed base and the *next* call composed it. Two
  calls, two byte sequences, one rendering:

  | input | once | twice |
  |---|---|---|
  | `U+0430` + `U+0301` | `0061 0301` | `00E1` |
  | `caf` + `U+0435` + `U+0301` | `63 61 66 0065 0301` | `63 61 66 00E9` |

  The second is the shape that matters: a spoofed `café` built from Cyrillic `е`. A
  registry storing one call's output and comparing against another's gets two keys for
  one input.

  The fold now iterates to a fixed point between normalization passes when a form is
  configured, which is what `canonicalize` has done since #416/#434 and the profiles
  never did. A single post-fold normalization is not enough and was the first attempt:
  TR39 skeletoning is not normalization-stable — it drops the diacritic on a *composed*
  accented letter (`ç` → `c`) but never on the decomposed form — so composing once left
  409 pairs whose next pass folded further.

  **No single-code-point output changed on any of the eight profiles.** The fix is
  invisible except on the sequences that were broken, and all eight are now fixed points
  over every (base, mark) pair.

  `tests/test_profiles_are_fixed_points.py` sweeps pairs as well as code points. The
  single-code-point sweep it had passed throughout — the same blind spot that let #835's
  regression reach `main`, closed for the key builders in #881 and now for the profiles.

- **The key-schema gate could not detect a missed bump (#887).**
  `KEY_SCHEMA_VERSION`'s doc comment claimed that regenerating the fixture without
  bumping the constant *"is a test failure rather than a silent lie"*. It was not: the
  check compared the fixture header against the constant, and `gen_key_fixture.py` writes
  the current constant **into** that header. A regenerated fixture always agreed with
  whatever the constant happened to be, stale or not. The gate was anchored to the thing
  that drifts.

  #873 tripped it. That change moved `strip_obfuscation` on 90 rows, regenerated the
  fixture, did not touch `src/api/metadata.rs`, and stayed green with the counter at `2`.
  Nothing shipped wrong only because #874 bumped it in the same unreleased cycle.

  `KEY_FIXTURE_SHA256` is the anchor the generator does not author — the SHA-256 of the
  fixture's decompressed bytes, recorded on the line below the version. Regenerating
  changes the digest and fails the gate, and fixing it means editing the file that holds
  the version, with the version adjacent. Forgetting the bump becomes a deliberate act
  rather than an invisible one.

  The generator now prints both lines to update, so the workflow is a two-line edit
  rather than a failing test to decode. The version's doc comment says what is actually
  guaranteed.

- **The `target_script` error named two of the four accepted values (#888).**
  It read `target_script must be 'latin' or 'cyrillic'` and stayed that way when #792
  added Arabic and Hebrew, on all three entry points — `normalize_confusables`,
  `unmapped_confusables`, `find_confusables`. A caller who trusted it could not discover
  the two targets that cycle existed to add.

  The doc comment on `TargetScript::ALL` already warns that these lists drift, and two
  tests hold the validator and the enum together. The message was a third copy nobody had
  wired in. It is now derived from `TargetScript::ALL`, so a fifth target updates it by
  construction, and a test asserts it names every accepted token and none of the
  unsupported ones.

  Measuring the accepted set against the table it comes from is worth recording. Counting
  `data/confusables.txt` by the script its target resolves to, **2,694 of 6,565 pairs —
  41% — point at a target that cannot be asked for**: Han is the second-largest target at
  1,471 pairs and is rejected, while Greek carries 161 and is rejected where Cyrillic (37)
  and Hebrew (24) are both accepted. Whether `target_script` should accept a script with
  no table is #884, deferred to 0.16.x; this entry is only the part that was wrong rather
  than incomplete.

- **The last profile that was not a fixed point (#751).** `llm_guardrail` returned `B`
  for `U+13F8` CHEROKEE SMALL LETTER YE on the first pass and `b` on the second, so its
  output depended on how many times you called it — which makes it unusable for a key.

  This is the mirror of #852 and its closing half. That change added a confusable pass
  *after* the case fold, so a cased letter whose folded form is in the table gets folded
  (`Þ` → `þ` → `p`). But the fold's **target** can be uppercase, and nothing case-folded
  after it. Ten Cherokee small letters fold to a capital Latin letter: `ᏸ`→`B`, `ᏺ`→`H`,
  `ꮷ`→`D`, scattered across three blocks.

  `PipelineSteps::FOLD_CASE_POST` closes it, gated exactly as `CONFUSABLES_POST` is —
  added only where a second confusable pass precedes it, so a pipeline without
  `confusables` gains no step and `explain()` never describes a mechanism it does not run.

  **All eight profiles are now fixed points over every code point that exists**, measured
  by exhaustive sweep rather than by sample: the ten are scattered enough that no
  hand-written list would have included `U+ABB7`. That sweep is now
  `tests/test_profiles_are_fixed_points.py`, which is also what #723's `PRESETS`-only
  version never reached.

- **The detector and the neutralizer disagreed about what is invisible (#812, #813, #814).**
  Three surfaces, one channel.

  Twelve `Cf` code points that Unicode marks `Default_Ignorable_Code_Point` — Duployan
  `U+1BCA0`–`U+1BCA3` and musical `U+1D173`–`U+1D17A` — were removed by nothing and
  reported by nothing. `pay` + `U+1D173` + `pal` survived `strip_format`, `canonicalize`,
  `canonicalize_strict`, `strip_obfuscation` and `llm_guardrail` untouched and screened
  clean. That is the worked example from the anomaly guide, which is caught with `U+200B`;
  these are invisible by **property** rather than by name, which is how they escaped every
  predicate. The other 29 surviving `Cf` code points render and carry meaning — Arabic and
  Kaithi number signs, Egyptian hieroglyph layout controls — and are still kept.

  A run of Private Use Area code points was removed by `canonicalize` and reported by
  nothing, so a guardrail screening with `has_anomalies` passed exactly what the
  comparison presets had already decided was not text. It is a **run** rule at a floor of
  four, not a neighbour rule: one PUA code point beside a letter is an icon-font glyph,
  which is the same reason #413 has `strip_format` keep the block at all.

  And `ProfileSpec` had no PUA field, so `llm_guardrail` — the profile the LLM-pipeline
  docs send a guardrail author to — could not strip the Private Use Area **even in
  principle**. Seven of the eight profiles now do. `code_context` does not, which is #413's
  rule applied to the profiles rather than an omission: it is the one profile whose job is
  to preserve its input.

  `docs/security/watermarks.md` measured this class before any of it was fixed and its
  "removed by nothing, reported by nothing" row held exactly these 12. That row is now
  empty.

  The twelve are defined once, in `invisibles.rs`, and both the strip path and the detector
  read that one definition — #700 found those two drifted apart, and restating the class
  in the second place is how that happens. One consequence is worth naming: the public
  `strip_zero_width_chars` widens by those twelve on every surface. It is the function
  whose own description is *"strip zero-width and invisible characters"*, and a code point
  that renders as nothing belongs to that set by that description.

- **The leet near-miss path was floored at six characters, so `1ogin` screened clean
  while `l0gin` was caught (#825).** The branch has two sub-paths — the decode is a
  lexicon word, or it is one edit from one — and the second carried an uncommented `>= 6`
  from #393. `leet_sub` maps `'1'` to `'i'` rather than `'l'`, which is correct, but it
  means a `1`-for-`l` substitution never decodes *exactly* and can only ever be caught by
  the second path. Below the floor that path does not run, so the entire substitution
  class went unreported on short targets: 0 of 5 five-letter brands against 7 of 7
  six-letter ones.

  Now five, and the number is measured. Over 65 ordinary digit-bearing tokens (`mp3`,
  `k8s`, `sha1`, `i18n`, `rtx4090`, …) against a 234k-word lexicon, and 8 single-
  substitution brand spoofs:

  | floor | false positives / 65 | spoofs caught / 8 |
  |------:|---------------------:|------------------:|
  | 3     | 22                   | 8                 |
  | 4     | 12                   | 8                 |
  | **5** | **5**                | **7**             |
  | 6     | 4                    | 3                 |

  Five costs exactly one false positive more than six — `top10`, whose decode `topio` is
  one edit from a word — and more than doubles the spoofs caught. The issue argued for
  removing the floor entirely, on the grounds that the exact path fires below it anyway;
  the measurement does not support that, and it is recorded on the constant so the next
  reader does not have to redo it.

  Two rows of #726's table moved with it. `gn0r3!` and `!dm1n` were asserted **clean**,
  with the six-character floor given as the reason — a test freezing the floor's own
  defect as correct. Both are one edit from the word they imitate, `ignore` and `admin`,
  and both are now reported.

- **The weekly advisory scan failed whenever it found something (#782).** On `schedule`
  there is no pull request to annotate, so `rustsec/audit-check` reports by opening an
  issue — `POST /repos/:owner/:repo/issues`. `ci.yml` grants `contents: read`, so that
  call returned *"Resource not accessible by integration"* and the job failed **after** a
  clean audit.

  The direction is the problem. The job passed every week it had nothing to say and
  failed every week it did: twelve consecutive red Mondays, each one a security report
  nobody received. None of it was visible on the pull-request path, which is the only
  path that gates a merge — so a workflow's non-PR triggers can rot indefinitely without
  anything going red where anyone looks.

  Fixed with a job-scoped `issues: write` (job permissions *replace* the workflow's
  rather than adding to them, so `contents: read` is restated). The last scan is on
  record as clean: no vulnerabilities, two `unmaintained` informational warnings —
  `bincode` and `proc-macro-error2`, both transitive.

  `tests/test_workflow_baselines.py` gains the gate, and it is anchored to the action
  rather than to the job name, so moving or renaming the job does not quietly empty it.

- **#803 fixed the presets and left `list_profiles()` behind (#853).** #757 measured
  `ml_normalize` turning `film’s` into `film right apostrophe s` — 326 code points carry
  neither the Unicode `Emoji` nor the `Extended_Pictographic` property and were named as
  English words. #803 gave `PRESETS` the skip and did not reach the profiles, so
  `ml_normalize("⛑")` was stable while `get_pipeline("ml_corpus_normalize")` renamed its
  own output on the next pass.

  That is the second time this boundary swallowed a fix; #757's own title records #614
  being lost across it one layer in. A **named profile is a curated recommendation**, like
  a preset, so it now takes the preset policy. `demojize` and a hand-built
  `TextPipeline(demojize=True)` still name everything: a caller who asked for the step by
  name gets exactly what it says.

  Measured over the BMP, 130 outputs change in the two demojizing profiles and every one
  is fewer spurious tokens — `¼` was `1 fraction slash 4` and is now `1/4`. No genuine
  emoji lost its name; zero pictographic code points are left unnamed.

  **`llm_guardrail` now clears the whole CVE matrix**, joining `canonicalize_strict`,
  `strip_obfuscation` and `catalog_key`. Naming the non-emoji rows was what broke it:
  `€xample.com` became `euro xample.com`, so the spoof and the genuine string stopped
  being equal rather than becoming equal — #614's mechanism, in the profiles.
  `docs/security/cve-validation.md` records it, because that is the entry point the LLM
  pipeline pages send a guardrail author to.

- **`strip_obfuscation` was not a fixed point: a fold target contained a source (#723).**
  `044B` ы mapped to `ƅi`, and `ƅ` (`U+0185`) is a source folding to `b`. The entry points
  that iterate reached `bi`; the single-pass ones — `strip_obfuscation`, and the
  `confusables` step inside `get_pipeline` — stopped at `ƅi`.

  The issue's title names why it survived: **the exhaustive idempotence gate tests the one
  function that iterates.** A gate aimed at the forgiving caller cannot see a defect only
  the strict one meets.

  Fixed in the data. `scripts/gen_confusables.py` now resolves every target through the
  map until it is a fixed point, and `build.rs`'s "a target must not itself be a source"
  assert — which previously checked only *single-character* targets, which is exactly the
  hole `ƅi` fell through — now checks every character of every target. The assert can hold
  only because the data satisfies it, which is what keeps the class closed.

  Two rows resolved: `044B` → `bi` (was `ƅi`) and `1D14` → `eo` (was `ǝo`), the second a
  chain the issue does not name. `strip_obfuscation` is now a fixed point over the whole
  BMP, where it had two exceptions.

- **#847 was silently reverted in full by #851, and `main` stayed green.** Every one of
  its fourteen files: 140 lines of `build.rs`, `data/confusables_lgr.tsv`,
  `tests/test_lgr_pairs.py`, the seventeen ICANN LGR rows in `confusables_to_latin.tsv`,
  and the documented count in four places.

  The consequence was behavioural. `canonicalize("ż") != canonicalize("ź")` again — the
  same-script Latin homoglyph pairs #831 closed had reopened, and the four hostname rows
  that issue names were live again.

  **Nothing caught it**, and the reason is the point: the test file that covers this class
  was deleted by the same commit, so it could not fail. The doc-count gates could not
  fire either, because the counts were reverted along with the table they check. A
  fixture diff of 40 rows was the only trace, and it was applied rather than questioned.

  The cause was `git reset --soft origin/main` used to collapse a branch, at a moment when
  `origin/main` had moved ahead of the working tree. The reset recorded the *difference*,
  which included deleting files the branch had never seen.

  Restored, and `tests/test_no_silent_revert.py` now checks the **artifacts** rather than
  the behaviour: a bundled data file must exist and something must reference it, and
  `build.rs` must still carry #831's two safety asserts. Behaviour tests travel with the
  feature and vanish with it; a data file's absence is a build-level fact a deleted test
  cannot hide.

- **`Step::Confusables` could not express the digit policy, so no preset could (#646 §2).**
  `digit_policy` reached exactly one function. The step carried a target script and
  nothing else, and the fold it calls — `normalize_confusables_into` — did a bare map
  lookup with no policy at all. Two call paths into one fold, and the one every preset
  uses could not say the security-relevant thing.

  The step now carries a `DigitPolicy`, which is where
  `docs/architecture/prototype-policy.md` §3 decided it belongs: the policy is a property
  of the fold, not of one function's signature. All three variants that fold confusables
  — `Confusables`, `ConfusablesNfcFixedPoint`, `ConfusablesMarkFixedPoint` — take it.

  **No output changes.** Every shipped preset passes `Numeric`, which is what they did
  implicitly before the step could say anything else, and
  `no_shipped_preset_uses_a_non_default_digit_policy` asserts that — a preset silently
  gaining `Tr39` would turn a number into a letter inside a key, which is the damage that
  page prices at `SKU-100` and `SKU-1O0` sharing one key.

  This widens what is *expressible*. Exposing the choice on `TextPipeline` is a public
  parameter owed across six bindings and is left to its own change.

- **`llm_guardrail` folded case after the confusable fold, so 126 code points needed a
  second call (#852).** A cased letter whose *folded* form is in the confusable table and
  whose original is not folded only on the second pass: `Þ` has no entry, case-folds to
  `þ`, and only then folds to `p`. The profile was not a fixed point.

  Fixed by running the confusable fold **again after** the case fold, in any pipeline that
  has both. 126 non-fixed-point code points become 10, and 19 sampled outputs change —
  all of them recoveries, none a loss.

  **Not by folding case first**, which would also close the class and is the wrong trade.
  73 cased code points fold to a *different* target than their case pair: `Ð` folds to `D`
  where `ð` is unmapped, and `Η` folds to `H` where `η` folds to `n`. Pre-folding would
  lose the uppercase mapping outright rather than reaching it one pass later — measured
  when a step-order lock caught `Ηello` turning into `nello`.

  The remaining 10 are Cherokee small letters, whose confusable target is an *uppercase*
  Latin letter, so the pair has to run more than twice. They converge in two further
  passes, which means the structure that closes them is a fixed-point loop — what the
  presets use — rather than another fixed pass. Recorded as a named class in
  `tests/test_guardrail_fold_order.py` rather than left as an unexplained number.

  A pipeline without `confusables` gains no step: reporting one that does nothing would
  make `explain()` describe a mechanism the pipeline does not run.

- **A preset linked every table any step could reach; `strip_format` cost 663 KB of wasm
  (#695).** `presets::run` walked a `&[Step]` and called `apply_into` with a *runtime*
  value, so the optimiser could not prove any of the eighteen match arms unreachable. A
  preset's declared step list had no bearing on what linked.

  `strip_format` declares five steps that neither transliterate nor demojize, and its own
  docstring calls it "lightweight cleanup". It linked the Hanzi pinyin **and** CLDR emoji
  tables.

  | single-export `wasm32-unknown-unknown` module | before | after |
  |---|---:|---:|
  | `strip_format` | 662,974 | **27,384** |
  | `canonicalize` | 663,299 | 209,949 |
  | `canonicalize_strict` | 663,458 | 219,112 |
  | `strip_obfuscation` | 663,281 | 426,933 |

  **−95.9%** for `strip_format`, with both tables gone. `strip_obfuscation` keeps the emoji
  table and is right to: it has a `Demojize` step. That is now the rule — a preset links
  what its own steps reach and nothing else.

  Two changes, and the second was the larger one. The step lists moved into a
  `static_steps!` macro that unrolls them into straight-line calls, so each `apply_into`
  call gets a `const` step it can fold to one arm. That alone got `strip_format` to
  275 KB. The rest was the **fast-path guard**: `Actionable::for_steps` took a runtime
  `&[Step]` and matched every variant, which kept the payload types and the emoji table
  alive through a function that only sets booleans. It is now a `const fn` and each preset
  computes its mask at compile time.

  `ml_normalize` deliberately keeps the dynamic path — it selects between two step lists at
  runtime, and links every table through its own steps anyway. `TextPipeline` keeps it too,
  and correctly: it is configured at runtime and can name any step.

  `tests/test_wasm_table_coupling.py` asserts the table presence exactly and the sizes as
  generous ceilings. The presence is the real check: a module's size drifts for ordinary
  reasons, but a table appearing in a surface that cannot reach it is categorical, and it
  is what regressed.

- **The script table contradicted the UCD for 33 code points; 19 of them reported as
  Latin (#819).** `detect_char_script` binary-searches a curated table of **block** ranges,
  and a block is not a script. #774 fixed the holes *inside* blocks; this is the part it
  did not reach — blocks that are mislabelled.

  | | |
  |---|---|
  | `Ϣ` U+03E2, UCD `Script=Coptic` | reported **Greek** — 14 Coptic letters sit inside the Greek block |
  | `ᴦ` U+1D26, UCD `Script=Greek` | reported **Latin** — Phonetic Extensions is mostly Latin and is not all Latin |
  | `ᴫ` U+1D2B, UCD `Script=Cyrillic` | reported **Latin** |

  The 19 that resolved to `Latin` are the ones that cost something: a token mixing one
  with ASCII read as single-script, so the mixed-script rule could not fire.
  `is_mixed_script("aᴦ")` was `False` and is now `True`. Contradictions: **0**.

  **A gate now separates a scope from a defect, which nothing did before.** The table
  *declining* to name a script is the curated 61-script scope working — 12,541 code points,
  mostly CJK and other extension blocks — and costs a missed detection. The table naming a
  **different** script is wrong under any curation policy.
  `tests/fixtures/ucd_script_ranges.tsv` is the independent data that lets the two be told
  apart; without it the only available comparison is the table against itself.

  One exemption, checked rather than assumed: `Script=Inherited` means "take the script of
  the preceding character", which a static range table cannot do. The table names the
  block's script instead, which is what makes `is_mixed_script` useful on Arabic or
  Cyrillic text carrying its own marks — an Arabic fatha inside Arabic is not evidence of
  mixing. The gate asserts every code point using that exemption is actually a combining
  mark, so it cannot cover a real disagreement.

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

- **Detection and reduction answer different questions, and nothing said so (#882).**
  `find_confusables` reports what *looks like* something else; `canonicalize` and the
  other key reducers report what two strings *collapse to*. Each interface reads as
  complete on its own, and neither is.

  Measured over `confusable-bench.v1` — 120 malicious identifiers, 20 benign controls:

  | surface | caught /120 | composability | impersonation | evasion | FP /20 |
  |---|---:|---:|---:|---:|---:|
  | six key reducers, union | 72 | 0/31 | 30/35 | **42/54** | 0 |
  | `find_confusables` | 66 | **31/31** | **35/35** | 0/54 | 0 |
  | **either firing** | **108** | 31/31 | 35/35 | 42/54 | **0** |

  A caller who picks one interface leaves between a third and a half of the corpus
  unreached, at **no** false-positive saving — both are 0/20 alone and together. The
  split is structural: the detector sees a character that has a fold target, so it takes
  composability and impersonation and cannot see evasion; the reducers are the mirror.

  Documented in the confusables guide with a worked registry example, and on both entry
  points. `tests/test_detector_and_reducers_pair.py` pins the structural claim — cases
  each surface catches and the other cannot — without fetching the corpus; the scoring
  itself belongs in `benchmarks/meta`, where a network dependency is declared.

- **The fold is not order-independent, and nothing said so (#834).**
  `normalize_confusables` folds the TR39 table against the input as written. Every preset
  and profile that folds confusables normalizes to NFKC first, so the fold there sees a
  decomposed image — and **68 code points get a different answer** for the Latin target, 8
  for Cyrillic. `normalize_confusables("ſ")` is `"f"`; `canonicalize("ſ")` is `"s"`.

  Both are defensible — TR39 assesses a long s as visually an `f`, NFKC says it is an `s` —
  and neither order wins everywhere:

  | class | count | standalone | after NFKC | better |
  |---|---:|---|---|---|
  | number forms (`⑴`, `⒈`, `ⅿ`) | 30 | `(l)`, `l.`, `rn` | `(1)`, `1.`, `m` | NFKC |
  | mathematical alphanumerics (`𝐦`) | 14 | `rn` | `m` | NFKC |
  | spacing modifiers (`´`, `¸`, `˜`) | 15 | `'`, `,`, `~` | space + combining mark | standalone |
  | the rest (`ſ`, `ϲ`, `℧`) | 9 | `f`, `c`, `E` | `s`, `ς`, `Ɛ` | judgment |

  44 favour the preset answer, 15 favour the standalone one, 9 are a genuine call between
  "looks like" and "decomposes to". disarm ships both because both are wanted; the defect
  was that two names reading as the same operation gave different answers silently.

  `docs/limitations.md` lists the shadowed rows rather than subtracting them, for the same
  reason that page refuses to filter the coverage report — *"a coverage number that quietly
  drops rows reads as coverage it does not have"* applies just as well to a row the
  pipeline order makes unreachable.

  The consequence for a caller building keys is now stated plainly on all three surfaces:
  **`normalize_confusables` alone is not a canonical skeleton.** `⑴` folds to `(l)` while
  ASCII `(1)` stays `(1)`, because the table carries only three ASCII sources (#725) — so
  two strings a reader cannot tell apart get different keys from the standalone call and
  the same key from any preset.

  This is the disarm-side instance of PRI #540 feedback ID20260222084837, which asks the
  UTC to document in UTS #39 that a pipeline running NFKC before confusable detection
  should filter the table against NFKC. disarm ships both orders as public API, so the
  rows are not dead here — they are reachable through one entry point and shadowed through
  the other.

  No behaviour changes. `tests/test_fold_order_divergence.py` pins the counts, the worked
  examples and the bucket totals to the pages that state them, keyed on the number rather
  than on the phrasing.

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
