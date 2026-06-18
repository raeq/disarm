# Fuzzing disarm's security transforms

Coverage-guided fuzzing of the defense pipelines with
[`cargo-fuzz`](https://github.com/rust-fuzz/cargo-fuzz) / libFuzzer. These run
**outside** the normal CI gate (they need a nightly toolchain and run
open-ended); the in-CI guarantees are the `proptest` invariants in
`src/presets.rs` and `src/confusables.rs`.

Each target asserts the THREAT_MODEL.md invariants — **no panic** on any input,
and **idempotence** (a stable fixed point) — across a coverage-guided corpus.

## Setup

```bash
rustup toolchain install nightly
cargo install cargo-fuzz
```

## Run

The core links PyO3 without the `extension-module` feature, so point at a Python:

```bash
PYO3_PYTHON=$(which python3) cargo +nightly fuzz run strip_obfuscation
```

Targets: `strip_obfuscation`, `canonicalize`, `canonicalize_strict`,
`normalize_confusables`.

Time-box a run (e.g. CI/nightly):

```bash
PYO3_PYTHON=$(which python3) cargo +nightly fuzz run canonicalize -- -max_total_time=300
```

Any crash/assertion is written to `fuzz/artifacts/`; minimize and add a
regression to the matching proptest in `src/`.
