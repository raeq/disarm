#!/usr/bin/env bash
# Generate docs/index.md from README.md + docs/_index_nav.md
#
# README.md is the single source of truth. This script:
# 1. Copies README.md content
# 2. Rewrites relative links: (docs/foo) → (foo)
# 3. Removes the Documentation section (replaced by the nav appendix)
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

{
    echo "<!-- AUTO-GENERATED from README.md + docs/_index_nav.md -->"
    echo "<!-- Do not edit directly. Run: bash scripts/generate_docs_index.sh -->"
    echo ""

    # Transform README.md:
    # - Strip (docs/ prefix from markdown links → (
    # - Strip docs/ prefix from link text like [docs/foo.md]
    # - Remove the "## Documentation" section (lines between ## Documentation and next ##)
    # - Remove the "## Links" section (already in nav, and URLs are absolute)
    # - Remove the "## License" line (already in nav)
    sed \
        -e 's|(docs/|(|g' \
        -e 's|\[docs/|\[|g' \
        "$README" \
    | awk '
        /^## Documentation$/ { skip=1; next }
        /^## Architecture$/  { skip=1; next }
        /^## Links$/         { skip=1; next }
        /^## License$/       { skip=1; next }
        /^## / && skip       { skip=0 }
        !skip                { print }
    '

    # Append the docs site navigation
    cat "$NAV"

} > "$OUTPUT"

echo "Generated $OUTPUT from README.md + docs/_index_nav.md"
