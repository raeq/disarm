#!/usr/bin/env python3
"""disarm binding-parity seeder/checker (v2).

Fixes over v0 (per external review):
  * Python surface = the authoritative `__all__` in disarm/__init__.py
    (v0 read only the `_api` import block -> 8 false nulls).
  * Rust surface  = `pub fn` in src/api/** PLUS `pub use ...::{...}` re-exports
    (v0 ignored re-exports -> has_anomalies/inspect_anomalies false nulls).
  * Ruby surface  = real `def` lines in bindings/ruby/lib/disarm.rb.
  * Schema gains `alias_of` and `provided_via` so folded/aliased ops are not
    mislabelled as gaps (reverse_transliterate via transliterate(target=...),
    strip_control_chars/strip_zero_width_chars via the pipeline, etc.).
Caveat: Python+Rust are verified against the real public surface; Ruby is parsed
from source defs (reliable) and Node from `export function` (reliable), but
neither is runtime-introspected (no toolchain) — finalize with
`Disarm.respond_to?` / Node export keys before wiring CI.
"""

from __future__ import annotations
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LANGS = ["rust", "python", "ruby", "node"]


def py_surface() -> set[str]:
    txt = (ROOT / "python/disarm/__init__.py").read_text()
    m = re.search(r"__all__\s*=\s*\[(.*?)\]", txt, re.S)
    names = re.findall(r'"([a-z_][a-z0-9_]*)"', m.group(1)) if m else []
    return {n for n in names if n != "__version__"}


def rust_surface() -> set[str]:
    out: set[str] = set()
    for p in (ROOT / "src/api").rglob("*.rs"):
        t = p.read_text()
        out |= set(re.findall(r"pub fn ([a-z0-9_]+)", t))
        for blk in re.findall(r"pub use [^;{]*\{([^}]*)\}", t):  # pub use x::{a, b, C}
            out |= {s.strip() for s in blk.split(",")}
        out |= set(re.findall(r"pub use [^;{]*::([a-z0-9_]+)\s*;", t))  # pub use x::name;
    out = {n for n in out if n and n[0].islower()}  # drop CamelCase types
    noise = {"as_str", "new", "run", "lang", "scheme", "tones", "on_unknown", "graphemes"}
    return out - noise


def ruby_surface() -> set[str]:
    t = (ROOT / "bindings/ruby/lib/disarm.rb").read_text()
    return set(re.findall(r"^\s*def (?:self\.)?([a-z0-9_]+[?!]?)", t, re.M)) - {"translate_errors"}


def node_surface() -> set[str]:
    t = (ROOT / "bindings/node/index.ts").read_text()
    return set(re.findall(r"export\s+(?:declare\s+)?function\s+([a-zA-Z0-9_]+)", t))


def camel_to_snake(s):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


RUBY_PRED = {
    "normalized": "is_normalized",
    "mixed_script": "is_mixed_script",
    "zalgo": "is_zalgo",
    "confusable": "is_confusable",
    "ascii": "is_ascii",
    "suspicious_hostname": "is_suspicious_hostname",
}


def canon(name, lang):
    if lang == "node":
        name = camel_to_snake(name)
    if lang == "ruby":
        name = name.rstrip("?!")
        name = RUBY_PRED.get(name, name)
    return name


# ops that exist but via another mechanism (not a top-level symbol) -> not a gap

ALIAS_OF = {  # Python-layer aliases / preset wrappers — fold into their target, not separate ops
    "casefold": "fold_case",
    "remove_accents": "strip_accents",
    "unidecode": "transliterate",
    "ascii_fold": "transliterate",
    "slugify_de": "slugify",
    "slugify_el": "slugify",
    "slugify_ru": "slugify",
    "slugify_unicode": "slugify",
    "slugify_url": "slugify",
    "slugify_filename": "slugify",
}

PROVIDED_VIA = {
    "reverse_transliterate": {"python": "transliterate(target=…)"},
    "strip_control_chars": {"python": "collapse_whitespace(strip_control=True) / get_pipeline()"},
    "strip_zero_width_chars": {
        "python": "collapse_whitespace(strip_zero_width=True) / get_pipeline()"
    },
}
# Deliberate scope decisions for Ruby/Node — not blind backfill:
#  * registration mutates process-global state; encoders are sink-context tools;
#  * dedup_batch / make_cached_transliterator are Python-idiomatic performance
#    helpers (Node/Ruby use native map / the Lexicon-style handle idiom);
#  * set_emoji_provider is global-state mutation + an FFI callback (#404).
SCOPE_REVIEW = {
    "register_lang",
    "register_replacements",
    "remove_replacement",
    "clear_replacements",
    "seal_registrations",
    "registrations_sealed",
    "decode_to_utf8",
    "detect_encoding",
    "escape_html",
    "percent_encode",
    "strip_log_injection",
    "list_langs",
    "reverse_langs",
    "is_ascii",
    "list_profiles",
    "display_clean",
    "ml_normalize",
    "normalize_user_input",
    "dedup_batch",
    "make_cached_transliterator",
    "set_emoji_provider",
}

SURF = {
    "rust": rust_surface(),
    "python": py_surface(),
    "ruby": ruby_surface(),
    "node": node_surface(),
}
canonmap: dict[str, dict[str, str]] = {}
for l in LANGS:
    for sym in SURF[l]:
        canonmap.setdefault(canon(sym, l), {})[l] = sym
ops = sorted(
    c
    for c in canonmap
    if (canonmap[c].get("rust") or canonmap[c].get("python")) and c not in ALIAS_OF
)


def covered(c, l):  # present as a symbol, or provided via another mechanism
    return (l in canonmap[c]) or (c in PROVIDED_VIA and l in PROVIDED_VIA[c])


cov = {l: sum(covered(c, l) for c in ops) for l in LANGS}
print("=== raw symbol counts ===")
[print(f"  {l:7}{len(SURF[l])}") for l in LANGS]
print(f"\n=== {len(ops)} canonical ops — coverage (symbol or provided_via) ===")
for l in LANGS:
    print(f"  {l:7}{cov[l]:2}/{len(ops)} ({100 * cov[l] // len(ops)}%)")


def matrix():
    rows = ["| operation | rust | python | ruby | node |", "|---|:--:|:--:|:--:|:--:|"]
    for c in ops:
        cells = []
        for l in LANGS:
            if l in canonmap[c]:
                cells.append("✓")
            elif c in PROVIDED_VIA and l in PROVIDED_VIA[c]:
                cells.append("⊃")  # provided_via
            else:
                cells.append("·")
        rows.append(f"| `{c}` | {' | '.join(cells)} |")
    return "\n".join(rows)


print("\n" + matrix())

for lang in ("ruby", "node", "python"):
    g = [
        c
        for c in ops
        if (canonmap[c].get("rust") or canonmap[c].get("python")) and not covered(c, lang)
    ]
    scoped = [c for c in g if c in SCOPE_REVIEW]
    hard = [c for c in g if c not in SCOPE_REVIEW]
    print(f"\n=== {lang}: {len(g)} true gaps ===")
    if scoped:
        print(f"  scope-decision ({len(scoped)}): " + ", ".join(scoped))
    if hard:
        print(f"  clear gaps   ({len(hard)}): " + ", ".join(hard))


# write corrected manifest with alias_of/provided_via support
def cell(c, l):
    if l in canonmap[c]:
        return canonmap[c][l]
    if c in PROVIDED_VIA and l in PROVIDED_VIA[c]:
        return '{ provided_via: "' + PROVIDED_VIA[c][l] + '" }'
    return "null"


out = [
    "# disarm parity manifest (v2 seed). symbol | {provided_via:…} | {alias_of:…} | null(gap).",
    "# Python=__all__, Rust=pub fn + pub use re-exports, Ruby=def lines, Node=export function.",
    "operations:",
]
for c in ops:
    out.append(f"  - id: {c}")
    out.append("    names:")
    for l in LANGS:
        out.append(f"      {l}: {cell(c, l)}")
# alias rows: live symbols that alias an existing op (Python-layer conveniences /
# preset wrappers). Recorded so the checker accounts for them as live exports rather
# than flagging them "undeclared"; excluded from the gap analysis above (not ops).
for alias, target in sorted(ALIAS_OF.items()):
    cells = {l: (alias if alias in SURF[l] else "null") for l in LANGS}
    if all(v == "null" for v in cells.values()):
        continue
    out.append(f"  - id: {alias}")
    out.append(f"    alias_of: {target}")
    out.append("    names:")
    for l in LANGS:
        out.append(f"      {l}: {cells[l]}")
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "generated/parity.yaml"
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(out) + "\n")
print(f"\nWROTE {OUT}")
