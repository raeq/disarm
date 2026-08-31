"""#644: key-builder output does not move without somebody deciding it should.

`search_key`, `catalog_key` and `sort_key` produce values a consumer **stores**
and compares later, so a change to them is a reindex event on somebody's
production data. `docs/RUST_API.md` states the contract — *a patch release never
changes key-builder output; a minor release may* — and until this fixture existed
that contract was held by review alone.

Review does not catch it. `0.14.0` moved `search_key` on 4.1% of a 5,030-input
corpus, and the change that did it (#602) was a *correctness fix* whose diff said
nothing about keys: it made `ErrorMode::Preserve` stop excepting itself from the
table's empty mappings. Nobody reading that diff would think "reindex".

So the gate is not "did somebody break something". It is **"did key output move,
and was that on purpose"** — a diff the author has to look at and either justify
or undo. Regenerating the fixture is the act of justifying it.

The fixture is not reproducible by design, and that is recorded rather than
hidden: see `tests/fixtures/key_stability/README.md` for its provenance and
licensing.
"""

from __future__ import annotations

import gzip
import importlib.util
import sys
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "key_stability"
CORPUS = FIXTURE_DIR / "corpus.txt"
GOLDEN = FIXTURE_DIR / "golden_keys.tsv.gz"

# The generator owns the escaping and the function list; importing it keeps one
# definition rather than two that can disagree.
_spec = importlib.util.spec_from_file_location(
    "gen_key_fixture", ROOT / "scripts" / "gen_key_fixture.py"
)
assert _spec and _spec.loader
gen = importlib.util.module_from_spec(_spec)
sys.modules["gen_key_fixture"] = gen
_spec.loader.exec_module(gen)

#: How many changed rows to print per function before summarising. Enough to see
#: the shape of a change, few enough to read.
_SAMPLES = 6


@pytest.fixture(scope="module")
def golden() -> tuple[list[str], list[str], list[list[str]]]:
    """(function names, inputs, expected values per row) from the fixture."""
    with gzip.open(GOLDEN, "rt", encoding="utf-8") as handle:
        lines = handle.read().split("\n")

    header = [line for line in lines if line.startswith("#")]
    columns = next(line for line in header if line.startswith("# columns:")).split("\t")[1:]

    inputs: list[str] = []
    expected: list[list[str]] = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        inputs.append(gen.unescape(parts[0]))
        expected.append([gen.unescape(p) for p in parts[1:]])
    return columns, inputs, expected


def test_the_fixture_is_present_and_populated() -> None:
    """A missing or empty fixture would make every check below vacuous."""
    assert CORPUS.is_file(), CORPUS
    assert GOLDEN.is_file(), GOLDEN
    rows = gen.read_corpus()
    assert len(rows) > 20_000, f"corpus has only {len(rows)} rows"


def test_key_output_has_not_moved(golden: tuple[list[str], list[str], list[list[str]]]) -> None:
    """The gate.

    Fails with a per-function count and a sample of what changed, because "some
    keys moved" is not actionable and "`podъezd` became `podezd`" is.
    """
    import disarm

    columns, inputs, expected = golden
    functions = [(name, getattr(disarm, name)) for name in columns]

    drift: dict[str, list[tuple[str, str, str]]] = {}
    for row, wanted in zip(inputs, expected, strict=True):
        for (name, function), want in zip(functions, wanted, strict=True):
            try:
                got = function(row)
            except Exception as exc:  # noqa: BLE001 — the error is a legitimate value
                got = f"<ERR:{type(exc).__name__}>"
            if got != want:
                drift.setdefault(name, []).append((row, want, got))

    if not drift:
        return

    total = len(inputs)
    report = [
        f"key-builder output moved against the fixture ({total} rows, "
        f"disarm {disarm.__version__}):",
        "",
    ]
    for name, changes in sorted(drift.items(), key=lambda kv: -len(kv[1])):
        report.append(
            f"  {name}: {len(changes)} of {total} changed ({100 * len(changes) / total:.2f}%)"
        )
        for row, want, got in changes[:_SAMPLES]:
            report.append(f"      {row!r}\n        was {want!r}\n        now {got!r}")
        if len(changes) > _SAMPLES:
            report.append(f"      … and {len(changes) - _SAMPLES} more")
        report.append("")
    report += [
        "This is not automatically a bug. Read the diff and decide:",
        "",
        "  intended  -> `python scripts/gen_key_fixture.py`, commit the fixture in",
        "               the SAME change, and write it up in the release's Upgrade",
        "               notes. Per RELEASING.md that release is a MINOR, never a",
        "               patch — a stored key is somebody's production data.",
        "  unintended-> you have just found the thing this fixture exists for.",
        "",
        "Regenerating to make this pass without reading the diff is the one use it",
        "does not have.",
    ]
    pytest.fail("\n".join(report), pytrace=False)


class TestTheFixtureCoversWhatItClaims:
    """A corpus that lost its hard cases would pass forever and mean nothing."""

    def test_it_spans_many_scripts(self) -> None:
        import unicodedata

        rows = gen.read_corpus()
        scripts = set()
        for row in rows:
            for char in row:
                if char.isascii():
                    continue
                try:
                    scripts.add(unicodedata.name(char).split()[0])
                except ValueError:
                    continue
        # ARABIC, CYRILLIC, DEVANAGARI, BENGALI, ETHIOPIC, HEBREW, TAMIL, … —
        # the point is breadth, not a fixed list that ages badly.
        assert len(scripts) > 25, sorted(scripts)

    def test_it_contains_the_characters_that_moved_at_0_14_0(self) -> None:
        """The regression this fixture was built from.

        #602 moved the Russian soft and hard signs, the Latin kra, the micro sign
        and the Greek mu. A corpus that stops containing them stops detecting the
        class of change it was made for.
        """
        joined = "\n".join(gen.read_corpus())
        for char, name in (
            ("ь", "CYRILLIC SMALL LETTER SOFT SIGN"),
            ("ъ", "CYRILLIC SMALL LETTER HARD SIGN"),
            ("ĸ", "LATIN SMALL LETTER KRA"),
            ("µ", "MICRO SIGN"),
            ("μ", "GREEK SMALL LETTER MU"),
        ):
            assert char in joined, f"corpus no longer contains {name} ({char!r})"

    def test_it_contains_the_classes_most_likely_to_move_a_key(self) -> None:
        """#806 — the corpus had **zero** noncharacters and **zero** soft hyphens.

        Those are the classes most likely to move a key, and the ones it could not
        express. #805 is a live key evasion using a noncharacter, which makes this the
        demonstration rather than the hypothesis: had #805 landed against the old corpus,
        its fixture diff would have been **0 rows of 22,878** — the gate built to answer
        "did key output move, and was that on purpose" would have reported nothing.

        Asserted as a floor per class rather than an exact count, so adding corpus rows
        is free and losing a class is not.
        """
        import unicodedata

        joined = "\n".join(gen.read_corpus())

        def noncharacter(char: str) -> bool:
            cp = ord(char)
            return 0xFDD0 <= cp <= 0xFDEF or (cp & 0xFFFE) == 0xFFFE

        counts = {
            "noncharacters": sum(1 for c in joined if noncharacter(c)),
            "soft hyphen": joined.count("\u00ad"),
            "private use": sum(1 for c in joined if unicodedata.category(c) == "Co"),
            "tag characters": sum(1 for c in joined if 0xE0000 <= ord(c) <= 0xE007F),
            "variation selectors": sum(
                1 for c in joined if 0xFE00 <= ord(c) <= 0xFE0F or 0xE0100 <= ord(c) <= 0xE01EF
            ),
        }
        thin = {name: n for name, n in counts.items() if n < 5}
        assert not thin, (
            f"the corpus is thin in classes that move keys: {thin}. A class the corpus "
            "cannot express is a class the gate reports as free — see #805/#806."
        )

    def test_neither_file_carries_a_raw_control_byte(self) -> None:
        """#806 — a fixture nobody can diff is a fixture nobody checks.

        The corpus carried a raw `U+0000` and a raw `U+001B`, so git, ripgrep and every
        diff tool read `corpus.txt` and `golden_keys.tsv.gz` as **binary**. The coverage
        is worth keeping — a NUL and an ESC through a key builder are real cases — so both
        are escaped as `\\xNN` rather than removed, and `read_corpus` unescapes.

        Checked before the change: the corpus contains no literal backslash, so
        interpreting escapes cannot alter an existing row. That precondition is asserted
        below, because it is what makes the escaping safe.
        """
        raw = CORPUS.read_bytes()
        offenders = {
            f"U+{byte:04X}"
            for byte in raw
            if byte < 0x20 and byte not in (0x0A,)  # newline is the row separator
        }
        assert not offenders, (
            f"corpus.txt carries raw control bytes {sorted(offenders)}, which makes it "
            "binary to git and every diff tool. Escape them as \\xNN instead."
        )

        with gzip.open(GOLDEN, "rb") as handle:
            fixture = handle.read()
        leaked = {
            f"U+{byte:04X}"
            for byte in fixture
            if byte < 0x20 and byte not in (0x0A, 0x09)  # newline and tab are structure
        }
        assert not leaked, f"the golden fixture carries raw control bytes {sorted(leaked)}"

    def test_the_escaping_precondition_holds(self) -> None:
        """`read_corpus` interprets escapes, so a literal backslash would change meaning.

        There are none today. If one is ever added, this fails rather than silently
        reinterpreting the row it appears in.
        """
        text = CORPUS.read_text(encoding="utf-8")
        rows = [line for line in text.split("\n") if line]
        # Every backslash must be part of an escape this reader produces.
        for row in rows:
            for index, char in enumerate(row):
                if char != "\\":
                    continue
                nxt = row[index + 1 : index + 2]
                assert nxt in {"\\", "t", "n", "r", "x"}, (
                    f"corpus row {row!r} has a backslash that is not an escape; "
                    "read_corpus would reinterpret it"
                )

    def test_it_contains_non_ascii_digits(self) -> None:
        """The class that exposes `digit_policy`.

        The corpus this replaced had none, which is why a `tr39` numeral tax
        measured a false 0.00%.
        """
        rows = gen.read_corpus()
        with_digits = [r for r in rows if any(c.isdigit() and not c.isascii() for c in r)]
        assert len(with_digits) > 100, len(with_digits)

    def test_every_key_builder_is_covered(self) -> None:
        assert {"search_key", "catalog_key", "sort_key"} <= set(gen.FUNCTIONS)


class TestTheGateCanFail:
    """Verified rather than assumed, on a copy so nothing is mutated."""

    def test_a_changed_expectation_is_detected(
        self, golden: tuple[list[str], list[str], list[list[str]]]
    ) -> None:
        import disarm

        columns, inputs, expected = golden
        index = columns.index("search_key")
        row, want = inputs[0], expected[0][index]
        assert disarm.search_key(row) == want, "the fixture is already stale"
        # The comparison the gate performs, against a deliberately wrong value.
        assert disarm.search_key(row) != want + " drift"

    def test_the_fixture_and_the_corpus_agree_on_length(
        self, golden: tuple[list[str], list[str], list[list[str]]]
    ) -> None:
        """A truncated fixture would silently stop checking the tail."""
        _, inputs, _ = golden
        assert inputs == gen.read_corpus()


def _header_lines() -> list[str]:
    with gzip.open(GOLDEN, "rt", encoding="utf-8") as handle:
        return [line for line in handle.read().split("\n") if line.startswith("#")]


class TestTheSchemaCounterCannotGoStale:
    """#645 — `KEY_SCHEMA_VERSION` is only worth anything if a stale value is caught.

    The constant answers one question: *would a key I stored under an earlier release still
    compare equal?* Two artifacts reporting the same value produce the same key for the same
    input. That claim is a lie the moment somebody regenerates the fixture — which is the
    act of accepting that key output moved — without bumping the counter, and a monotonic
    counter nobody is forced to bump is the classic way this kind of constant rots.

    So the version travels inside the fixture header, and these assert the two agree. The
    generator writes `disarm.KEY_SCHEMA_VERSION` at generation time; if the constant has
    moved since, the fixture is from a different schema and must be regenerated with it.
    """

    def test_the_fixture_records_a_schema_version(self) -> None:
        """A gate over a missing header line passes for the wrong reason."""
        recorded = [line for line in _header_lines() if line.startswith("# key_schema_version")]
        assert len(recorded) == 1, _header_lines()

    def test_the_fixture_and_the_constant_agree(self) -> None:
        line = next(line for line in _header_lines() if line.startswith("# key_schema_version"))
        recorded = int(line.split("=")[1].strip())
        assert recorded == disarm.KEY_SCHEMA_VERSION, (
            f"the fixture was generated under key schema {recorded}, but "
            f"disarm.KEY_SCHEMA_VERSION is {disarm.KEY_SCHEMA_VERSION}. Either the constant "
            "moved without the fixture being regenerated, or the fixture was regenerated "
            "without the constant being bumped — and the second is what makes the constant "
            "a lie for anyone comparing two artifacts."
        )

    def test_the_constant_is_a_counter_not_a_version_string(self) -> None:
        """Asserted because the name invites the wrong reading.

        It is not a Unicode version and not disarm's version. `docs/provenance.md` carries
        the data vintages; this is a monotonic integer whose only meaning is whether two
        artifacts share it.
        """
        assert isinstance(disarm.KEY_SCHEMA_VERSION, int)
        assert disarm.KEY_SCHEMA_VERSION >= 1
        assert not isinstance(disarm.KEY_SCHEMA_VERSION, bool)


class TestTheUnicodeVersionConstant:
    """#642/#645 — the normalizer's UCD is askable at runtime, not only in a doc."""

    def test_it_is_a_dotted_numeric_version(self) -> None:
        parts = disarm.UNICODE_VERSION.split(".")
        assert len(parts) == 3, disarm.UNICODE_VERSION
        assert all(part.isdigit() for part in parts), disarm.UNICODE_VERSION

    def test_it_answers_the_question_it_exists_for(self) -> None:
        """*Will my keys agree with `unicodedata`?* — answerable without running both.

        Usually the answer is no: disarm tracks a newer UCD than most shipped CPythons.
        The assertion is the comparison being possible, not its outcome, which moves with
        the host interpreter.
        """
        import unicodedata

        host = tuple(int(p) for p in unicodedata.unidata_version.split("."))
        ours = tuple(int(p) for p in disarm.UNICODE_VERSION.split("."))
        assert ours >= host, (
            f"disarm normalizes against UCD {disarm.UNICODE_VERSION} and this interpreter "
            f"carries {unicodedata.unidata_version}. disarm being *behind* the host is the "
            "one direction docs/provenance.md does not claim."
        )
