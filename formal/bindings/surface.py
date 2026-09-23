"""Surface inventory: which core `api` functions each binding exposes.

    DISARM_PYTHON=... python3 formal/bindings/surface.py

Names are normalised to the core's snake_case (camelCase split, a Ruby `?` suffix
dropped, `is_`/`has_` kept), then compared against the public functions of
`src/api/*.rs`. Registration, streaming and the Python-only helpers are listed
separately rather than counted as gaps: the bindings do not claim them.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TARGET = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target" / "formal-bindings"))


def snake(n: str) -> str:
    n = n.rstrip("?")
    n = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", n).lower()
    return n


RUBY_PRED = {  # Ruby predicate spelling -> core name
    "confusable": "is_confusable",
    "canonical": "is_canonical",
    "case_fold_stable": "is_case_fold_stable",
    "suspicious_hostname": "is_suspicious_hostname",
    "normalized": "is_normalized",
    "zalgo": "is_zalgo",
    "mixed_script": "is_mixed_script",
    "bidi_conflict": "has_bidi_conflict",
    "bidi_control": "has_bidi_control",
}


def core() -> set[str]:
    names = set()
    for f in (ROOT / "src" / "api").glob("*.rs"):
        names |= set(re.findall(r"^pub fn (\w+)", f.read_text(), re.M))
    return names


def node() -> set[str]:
    out = subprocess.run(
        [
            "node",
            "-e",
            "console.log(JSON.stringify(Object.keys(require(process.argv[1]))))",
            str(ROOT / "bindings" / "node" / "index.js"),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {snake(n) for n in json.loads(out)}


def ruby() -> set[str]:
    out = subprocess.run(
        [
            "ruby",
            "-I",
            str(ROOT / "bindings" / "ruby" / "lib"),
            "-rdisarm",
            "-rjson",
            "-e",
            "puts JSON.generate(Disarm.singleton_methods.map(&:to_s).reject { |m| m.start_with?('_') })",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    res = set()
    for n in json.loads(out):
        base = n.rstrip("?")
        res.add(RUBY_PRED.get(base, base) if n.endswith("?") else base)
    return res


def java() -> set[str]:
    src = (
        ROOT
        / "bindings"
        / "java"
        / "disarm-java"
        / "src"
        / "main"
        / "java"
        / "dev"
        / "disarm"
        / "Disarm.java"
    ).read_text()
    return {snake(n) for n in re.findall(r"public static \S+(?:<[^>]*>)? (\w+)\(", src)}


def cabi() -> set[str]:
    h = (ROOT / "bindings" / "cabi" / "disarm.h").read_text()
    names = set(re.findall(r"^disarm_(\w+) \(", h, re.M))
    return {re.sub(r"_opts$", "", n) for n in names} - {"string_free"}


def python() -> set[str]:
    py = os.environ.get("DISARM_PYTHON", sys.executable)
    out = subprocess.run(
        [
            py,
            "-c",
            "import disarm, json; print(json.dumps([n for n in dir(disarm) if not n.startswith('_') and callable(getattr(disarm, n))]))",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return set(json.loads(out))


# Idiomatic renames: the same core function under a binding-specific name.
ALIASES = {
    "analyze_hostname_with": "analyze_hostname",
    "canonicalize_with": "canonicalize",
    "canonicalize_strict_with": "canonicalize_strict",
    "strip_obfuscation_with": "strip_obfuscation",
    "search_key_with": "search_key",
    "sort_key_with": "sort_key",
    "catalog_key_with": "catalog_key",
    "normalize_confusables_with": "normalize_confusables",
    "find_confusables_with": "find_confusables",
    "is_mixed_script_per_word": "is_mixed_script",
    "has_bidi_conflict_per_word": "has_bidi_conflict",
}
NOT_CLAIMED = {  # process-global registration and streaming: Python/Rust only by design
    "register_lang",
    "register_replacements",
    "remove_replacement",
    "clear_replacements",
    "seal_registrations",
    "registrations_sealed",
    "graphemes",
    "lexicon",
}


def main() -> None:
    c = {ALIASES.get(n, n) for n in core()} - NOT_CLAIMED
    surf = {"python": python(), "node": node(), "ruby": ruby(), "java": java(), "c": cabi()}
    # Python spells hostname analysis as is_suspicious_hostname(...)[1] and reverse
    # transliteration as transliterate(target=...): count those as present.
    surf["python"] |= {"analyze_hostname", "reverse_transliterate"}
    print(f"core api functions considered: {len(c)}")
    rows = []
    for name in sorted(c):
        have = [b for b, s in surf.items() if name in s]
        if len(have) < len(surf):
            rows.append((name, [b for b in surf if b not in have]))
    for b, s in surf.items():
        print(f"{b:7} exposes {len(c & s):3} of {len(c)}")
    print("\nmissing (core function -> bindings without it):")
    for name, missing in rows:
        print(f"  {name:32} {', '.join(missing)}")


if __name__ == "__main__":
    main()
