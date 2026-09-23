- **Every stated platform floor is one upstream still supports and CI tests, and a gate
  holds each one to its source.** The README said "Rust 1.81+" in two places, and
  `docs/rust/getting-started.md` gave the MSRV as 1.81, long after #718 moved
  `rust-version` to 1.88; CONTRIBUTING asked for 1.70. They now say 1.88, and so do the
  Node, Ruby, C-ABI and JNI binding crates, which declared 1.81 and 1.85 while
  depending on a core that cannot build below 1.88. `tests/test_msrv_claims.py` now
  reads the README, `docs/`, the binding READMEs, CONTRIBUTING and the crate's rustdoc,
  and fails on any Rust floor that differs from `Cargo.toml`.
