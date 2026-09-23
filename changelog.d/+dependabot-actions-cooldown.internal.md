- **Dependabot's configuration parses again (#PR).** The `github-actions` entry in
  `.github/dependabot.yml` set per-semver cooldowns, which Dependabot does not support
  for that ecosystem, and it now rejects the file for them. Actions keep the flat
  7-day soak window; every other ecosystem keeps its per-semver windows.
