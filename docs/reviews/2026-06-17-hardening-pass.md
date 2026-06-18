# HAI-SDLC Hardening Review — disarm

- **Date:** 2026-06-17 (17:52 UTC)
- **Commit:** `fd7a54f` (main, clean working tree)
- **Scope:** Rust core (`src/`) + all bindings (PyO3 `src/py/`, Node `bindings/node/`, Ruby `bindings/ruby/`, Python wrapper `python/disarm/`)
- **Budget profile:** Standard
- **Mode:** Analysis only — no code was changed. This file is the sole deliverable.

> ## Resolution status (2026-06-18 follow-up)
>
> A post-0.11 hardening pass actioned this report.
>
> **Fixed:** H-P1 (`fold_case_cow` single pass), H-P2 (`is_zalgo` early-exit),
> H-P3 (`strip_zalgo` fast path, with an NFC property test), H-P5
> (`grapheme_width` ASCII fast path), H-D1 (slug `lang` doc), H-D2 (Python slug
> `Raises`), H-D3 (Node `getPipeline` doc + a new Policy-pipelines section),
> M-C1 (slug trailing partial multi-char separator, + proptest), M-P3
> (`detect_scripts` linear dedup), M-P4 (`truncate_to_graphemes` result-sized
> reserve), M-P5 (`strip_control`/`strip_zero_width` reserve), M-D1 (stale
> `allow(dead_code)`), M-D2 (`Error::code`/`kind` `#[must_use]`), M-D3 (Ruby/Node
> "not surfaced" notes incl. `strip_log_injection`), L-D1 (deprecation docstrings
> "when explicitly passed"), L-P1 (slug regex no-match `Cow`).
>
> **Stale:** L-C1 — the `collapse_whitespace` `strip_control=false` mode it cites
> was removed by the #433 whitespace split.
>
> **Deferred (not a re-architecture, but low-value or not a clear win):**
> H-P4 (preset ping-pong reroute — structural; see the delta report),
> M-P1 (`confusables` maps ASCII sources by design, so no no-op fast path is
> correct), M-P2 (`Pipeline::process` returns an owned `String`, so the up-front
> `to_owned` is the required result, not waste), L-P2/L-P3/L-P5 (per-call caching
> — adds state for Low value), L-P4 (the 10% fold over-reserve is a deliberate,
> documented anti-realloc tradeoff), L-C2 (CLDR uses `": "` as its base/qualifier
> delimiter, so the first-match cut is intended; a change needs a table audit),
> L-S1/L-S2 (informational — cannot flip the fail-closed hostname verdict).

## How this run was conducted

Pass 0 surveyed the architecture, then four analysts ran in parallel — Correctness
(passes 1–3), Harden/Security (4–5), Optimise/Performance (6–7), Polish (8–10).
Every High/Critical finding below was then independently re-checked against the
source by reading the cited lines; the verification result is recorded inline.
One severity was recalibrated during verification (the performance "Critical" is a
linear 2× constant factor, not a super-linear blow-up, so it is reported as High).

## Architecture (Pass 0)

`disarm` is a layered Unicode text-security / canonicalization library:

- **Layer 1** — algorithm modules in `src/*.rs` (transliterate, scripts, confusables,
  normalize, slugify, filename, hostname, log_injection, zalgo, anomalies, emoji,
  width, grapheme, whitespace, encoding, reverse, case_fold, context, pipeline,
  presets).
- **Layer 2** — the idiomatic, pyo3-free public Rust API in `src/api/` plus the
  `DisarmStr` extension trait. This is the one place public Rust behaviour is defined.
- **Binding shims** — PyO3 (`src/py/`), Node/napi (`bindings/node/src/lib.rs`),
  Ruby/magnus (`bindings/ruby/ext/disarm/src/lib.rs`), and the Python wrapper
  (`python/disarm/`). All consume the same Layer-1 core.
- **Codegen** — `build.rs` (~900 lines) builds PHF tables from TSV in
  `src/tables/data/`, with compile-time ASCII-only assertions on table values.

**Security posture is strong by construction:** `unsafe_code = "forbid"` (zero
`unsafe` in the core), centralized resource limits in `src/limits.rs`, a documented
`THREAT_MODEL.md`, and atomic "has any registration?" gates that keep locks off the
common path. The trust boundary is untrusted text input; the headline risk class for
a sanitization library is panic-on-adversarial-input (DoS) and neutralization bypass.

## Overall verdict

**No blocking issues. No Critical or High security or correctness defects.** The
codebase is unusually well-hardened: the ~202 `.unwrap()` / 25 `.expect()` / 7
`panic!`-family sites are overwhelmingly test-only, and the handful in production
paths are guarded or bounds-checked to provable infallibility. Byte-slicing is
uniformly ASCII-anchored or `char_boundary`-guarded; injection-neutralization
controls (log-injection, bidi stripping, filename sanitization) are complete against
the character-level vectors they claim, with matching doc/impl/regression-test triples.

The real, actionable findings cluster in two areas:

1. **Performance headroom in the preset pipelines and a few secondary modules** —
   per-stage allocation in the presets, and missing early-exit / fast-path in
   `fold_case`, `zalgo`, and `width`. Two of these are DoS-adjacent on long input.
2. **Documentation-vs-code drift** — three public-doc claims that describe behaviour
   the code does not implement (the highest-value polish items, because users trust
   them).

Recommended priority order is at the end.

---

## Findings

Severity reflects real-world impact, not theoretical reachability. `[VERIFIED]`
means I re-read the cited source and confirmed the finding during this run.

### Performance (Optimise)

#### H-P1 · `fold_case_cow` double-scans and double-probes the PHF on the owned path · **High** `[VERIFIED]`
- **Location:** `src/case_fold.rs:31-41` (`fold_case_cow` detect scan) + `:54-69` (`fold_case_into` fold scan)
- **What:** `fold_case_cow` runs `chars().any(|c| … lookup(c).is_some())` over the
  whole string (one PHF probe per non-ASCII char), and on a hit calls
  `fold_case_impl` → `fold_case_into`, which scans again with the *same* probe.
  Every foldable char is looked up twice. The borrowed (zero-alloc) fast path is fine.
- **Why it matters:** 2× CPU and 2× PHF work on exactly the most expensive inputs
  (large all-foldable text — Greek/Cyrillic uppercase, `ß` runs). `fold_case` is a
  documented per-call hot path and backs `DisarmStr::fold_case`.
- **Fix direction:** Fold in a single pass: build optimistically and track whether
  any char differed; return `Cow::Borrowed` if not. Or have `fold_case_into` return a
  `changed` bool so detect and fold fuse.
- **Severity note:** The Optimise analyst rated this Critical; verification confirms
  the double-probe but it is a linear 2× constant factor (not super-linear), so it is
  reported as **High**.
- **Confidence:** High. Verify with a bench on ~1 MB of `Ω`.

#### H-P2 · `is_zalgo` cannot early-exit — always walks the whole NFD stream · **High** `[VERIFIED]`
- **Location:** `src/zalgo.rs:57-63` (`is_zalgo`) → `:31-46` (`max_combining_run`)
- **What:** `is_zalgo` only needs "does any run exceed `threshold`?" but
  `max_combining_run` computes the maximum run over the entire string before comparing.
  No break on first violation past the ASCII gate.
- **Why it matters:** DoS shape — a 4-mark zalgo burst prepended to a 10 MB benign
  tail forces a full NFD walk of all 10 MB though the verdict was settled in the first
  few chars. **Perf + DoS.**
- **Fix direction:** Give `is_zalgo` a streaming loop over `text.nfd()` that returns
  `true` the instant `current_run > threshold`.
- **Confidence:** High. Verify: `is_zalgo("a" + "\u{0300}"*4 + huge_tail)` scales with
  tail length today; should be ~constant after.

#### H-P3 · `strip_zalgo_into` runs NFD→temp→NFC unconditionally for all non-ASCII · **High** `[VERIFIED, with correctness caveat]`
- **Location:** `src/zalgo.rs:83-109` (temp `String` at `:91`, `out.extend(filtered.nfc())` at `:108`)
- **What:** Any non-ASCII input pays a full NFD decompose into a heap temp, then a
  full NFC recompose, plus an input-sized temp allocation — even with zero marks (plain
  CJK, emoji, `café`). The fast path covers only pure ASCII.
- **Why it matters:** Most non-ASCII text needs no stripping yet pays the two most
  expensive ops in the module plus an extra allocation. Hit on every
  `strip_obfuscation` / `normalize_user_input` call. **Perf + DoS-adjacent.**
- **Fix direction:** Add a streaming pre-check for "any run > max_marks"; if none, skip
  the round-trip.
- **⚠ Caveat surfaced during verification:** The documented contract is "operates in
  NFD space and recomposes to **NFC**," so the output is always NFC. A naive
  "no excess marks → `push_str` the input verbatim and return" optimization would
  **skip normalization** and return non-NFC input unchanged — a behaviour change. The
  early-out is only safe if the input is already NFC (or you keep NFC-ing the result).
  Implement the fast path so it preserves the NFC guarantee, and add a property test
  asserting `strip_zalgo(x)` is always NFC.
- **Confidence:** High that the round-trip is unconditional for non-ASCII.

#### H-P4 · Preset pipelines allocate a fresh `String` per stage · **High** `[VERIFIED]`
- **Location:** `src/presets.rs` — `security_clean:147`, `ml_normalize:173`,
  `catalog_key:235`, `search_key:280`, `sort_key:376`, `normalize_user_input:431`,
  `strip_obfuscation:482`
- **What:** Each preset chains the *returning* forms (`nfkc_normalize`, `strip_bidi`,
  `normalize_confusables`, `transliterate_impl().into_owned()`, `strip_accents`,
  `fold_case`, `collapse_whitespace`, …); every stage allocates and returns a new
  `String` and the previous is dropped — even no-op stages. `Pipeline::process`
  (`src/pipeline.rs:214`) already solved this with a two-buffer ping-pong (#236 item 7);
  the presets never adopted it. (Verified `security_clean` and `search_key` directly.)
- **Why it matters:** `search_key` / `sort_key` / `catalog_key` are the documented
  per-call short-string hot paths in `docs/performance.md`. A 6-stage preset does ~6
  heap allocs + 6 full copies where the engine does ~2. On short inputs the per-call
  allocation count dominates the boundary-crossing budget the docs optimize for.
- **Fix direction:** Refactor presets onto the ping-pong (the `*_into` variants already
  exist for normalize/strip_accents/fold_case/confusables/strip_bidi/collapse/zalgo/
  demojize), or express them as `Pipeline` specs routed through `process`.
- **Confidence:** High. Verify by counting allocations through `search_key(...)` vs an
  equivalent `Pipeline::process`.

#### H-P5 · `grapheme_width_opts` pays two binary searches per ASCII char (no ASCII fast path) · **High** `[VERIFIED]`
- **Location:** `src/width.rs:84-93` — `base_emoji` (`EMOJI_PRESENTATION_RANGES` search) and `base_class` (`width_class`) computed eagerly
- **What:** For every cluster, both the emoji-presentation range search and the
  width-class search run, even for ASCII/Latin-1 bases (`cp < 0x300`) that can never be
  emoji or wide. `terminal_width_opts` calls this per cluster. No early-out at the top.
- **Why it matters:** For long pure-ASCII input (identifiers, URLs, usernames — the
  dominant input for this library), every char costs ~2·log₂(table) comparisons instead
  of O(1). Constant-factor multiplier on long/adversarial input.
- **Fix direction:** Top-of-function guard: `if (base as u32) < 0x300 && rest.is_empty() { return ascii_width }`, skipping both searches.
- **Confidence:** High. Verify with a Criterion bench on a long ASCII string.

#### Medium / Low performance items (not individually re-verified — analyst confidence noted)
- **M-P1** `confusables::normalize_confusables_into` has no borrowed/no-op fast path; the `Pipeline` CONFUSABLES step (`pipeline.rs:291`) always returns `Ok(true)` and full-copies even on no-op input, unlike the TRANSLITERATE branch. *(Medium, High confidence)*
- **M-P2** `Pipeline::process` does `text.to_owned()` up front (`pipeline.rs:224`) before any step decides to mutate — wasteful on empty/ASCII-passthrough pipelines. *(Medium)*
- **M-P3** `detect_scripts` builds a `HashSet` per call (`scripts.rs:9-21`) to dedup ≤~3 scripts; a linear `Vec::contains` avoids the alloc. *(Medium, High confidence)*
- **M-P4** `truncate_to_graphemes` reserves the full input length (`grapheme.rs:43`) regardless of `max_graphemes` — O(len) memory to keep a tiny result. *(Medium)*
- **M-P5** `strip_control_chars[_into]` / `strip_zero_width_chars_into` (non-ASCII branch) lack `reserve` (`whitespace.rs:71-84`, `:94-103`). *(Medium)*
- **L-P1** slugify step-5 custom-regex stage force-allocates on no match (`slugify.rs:533-535`, also `:437`) — `replace_all` already returns a borrowing `Cow`. *(Low)*
- **L-P2** slugify rebuilds the `safe_chars` `HashSet` per call (`slugify.rs:546-551`) instead of caching like the stopword set. *(Low)*
- **L-P3** `filter_stopwords` `save_order` branch materializes a full `Vec<&str>` + triple walk (`slugify.rs:622-631`). *(Low)*
- **L-P4** `fold_case_into` over-reserves 10% on every non-ASCII input (`case_fold.rs:54-57`). *(Low)*
- **L-P5** `list_langs` clones + re-sorts all builtins per call even when nothing is registered (`tables/mod.rs:~438`). *(Low)*

### Polish (documentation & API)

#### H-D1 · Rust doc asserts a Python `slugify` lang-validation that does not exist · **High** `[VERIFIED]`
- **Location:** `src/api/text.rs:279-281` (doc on `api::slugify`), vs `src/slugify.rs:357` (`with_lang` "best-effort; not validated") and `python/disarm/_api.py` (`slugify` passes `lang` straight to the core)
- **What:** The doc says *"This differs from the Python `slugify`, whose convenience
  wrapper eagerly validates `lang` and raises."* It does not — Python forwards `lang`
  unvalidated to the core, which silently falls back to the default transliterator for
  an unknown code. No binding raises on a bad slug `lang`. The doc is internally
  contradictory (it correctly says Rust doesn't validate, then wrongly says Python does).
- **Why it matters:** A user relies on a `ValueError`/`DisarmError` that never fires —
  a silent-fallback footgun in exactly the spot the doc advertises as a guardrail.
- **Fix direction:** State that *both* Rust and Python treat slug `lang` as
  best-effort/unvalidated; point at `list_langs()` for a pre-check.
- **Confidence:** High (all three sites verified).

#### H-D2 · Python `slugify` docstring lists an exception it never raises · **High** `[VERIFIED]`
- **Location:** `python/disarm/_api.py:576-577`
- **What:** The `Raises:` block says `DisarmError: … invalid regex_pattern or unknown
  lang code`. An unknown `lang` does **not** raise (per H-D1); only `regex_pattern` does.
- **Fix direction:** Drop "or unknown `lang` code" from the `Raises:` clause; keep the
  `regex_pattern` case.
- **Confidence:** High.

#### H-D3 · Node docs say `getPipeline` is "not yet surfaced" — but it is exported · **High** `[VERIFIED]`
- **Location:** `docs/node/api.md:351-352` (and the subset note at `:8`) vs
  `bindings/node/index.ts:286` (`export function getPipeline`) and
  `bindings/node/src/lib.rs:596` (`get_pipeline` shim)
- **What:** The Stability note disclaims *"not the full `getPipeline` registry"*, but
  `getPipeline(profile)` and the `Pipeline` class are fully exported and implemented in
  the Node package. There is also **no `## Pipeline` reference section** in
  `docs/node/api.md` for this shipped, public API. (`mlNormalize` and the fluent `Text`
  builder genuinely are Node-absent — verified — so leave those in the note.)
- **Why it matters:** Node users are told to "reach for another binding" for
  functionality that ships in the Node package. Clearest doc-vs-code defect in the
  binding docs.
- **Fix direction:** Remove `getPipeline` from the "not yet surfaced" list and add a
  `## Policy pipelines` section documenting `getPipeline(profile)` and `Pipeline#process`.
- **Confidence:** High.

#### Medium / Low polish items
- **M-D1** Stale `#[allow(dead_code)]` + inaccurate comment on `ErrorRepr::code()` (`src/error.rs:445-451`): the method is reachable via the public `Error::code()` (`:700`, exercised at `api/mod.rs:258`), so the `allow` suppresses nothing and the comment misdescribes the wiring. Boy-Scout fix. *(Medium, High confidence)*
- **M-D2** Public `Error::code()` (`error.rs:700`) and `Error::kind()` (`:648`) lack `#[must_use]`, unlike the rest of the Layer-2 surface. *(Medium)*
- **M-D3** The output-encoder / encoding / log-injection / pipeline family (`escape_html`, `percent_encode`, `detect_encoding`, `decode_to_utf8`, `strip_log_injection`, `display_clean`, `ml_normalize`, `normalize_user_input`, `list_profiles`, `list_langs`, `reverse_langs`, `is_ascii`) is Python-exposed but absent from Node and Ruby. Node has a (now partly stale) note; **Ruby has no "not surfaced" note at all**, so the omission — including the security-relevant `strip_log_injection` — is undocumented. Either surface the high-value ones or add an accurate "not surfaced in this binding" note to `docs/ruby/api.md` (and sync the Node note). *(Medium, High confidence on the gap)*
- **L-D1** `is_confusable` / `demojize` deprecation docstrings (`_api.py:1655-1657`) read as if the `DeprecationWarning` always fires, but the code only warns when the removed param is explicitly passed (the correct, quieter behaviour). Add "when explicitly passed". *(Low)*

### Correctness

#### M-C1 · `slugify` word-boundary truncation can leave a trailing partial/whole separator (custom multi-char separator only) · **Medium** `[VERIFIED]`
- **Location:** `src/slugify.rs:657-667` (`truncate_at_boundary`), reached from `:592-594`
- **What:** The non-`word_boundary` path (`:596-602`) explicitly strips a trailing
  separator after `floor_char_boundary` truncation. The `word_boundary` path
  (`truncate_at_boundary`) does not: when `truncated.rfind(separator)` returns `None`
  it returns `truncated` verbatim. With a **multi-byte separator**, `floor_char_boundary`
  can cut *inside* the separator (e.g. separator `"--"`, slug `"ab--cd"`,
  `max_length=3` → `"ab-"`), and `rfind("--")` then misses, yielding a trailing `"-"`.
  Verified: the default single-char `"-"` is unaffected (a trailing single-char
  separator is always re-found by `rfind` and cut), so this manifests only with a custom
  multi-char separator — which is why the `slugify_output_charset` proptest (default
  separator only) doesn't catch it.
- **Why it matters:** Violates the "no trailing separator" slug invariant and breaks
  re-slugify idempotence for callers using a multi-char separator.
- **Fix direction:** After `truncate_at_boundary`, strip a trailing (possibly partial)
  separator the same way the non-word-boundary branch does; extend the proptest to a
  multi-char separator.
- **Confidence:** Medium-High. Reproduce with `SlugConfig { separator: "--", max_length: 3, word_boundary: true, .. }` on input slugifying to `"ab--cd"`.

#### Low correctness items
- **L-C1** `collapse_whitespace` doesn't reset the space-run state across a *preserved* control char (`whitespace.rs:43-48`, `strip_control=false` mode): `"a \x01 b"` → `"a \x01b"`, dropping a separating space. Security presets always strip controls, so not a security concern. *(Low)*
- **L-C2** `strip_modifier_suffix` cuts the CLDR name at the first `": "` (`emoji.rs:286-293`), which over-truncates any base name containing `": "`; only the opt-in `strip_modifiers=true` path. Worth a quick scan of the emoji table for affected names. *(Low)*

---

## Security findings (Harden)

No Critical or High vulnerabilities. The four hardening areas flagged at the start
(panic-as-DoS, resource amplification, injection-neutralization, binding-boundary
safety) are each already addressed with deliberate, tested controls (verified during
Pass 0 and the security pass):

- **Panic surface:** essentially the entire 200+ `unwrap` count is `#[cfg(test)]`. The
  non-test production unwraps in the transform modules are provably guarded —
  `transliterate.rs:634` (`is_mapped`-gated), `context.rs:93,104` (slice already
  bounds-checked to exactly 2/4 bytes; the binary dict parser fails closed on malformed
  input), `slugify.rs:466` / `reverse.rs:95` (loop-invariant / `if let` guarded).
- **Amplification:** the one real vector (caller-registered replacement *values*) is
  capped **incrementally during construction** at `tables/mod.rs:672`, so the
  over-limit buffer is never fully realized. `MAX_BATCH_SIZE`, `MAX_REGEX_PATTERN_BYTES`,
  `MAX_REGEX_DFA_BYTES` (`RegexBuilder::size_limit`), and the registration caps are all
  enforced at the entry points.
- **Injection neutralization:** `log_injection.rs` covers C0/C1 (so NEL U+0085, CSI
  U+009B), LS U+2028, PS U+2029, DEL, and validates the replacement can't reintroduce a
  neutralized char; `strip_bidi` covers the full UAX#9 set + ALM + soft hyphen +
  deprecated format controls + interlinear annotation marks (regression-tested);
  `filename.rs` collapses `..` before *and* after transliteration and handles
  post-truncation Windows reserved names.
- **FFI boundaries:** all three shims are thin, return `Result`→host-exception (no
  `unwrap` across FFI), reject negative lengths before the `usize` cast (Node `i64`
  `checked_size`), and the `min_confidence` range/NaN check lives in the **core**
  (`encoding.rs:101`), not just the Python wrapper.

**Low / advisory:**
- **L-S1** `hostname.rs:151-159` feeds best-effort-decoded bytes from a *malformed* ACE
  label into the advisory `canonical` / `scripts` fields. It **cannot** flip the
  already-fail-closed `suspicious=true` verdict, so there's no impact on the asset the
  threat model stands behind — but `analysis.canonical` of a malformed IDN shouldn't be
  treated as authoritative. Consider skipping/marking-untrusted the canonical form on
  the error arm. *(Low)*
- **L-S2** `recover_lock` poison recovery (`lib.rs:333-373`) returns the inner guard
  rather than propagating. Recovered std collections are valid-but-unspecified (never
  UB — `unsafe` is forbidden), and current mutators don't panic mid-critical-section, so
  this is a latent invariant to watch, not a present bug. *(Low/informational)*

**Out of scope per `THREAT_MODEL.md` (not bugs):** no input-size cap on transforms
(caller's responsibility); confusables outside the bundled TR39 table; whole-script and
multi-character (`rn`→`m`) spoofs; NFKC unmasking ASCII metacharacters
(`＜script＞`→`<script>`) — `escape_html` / `percent_encode` are terminal output
encoders the caller applies at the sink; pure-ASCII XSS/SQL payloads passing through.

---

## Recommended priority order

1. **H-D1 / H-D2 / H-D3 (docs)** — cheap, and they are correctness claims a user will
   trust; H-D1 touches a security-adjacent silent fallback the doc currently advertises
   as a guardrail. Highest value-per-effort.
2. **H-P2 + H-P3 (zalgo early-exit / round-trip)** — the two DoS-adjacent perf items on
   long input; implement H-P3 with the NFC caveat above and a property test.
3. **H-P4 (preset allocation)** — biggest steady-state perf win; the `*_into` machinery
   already exists, so it's a refactor onto an existing pattern.
4. **H-P1 (fold_case single-pass)** and **H-P5 (width ASCII fast path)** — constant-factor
   wins on hot paths.
5. **M-C1 (slug trailing separator)** — correctness, but only on a non-default
   configuration; pair the fix with a multi-char-separator proptest.
6. **M-D1 / M-D2 (Boy-Scout: stale `allow`, missing `#[must_use]`)** and the remaining
   Medium/Low items as area is touched, per the project's broken-windows rule.

## What was checked and found clean

Transliterate engine (ASCII passthrough → `Cow::Borrowed`, word-at-a-time ASCII-run
skipping, bounded capacity estimator, single-pass strict mode), table lookup layer
(atomic gates, prebuilt aho-corasick, no lock on the common path), `normalize` (ASCII
fast path, early-exit `is_normalized`), `scripts` (binary-searched ranges, short-circuit
mixed-script), `grapheme`/`width` segmentation correctness, `confusables_cow`,
`emoji` trie walk, `Pipeline::process` ping-pong, `filename` reserved-name handling
(incl. post-truncation), cross-binding default parity (separator, lowercase,
entities/decimal/hexadecimal, strip_control/strip_zero_width, filename defaults,
negative-size rejection), and `build.rs` codegen (repo-controlled TSV, compile-time
ASCII assertion).

---

*Generated by the HAI-SDLC hardening sequence — analysis only. No source files were
modified. Findings cite `path:line` at commit `fd7a54f`; line numbers may drift as the
tree changes.*
