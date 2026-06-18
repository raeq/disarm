# HAI-SDLC Hardening Review (Delta) — disarm

- **Date:** 2026-06-18
- **Range:** `fd7a54f..f24b8e3` (delta since the prior review of 2026-06-17)
- **Scope:** Rust core + all bindings, **delta-scoped** to changed files + blast radius
- **Budget profile:** Standard
- **Mode:** Analysis only — no code changed. This file is the deliverable.

> ## Resolution status (2026-06-18 follow-up)
>
> A post-0.11 hardening pass actioned this report. Status of each finding:
>
> **Already fixed by the 0.11 merges (stale here):**
> - **D-1** (`canonicalize`/`canonicalize_strict` not raw-idempotent) → **#434** (confusables iterated to a fixed point). Verified idempotent.
> - **D-5** (`sort_key` fold-before-transliterate) → **#419**. Verified idempotent.
>
> **Fixed in the follow-up pass:**
> - **D-2** — `is_presentation_base` now rejects bases a later strip removes (control / zero-width / blank-render); added a `strip_format` idempotency proptest + deterministic test.
> - **D-6** — the emoji-flag tail is validated against the RGI subdivision allowlist (England/Scotland/Wales); any other payload is stripped. Fully closes the channel (not just the partial cap).
> - **D-3 (sub-finding) / M-P5** — `reserve` added to `strip_control_chars_into` / `strip_zero_width_chars_into`; ASCII fast path + guard test added to `strip_bidi_into`.
> - **D-4** — `Text.canonicalize` and `_presets.strip_format` pipeline docstrings regenerated.
> - **D-8** — the "collapse is the terminal whitespace step" contract is documented on `collapse_whitespace`.
> - **D-1 proptest generator** — `U+0327`/`U+0308` added to the adversarial `SPECIAL` set. *This surfaced a new latent bug:* `sort_key` was non-idempotent when transliteration **emits** uppercase (Old Persian `𐏈` → `Auramazda`); fixed with a second `fold_case` after transliterate (the #419 pattern), with a regression test.
>
> **Deferred — would require a re-architecture or is not a clear win:**
> - **D-3 (main) / H-P4** — routing all presets through the `*_into` ping-pong is a structural rewrite of the idempotency-critical preset layer (the `canonicalize` fixed-point loop + NFC sandwiches don't ping-pong cleanly). Warrants its own PR with allocation benchmarks. The cheap sub-parts (reserves, fast paths) are done.
> - **D-7** — folded into the D-3 ping-pong; same deferral.
>
> See the base report below for the carried-over polish/perf items, similarly actioned.

## What changed since the last review

15 commits. The substantive code delta is concentrated in the sanitization core:

- **`src/invisibles.rs` (NEW, #413/#428)** — strips the "ASCII-smuggling" classes (Unicode Tags, variation selectors, CGJ, noncharacters, PUA), preserving well-formed emoji subdivision-flag sequences and (rendering policy) presentation selectors.
- **`src/presets.rs`** — `security_clean` is now a **10-stage** pipeline: NFKC → strip_bidi → strip_invisible_classes → strip_control → strip_zero_width → collapse_whitespace → strip_zalgo(2) → NFC → confusables→latin → NFC. The confusables fold is **NFC-sandwiched** (#416/#418) and **path-separator neutralization was removed** (#431).
- **`src/whitespace.rs` (#433/#437)** — the fused `collapse_whitespace(_, true, true)` was split into three functions (`strip_control_chars` / `strip_zero_width_chars` / `collapse_whitespace`); line controls now fold to a space (`a\rb`→`a b`) instead of being deleted.
- **`src/pipeline.rs`, `src/api/{presets,text}.rs`**, the **Node TS6 migration**, and matching Ruby/Python binding updates surfacing the new ops.
- **confusables tables** — Greek iota U+03B9 re-pointed to the i-class (#438).

## How this run was conducted

Delta-aware Pass 0, then four analysts (Correctness, Security, Performance, Polish) scoped to the diff, then a verification pass that re-checked every High/Critical against source. **The verification pass mattered this time:** the Correctness and Security analysts reached *opposite* conclusions on the headline idempotency guarantee, and independent checking of the confusables tables sided with Correctness (details under D-1).

---

## Verdict

The new code is, in isolation, well-built — `invisibles.rs` has exactly-correct range predicates, complete class coverage, ASCII fast paths, and clean cross-binding parity; the path-separator removal is correct and honestly documented; the whitespace split closes an invisible-join vector. **But the central `f(f(x)) == f(x)` guarantee this delta claims to establish is still broken in three independent, verified ways**, and the test suite gives *false assurance* on exactly that property (one proptest passes vacuously, one preset has no idempotency proptest, one is deliberately omitted). There is also a verified partial bypass of the new anti-smuggling control, and the documented preset-allocation debt (prior H-P4) regressed.

Nothing here is an unconditional Critical, but **D-1 is the most important finding of either review** and should gate any claim that idempotency is "done."

---

## Findings (all independently verified against source)

### D-1 · `security_clean` / `normalize_user_input` are NOT raw-idempotent · **High** *(Correctness analyst rated Critical)* `[VERIFIED — table entries confirmed]`
- **Location:** `src/presets.rs` `security_clean` (10-stage pipeline), `normalize_user_input`
- **Trigger:** `security_clean("\u{0441}\u{0327}")` (Cyrillic `с` + combining cedilla) → **pass 1 = `"ç"`**, **pass 2 = `"c"`**.
- **Mechanism (verified):** the single confusables pass folds `с`(U+0441)→`c` while the combining cedilla floats free; the **terminal NFC then composes `c`+U+0327 → `ç`(U+00E7)**, which is *itself* a confusables key. The next call folds `ç`→`c`. I confirmed all three preconditions directly in the source: `confusables_to_latin.tsv` contains `0441 → c` **and** `00E7 → c`, and Unicode NFC composes `c`+U+0327 to U+00E7. The trigger family is the ~8 precomposed letters that are simultaneously confusables keys and decompose to base+dropped-diacritic: `Ç ç Ǿ ί ϊ ό ї إ` (verified `00C7→C`, `01FE→O`, `03AF→i`, `03CA→i`, `03CC→o`, `0457→i`, `0625→l` all present).
- **Why the #416 NFC-sandwich doesn't cover it:** the sandwich feeds the fold a *consistent composed form*, but the failing case is one where the fold **itself un-masks** a cross-script base into Latin `c`; the *post-fold* NFC then synthesizes a precomposed confusable the fold already passed. This is exactly the "moves the asymmetry one pass downstream" risk flagged when this fix was scoped last session — the robust fix is to **fold on NFD** (so composed and decomposed fold identically) or **iterate fold+NFC to convergence** (bounded — the trigger set is finite and each pass strictly shrinks).
- **Why the proptest misses it (false assurance):** `security_clean_idempotent` asserts *raw* equality (good) but its generator's combining-mark set is only U+0301/U+0300/U+0489 — none compose a Latin confusable base into a precomposed table key. The property passes vacuously. **Add U+0327 (and one representative of each trigger mark) plus a confusable base to the generator.**
- **Why it matters:** violates the idempotency invariant that THREAT_MODEL.md and the docstrings assert as a security property — a canonicalize-on-write vs canonicalize-on-compare denylist can derive two different keys for the same input. Pre-existing; #416 narrowed but did not close it.
- **Note on the analyst disagreement:** the Security analyst concluded idempotency was "closed" — but it only reasoned about zalgo marks, never the confusable-base + combining-mark path. Verification (the table-entry check above) confirms Correctness was right.
- **Confidence:** High. Reproduce: `security_clean("\u{0441}\u{0327}")`.

### D-2 · `display_clean` is NOT idempotent — VS carve-out tests the base before later strips remove it · **High** `[VERIFIED]`
- **Location:** `src/presets.rs` `display_clean`; `src/invisibles.rs:101-103` (`is_presentation_base`), `:175-182` (VS keep)
- **Trigger:** `display_clean("\u{2800}\u{FE0F}x")` → **pass 1 = `"\u{FE0F}x"`**, **pass 2 = `"x"`**. Also U+115F/1160/3164/FFA0 (Hangul fillers), NUL, ZWSP in front of the selector.
- **Mechanism (verified):** `display_clean` runs `strip_invisible_classes` (step 1b) **before** the whitespace/control strips. `is_presentation_base(ch)` is literally `!ch.is_whitespace()`, and U+2800 is category `So` (not whitespace), so the VS16 after it is **kept**. Then `collapse_whitespace` (step 2) folds U+2800 because it's in the `is_blank_render` set (`whitespace.rs:93`) and trims it as leading space — leaving the VS16 leading, which the *next* call strips. The function's own comment claims "No NFC pass … idempotent," reasoning about base+mark but missing this carve-out/strip ordering.
- **Why it matters:** another broken `f(f(x))==f(x)`, and **`display_clean` has no idempotency proptest at all** — wholly uncaught. Lower than D-1 only because it's the rendering preset, not the comparison path.
- **Fix direction:** decide the presentation-VS fate *after* the control/zero-width/blank-render strips (run the invisibles VS handling last), or make `is_presentation_base` reject the blank-render/control set. Add a `display_clean` idempotency proptest.
- **Confidence:** High. Reproduce: `display_clean("\u{2800}\u{FE0F}x")`.

### D-3 · Preset per-stage allocation (prior H-P4) regressed — now 7–10 `String`s/call · **High** `[VERIFIED]`
- **Location:** `src/presets.rs` (all presets); contrast `src/pipeline.rs` ping-pong
- **What:** presets still chain the *returning* forms instead of the `*_into` two-buffer ping-pong the engine uses, and the delta made it worse: the #433 whitespace split turned one fused call into **three** allocating calls, and #413 added the `strip_invisible_classes` stage. Verified stage counts: `security_clean` 6→**10**, `catalog_key` 6→**9**, `search_key` 6→**8**, `sort_key` 6→**7**, `normalize_user_input`→9, `strip_obfuscation`→10. I confirmed `security_clean`'s 10 stages by direct read.
- **Sub-finding (High):** `strip_control_chars` (`whitespace.rs`) and `strip_bidi` (`presets.rs`) start from `String::new()` with no `reserve` and no ASCII fast path — unlike their siblings (`strip_zero_width_chars`, `strip_zalgo`, `strip_invisible_classes`, `collapse_whitespace` all have one). `strip_control_chars` is now a mandatory stage in all six key paths.
- **Why it matters:** `search_key`/`sort_key`/`catalog_key` are the documented per-call short-string hot paths; they now do 7–9 heap allocs + full copies where the engine does ~2. On uncapped adversarial input, `security_clean` is a 10× linear constant (not super-linear — every stage is O(n) — so DoS-adjacent, not algorithmic).
- **Fix direction:** route presets through the existing `*_into` ping-pong (add an `_into` form to `strip_invisible_classes`); add `reserve(text.len())` to `strip_control_chars_into` and an `is_ascii()` fast path to `strip_bidi_into` (none of its targets are ASCII). One move reverses the regression and absorbs the split cost.
- **Confidence:** High.

### D-4 · Stale Python docstrings describe pre-#413 pipelines (doc-vs-code drift) · **High** `[VERIFIED]`
- **Location:** `python/disarm/_text.py:258` (`Text.security_clean`), `:280` (`Text.display_clean`), `python/disarm/_presets.py:144` (`display_clean`)
- **What:** `Text.security_clean` docstring still reads "NFKC → confusables → strip bidi/format → collapse_whitespace" — omitting strip-invisibles (#413), the anti-zalgo cap (#429), the NFC-sandwich (#416), and the step reordering (it now does ~10 steps). `Text.display_clean` reads "Collapse whitespace, strip control and zero-width characters" — omits strip-bidi (which it does) and strip-invisibles. `_presets.display_clean`'s "Pipeline:" line omits the #413 strip — and because `docs/api/pipelines.md` embeds that docstring *and* prints a correct hand-written step list below it, the rendered page **contradicts itself**.
- **Why it matters:** the exact doc-vs-code drift class the run targets, on security-relevant presets; the sibling `collapse_whitespace` docstring *was* updated in this same delta, so the omission is conspicuous.
- **Fix direction:** regenerate the three docstrings from the current pipeline.
- **Confidence:** High.

### D-5 · `sort_key` still non-idempotent (transliterate-before-fold) — proptest deliberately omitted · **Medium** `[VERIFIED]`
- **Location:** `src/presets.rs` `sort_key`; proptest omission comment at `src/presets.rs:1063`
- **Trigger:** `sort_key("\u{1CB1}")` (Georgian Mtavruli HE) → pass 1 = `"\u{10F1}"`(ჱ) → pass 2 = `"he"`.
- **Mechanism (verified):** `sort_key` transliterates **before** `fold_case`. U+1CB1 is absent from `translit_default.tsv` (preserved), `fold_case` lowercases it to U+10F1, which **is** in the table (`10F1 → he`, confirmed). So the second pass transliterates it. General case-before-transliterate ordering bug.
- **Status:** this is the bug deferred last session (now tracked as **#419**). The delta **deliberately omits** the global `sort_key_idempotent` proptest (comment confirmed at `presets.rs:1063`) rather than fixing it — a known-broken invariant hidden from CI, against the project's broken-windows norm.
- **Fix direction:** fold before transliterate (or iterate to convergence); then re-enable the omitted proptest. (This matches the Option-1 plan agreed last session — the fix just hasn't landed yet.)
- **Confidence:** High.

### D-6 · Emoji-flag carve-out is a partial ASCII-smuggling bypass · **Medium** `[VERIFIED]`
- **Location:** `src/invisibles.rs` `consume_flag_tail` (reached by `strip_tags` / `strip_invisible_classes`)
- **What:** `consume_flag_tail` preserves any run of tag letters (U+E0061–E007A) terminated by CANCEL TAG (U+E007F) following `U+1F3F4`, **without checking it spells a real ISO-3166 subdivision** (verified: the function just accumulates tag letters and accepts on the terminator). Tag letters decode to ASCII lowercase `a–z` — the standard smuggling alphabet. So a lowercase payload wrapped as `U+1F3F4` + payload-as-tag-chars + `U+E007F` survives `strip_tags`, `security_clean`, and `normalize_user_input`.
- **Why it matters:** the feature's docs/CHANGELOG promise to neutralize the "ASCII smuggling into LLMs" Tags channel; THREAT_MODEL.md doesn't carve out the flag exception. Bounded to lowercase (uppercase/digits/space break the tail), so it's a **partial** channel, not a full one — hence Medium.
- **Fix direction:** validate the tail against the known subdivision allowlist (the emoji engine already matches real flags elsewhere), or cap to the ≤6-letter region-subtag shape; otherwise document the carve-out as an explicit limitation.
- **Confidence:** High.

### Medium / Low (carried-over and minor)
- **D-7 (Medium, perf):** the 3-way whitespace split triples passes over the tail in every key path (`strip_control` + `strip_zero_width` + `collapse_whitespace` where there was one fused call). Folded into the D-3 ping-pong fix. *(Verified mechanism; impact modest — tail buffers are usually short.)*
- **D-8 (Low, correctness):** the three whitespace functions are not order-commutative; presets always call them in the safe order (collapse last), but the public `Pipeline` builder lets a caller sequence `COLLAPSE_WS` before a strip and get untrimmed output. Document the "collapse is the terminal whitespace step" contract.
- **Prior polish findings still open (unchanged in delta):** **H-D1** (`api::slugify` doc claims Python validates `lang` — `api/text.rs`), **H-D2** (Python `slugify` `Raises:` lists unraised unknown-`lang` — `_api.py:576`), **H-D3** (Node `docs/node/api.md` still says `getPipeline` "not yet surfaced" though exported — now asymmetric since Ruby *did* add its `get_pipeline` section), **M-D3** (output-encoder/`strip_log_injection` family Python-only, undocumented-as-absent in Ruby/Node). **M-D1/M-D2** (`error.rs` stale `#[allow(dead_code)]` / missing `#[must_use]`) are out of delta scope — `error.rs` unchanged.

---

## Resolved / improved since the last review
- **Path-separator neutralization removed (#431)** — correct and **honestly documented**: THREAT_MODEL.md states disarm is an input-normalizer and path-traversal defence belongs at the sink; no preset name/docstring still implies path sanitization; a regression test (`test_presets_do_not_mangle_path_separators`) pins it. Resolves the prior concern about presets implying a guarantee they didn't deliver.
- **New `invisibles.rs` is clean** — every range predicate (`is_tag`, `is_variation_selector`, `is_noncharacter` incl. the `(cp & 0xFFFF) >= 0xFFFE` plane math, `is_pua`, `is_tag_letter`) is exactly correct (exhaustively checked); ASCII fast path + `with_capacity` present; `#[must_use]` on the Layer-2 surface; new ops surfaced and tested across all four languages.
- **Greek-iota remap (#438)** introduces no fold cycle (verified: Latin `03B9→i` terminal; Cyrillic `03B9→0456` non-key).
- **Whitespace line-control fold (#433)** closes an invisible-join vector (`a\rb`→`a b`); fold and zero-width sets are disjoint.
- **`security_clean` idempotency (#416)** — *partially* resolved: the NFC-sandwich closes the confusables-emits-decomposed-skeleton case, but D-1 remains.

## Recommended priority order
1. **D-1** — the headline. Fix with NFD-fold or iterate-to-convergence, and extend the proptest generator to the cedilla/trigger-mark class so the property stops passing vacuously. Until then, the idempotency guarantee should not be advertised as complete.
2. **D-2** — reorder the presentation-VS decision after the strips; add a `display_clean` idempotency proptest.
3. **D-5** — land the `sort_key` fold-before-transliterate fix (the agreed Option-1 follow-up) and re-enable the omitted proptest.
4. **D-6** — validate the emoji-flag tail against the real subdivision allowlist (or document the carve-out).
5. **D-3 / D-7** — route presets through the `*_into` ping-pong; add `reserve`/ASCII fast paths to `strip_control_chars`/`strip_bidi`.
6. **D-4** and the carried-over **H-D1/H-D2/H-D3/M-D3** docs items — cheap, user-trust-facing.

## Test-suite gap (cross-cutting)
The three idempotency defects (D-1, D-2, D-5) are all in the property the delta is *about*, yet: `security_clean_idempotent` passes **vacuously** (generator can't reach the trigger marks), `display_clean` has **no** idempotency proptest, and `sort_key_idempotent` is **deliberately omitted**. The proptests currently certify a guarantee that three short strings break (`"\u{0441}\u{0327}"`, `"\u{2800}\u{FE0F}x"`, `"\u{1CB1}"`). Strengthening the generators is as important as the fixes.

---

*Generated by the HAI-SDLC hardening sequence — delta re-run, analysis only. No source files were modified. Findings cite `path:line` / table entries at `f24b8e3`. Every High/Critical was independently verified against source (confusables TSV entries, Unicode normalization behavior, and pipeline step order) during this run.*
