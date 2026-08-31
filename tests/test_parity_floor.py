"""#698/#707/#677/#660 — the parity matrix has to *fail*, not warn.

`tests/test_parity.py` re-seeds the same matrix and emits `ParityWarning`. That was a
deliberate choice — a security release must never wait on interface parity — but it means
a gap can sit in the matrix indefinitely while every run is green. Four did:
`strip_format` was missing on Node, Ruby and the C ABI; `sanitize_filename`, the one entry
point whose whole purpose is a filesystem sink, was missing on the C ABI; the JVM had
neither `canonicalizeStrict` nor `stripFormat`; and `LANG_AUTO` was the single `LANG_*`
constant of eighty-four that Python never exported.

This gate is the complement, and it is deliberately narrow so it keeps that release
property: the advisory check still owns the whole 79-operation matrix, while this one
asserts a **floor** — a fixed list of operations that are complete on all seven surfaces
today and must stay that way. Adding a binding-specific operation does not touch it;
dropping a column from a floor row fails.

Regenerating the manifest is not required: the assertion reads the committed
`generated/parity.yaml`, so a stale manifest is caught by the advisory check and a real
regression is caught here.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "generated" / "parity.yaml"

#: The seven modelled surfaces. `rust` is the core; the other six are bindings.
LANGS = ("rust", "python", "ruby", "node", "java", "kotlin", "cabi")

#: Operations that must exist on every surface. Seeded from the 38 complete rows at the
#: time #762's P21 closed the four gaps above — a ratchet, not an aspiration. An entry
#: comes off this list only with a written reason; nothing comes off to make a build pass.
FLOOR = frozenset(
    {
        "canonicalize",
        "canonicalize_strict",
        "catalog_key",
        "collapse_whitespace",
        "confusables_version",
        # #645: added complete on all seven, so they join the floor in the same
        # change rather than waiting for a later one to notice they drifted.
        "unicode_version",
        "key_schema_version",
        "demojize",
        "find_key_collisions",
        "find_unmapped_confusables",
        "fold_case",
        "grapheme_len",
        "has_bidi_conflict",
        "inspect_anomalies",
        "inspect_auto_lang",
        "is_case_fold_stable",
        "is_mixed_script",
        "is_suspicious_hostname",
        "lang_info",
        "ml_normalize",
        "normalize",
        "normalize_confusables",
        "reverse_transliterate",
        "sanitize_filename",
        "script_info",
        "search_key",
        "sort_key",
        "strip_accents",
        "strip_bidi",
        "strip_control_chars",
        "strip_format",
        "strip_noncharacters",
        "strip_obfuscation",
        "strip_pua",
        "strip_tags",
        "strip_variation_selectors",
        "strip_zero_width_chars",
        "terminal_width",
        "transliterate",
        "unmapped_confusables",
    }
)

#: The three matrix rows this gate exists for, kept separate so a failure names the
#: issue. P21 closed four gaps; the fourth was `LANG_AUTO`, a Python-only export that
#: the parity matrix does not model — `tests/test_lang_constant_exports.py` holds it.
CLOSED_IN_P21 = {
    "strip_format": ("node", "ruby", "cabi", "java", "kotlin"),
    "sanitize_filename": ("cabi",),
    "canonicalize_strict": ("java", "kotlin", "ruby", "cabi", "node"),
}


def _matrix() -> dict[str, dict[str, str | None]]:
    """Parse the committed manifest into {op: {lang: name-or-None}}."""
    text = MANIFEST.read_text(encoding="utf-8")
    out: dict[str, dict[str, str | None]] = {}
    for op, block in re.findall(r"- id: ([a-z0-9_]+)\n    names:\n((?:      \w+: .*\n)+)", text):
        out[op] = {
            lang: (None if value == "null" else value)
            for lang, value in re.findall(r"      (\w+): (.*)", block)
        }
    return out


@pytest.fixture(scope="module")
def matrix() -> dict[str, dict[str, str | None]]:
    if not MANIFEST.exists():  # pragma: no cover - manifest is committed
        pytest.skip("generated/parity.yaml not present")
    return _matrix()


def test_the_manifest_parses(matrix: dict[str, dict[str, str | None]]) -> None:
    """A gate over an empty matrix passes for the wrong reason."""
    assert len(matrix) > 70, len(matrix)
    assert set(next(iter(matrix.values()))) == set(LANGS)


def test_the_floor_is_covered_by_the_manifest(matrix: dict[str, dict[str, str | None]]) -> None:
    """A renamed operation must move the floor entry, not silently drop off it."""
    missing = sorted(FLOOR - set(matrix))
    assert not missing, f"floor names operations the matrix does not have: {missing}"


@pytest.mark.parametrize("op", sorted(FLOOR))
def test_every_floor_operation_reaches_every_surface(
    op: str, matrix: dict[str, dict[str, str | None]]
) -> None:
    """The assertion the advisory check makes as a warning."""
    gaps = sorted(lang for lang in LANGS if matrix[op][lang] is None)
    assert not gaps, (
        f"`{op}` is missing on {gaps}. Every surface carries it today; a caller there has "
        "no way to reach the behaviour, which is the shape of #698/#707/#677."
    )


@pytest.mark.parametrize(("op", "langs"), sorted(CLOSED_IN_P21.items()))
def test_the_rows_p21_closed_stay_closed(
    op: str, langs: tuple[str, ...], matrix: dict[str, dict[str, str | None]]
) -> None:
    """Named separately so a regression cites the issue rather than a bare row."""
    for lang in langs:
        assert matrix[op][lang] is not None, f"{op} regressed on {lang}"
