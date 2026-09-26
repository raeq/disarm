#!/usr/bin/env bash
# Pin a binding's Cargo.lock to the core version this ref releases.
#
#   bash scripts/pin_published_core.sh <cargo-workspace-dir>
#
# The binding glue asks for the core as `disarm = "0.MINOR"`, so a build resolves
# whatever 0.MINOR.* is newest on crates.io when it runs. On a patch release that is
# the PREVIOUS patch until publish.yml has pushed the new core, several minutes in:
# 0.17.1's npm and Maven artifacts were built against core 0.17.0 that way, and the
# fix the release existed for was not in them. The wait-for-core poll now waits for
# this exact version; this makes every build resolve it, and fails the build rather
# than ship a binding around any other core.
#
# The version is the root Cargo.toml's, which is the core a release tag publishes.
# Run it only on the publish path (release / workflow_dispatch). The validation
# builds redirect the core to the in-repo path instead, and must not be pinned to a
# published version.
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <cargo-workspace-dir>" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="$1"

want="$(sed -n '/^\[package\]/,/^\[/s/^version = "\([^"]*\)".*/\1/p' "$repo_root/Cargo.toml" | head -n1)"
if [ -z "$want" ]; then
  echo "::error::could not read [package] version from $repo_root/Cargo.toml" >&2
  exit 1
fi

# The registry `disarm` in the lockfile. The bindings' own crates are also named
# `disarm` (version 0.0.0), but they have no `source` line, so they never match.
resolved() {
  awk '
    /^\[\[package\]\]/ { name = ""; version = "" }
    /^name = /         { name = $3 }
    /^version = /      { version = $3 }
    /^source = "registry\+/ {
      if (name == "\"disarm\"") { gsub(/"/, "", version); print version }
    }
  ' "$workspace/Cargo.lock"
}

(cd "$workspace" && cargo generate-lockfile --quiet)
got="$(resolved)"
if [ -n "$got" ] && [ "$got" != "$want" ]; then
  # A version that is not on the index fails here; the check below says why.
  (cd "$workspace" && cargo update --quiet -p "disarm@$got" --precise "$want") || true
  got="$(resolved)"
fi

if [ "$got" != "$want" ]; then
  echo "::error title=Wrong core::$workspace resolves core disarm ${got:-<none>}, but this ref releases $want. A binding built now would not contain the core it is released with." >&2
  exit 1
fi
echo "Pinned: $workspace/Cargo.lock resolves core disarm $want."
