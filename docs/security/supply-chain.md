# Supply-chain security of the build and release pipeline

This page is about how disarm itself is built and published: which jobs can publish
to which registry, what code runs next to those credentials, and what the repository
does to keep the two apart. What a consumer can verify about a published artifact
(PEP 740 attestations, the SBOM, the dependency policy gate) is in
[SECURITY.md](../SECURITY.md#supply-chain-assurance).

It was written after the September 2026 compromise of MemTensor's npm and PyPI
packages, and the last section lists what the repository owner has to configure on the
registries and in GitHub, because a workflow file cannot do it.

## The attack this responds to

On 23 September 2026 malicious versions of two MemTensor packages were published:
`@memtensor/memos-cloud-openclaw-plugin` on npm (0.1.21, 0.1.23 and 0.1.25) and
`MemoryOS` on PyPI (2.0.34). As reported by SafeDep, StepSecurity, Aikido and The
Hacker News:

- **Infection vector.** The attacker obtained the npm and PyPI publish tokens from
  MemTensor's own GitHub Actions release pipelines, by pushing commits that made the
  release job hand its token to the attacker before the job published anything. The
  maintainers' issue report notes that the npm payload existed only in the published
  artifacts, with no matching tag or commit on the default branch.
- **Payload.** A Go implant, `sckit` (also called the "supplychain.local worm"),
  bundled as per-platform binaries and started in the background whenever the package
  loads. The npm variant adds `lib/sckit.js`, which spawns the binary detached, passes
  it the process environment, and explicitly reads `NPM_TOKEN` and `NODE_AUTH_TOKEN`.
- **What it steals.** Credentials from developer machines and from CI jobs, collected
  from the home directory: cloud, source-hosting, package-registry and developer-tool
  secrets. They go to servers under `skyleen[.]fr`.
- **Propagation.** It carries templates to install itself into npm packages, Python
  packages and GitHub Actions workflows, and copies itself into whatever repositories
  and packages the stolen credentials reach.

Sources: [SafeDep](https://safedep.io/memtensor-sckit-worm-npm-pypi/),
[SafeDep on the sckit framework](https://safedep.io/sckit-go-implant-framework/),
[StepSecurity](https://www.stepsecurity.io/blog/sckit-supply-chain-worm-hits-memtensor-npm-pypi-scopes),
[The Hacker News](https://thehackernews.com/2026/09/compromised-memtensor-packages-deliver.html),
and the maintainers'
[issue report](https://github.com/MemTensor/MemOS-Cloud-OpenClaw-Plugin/issues/173).

The general lesson is older than this worm: **a job that holds a publish credential
must not run code it did not write.** That code can be a pushed workflow change, a
dependency's install hook or build script, a poisoned cache, a moved action tag, or a
string from an event payload spliced into a shell script.

## Where the credentials are

| Registry | Workflow and job | Credential | Environment |
|---|---|---|---|
| PyPI (`disarm`) | `publish.yml` / `publish` | OIDC trusted publishing, `id-token: write` | `pypi` |
| PyPI (`translit-rs` shim) | `publish-translit-rs.yml` / `publish` | OIDC trusted publishing | `pypi` |
| crates.io | `publish.yml` / `publish-crate` | OIDC trusted publishing when configured, else the `CRATES_IO_API_TOKEN_001` secret | `crates-io` |
| npm | `publish-node.yml` / `publish` | OIDC trusted publishing, `id-token: write` | `npm` |
| RubyGems | `publish-ruby.yml` / `publish` | OIDC trusted publishing, `id-token: write` | `rubygems` |
| Maven Central | `publish-java.yml` / `publish` | `MAVEN_GPG_PRIVATE_KEY`, `MAVEN_GPG_PASSPHRASE`, `CENTRAL_PORTAL_USERNAME`, `CENTRAL_PORTAL_PASSWORD` | `maven-central` |
| GitHub Release assets | `publish.yml` / `sbom-attach` | `GITHUB_TOKEN`, `contents: write` | none |
| Docs site | `docs.yml` / `build-deploy` | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | none |

Two more jobs can change the repository without publishing anything:
`perf-gate.yml`'s `perf-record` pushes to the `perf-results` branch, and
`dependabot-auto-merge.yml` arms auto-merge on Dependabot's pull requests. The rest
read the repository and write, at most, metadata beside it: code-scanning results
(CodeQL), an issue (the RustSec audit and the nightly Hypothesis run), a cache deletion
(`cache-cleanup.yml`), or a preview comment (`docs.yml`).

## What the workflows enforce

**Publish jobs build nothing.** The PyPI, RubyGems, npm and translit-rs publish jobs
download artifacts that other, credential-free jobs built. `publish-crate` runs
`cargo publish --no-verify` after a separate `verify-crate` job has built the package,
so no dependency's build script or proc-macro runs beside the token. The npm publish
job still installs the Node toolchain to emit the loader and types, with
`npm ci --ignore-scripts`, so no dependency's install hook runs while an OIDC token can
be requested.

**No caches in the credential and artifact jobs that can do without.** A restored
`target/` can carry compiled build scripts and a restored package cache can carry
anything its writer put there. The crates.io, SBOM and npm release jobs restore no
cache. The Ruby gem builds still do; see the last section.

**Every action is pinned to a full commit SHA**, with the version in a comment, and
Dependabot's `github-actions` ecosystem proposes the updates. The comment is two spaces,
`# `, and the most specific tag that points at that SHA (`# v7.0.1`, never `# v7`), so
it names one commit rather than a ref that moves; a SHA no tag points at names the
branch it came from. One SHA carries one comment everywhere, the snippets in these docs
included. `tests/test_workflow_baselines.py` enforces all of it.

**Least-privilege tokens.** Every workflow defaults to `contents: read`, and a write
permission is granted to the one job that needs it. Where a job used to build or run
code and write in the same breath, it is now two jobs: the perf measurement and the
SBOM generation run read-only and hand their output to a separate job that only writes.
`docs.yml` is the remaining exception; see the last section.

**No persisted checkout token.** Every `actions/checkout` sets
`persist-credentials: false`, except `perf-record`, which pushes and runs nothing else.

**No template injection.** Event and ref data reach `run:` scripts through `env:`,
never by `${{ }}` expansion inside the script text.

**Validated binaries.** The Gradle wrapper jar is checked against Gradle's published
checksums before `./gradlew` runs. Downloaded tools (TLC, actionlint) are checked
against a pinned SHA-256, and the docs build, the perf comparators and the
workflow-lint tools install from hash-locked requirements files.

**A gate that keeps it that way.** The `workflow-lint` job in `ci.yml` runs actionlint
(with shellcheck over every `run:` script) and zizmor at medium severity and above, and
the required *All checks passed* check fails if either reports anything. Both tools are
pinned and zizmor runs offline, so the gate changes only when a workflow does. A
deliberate exception is an inline `# zizmor: ignore[<audit>]` comment with its reason.

## What the owner has to configure

None of this can be done from a workflow file. Items are ordered by how much they
reduce exposure.

### 1. Restrict the publishing Environments to release refs

This is the control that addresses the MemTensor vector directly. A repository secret
is available to a workflow run on any branch of this repository, and a Trusted
Publisher configured without an environment accepts a token from its workflow file on
any branch, including a branch someone pushes with a modified copy of that file. A
secret or publisher bound to an Environment with deployment rules is not.

In **Settings, Environments**, for each of `pypi`, `crates-io`, `npm`, `rubygems` and
`maven-central`:

- **Deployment branches and tags:** "Selected branches and tags", with a tag rule `v*`
  and a branch rule `main`. The release trigger runs on the tag; `main` keeps the
  documented `workflow_dispatch` recovery path in [RELEASING.md](../RELEASING.md)
  working.
- **Required reviewers:** optional. It adds one approval click per registry per
  release, and it is the strongest control for `crates-io` and `maven-central` while
  they still use long-lived secrets.

The `npm` environment is new with this change; GitHub creates it, without rules, on the
first run that references it.

Then protect the tags themselves: a **tag ruleset** targeting `v*` that restricts
creation, update and deletion to the maintainers, so a deployment rule on `v*` means
something.

### 2. Move the long-lived secrets into their Environments

Under **Settings, Secrets and variables, Actions**, recreate as **environment**
secrets and delete the repository-level copies:

- `CRATES_IO_API_TOKEN_001` into `crates-io` (until step 3 removes it);
- `MAVEN_GPG_PRIVATE_KEY`, `MAVEN_GPG_PASSPHRASE`, `CENTRAL_PORTAL_USERNAME` and
  `CENTRAL_PORTAL_PASSWORD` into `maven-central`.

A repository secret is readable by every workflow in the repository; an environment
secret only by jobs that name the environment and pass its deployment rules. The jobs
already name them, so no workflow change is needed. Maven Central offers no trusted
publishing, so the Maven secrets stay, and this is their main protection.

`CLOUDFLARE_API_TOKEN` is the one secret that has to stay at repository level while
`docs.yml` deploys pull-request previews, because preview deploys run on pull-request
branches. Scope the token in Cloudflare to the `disarm-docs` Pages project only.

### 3. Configure crates.io trusted publishing, then delete the token

On crates.io, crate `disarm`, **Settings, Trusted Publishing, Add**:

| Field | Value |
|---|---|
| Publisher | GitHub |
| Repository owner | `raeq` |
| Repository name | `disarm` |
| Workflow filename | `publish.yml` |
| Environment | `crates-io` |

`publish-crate` already tries the OIDC exchange first
(`rust-lang/crates-io-auth-action`) and falls back to the secret only when the exchange
fails. After the next release has published through trusted publishing (its log shows
the exchange step succeeding), delete `CRATES_IO_API_TOKEN_001` from GitHub and revoke
the token on crates.io under **Account Settings, API Tokens**. From then on a failed
exchange fails the publish instead of falling back. If crates.io offers a setting to
require trusted publishing for the crate, enable it.

### 4. Check the Trusted Publishers that already exist

| Registry and project | Owner | Repository | Workflow | Environment |
|---|---|---|---|---|
| PyPI `disarm` | `raeq` | `disarm` | `publish.yml` | `pypi` |
| PyPI `translit-rs` | `raeq` | `disarm` | `publish-translit-rs.yml` | `pypi` |
| npm `disarm` | `raeq` | `disarm` | `publish-node.yml` | `npm` |
| RubyGems `disarm` | `raeq` | `disarm` | `publish-ruby.yml` | `rubygems` |

A publisher with an empty environment accepts a token from any job in that workflow
file, so filling it in is what ties the registry to the Environment rules in step 1.
The npm publisher is the one to check first: until now its job had no environment, so
the field is probably empty. If it names a different environment, set it to `npm`,
because the job now runs in `npm` and a mismatch fails the publish.

Then remove the token paths the publishers replaced: on npm, under the package's
**Settings, Publishing access**, choose "Require two-factor authentication and
disallow tokens"; on PyPI and RubyGems, revoke any API token with upload or push scope
for these projects.

### 5. Repository settings

- **Settings, Actions, General:**
  - Workflow permissions: "Read repository contents and packages permissions". Every
    workflow here sets its own permissions, so this changes nothing today and protects
    a future workflow that forgets to.
  - Leave "Allow GitHub Actions to create and approve pull requests" off.
    `dependabot-auto-merge.yml` arms auto-merge and approves nothing.
  - Fork pull request workflows: "Require approval for all external contributors".
  - Actions permissions: allow only actions pinned to a full-length commit SHA, if the
    option is offered. The `workflow-lint` job enforces the same rule on pull requests;
    the setting enforces it on every run.
- **Settings, Code security:** secret scanning with push protection, Dependabot alerts
  and Dependabot security updates.

## Considered and not done

- **Egress filtering (`step-security/harden-runner`).** Blocking outbound traffic from
  the publish jobs would stop an exfiltration like sckit's outright. It was not added:
  audit mode blocks nothing, and block mode needs an allow-list learned from a few
  audited releases, which a change made without running a release cannot supply. It
  would also put a third-party action, running with `sudo`, first in exactly the jobs
  this page is protecting. It is a reasonable next step once someone can watch two
  releases in audit mode and build the allow-list from what they see.
- **Committing `Cargo.lock` and `Gemfile.lock`.** Without a lockfile every CI run and
  every release resolves the newest matching version of each dependency at that
  moment, so a dependency version published an hour before a release is built into it,
  and Dependabot's cooldown does not apply. Committing the lockfiles, and building with
  `--locked`, fixes that. It is a policy change for a library crate, with effects on
  the MSRV hold in `.github/dependabot.yml`, the audit jobs and the SBOM, so it is
  proposed here rather than made.
- **Signing the Maven artifacts outside Gradle.** The Maven publish job runs Gradle,
  and its plugins, with the signing key in the environment. Moving signing into a
  separate job with plain `gpg` would take the key out of the build. It changes the
  publishing flow, so it is left for a change that can be tested against the Central
  Portal.
- **Hash-locking the remaining `pip install`s** (maturin, the test extras). They run
  in jobs with no secrets and a read-only token, where the build and docs requirements
  files already set the pattern to follow.
- **`distributionSha256Sum` for the Gradle wrapper**, so the downloaded distribution is
  checked as well as the wrapper jar. Regenerate the wrapper with
  `./gradlew wrapper --gradle-version <v> --gradle-distribution-sha256-sum <sha>`, using
  the checksum Gradle publishes for that distribution.
- **Splitting `docs.yml`.** One job builds the site from the pull request (mkdocs runs
  the repository's own hooks) and then deploys it with the Cloudflare token and a
  `pull-requests: write` token. Fork and Dependabot pull requests get neither, and the
  docs requirements are hash-locked, so the exposure is a same-repository branch or a
  compromised hook. A build job that uploads `site/` and a deploy job that only
  downloads it would close it. `cloudflare/wrangler-action` also installs `wrangler`
  from npm at run time; its `wranglerVersion` input can pin it.
- **Dropping the bundler and cargo caches from the Ruby gem builds**
  (`publish-ruby.yml`, `cross-gems` and `source-gem`). These jobs hold no credential,
  but their output ships. `bundler-cache: true` is also what runs `bundle install`
  there, so removing it needs an explicit install step and a release to test it on.
- **A checksum for the Lean toolchain tarball** in `formal.yml`, as the TLC download
  already has. It runs in a job with no secrets.
- **Build-provenance attestations for the gem, the JAR and the crate**
  (`actions/attest-build-provenance`). PyPI and npm already carry provenance; the other
  three registries do not verify it, so the benefit is a GitHub-side record only.
