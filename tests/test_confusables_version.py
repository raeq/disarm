"""#560 — the bundled ``confusables.txt`` version is reachable from a running program.

The version was already written down twice at build time (the TSV header and
``docs/provenance.md``), but neither is reachable at runtime, so a caller could not
answer "is my confusables fold stale?" without inferring it from behaviour. These tests
pin the runtime accessor and, more importantly, pin it to the data it describes: every
assertion here is derived from the table or the docs, never from a literal typed into
the test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import disarm

REPO_ROOT = Path(__file__).resolve().parent.parent
LATIN_TSV = REPO_ROOT / "src" / "tables" / "data" / "confusables_to_latin.tsv"
CYRILLIC_TSV = REPO_ROOT / "src" / "tables" / "data" / "confusables_to_cyrillic.tsv"
PROVENANCE = REPO_ROOT / "docs" / "provenance.md"

#: The header line ``scripts/gen_confusables.py`` writes, e.g.
#: ``# Unicode UTS#39 confusables.txt 17.0.0, folded to Latin, ...``
HEADER_RE = re.compile(r"^# Unicode UTS#39 confusables\.txt (?P<version>[0-9]+(?:\.[0-9]+)+)")


def _header_version(tsv: Path) -> str:
    """The version named on line 1 of a confusables TSV."""
    first_line = tsv.read_text(encoding="utf-8").splitlines()[0]
    match = HEADER_RE.match(first_line)
    assert match is not None, f"{tsv.name}: header does not name a version: {first_line!r}"
    return match.group("version")


def test_constant_is_exported() -> None:
    assert isinstance(disarm.CONFUSABLES_VERSION, str)
    assert disarm.CONFUSABLES_VERSION


def test_constant_is_a_dotted_numeric_version() -> None:
    parts = disarm.CONFUSABLES_VERSION.split(".")
    assert len(parts) >= 2, f"expected at least major.minor, got {disarm.CONFUSABLES_VERSION!r}"
    assert all(part.isdigit() for part in parts), disarm.CONFUSABLES_VERSION


@pytest.mark.skipif(not LATIN_TSV.exists(), reason="source checkout only")
def test_constant_matches_the_latin_table_header() -> None:
    """Derived, not typed twice — the acceptance criterion for #560."""
    assert disarm.CONFUSABLES_VERSION == _header_version(LATIN_TSV)


@pytest.mark.skipif(not CYRILLIC_TSV.exists(), reason="source checkout only")
def test_both_tables_agree_on_the_version() -> None:
    """One constant covers both tables only while both name the same release.

    build.rs asserts this at build time. Asserting it here as well means the reason the
    API is a single constant, rather than a per-table accessor, stays visible.
    """
    assert _header_version(LATIN_TSV) == _header_version(CYRILLIC_TSV)


@pytest.mark.skipif(not PROVENANCE.exists(), reason="source checkout only")
def test_provenance_doc_names_the_same_version() -> None:
    """``docs/provenance.md`` is what users pin against; it must not drift from the code."""
    row = next(
        line
        for line in PROVENANCE.read_text(encoding="utf-8").splitlines()
        if "confusables_to_latin.tsv" in line
    )
    assert f"**{disarm.CONFUSABLES_VERSION}**" in row, row


@pytest.mark.skipif(not LATIN_TSV.exists(), reason="source checkout only")
def test_distinct_from_the_package_version() -> None:
    """Data vintage and release number are different facts and move independently.

    Not an assertion that they never coincide — an assertion that the constant reports
    the table, so it must equal the table header rather than ``__version__``.
    """
    assert disarm.CONFUSABLES_VERSION == _header_version(LATIN_TSV)


def test_unicode_version_is_scoped_to_the_normalizer() -> None:
    """The #560 guard, discharged and rewritten (#645).

    This test used to assert ``not hasattr(disarm, "UNICODE_VERSION")``. Its stated purpose
    was to force whoever added that name to reckon with the per-table versions first,
    because disarm's tables do not share one Unicode release and a library-wide constant
    would be wrong for most of them. #645 is that reckoning: the constant now exists, and
    it is **not** library-wide. It names the UCD the *normalizer* implements — the only
    scope for which one number is correct, and the one integrators actually ask about,
    because it decides whether disarm's normalization agrees with the host platform's.

    So the guard is kept and pointed at the thing that still matters: that the two
    constants stay distinct questions, and that no third constant appears claiming to
    cover the artifact as a whole. ``docs/provenance.md`` remains the census.
    """
    assert hasattr(disarm, "UNICODE_VERSION")
    assert disarm.UNICODE_VERSION.count(".") == 2, disarm.UNICODE_VERSION

    # No third constant claiming to cover the artifact as a whole. The bundled tables
    # that track other releases — case folding 16.0, East Asian width 15.1.0 — are
    # deliberately not exposed as constants, so a caller cannot mistake any one number
    # for the library's Unicode version.
    assert not hasattr(disarm, "CASE_FOLDING_VERSION")
    assert not hasattr(disarm, "EAST_ASIAN_WIDTH_VERSION")


def test_unicode_version_answers_the_question_it_exists_for() -> None:
    """*Will my normalization agree with the host platform's?* — askable, not guessed.

    The assertion is the direction, not the gap: `docs/provenance.md` claims every
    divergence is disarm being **more** current, and disarm falling behind the host is the
    one case it does not describe. The gap itself moves with the interpreter, so pinning a
    number here would only pin this machine.
    """
    import unicodedata

    host = tuple(int(part) for part in unicodedata.unidata_version.split("."))
    ours = tuple(int(part) for part in disarm.UNICODE_VERSION.split("."))
    assert ours >= host, (
        f"disarm normalizes against UCD {disarm.UNICODE_VERSION}, this interpreter "
        f"carries {unicodedata.unidata_version}"
    )


def test_the_two_version_constants_are_different_questions() -> None:
    """They read 17.0.0 both today, which is exactly why this asserts the wiring.

    `CONFUSABLES_VERSION` is parsed from the TSV header by `build.rs`;
    `UNICODE_VERSION` comes from `unicode-normalization`. If the second were ever wired
    to the first, the values would agree forever and nothing would notice — so the check
    is that the confusable constant still tracks its table, independently.
    """
    assert disarm.CONFUSABLES_VERSION == _header_version(LATIN_TSV)
    assert disarm.UNICODE_VERSION != "", "the normalizer version must be populated"


def test_no_source_claims_a_missing_accessor_that_now_exists() -> None:
    """#645 — three files said "there is no runtime accessor for this version yet".

    They were true when written and false the moment the constant shipped, and nothing
    connected the two. The sentence survived in `docs/provenance.md`, the `normalize`
    rustdoc and the Python `normalize` docstring, in the same change that added the
    accessor they denied — one of them two paragraphs above the table announcing it.

    The gate is the negation: if a constant is reachable, no file may say it is not. It
    scans for the phrasing rather than for a specific sentence, because the next instance
    will be worded differently and the point is the claim, not the wording.
    """
    root = Path(__file__).resolve().parent.parent
    # The claim, in the shapes it has actually taken here.
    denial = re.compile(
        r"no runtime accessor|not reachable at runtime|no accessor for (this|that) version",
        re.I,
    )
    searched = [
        root / "docs" / "provenance.md",
        root / "src" / "api" / "text.rs",
        root / "src" / "api" / "metadata.rs",
        root / "python" / "disarm" / "_api.py",
        root / "python" / "disarm" / "__init__.py",
    ]
    offenders = []
    for path in searched:
        if not path.exists():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if denial.search(line):
                offenders.append(f"{path.relative_to(root)}:{number}: {line.strip()}")

    assert not offenders, (
        "these lines say a version has no runtime accessor, but "
        f"UNICODE_VERSION ({disarm.UNICODE_VERSION}), KEY_SCHEMA_VERSION "
        f"({disarm.KEY_SCHEMA_VERSION}) and CONFUSABLES_VERSION "
        f"({disarm.CONFUSABLES_VERSION}) are all reachable:\n  " + "\n  ".join(offenders)
    )
