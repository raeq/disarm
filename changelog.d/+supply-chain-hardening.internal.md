- **The release pipeline keeps third-party code away from publish credentials.** A
  review against the September 2026 sckit worm, which stole npm and PyPI tokens out of
  MemTensor's own release jobs, found the same exposure here in smaller form.
  `cargo publish` built the crate, running every dependency's build script, in the step
  holding the crates.io token; the npm publish job ran dependency install hooks while it
  could mint an OIDC publish credential; the translit-rs shim publisher built in its
  publish job; and the SBOM and perf-results jobs held `contents: write` while compiling
  third-party code. Each is now split so the job holding the credential builds nothing.
  `publish-crate` also tries crates.io trusted publishing first and falls back to the
  token until it is configured. Every action is pinned to a commit SHA, no checkout
  persists its token, event data reaches scripts through `env:`, the crates.io, SBOM
  and npm release jobs restore no cache, and the Gradle wrapper jar is validated
  before it runs. A new
  `workflow-lint` job (actionlint and zizmor, both pinned) is part of *All checks
  passed*. Dependabot now also watches the Java and C-ABI crates and the Gradle build.
  `docs/security/supply-chain.md` records the review and the registry and repository
  settings only the owner can change.
