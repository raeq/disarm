# HAI-SDLC Hardening Review (Deep, Full-Tree) — disarm

- **Date:** 2026-06-18
- **Commit:** `fb5524f` (`main`, active worktree; tree clean apart from CHANGELOG)
- **Scope:** Full tree, no baseline — Rust core (`src/`, ~23.3k LOC) + PyO3 (`src/py/`), Node, Ruby bindings + Python wrapper (`python/disarm/`, ~5.4k LOC). Analyzed as-is, not as a diff.
- **Budget profile:** Deep — five analysts (Correctness, Security, Performance, Polish, + a dedicated fast-path/idempotency deep-dive), exhaustive module coverage.
- **Mode:** Analysis only — no source changed. This file is the deliverable.

## Method

Pass 0 surveyed the current tree, then five analysts ran in parallel: the four lenses across the full module set, plus a dedicated deep-dive on the reworked preset layer's two crown-jewel guarantees (fast-path equivalence, idempotency). Every High/Critical and the two crown-jewel guarantees were then independently verified against source — confusables TSV entries, the fixed-point loop body, the proptest generators, and the guard predicate. Where no Rust toolchain was available, idempotency/equivalence claims were modeled semantically against the real Unicode tables and stated as such.

## Verdict

**The strongest result of the three reviews. No Critical or High security or correctness defect; the highest-severity finding is Medium.** Most importantly, the guarantees that were *broken* in the prior delta review are now verified to **hold**:

- **`canonicalize` / `canonicalize_strict` / `strip_format` / `strip_obfuscation` / `sort_key` are raw-idempotent** — the #434 `ConfusablesNfcFixedPoint` loop iterates confusables→NFC to a fixed point, resolving the `"с\u{0327}"`→"ç"→"c" cascade *within a single call*. Verified: the loop body breaks on `nxt == cur`; the `canonicalize_idempotent` proptest now asserts **raw** equality with `\u{0327}`/`\u{0308}` added to its generator (closing the exact "vacuous pass" false-assurance gap I flagged last time), and `"c\u{0327}\u{0327}"` is pinned deterministically. The `display_clean`/`strip_format` VS-carve-out (D-2) and `sort_key` transliterate-order (D-5) cases are likewise fixed, with regression tests.
- **The #458–#463 fast-path guard is sound** — no input was found that the guard classifies "benign" (returning `Cow::Borrowed`, untouched) while the pipeline would actually modify it. The guard's predicates reuse the *same* classifier functions the strip stages call; the ASCII-confusable set is `build.rs`-generated from the same TSV as the PHF (can't rot out of lockstep); and a base+combining-mark that would compose into a confusable is caught by the `marks` predicate. Two independent analysts reached this conclusion.
- **The H-P4 allocation debt is resolved** — all presets route through a shared two-buffer ping-pong runner (#453/#454); no-op stages skip the swap; benign ASCII is genuinely zero-alloc (`Cow::Borrowed`).

The actionable findings are perf-margin refinements and documentation polish.

## Architecture (Pass 0)

Unchanged in shape from prior reviews (layered Layer-1 algorithms → Layer-2 `api/` → PyO3/Node/Ruby shims → Python wrapper; `build.rs` PHF codegen; `unsafe` forbidden; limits in `limits.rs`). The preset layer was substantially reworked: presets renamed to mechanism names (`canonicalize`, `canonicalize_strict`, `strip_format`, `catalog_key`, `search_key`, `sort_key`, `ml_normalize`, `strip_obfuscation`) with deprecation aliases (#430/#450); all return `Cow<str>` and run through a `Step`-enum ping-pong runner behind a byte-mask fast-path guard; confusables iterate to a bounded fixed point.

---

## Findings (all independently verified against source)

Severity reflects real-world impact. No Critical or High. Highest is Medium.

### Performance

#### P-1 · Fast-path guard orders the expensive normalization predicates before the cheap range checks · **Medium** *(Performance analyst rated High)* `[VERIFIED]`
- **Location:** `src/presets.rs` `acts_on_nonascii`
- **What:** the per-non-ASCII-char predicate chain is `m.transliterate || (m.nfkc && nfkc_changes(ch)) || (m.marks && is_combining_mark(ch)) || (m.strip_accents && decomposes_to_mark(ch)) || (zalgo nfd_mark_run_exceeds) || … || (m.bidi && is_bidi_or_format(ch)) || (m.zero_width && …) || (m.invisible && …)`. The two costliest predicates — `nfkc_changes(ch)` and `decomposes_to_mark(ch)`, which spin up single-scalar NFKC/NFD normalization iterators — run **before** the cheap pure-range `matches!` checks (bidi/zero-width/invisible). For a *transliterating* preset `m.transliterate` short-circuits the whole scan to O(1)/char (great). For the *non-transliterating* presets (`canonicalize`, `canonicalize_strict`, `strip_obfuscation`, `ml_normalize` without lang), `m.transliterate` is false, so the first non-ASCII char pays an NFKC-iterator probe.
- **Why it matters:** on benign **non-ASCII** input (clean CJK/Hangul/accented-Latin through `canonicalize`), the guard's per-char cost approaches the first pipeline stage it's trying to skip, so the margin is thin — it still wins for a multi-stage preset, but not by much. (Benign **ASCII** — the deployment norm — is unaffected: the byte-loop never reaches `acts_on_nonascii`.)
- **Severity note:** the analyst rated this High; recalibrated to **Medium** — it's a constant-factor optimization opportunity on one input class, not a regression, correctness, or DoS issue, and the guard is still a net win.
- **Fix direction:** reorder predicates cheapest-first (pure range checks before the NFKC/NFD iterators); optionally gate the normalization probes behind a coarse BMP-block bitmap (cf. the `transliterate.rs` `BLOCK_CLASS` precedent) so inert blocks (CJK, Hangul) skip the iterator.
- **Confidence:** High the ordering is suboptimal; magnitude unmeasured (no profiler). Verify with a Criterion bench of `canonicalize` on ASCII vs clean-CJK vs clean-accented-Latin, guarded vs `without_fastpath`.

#### P-2 · Confusables fixed-point loop re-NFCs and re-folds the whole string each iteration (bounded DoS amplifier) · **Medium** `[VERIFIED]`
- **Location:** `src/presets.rs` `Step::ConfusablesNfcFixedPoint` (the #434 loop)
- **What:** each iteration runs `normalize_confusables_into` then a full-string `NFC` over the result; up to `CONFUSABLE_FIXED_POINT_ITERS = 8` passes. Buffers are reused across iterations (good — no per-pass alloc), but every pass re-scans and re-normalizes the entire string even though only changed regions can produce new foldable forms.
- **Why it matters:** in the two hottest defense presets. Benign input converges in 1–2 passes (verified: the deep-dive modeled max 5 iterations even for triple-stacked marks, and the loop's `break` fires early). The DoS angle is bounded: an adversarial duplicate-mark string can force more passes, but the cap is a hard 8× linear constant, not unbounded — hence Medium, and the Zalgo(2) cap before the loop limits realistic depth to ~4.
- **Fix direction:** skip the NFC pass when the confusables pass changed nothing; or fold-aware incremental NFC over only the touched region. Confirm the worst-case iteration count with an instrumented bench.
- **Confidence:** High on the mechanism; the 8× worst case requires a deliberately near-non-converging input.

#### P-3 · `sort_key`'s `transliterate_preserving_latin` re-pays per-run transliterate setup + a per-char script binary search · **Medium** `[plausible, not independently re-verified]`
- **Location:** `src/presets.rs` `transliterate_preserving_latin_into`
- **What:** walks char-by-char calling `scripts::detect_char_script` (O(log n) binary search per char) and invokes `transliterate_impl` once per non-Latin run, each call re-resolving the lang map and re-running the 256-char capacity estimator, plus a per-run `String` the ping-pong can't absorb. Bites mixed-script titles — exactly `sort_key`'s use case.
- **Fix direction:** replace the per-char full script lookup with a cheap 3-way Latin/Common/Inherited range check; use a lighter capacity hint for short runs.
- **Confidence:** Medium (well-tested for correctness; cost only on mixed-script input).

*(Lows: `run` always `to_owned()`s past the guard even for inputs the pipeline leaves unchanged; `pad_emoji_replacement`/VS-keep call `chars().next_back()` per item; `is_windows_reserved` allocates an uppercase `String` up to 3×/call. All negligible.)*

### Correctness

#### C-1 · Binary-searched `metadata.rs` arrays have no sortedness guard · **Medium** `[VERIFIED]`
- **Location:** `src/metadata.rs` (`lang()` `:1339`, `script()` `:1347`, `binary_search_by_key`); `SCRIPTS` in `api/metadata.rs`
- **What:** `LANGS`, `SCRIPTS_META`, `SCRIPTS` are binary-searched but `metadata.rs` has no test module and no sortedness assertion — unlike the analogous `BUILTIN_LANGS`, which *is* guarded by `builtin_langs_is_sorted` (`tables/mod.rs:859`, verified). The arrays are currently sorted, so this is latent risk, not an active miscompute: if `gen_metadata.py` ever emits an out-of-order row, `lang_info`/`script_info` would silently return wrong/missing metadata with no test catching it.
- **Fix direction:** add a `#[test]` or `build.rs` const-assertion that each array is strictly sorted by key, mirroring `builtin_langs_is_sorted`.
- **Confidence:** High the guard is absent and the convention is established elsewhere.

*(Lows: `reverse.rs` uses a byte-width window for a documented char-width key bound — safe today because all reverse keys are ASCII, fragile if a non-ASCII key is ever added; `emoji.rs` `is_emoji_codepoint` silently skips the U+1FB00–1FBFF Legacy Computing block — correct but undocumented; `strip_zalgo` "kept marks" count is pre-NFC — intended, a doc-clarity note.)*

### Security

No High/Critical, in scope or otherwise. The panic surface is disciplined (untrusted `.bin` dict parsing in `context.rs` is fully fallible with bounds-checked reads; slicing is char-boundary-clamped; FFI lengths validated via `checked_size`; `unsafe` forbidden), the neutralization controls cover their claimed inputs (log-injection C0/C1/NEL/LS/PS; filename double dot-collapse + pre/post-truncation reserved-name handling; the invisibles emoji-flag carve-out validates against an **exact RGI subdivision allowlist** `["gbeng","gbsct","gbwls"]`, not just shape — stronger than the prior partial check, closing the old D-6), and the fast-path guard was independently confirmed not to skip any class needing cleaning.

- **S-1 (Low):** `compile_regex` (`src/slugify.rs:33`) sets `.size_limit(MAX_REGEX_DFA_BYTES)` but not `.dfa_size_limit(...)`, so the match-time lazy-DFA cache uses the regex-crate default rather than the project constant. Pattern length is pre-capped and compile errors are typed (no panic), so this is symmetry hardening, not a hole.
- **S-2 (Low/info):** `THREAT_MODEL.md` says slugify is "bounded by an input-size cap" — the bound is on *pattern* size, not input. Reconcile wording.
- **S-3 (Low/info):** stale secondary lockfile `bindings/ruby/ext/disarm/Cargo.lock` pins `magnus 0.7.1` while the active build uses 0.8.2 — cosmetic drift; regenerate to avoid a misleading future audit.
- **S-4 (Low):** no binding-scoped no-panic clippy gate (`-D clippy::unwrap_used,indexing_slicing`) to structurally lock in the "shims never panic across FFI" property the code currently upholds by hand.
- **Suggested test hardening:** add a base+combining-mark dimension to the fast-path equivalence proptest generator — the soundness for that class currently rests on the `marks` argument, not on a test that exercises a composing pair.

### Polish

#### Pol-1 · Node `collapseWhitespace` doc invents a non-existent `options` param and states the opposite of the real behavior · **Medium (security-relevant)** `[VERIFIED]`
- **Location:** `docs/node/api.md:132-136` vs `bindings/node/index.ts:238`
- **What:** the doc signature is `collapseWhitespace(text, options?)` and claims it "By default also strips control and zero-width characters (`options.stripControl` / `options.stripZeroWidth`, both `true`)." The real export takes **only `text`** — no options — and its own JSDoc says it "does NOT delete control or zero-width characters — use `stripControlChars` / `stripZeroWidthChars` for that." The doc describes the exact opposite of reality.
- **Why it matters:** a Node user trusting the doc believes control/zero-width chars are stripped when they are not — a security-relevant false assurance on a public npm surface, and passing `{stripControl:false}` is silently ignored. Highest-value doc defect found.
- **Fix direction:** rewrite to `collapseWhitespace(text)`; drop the options claim; point to `stripControlChars`/`stripZeroWidthChars`, matching the JSDoc.
- **Confidence:** High (both files read).

#### Pol-2 · `strip_obfuscation` has no section in the pipelines reference · **Medium** `[analyst-verified]`
- **Location:** `docs/api/pipelines.md` (jumps from `canonicalize_strict` to `PRESETS`)
- **What:** every other preset gets a `## <name>` section with steps + examples; `strip_obfuscation` — a root-exported, README-featured preset — has none. Add a section mirroring the others.

#### Pol-3 · Python `Text` fluent builder omits `canonicalize_strict` / `strip_obfuscation` (+ the `normalize_user_input` alias) · **Medium** `[analyst-verified]`
- **Location:** `python/disarm/_text.py:258-305`, `_text.pyi`
- **What:** `Text` exposes `canonicalize`/`strip_format` (and their aliases) but not `canonicalize_strict` or `strip_obfuscation`, both of which exist at module level — so the arguably-primary "normalize untrusted input" preset isn't chainable while less safety-critical siblings are. Add them (with the deprecated `normalize_user_input`) + parity tests, or document the omission deliberately.

*(Lows: two `_presets.py` docstrings still steer users to the deprecated `display_clean` instead of `strip_format`; the Rust `sort_key` doc-summary omits the second `FoldCase` + terminal NFC that the `STEPS` array two lines below includes; deprecated aliases lack a warning-emission test; cross-binding alias asymmetry — Node/Ruby carry only `security_clean`, defensible since they never exposed the other two names but worth a one-line note.)*

### Fast-path / idempotency deep-dive

**Verdict: fast-path equivalence HOLDS; idempotency HOLDS for all five presets.** One latent-fragility note worth recording:

- **FP-1 (Low, latent — not a current bypass):** the fold_case predicate gates on `ch.is_alphabetic()` (std's Unicode-`Alphabetic`), but the actual fold uses the `case_folding.tsv` table, which can fold non-alphabetic chars (circled capitals, Roman numerals) and may track a different Unicode version. **Not exploitable today** because every preset that sets `fold_case` *also* sets `transliterate`, which short-circuits `acts_on_nonascii` first, so `is_alphabetic()` is never the sole gate for any non-ASCII char in any shipped preset (and circled letters are independently backstopped by `nfkc_changes`). Fix by matching the predicate to the fold table directly (`case_folding_data::lookup(ch).is_some()`) or a `build.rs` assertion, to remove the coupling before some future fold-only preset relies on it.
- **Test-assurance notes:** `strip_obfuscation_idempotent` asserts only `nfc(once)==nfc(twice)` where the code actually provides raw idempotency — weaker than the raw-equality assertions its four peers use; tighten for parity. The tier-3 exhaustive fast-path audit (`#[ignore]`d by design) doesn't cover the plane-1 foldable-letter blocks (U+10570 Vithkuqi, U+10D50 Garay) — irrelevant today given the transliterate backstop, but a blind spot if that coupling changes.

---

## Previously-broken guarantees now verified fixed

For continuity (the prior two reviews are in this folder): **D-1** (canonicalize/normalize_user_input non-idempotent) → fixed by #434's fixed-point loop, verified; **D-2** (strip_format VS carve-out) → fixed, regression-tested; **D-5** (sort_key transliterate-order, incl. transliteration that *emits* uppercase) → fixed with a second fold_case + test; **D-6** (emoji-flag smuggling bypass) → fixed with an exact RGI allowlist; **H-P4** (preset per-stage allocation) → fixed via the ping-pong runner; **H-D1/H-D2/H-D3/M-D3** and the first review's `error.rs` items → all fixed (the slugify-`lang` docs now state best-effort honestly; Node `getPipeline` is surfaced with a Policy-pipelines section; `strip_log_injection` absence is noted in both bindings; `Error::code/kind` carry `#[must_use]`). The proptest generator that previously passed D-1 *vacuously* now includes the triggering combining marks.

## Recommended priority order
1. **Pol-1** — the Node `collapseWhitespace` doc inversion; cheap and the only finding with a (false-assurance) security flavor.
2. **C-1** — add the `metadata.rs` sortedness guard; one test, closes a silent-failure class the codebase already guards elsewhere.
3. **P-1 / P-2** — reorder the guard predicates cheapest-first and short-circuit the fixed-point loop's NFC when nothing changed; the two real perf refinements (constant-factor, no correctness risk).
4. **Pol-2 / Pol-3** — pipelines-doc section for `strip_obfuscation`; complete the `Text` builder.
5. **FP-1 / S-1 / S-4** and the Lows — decouple the fold_case predicate from `is_alphabetic`; `.dfa_size_limit()`; binding no-panic gate; per the Boy-Scout rule as the areas are touched.

## Coverage
All of `src/` was read across the five analysts (every Layer-1 module read in full by at least one lens; `presets.rs` read in full by three including the dedicated deep-dive), plus `build.rs` codegen, the binding shims (Node/Ruby `lib.rs` + `index.ts`/`disarm.rb`), the Python wrapper preset/slug surface, `docs/{node,ruby,api}/`, and the proptests/regressions. Not exhaustively read (data, not logic): the generated PHF/trie table modules and the per-language transliteration TSV rows. No build or test run was performed — analysis only; idempotency/equivalence were verified by source inspection + semantic modeling against the real Unicode tables.

## Posture
This is a mature, unusually well-hardened library that has visibly absorbed two prior hardening passes: the idempotency and fast-path-bypass risks that were open or broken before are now closed and, crucially, backed by *raw-equality* proptests whose generators actually reach the trigger classes. The fast-path guard — the highest-risk recent optimization, since a misclassification would silently skip the security cleaner — is built on conservative, lockstep-generated predicates and exhaustive equivalence tests, and survived a dedicated adversarial deep-dive. The residual work is genuine but minor: a per-char predicate-ordering refinement and a bounded fixed-point-loop cost on the new fast path (both constant-factor, no correctness risk), a missing sortedness invariant on three metadata arrays, and a handful of documentation-sync items led by one Node doc that inverts a function's real behavior. Nothing here blocks a release.

---

*Generated by the HAI-SDLC hardening sequence — deep full-tree run, analysis only. No source files were modified. Findings cite `path:line` at `fb5524f`. Every High/Critical (none found) and both crown-jewel guarantees were independently verified against source during this run.*
