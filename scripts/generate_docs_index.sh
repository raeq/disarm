#!/usr/bin/env bash
# Generate docs/index.md from README.md + docs/_index_nav.md
#
# README.md is the single source of truth. This script:
# 1. Copies README.md content
# 2. Rewrites relative links: (docs/foo) → (foo)
# 3. Removes the Architecture, Links, and License sections (already in the nav appendix)
# 4. Appends the docs site navigation from docs/_index_nav.md
#
# Run from the project root:
#   bash scripts/generate_docs_index.sh           # write docs/index.md
#   bash scripts/generate_docs_index.sh --check   # fail if it is out of date
#
# --check is the gate (#656). Nothing used to regenerate or verify this file, so
# `docs/index.md` drifted from the README it declares as its source in both
# directions at once: two Features bullets existed only in the generated file and
# would have been destroyed by the next run, while a Node.js nav entry, a
# whole-script-spoof example and a coverage-residue note existed only in the
# sources and never reached the site. The "Do not edit directly" banner was the
# only thing holding the line, and a banner is not a check.
#
# It is also what makes README.md's Python blocks *executed*: every one of them
# lands in docs/index.md, which is first on `EXECUTED_RECIPES` in docs/conftest.py
# and runs under Sybil on every CI run. In sync, the README is covered; out of
# sync, it is not — so this check is the coverage.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
README="$ROOT/README.md"
NAV="$ROOT/docs/_index_nav.md"
OUTPUT="$ROOT/docs/index.md"

# Reject anything that is not exactly `--check` or nothing at all. A typo must
# not fall through to the write path: this script overwrites docs/index.md, and
# `--chekc` silently regenerating the file it was asked to verify is the one
# failure mode that would defeat the point of having a --check at all.
CHECK=0
case $# in
    0) ;;
    1)
        if [[ "$1" == "--check" ]]; then
            CHECK=1
        else
            echo "usage: $0 [--check]" >&2
            exit 2
        fi
        ;;
    *)
        echo "usage: $0 [--check]  (takes at most one argument, got $#: $*)" >&2
        exit 2
        ;;
esac

if [[ ! -f "$README" ]]; then
    echo "ERROR: README.md not found at $README" >&2
    exit 1
fi
if [[ ! -f "$NAV" ]]; then
    echo "ERROR: docs/_index_nav.md not found at $NAV" >&2
    exit 1
fi

# Write to a temp file and move into place atomically, so a mid-pipeline failure
# (set -euo pipefail) never leaves docs/index.md empty or partially written.
TMPOUT="$(mktemp "$ROOT/docs/.index.md.XXXXXX")"
trap 'rm -f "$TMPOUT"' EXIT
# mktemp creates the file 0600; `mv` would carry that through, leaving the
# generated docs index non-world-readable. Restore the normal 0644 a plain
# `> "$OUTPUT"` redirect (umask 022) would have produced.
chmod 644 "$TMPOUT"

{
    echo "<!-- AUTO-GENERATED from README.md + docs/_index_nav.md -->"
    echo "<!-- Do not edit directly. Run: bash scripts/generate_docs_index.sh -->"
    echo ""

    # Transform README.md:
    # - Strip (docs/ prefix from markdown links → (
    # - Strip docs/ prefix from link text like [docs/foo.md]
    # - Remove the "## Architecture" section (already in nav appendix)
    # - Remove the "## Links" section (already in nav, and URLs are absolute)
    # - Remove the "## License" section, heading and body (already in nav)
    # Each rule skips from its heading until the next "## " heading.
    sed \
        -e 's|(docs/|(|g' \
        -e 's|\[docs/|\[|g' \
        "$README" \
    | awk '
        /^## Architecture$/  { skip=1; next }
        /^## Links$/         { skip=1; next }
        /^## License$/       { skip=1; next }
        /^## / && skip       { skip=0 }
        !skip                { print }
    '

    # Append the docs site navigation
    cat "$NAV"

} > "$TMPOUT"

if [[ "$CHECK" -eq 1 ]]; then
    if diff -u "$OUTPUT" "$TMPOUT" > /dev/null 2>&1; then
        echo "docs/index.md is up to date with README.md + docs/_index_nav.md"
        exit 0
    fi
    {
        echo "ERROR: docs/index.md is out of date."
        echo
        echo "It is generated from README.md + docs/_index_nav.md, and one of the three"
        echo "has moved without the others following. Regenerate and commit the result:"
        echo
        echo "    bash scripts/generate_docs_index.sh"
        echo
        echo "Edit README.md or docs/_index_nav.md, never docs/index.md — a change made"
        echo "there is destroyed by the next run, and one made in the sources never"
        echo "reaches the site. Both have happened."
        echo
        echo "--- committed docs/index.md          +++ regenerated"
    } >&2
    diff -u "$OUTPUT" "$TMPOUT" >&2 || true
    exit 1
fi

mv "$TMPOUT" "$OUTPUT"

echo "Generated $OUTPUT from README.md + docs/_index_nav.md"
