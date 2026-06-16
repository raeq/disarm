# HANDOFF — #389 anomaly detector (`feat/has-anomalies`)

> **DELETE THIS FILE when you pick the work up** (`git rm HANDOFF.md`). It must not
> reach the PR. It is committed only so the handoff survives across machines.

Work paused mid-task (location switch / outage). Branch `feat/has-anomalies`,
rebased onto `main`, checkpoint commit `74bf9ee`. Goal: land #389 — the
`has_anomalies` / `inspect_anomalies` out-of-place-character detector — across the
**Rust core + Python + Ruby + Node bindings + docs**, then PR (folding in #389)
and shepherd to merge.

## ✅ Done (on the branch)

- Rebased onto current `main`.
- **Rust core tests** — `src/anomalies.rs`: 16/16 pass. Cover all six branches
  (invisible, bidi, zalgo, mixed_script, leet, segmentation) and the
  false-positive guards (emoji/Arabic ZWJ, bidi marks/embeddings, CJK/units,
  `win32`/`Power5`/ordinals/times, `6-foot-6`). Run: `cargo test --no-default-features anomalies`.
- **Python shim started** — `src/py/anomalies.rs`: `AnomalyReport`/`Finding`
  pyclasses + `_has_anomalies`/`_inspect_anomalies`. **NOT yet wired** (orphan
  file), so the build is still green.

## Core surface (already in `disarm::api`)

```rust
has_anomalies(text: &str, lexicon: &HashSet<String>) -> bool
inspect_anomalies(text: &str, lexicon: &HashSet<String>) -> AnomalyReport
// AnomalyReport { anomalous: bool, kinds: Vec<AnomalyKind>, findings: Vec<Finding>, reason: Option<String> }
// Finding { kind: AnomalyKind, token: String, start: usize, end: usize, detail: String }  + .reason() -> String
// AnomalyKind::as_str() -> "invisible"|"bidi"|"zalgo"|"mixed_script"|"leet"|"segmentation"
```

The **lexicon** is a caller-supplied set of common words (used only by the leet
and segmentation branches). Each binding accepts it as the ecosystem's idiom:
Python `set[str]`, Ruby `Array`/`Set`, Node `string[]`.

## ⏳ Remaining steps (in order)

### 1. Finish Python binding
- `src/py/mod.rs`: add `pub mod anomalies;`.
- `src/lib.rs` (the `#[pymodule]`): `m.add_function(wrap_pyfunction!(py::anomalies::_has_anomalies, m)?)?;`
  + `_inspect_anomalies`; `m.add_class::<py::anomalies::AnomalyReport>()?;` +
  `Finding`. (Mirror how `_is_suspicious_hostname` / `HostnameAnalysis` are registered.)
- `python/disarm/_api.py`: import `_has_anomalies`, `_inspect_anomalies`,
  `AnomalyReport`, `Finding`; add public `has_anomalies(text, lexicon)` /
  `inspect_anomalies(text, lexicon)` wrappers (mirror `is_suspicious_hostname` at
  `_api.py:1148`).
- `python/disarm/__init__.py`: re-export the 2 funcs + 2 classes and add to `__all__`.
- `.pyi` stubs (find with `grep -rl HostnameAnalysis python/disarm/*.pyi`).
- Verify: `maturin develop && pytest -m "not formal and not hypothesis"` + a new
  `tests/test_anomalies.py`.

### 2. Ruby binding
- `bindings/ruby/ext/disarm/src/lib.rs`: `_has_anomalies(text, lexicon: Vec<String>) -> bool`
  and `_inspect_anomalies` returning a tuple/array the Ruby layer shapes into a Hash
  (mirror `inspect_auto_lang`). Register in `init`.
- `bindings/ruby/lib/disarm.rb`: `has_anomalies?(text, lexicon)` and
  `inspect_anomalies(text, lexicon)` (→ `{ anomalous:, kinds:, findings: [{kind:,token:,start:,end:,detail:}], reason: }`).
- RSpec in `bindings/ruby/spec/disarm_spec.rb`.
- Verify with ruby@3.3: `PATH="/opt/homebrew/opt/ruby@3.3/bin:$PATH" BUNDLE_GEMFILE=$PWD/bindings/ruby/Gemfile`
  → `cd bindings/ruby && bundle exec rake compile && bundle exec rake spec`. Also the
  `[patch.crates-io] disarm = { path = "../.." }` local-core mirror (the #374 gate).

### 3. Node binding
- `bindings/node/src/lib.rs`: `#[napi] hasAnomalies(text, lexicon: Vec<String>) -> bool`;
  `inspectAnomalies` returning `#[napi(object)]` structs (`AnomalyReport`, `Finding`).
- `bindings/node/index.ts`: idiomatic wrappers + types.
- `bindings/node/__test__/`: vitest.
- Verify: `cd bindings/node && npm run build:debug && npm test` (+ local-core patch mirror).

### 4. Docs
- Concept/security page for the detector (it's a **defensive publication** — keep
  the prior-art framing). Add to the Python/Ruby/Node API pages with gated
  examples (`scripts/check_doc_ruby_examples.rb` / `check_doc_node_examples.mjs` /
  Sybil). `CHANGELOG.md` under `### Added`.

### 5. PR
- `git rm HANDOFF.md` first. Open PR with "Closes #389"; shepherd CI + Copilot →
  merge. Full Tier-1 gate before pushing (core change): `cargo test --no-default-features`,
  `cargo clippy --no-default-features -- -D warnings`, `cargo fmt --all -- --check`,
  `maturin develop && pytest`, ruff/mypy, + each binding's gate.

## Gotchas
- Generating literal invisible/combining chars (ZW/bidi/zalgo) in test & doc files
  is error-prone — build them programmatically (`\u{…}` in Rust; `String.fromCharCode(92)+'u200B'`
  in JS/Ruby scripts), as done in the existing tabs.
- `inspectAutoLang('Straße')` precedent: napi `Option::None` → an **absent** JS key
  (Ruby returns `nil`); document per-binding accurately.
- Branch was rebased → push with `--force-with-lease`.
