#!/usr/bin/env python3
"""Harvest Persian word romanizations from English Wiktionary.

Fetches all Persian lemmas from Wiktionary's API and extracts their
romanized forms from fa-IPA templates and tr= parameters.

Output: TSV file with (persian_word, romanization) pairs suitable for
building context dictionaries.

Usage:
    python scripts/harvest_wiktionary_persian.py -o data/corpora/wiktionary_persian.tsv
    python scripts/harvest_wiktionary_persian.py -o data/corpora/wiktionary_persian.tsv --limit 500

This is a reproducible data source: same Wiktionary state → same output.
Rate-limited to respect Wiktionary's API guidelines.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "disarm-dict-builder/0.5 (https://github.com/raeq/disarm)"
API = "https://en.wiktionary.org/w/api.php"


def api_get(params: dict) -> dict:
    """Make a Wiktionary API request with rate limiting."""
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def get_persian_lemmas(limit: int = 0) -> list[str]:
    """Fetch all Persian lemma titles from Wiktionary category."""
    titles: list[str] = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": "Category:Persian lemmas",
        "cmlimit": "500",
        "cmtype": "page",
        "format": "json",
    }

    while True:
        data = api_get(params)
        members = data["query"]["categorymembers"]
        for m in members:
            title = m["title"]
            # Skip appendix pages and punctuation
            if ":" in title or len(title) < 2:
                continue
            # Only keep titles that contain Persian script
            if any("\u0600" <= c <= "\u06ff" or "\ufb50" <= c <= "\ufdff" for c in title):
                titles.append(title)

        if limit and len(titles) >= limit:
            titles = titles[:limit]
            break

        if "continue" in data:
            params["cmcontinue"] = data["continue"]["cmcontinue"]
            time.sleep(0.1)  # Rate limit
        else:
            break

        if len(titles) % 1000 == 0:
            print(f"  Fetched {len(titles)} titles...", file=sys.stderr)

    return titles


def extract_romanization(title: str) -> str | None:
    """Fetch a Wiktionary entry and extract its Persian romanization."""
    try:
        data = api_get(
            {
                "action": "parse",
                "page": title,
                "prop": "wikitext",
                "format": "json",
            }
        )
        wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
    except Exception:
        return None

    if not wikitext:
        return None

    # Strategy 1: fa-IPA template (most reliable)
    # {{fa-IPA|kitāb}} or {{fa-IPA|sa`lām}}
    ipa_match = re.search(r"\{\{fa-IPA\|([^|}]+)", wikitext)
    if ipa_match:
        rom = ipa_match.group(1).strip()
        # Clean up IPA notation to simple romanization
        rom = rom.replace("`", "").replace("'", "").replace("ˈ", "")
        # Remove macrons and convert to plain ASCII vowels
        rom = rom.replace("ā", "aa").replace("ī", "ii").replace("ū", "uu")
        rom = rom.replace("š", "sh").replace("č", "ch").replace("ž", "zh")
        rom = rom.replace("ḵ", "kh").replace("ḡ", "gh").replace("ẕ", "z")
        if rom.isascii() and len(rom) >= 2:
            return rom

    # Strategy 2: tr= in Persian headword templates
    # {{fa-noun|tr=ketâb}} or {{fa-adj|tr=bozorg}}
    tr_match = re.search(r"\{\{fa-(?:noun|adj|verb|adv|proper noun)[^}]*\|tr=([^|}]+)", wikitext)
    if tr_match:
        rom = tr_match.group(1).strip()
        rom = rom.replace("â", "aa").replace("ā", "aa")
        rom = rom.replace("ê", "e").replace("î", "ii").replace("û", "uu")
        rom = rom.replace("š", "sh").replace("č", "ch").replace("ž", "zh")
        # Strip bold/italic markers
        rom = rom.replace("'", "").replace("'''", "").replace("''", "")
        if rom.isascii() and len(rom) >= 2:
            return rom

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest Persian romanizations from Wiktionary")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output TSV file")
    parser.add_argument("--limit", type=int, default=0, help="Max entries to fetch (0=all)")
    args = parser.parse_args()

    print("Fetching Persian lemma titles from Wiktionary...", file=sys.stderr)
    titles = get_persian_lemmas(limit=args.limit)
    print(f"Got {len(titles)} Persian lemma titles", file=sys.stderr)

    print("Extracting romanizations...", file=sys.stderr)
    pairs: list[tuple[str, str]] = []
    errors = 0

    for i, title in enumerate(titles):
        if (i + 1) % 100 == 0:
            print(f"  [{i + 1}/{len(titles)}] {len(pairs)} extracted...", file=sys.stderr)

        rom = extract_romanization(title)
        if rom:
            pairs.append((title, rom))
        else:
            errors += 1

        time.sleep(0.05)  # Rate limit: ~20 req/sec

    # Write TSV
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("# Persian words with romanizations harvested from English Wiktionary\n")
        f.write("# Format: persian_word<TAB>romanization\n")
        f.write(f"# Entries: {len(pairs)}\n")
        f.write("# Source: en.wiktionary.org Category:Persian_lemmas\n")
        for word, rom in sorted(pairs):
            f.write(f"{word}\t{rom}\n")

    print("\n--- Results ---", file=sys.stderr)
    print(f"Titles fetched:      {len(titles)}", file=sys.stderr)
    print(f"Romanizations found: {len(pairs)}", file=sys.stderr)
    print(f"Extraction failures: {errors}", file=sys.stderr)
    print(f"Written: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
