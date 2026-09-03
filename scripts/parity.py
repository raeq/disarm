#!/usr/bin/env python3
"""disarm binding-parity seeder/checker (v2).

Fixes over v0 (per external review):
  * Python surface = the authoritative `__all__` in disarm/__init__.py
    (v0 read only the `_api` import block -> 8 false nulls).
  * Rust surface  = `pub fn` in src/api/** PLUS `pub use ...::{...}` re-exports
    (v0 ignored re-exports -> has_anomalies/inspect_anomalies false nulls).
  * Ruby surface  = real `def` lines in bindings/ruby/lib/disarm.rb.
  * Schema gains `alias_of` and `provided_via` so folded/aliased ops are not
    mislabelled as gaps (reverse_transliterate via transliterate(target=...)).
    Use `provided_via` only for a route that is real and callable: the entries
    for strip_control_chars/strip_zero_width_chars named
    `collapse_whitespace(strip_control=True)`, a signature that never existed,
    which hid the gap until #616 exported both from Python.
#677/#698/#707 add java, kotlin and cabi. Until then the matrix covered four of the
seven shipped surfaces, so three could not be measured at all — which is why #677 and
#707 were both found by reading declarations by hand, and why both understate their own
gap. Measured here: the JVM is missing six operations, not the two #677 names, and the C
ABI twenty, not the one #707 names.

Caveat: Python+Rust are verified against the real public surface; Ruby is parsed
from source defs (reliable) and Node from `export function` (reliable), but
neither is runtime-introspected (no toolchain) — finalize with
`Disarm.respond_to?` / Node export keys before wiring CI. The three new columns carry
the same caveat and one more: each is read with a different regex because each binding
declares its surface differently, and a reader that is wrong fails *quietly*, by
reporting a smaller surface rather than by erroring.
"""

from __future__ import annotations
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LANGS = ["rust", "python", "ruby", "node", "java", "kotlin", "cabi"]


def py_surface() -> set[str]:
    txt = (ROOT / "python/disarm/__init__.py").read_text()
    m = re.search(r"__all__\s*=\s*\[(.*?)\]", txt, re.S)
    names = re.findall(r'"([a-z_][a-z0-9_]*)"', m.group(1)) if m else []
    return {n for n in names if n != "__version__"}


def rust_surface() -> set[str]:
    out: set[str] = set()
    for p in (ROOT / "src/api").rglob("*.rs"):
        t = p.read_text()
        # ^pub fn = module-level free functions only; an indented `    pub fn` is an
        # impl method (e.g. Pipeline::process), not part of the api op surface.
        out |= set(re.findall(r"^pub fn ([a-z0-9_]+)", t, re.M))
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


# The three surfaces below were unmodelled until #677/#698/#707. Each is read from the
# declaration that actually ships, and each needs a different shape — which is the reason
# the gaps went unnoticed: there is no one regex that reads all six bindings.


def java_surface() -> set[str]:
    """`public static` methods on the JVM facade. Overloads collapse to one name."""
    t = (ROOT / "bindings/java/disarm-java/src/main/java/dev/disarm/Disarm.java").read_text()
    return set(re.findall(r"public\s+static\s+[\w<>\[\], ]+?\s+([a-zA-Z0-9_]+)\s*\(", t))


def kotlin_surface() -> set[str]:
    """Kotlin ships **extension functions** (`fun String.canonicalize()`), so the receiver
    has to be skipped. A regex that captures the first identifier after `fun` reads the
    receiver type instead of the operation and reports a 7-symbol surface for a 51-symbol
    file."""
    t = (
        ROOT / "bindings/java/disarm-kotlin/src/main/kotlin/dev/disarm/kotlin/Disarm.kt"
    ).read_text()
    return set(re.findall(r"^fun\s+(?:[\w<>, ]+\.)?([a-zA-Z0-9_]+)\s*\(", t, re.M))


def cabi_surface() -> set[str]:
    """Symbols in the generated C header, less the memory-management entry point.

    `disarm.h` is regenerated from the crate by `test_cabi_header_drift.py`, so a function
    never added to `bindings/cabi/src/lib.rs` is missing from *both* sides and that gate
    stays green over it. This column is the check that notices."""
    t = (ROOT / "bindings/cabi/disarm.h").read_text()
    return {n[len("disarm_") :] for n in re.findall(r"\bdisarm_[a-z0-9_]+", t)} - {"string_free"}


def camel_to_snake(s):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


RUBY_PRED = {
    "case_fold_stable": "is_case_fold_stable",
    "normalized": "is_normalized",
    "mixed_script": "is_mixed_script",
    "bidi_conflict": "has_bidi_conflict",
    "bidi_control": "has_bidi_control",
    "zalgo": "is_zalgo",
    "confusable": "is_confusable",
    "ascii": "is_ascii",
    "suspicious_hostname": "is_suspicious_hostname",
}


# The C ABI spells the opt-in contraction pass as a separate symbol rather than a widened
# one (`disarm.h:38` records the reason), so it needs the alias its siblings do not.
#
# Deliberately NOT aliased: `analyze_hostname`. Every binding ships BOTH `analyzeHostname`
# and `isSuspiciousHostname`, so folding the first onto the second collides with a symbol
# the binding already has, and `canonmap` would then keep whichever the iteration reached
# last. That op has no `rust`/`python` counterpart under either name, so it stays out of
# `ops` exactly as Node's has always done. The three-way naming of this family
# (`is_suspicious_hostname` / `analyze_hostname` / `analyze_hostname_with`) is a real
# divergence and #677 §2 is the place to settle it, not a canon rule here.
HOSTNAME_ALIASES = {
    "analyze_hostname_opts": "analyze_hostname_with",
    # #896: the six key builders take `digit_policy` through `_opts` symbols for the same
    # ABI reason, and each reads as the Rust `_with` form it wraps.
    "canonicalize_opts": "canonicalize_with",
    "canonicalize_strict_opts": "canonicalize_strict_with",
    "strip_obfuscation_opts": "strip_obfuscation_with",
    "search_key_opts": "search_key_with",
    "sort_key_opts": "sort_key_with",
    "catalog_key_opts": "catalog_key_with",
}


def canon(name, lang):
    if lang in ("node", "java", "kotlin"):
        name = camel_to_snake(name)
    if lang == "ruby":
        name = name.rstrip("?!")
        name = RUBY_PRED.get(name, name)
    if lang in ("java", "kotlin", "cabi", "node"):
        name = HOSTNAME_ALIASES.get(name, name)
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
    # #560: a version is a constant, not an operation, so each language exposes it the
    # way that language names constants. Python and Rust have real ones; the compiled
    # bindings expose a nullary accessor because a native module cannot export a static.
    "confusables_version": {"python": "disarm.CONFUSABLES_VERSION"},
    # #645 extends the same channel with two more constants, so they take the same
    # shape: a real constant in Python and Rust, a nullary accessor everywhere else.
    "unicode_version": {"python": "disarm.UNICODE_VERSION"},
    "key_schema_version": {"python": "disarm.KEY_SCHEMA_VERSION"},
    "reverse_transliterate": {"python": "transliterate(target=…)"},
}
# Deliberate scope decisions for Ruby/Node — not blind backfill:
#  * registration mutates process-global state; encoders are sink-context tools;
#  * dedup_batch / make_cached_transliterator are Python-idiomatic performance
#    helpers (Node/Ruby use native map / the Lexicon-style handle idiom);
#  * set_emoji_provider is global-state mutation + an FFI callback (#404).
# `ml_normalize` was here until it reached every binding — it is the ML/NLP entry point,
# so a scope decision that kept it Python-only made disarm unusable from a Node or JVM
# model pipeline. Removed rather than annotated: it is now covered everywhere.
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
    "java": java_surface(),
    "kotlin": kotlin_surface(),
    "cabi": cabi_surface(),
}
canonmap: dict[str, dict[str, str]] = {}
for l in LANGS:
    # `sorted`, not set order: if two symbols in one binding ever canon to the same name,
    # the survivor must be the same on every run. Unsorted, the committed manifest and a
    # fresh regeneration disagreed run-to-run and the staleness warning flapped.
    #
    # Determinism alone is not enough, though: the assignment would still *discard* one of
    # the two symbols and under-report that binding's surface with no signal — the same
    # "fails quietly" shape these columns exist to close. So a collision is an error.
    # Measured: zero across all seven surfaces. The only one ever seen was a bad alias
    # rule written during #677/#698/#707, which is precisely what this catches.
    for sym in sorted(SURF[l]):
        c = canon(sym, l)
        if l in canonmap.get(c, {}):
            raise SystemExit(
                f"parity: {l} symbols {canonmap[c][l]!r} and {sym!r} both reduce to {c!r}. "
                f"One would be dropped and {l}'s surface under-reported. Fix the canon or "
                f"alias rule — do not let the later symbol win."
            )
        canonmap.setdefault(c, {})[l] = sym
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
    rows = [
        "| operation | " + " | ".join(LANGS) + " |",
        "|---|" + "|".join([":--:"] * len(LANGS)) + "|",
    ]
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

for lang in [l for l in LANGS if l != "rust"]:
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


# ── docs coverage ─────────────────────────────────────────────────────────────
# An op is "documented" in language L if its L-specific symbol appears in L's docs:
# the per-language API / getting-started pages, plus that language's content-tab
# blocks (`=== "Node"` …) in the shared guides. Same presence heuristic as the symbol
# parity above — it catches code that shipped without docs.
DOC_PRIMARY = {
    "rust": ["docs/RUST_API.md", "docs/rust"],
    "python": ["docs/api", "docs/python"],
    "ruby": ["docs/ruby"],
    "node": ["docs/node"],
    # Java and Kotlin share one page (#628). The C ABI has no page at all, so its docs
    # column reads 0 by construction — that is the finding, not a bug in this script.
    "java": ["docs/java"],
    "kotlin": ["docs/java"],
    "cabi": [],
}
DOC_TAB_DIRS = ["docs/user-guide", "docs/concepts", "docs/migration"]
DOC_TAB_LABEL = {
    "rust": "Rust",
    "python": "Python",
    "ruby": "Ruby",
    "node": "Node",
    "java": "Java",
    "kotlin": "Kotlin",
    "cabi": "C",
}


def _read_md(rel):
    p = ROOT / rel
    if p.is_file():
        return p.read_text()
    if p.is_dir():
        return "\n".join(f.read_text() for f in sorted(p.rglob("*.md")))
    return ""


def _tab_blocks(text, label):
    # mkdocs-material content tabs: `=== "Label"` then a body until the next tab
    # marker (at any indentation) or a column-0 Markdown heading. Tab markers are
    # matched at line start with optional leading whitespace, so tabs nested under
    # a list item (`  === "Node"`, as on tokenizer-preprocessing.md) are scraped
    # too — otherwise ops mentioned only in an indented tab look undocumented.
    pat = rf'^[ \t]*===\s+"{label}"\s*\n(.*?)(?=\n[ \t]*===\s+"|\n#|\Z)'
    return "\n".join(re.findall(pat, text, re.S | re.M))


def docs_text(lang):
    parts = [_read_md(r) for r in DOC_PRIMARY[lang]]
    shared = "\n".join(_read_md(d) for d in DOC_TAB_DIRS)
    parts.append(_tab_blocks(shared, DOC_TAB_LABEL[lang]))
    return "\n".join(parts)


DOCS = {lang: docs_text(lang) for lang in LANGS}


def docs_covered(c, lang):
    sym = canonmap[c].get(lang)
    return bool(sym) and (sym in DOCS[lang] or sym.rstrip("?!") in DOCS[lang])


print("\n=== docs coverage (op documented in the language's docs) ===")
for lang in LANGS:
    exposed = [c for c in ops if canonmap[c].get(lang)]
    doc = sum(docs_covered(c, lang) for c in exposed)
    print(f"  {lang:7}{doc:2}/{len(exposed)} ({100 * doc // max(len(exposed), 1)}%)")

for lang in LANGS:
    exposed = [c for c in ops if canonmap[c].get(lang)]
    undoc = sorted(c for c in exposed if not docs_covered(c, lang))
    print(f"\n=== {lang}: {len(undoc)} docs gaps ===")
    if undoc:
        print("  " + ", ".join(undoc))


# write corrected manifest with alias_of/provided_via support
def cell(c, l):
    if l in canonmap[c]:
        return canonmap[c][l]
    if c in PROVIDED_VIA and l in PROVIDED_VIA[c]:
        return '{ provided_via: "' + PROVIDED_VIA[c][l] + '" }'
    return "null"


out = [
    "# disarm parity manifest (v2 seed). symbol | {provided_via:…} | {alias_of:…} | null(gap).",
    "# Python=__all__, Rust=pub fn + pub use re-exports, Ruby=def lines, Node=export function,",
    "# Java=public static, Kotlin=fun (extension receiver skipped), C ABI=disarm_* in disarm.h.",
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
