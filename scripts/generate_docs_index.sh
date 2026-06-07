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
#   bash scripts/generate_docs_index.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
README="$ROOT/README.md"
NAV="$ROOT/docs/_index_nav.md"
OUTPUT="$ROOT/docs/index.md"

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

mv "$TMPOUT" "$OUTPUT"

echo "Generated $OUTPUT from README.md + docs/_index_nav.md"
