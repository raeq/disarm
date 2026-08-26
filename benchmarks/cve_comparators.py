"""How disarm, decancer and unidecode handle the CVE vectors in the matrix.

Regenerates the comparator table in ``docs/security/cve-validation.md``:

    python benchmarks/cve_comparators.py            # the table
    python benchmarks/cve_comparators.py --markdown # ready to paste

Install the comparators first::

    pip install --require-hashes -r requirements/bench.txt

**One predicate, applied identically to every tool.** No tool gets a rule shaped
to suit it, and the predicate is the repo's existing XMR idea rather than a new
one invented here:

*Collapse* cases have a benign twin, so the test is ``P(attack) == P(benign)``
case-insensitively — a tool that lowercases (decancer always does) is not
penalized for it. *Removal* cases have no benign twin, so the test is that the
attack primitive is gone from the output.

**These are three tools built for three jobs, and the table is not a ranking.**
`unidecode` is a romanizer: it maps by *sound*, and was never intended as a
security control. `decancer` is an anti-obfuscation cleaner, so it is the one
genuine peer here. disarm maps by *appearance* per TR39. Reading a score without
that context gets the wrong answer — see ``_discrimination_probe`` below, which
shows why unidecode's score on the homoglyph rows is an artifact of which
homoglyph the attacker picked.

Thirteen hand-picked vectors are a spot check, not a measurement of the
confusable space. The broad-sample numbers (XMR over 1,314 TR39 sources) live in
``benchmarks/adversarial_eval`` and are quoted in the README.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

import disarm

#: Bidi controls: UAX#9 embeddings, overrides, isolates and marks.
BIDI = "‪‫‬‭‮⁦⁧⁨⁩‎‏؜"
#: Introducers a terminal acts on.
TERMINAL = ("\x1b", "\r", "\n", "\x07", "\x00")


def _has_tag_chars(text: str) -> bool:
    return any(0xE0000 <= ord(ch) <= 0xE007F for ch in text)


def _no_bidi(text: str) -> bool:
    return not any(ch in text for ch in BIDI)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
# Vectors are written independently of tests/test_cve_vectors.py on purpose:
# two reconstructions of the same CVE are a weak cross-check on both. The CVE
# *set* is gated against the registry by TestComparatorCorpusDrift.

#: (cve, attack, benign) — handled when P(attack) == P(benign), casefolded.
COLLAPSE: list[tuple[str, str, str]] = [
    ("CVE-2021-42694", "isАdmin", "isAdmin"),
    ("CVE-2019-19844", "admın@example.com", "admin@example.com"),
    ("CVE-2013-7236", "аdmin", "admin"),
    ("CVE-2020-12063", "bοss@example.com", "boss@example.com"),
    ("CVE-2014-9390", ".g‌it/config", ".git/config"),
    ("CVE-2017-7832", "mı́guel.example", "míguel.example"),
    ("CVE-2017-7833", "exaّmple.com", "example.com"),
    ("CVE-2017-5383", "ex‐ample.com", "ex-ample.com"),
    ("CVE-2023-24329", "\x00https://evil.example.net", "https://evil.example.net"),
]

#: (cve, attack, predicate) — handled when the primitive is gone from the output.
REMOVAL: list[tuple[str, str, Callable[[str], bool]]] = [
    ("CVE-2021-42574", "/*‮ } ⁦if (isAdmin)⁩ ⁦ begin admins only */", _no_bidi),
    (
        "CVE-2009-3376",
        "photo_high_re‮gnp.js",
        lambda out: _no_bidi(out) and out.casefold().endswith(".js"),
    ),
    (
        "CVE-2023-33955",
        "report‮fdp.exe",
        lambda out: _no_bidi(out) and out.casefold().endswith(".exe"),
    ),
    (
        "CVE-2008-2383",
        "\x1bP$q\nrm -rf ~\n\x1b\\",
        lambda out: not any(ch in out for ch in TERMINAL),
    ),
    (
        "CVE-2019-9535",
        "\x1bP1000p%output %1 malicious\x1b\\",
        lambda out: not any(ch in out for ch in TERMINAL),
    ),
    (
        "CVE-2025-32711",
        "Please summarize." + "".join(chr(0xE0000 + ord(c)) for c in "Ignore all"),
        lambda out: not _has_tag_chars(out),
    ),
]

#: Every CVE this comparison covers. Gated against the test registry.
COVERED = frozenset([c for c, _, _ in COLLAPSE] + [c for c, _, _ in REMOVAL])


def build_tools() -> dict[str, Callable[[str], str]]:
    """The tools, or as many as are installed. Missing ones are reported, not faked."""
    tools: dict[str, Callable[[str], str]] = {
        "disarm.canonicalize": disarm.canonicalize,
        "disarm.strip_obfuscation": disarm.strip_obfuscation,
    }
    try:
        import decancer_py

        tools["decancer.parse"] = lambda s: str(decancer_py.parse(s))
    except ImportError:  # pragma: no cover - depends on the local env
        print("note: decancer-py not installed, column omitted", file=sys.stderr)
    try:
        from unidecode import unidecode

        tools["unidecode"] = unidecode
    except ImportError:  # pragma: no cover - depends on the local env
        print("note: Unidecode not installed, column omitted", file=sys.stderr)
    return tools


def _apply(fn: Callable[[str], str], text: str) -> str | None:
    """A tool that raises has not handled the vector; it has failed on it."""
    try:
        return fn(text)
    except Exception:  # noqa: BLE001 - any failure is a non-result, not a crash
        return None


def evaluate(tools: dict[str, Callable[[str], str]]) -> dict[str, dict[str, bool]]:
    """``{cve: {tool: handled}}`` for every case, every tool."""
    results: dict[str, dict[str, bool]] = {}
    for cve, attack, benign in COLLAPSE:
        row = {}
        for name, fn in tools.items():
            got, want = _apply(fn, attack), _apply(fn, benign)
            row[name] = got is not None and want is not None and got.casefold() == want.casefold()
        results[cve] = row
    for cve, attack, predicate in REMOVAL:
        row = {}
        for name, fn in tools.items():
            out = _apply(fn, attack)
            row[name] = out is not None and predicate(out)
        results[cve] = row
    return results


#: Two homoglyphs, two outcomes — the reason a score alone misleads.
#: Cyrillic ``р`` (U+0440) *looks* like ``p`` and *sounds* like ``r``; Cyrillic
#: ``А`` (U+0410) looks and sounds like ``A``. A phonetic tool gets the second
#: right by coincidence and the first wrong by design, so how well it appears to
#: do is decided by which character the attacker reached for.
DISCRIMINATION = [
    ("рroduсt", "product", "visual and phonetic disagree"),
    ("isАdmin", "isAdmin", "visual and phonetic agree"),
]


def _discrimination_probe(tools: dict[str, Callable[[str], str]]) -> list[str]:
    lines = ["", "Why the homoglyph rows need reading twice:"]
    for attack, expected, note in DISCRIMINATION:
        lines.append(f"  {attack!r} -> {expected!r}  ({note})")
        for name, fn in tools.items():
            lines.append(f"      {name:<26} {_apply(fn, attack)!r}")
    return lines


def render_text(tools, results) -> str:
    names = list(tools)
    width = max(len(n) for n in names) + 2
    out = [f"{'CVE':<16}" + "".join(f"{n:>{width}}" for n in names)]
    for cve in sorted(results):
        out.append(
            f"{cve:<16}" + "".join(f"{'PASS' if results[cve][n] else '-':>{width}}" for n in names)
        )
    total = len(results)
    out.append(
        f"{'TOTAL/' + str(total):<16}"
        + "".join(f"{sum(results[c][n] for c in results):>{width}}" for n in names)
    )
    out.extend(_discrimination_probe(tools))
    return "\n".join(out)


def render_markdown(tools, results) -> str:
    names = list(tools)
    out = ["| CVE | " + " | ".join(f"`{n}`" for n in names) + " |"]
    out.append("|---|" + "---|" * len(names))
    for cve in sorted(results):
        cells = " | ".join("yes" if results[cve][n] else "**no**" for n in names)
        out.append(f"| {cve} | {cells} |")
    scores = " | ".join(f"**{sum(results[c][n] for c in results)}/{len(results)}**" for n in names)
    out.append(f"| **Handled** | {scores} |")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", action="store_true", help="emit the docs table")
    args = parser.parse_args(argv)

    tools = build_tools()
    results = evaluate(tools)
    print(render_markdown(tools, results) if args.markdown else render_text(tools, results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
