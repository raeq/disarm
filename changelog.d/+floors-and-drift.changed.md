- **Every stated platform floor is one upstream still supports and CI tests, and a gate
  holds each one to its source.** The README said "Rust 1.81+" in two places, and
  `docs/rust/getting-started.md` gave the MSRV as 1.81, long after #718 moved
  `rust-version` to 1.88; CONTRIBUTING asked for 1.70. They now say 1.88, and so do the
  Node, Ruby, C-ABI and JNI binding crates, which declared 1.81 and 1.85 while
  depending on a core that cannot build below 1.88. `tests/test_msrv_claims.py` now
  reads the README, `docs/`, the binding READMEs, CONTRIBUTING and the crate's rustdoc,
  and fails on any Rust floor that differs from `Cargo.toml`.

  **The Node.js floor is 22, up from 14, and the Ruby floor is 3.3, up from 3.1.**
  `package.json` declared Node >= 14, which reached end of life in April 2023, and CI
  tested 20 and 22; Node 20 reached end of life on 2026-04-30 too. `engines` is now
  `>= 22`, CI tests 22, 24 and 26, and the release and dependency-audit jobs run on 22.
  The gem declared Ruby >= 3.1; 3.1 reached end of life on 2025-03-26 and 3.2 on
  2026-04-01. `required_ruby_version` is now >= 3.3, CI and the release workflow test
  3.3, 3.4 and 4.0, and platform gems are built for those three ABIs only, so a Ruby 3.1
  or 3.2 install resolves to an earlier release. Python stays at 3.10, which is
  supported until 2026-10-01, and CI now installs and exercises the built wheel and
  sdist on 3.10 rather than only on 3.12. Java stays at 21. `tests/test_toolchain_pins.py`
  fails when a binding's manifest, the lowest version CI installs and the READMEs and
  getting-started pages disagree, or when a floor is a version already known to be
  retired.
