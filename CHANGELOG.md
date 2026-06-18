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

- **`security_clean` and `normalize_user_input` no longer neutralize path
  separators (#431, reverses #248).** The presets previously rewrote `/` and `\`
  to `_` and collapsed `..` runs so the output was safe to drop into a filesystem
  path. That is *sink-specific output sanitization* — out of scope for the
  canonicalization presets per [THREAT_MODEL.md](THREAT_MODEL.md) — and it
  corrupted legitimate input: URLs, file paths, and any `/`- or `\`-bearing
  string came back mangled (`"https://example.com/path"` →
  `"https:__example.com_path"`). The presets now pass separators through
  verbatim. **Migration:** if you fed preset output straight into a filesystem
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

### Fixed

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
  invisible character (e.g. `"pass­word"`, `"user‮txt"`) produced a
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
