"""#641: the extractor behind the docs-vs-release gate does what it claims.

``scripts/check_docs_against_release.py`` compares every ``disarm`` name the
documentation uses against the newest *published* wheel. That comparison runs in
``.github/workflows/docs-release-drift.yml``, on a schedule, against an artifact
this test suite has no access to.

What is testable here is the half that decides *which names count*. An extractor
that quietly matches nothing produces a permanently green gate, which is worse
than no gate — so the cases below pin both directions: the forms that must be
found, and the near-misses that must not be.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# Import the checker directly (it lives in scripts/, not on the path) — same
# idiom as tests/test_excluded_compositions_sync.py.
_spec = importlib.util.spec_from_file_location(
    "check_docs_against_release", REPO / "scripts" / "check_docs_against_release.py"
)
assert _spec and _spec.loader
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


def _names(markdown: str) -> set[str]:
    """Every disarm name the extractor finds in a Markdown fragment."""
    found: set[str] = set()
    for body, _ in checker._python_blocks(markdown):
        found |= {dotted for dotted, _ in checker._names_from_python(body)}
    found |= {m.group(1) for m in checker._MKDOCSTRINGS_RE.finditer(markdown)}
    found |= {dotted for dotted, _ in checker.prose_names(markdown)}
    return found


class TestExtractsWhatAReaderWouldRun:
    """The three sources the gate reads, each a claim a reader can act on."""

    def test_from_import_in_a_python_block(self) -> None:
        assert "disarm.canonicalize" in _names(
            "```python\nfrom disarm import canonicalize\ncanonicalize('x')\n```\n"
        )

    def test_multiple_names_in_one_import(self) -> None:
        found = _names("```python\nfrom disarm import search_key, catalog_key, sort_key\n```\n")
        assert {"disarm.search_key", "disarm.catalog_key", "disarm.sort_key"} <= found

    def test_parenthesised_multiline_import(self) -> None:
        found = _names(
            "```python\nfrom disarm import (\n    slugify,\n    transliterate,\n)\n```\n"
        )
        assert {"disarm.slugify", "disarm.transliterate"} <= found

    def test_aliased_import_reports_the_real_name(self) -> None:
        """``as`` renames the local binding, not the thing that has to exist."""
        found = _names("```python\nfrom disarm import canonicalize as clean\n```\n")
        assert "disarm.canonicalize" in found
        assert "disarm.clean" not in found

    def test_attribute_access(self) -> None:
        assert "disarm.normalize" in _names(
            "```python\nimport disarm\ndisarm.normalize('x')\n```\n"
        )

    def test_submodule_path(self) -> None:
        assert "disarm.codec.detect_encoding" in _names(
            "```python\nimport disarm\ndisarm.codec.detect_encoding(b'x')\n```\n"
        )

    def test_pycon_session(self) -> None:
        """``>>>`` blocks are most of the user guide and are not valid Python."""
        assert "disarm.has_anomalies" in _names(
            "```pycon\n>>> import disarm\n>>> disarm.has_anomalies('x')\nTrue\n```\n"
        )

    def test_mkdocstrings_directive(self) -> None:
        """An API page whose identifier is gone renders an empty section."""
        assert "disarm.find_key_collisions" in _names("::: disarm.find_key_collisions\n")

    def test_inline_code_span_in_prose(self) -> None:
        assert "disarm.strip_obfuscation" in _names(
            "Reach for `disarm.strip_obfuscation` instead.\n"
        )

    def test_inline_span_with_call_parens(self) -> None:
        assert "disarm.fold_case" in _names("Call `disarm.fold_case()` first.\n")

    def test_a_block_that_does_not_parse_still_yields_names(self) -> None:
        """Docs contain deliberately broken snippets; they still make claims."""
        assert "disarm.canonicalize" in _names(
            "```python\ndisarm.canonicalize(  # intentionally unfinished\n```\n"
        )


class TestDoesNotInventNames:
    """Every false positive here is a name no release could ever provide, so
    each one would make the gate permanently red and then permanently ignored."""

    @pytest.mark.parametrize(
        "markdown",
        [
            pytest.param("See <https://docs.disarm.dev/> for more.\n", id="bare-url"),
            pytest.param("Visit `docs.disarm.dev` for the site.\n", id="hostname-in-code-span"),
            pytest.param("Install it with `pip install disarm`.\n", id="install-command"),
            pytest.param("The Ruby entry point is `disarm.rb`.\n", id="filename"),
            pytest.param("```rust\nlet x = disarm::api::canonicalize(s);\n```\n", id="rust-path"),
            pytest.param("```ts\nimport { canonicalize } from 'disarm';\n```\n", id="typescript"),
            pytest.param(
                "```bash\npip install disarm && python -c 'import disarm'\n```\n", id="shell"
            ),
        ],
    )
    def test_non_python_mentions_are_not_names(self, markdown: str) -> None:
        assert _names(markdown) == set()

    def test_a_ruby_block_naming_the_gem_is_not_a_python_name(self) -> None:
        assert _names("```ruby\nrequire 'disarm'\nDisarm.canonicalize('x')\n```\n") == set()


class TestResolution:
    """``resolve`` is what turns a name into a pass or a fail."""

    def test_a_real_entry_point_resolves(self) -> None:
        assert checker.resolve("disarm.canonicalize") is True

    def test_an_invented_name_does_not(self) -> None:
        assert checker.resolve("disarm.definitely_not_an_entry_point") is False

    def test_a_submodule_resolves_even_before_it_is_imported(self) -> None:
        """A submodule is not an attribute of its parent until something imports
        it, so a plain ``getattr`` would report a false failure."""
        assert checker.resolve("disarm.codec.detect_encoding") is True

    def test_an_unimportable_top_level_package_does_not_resolve(self) -> None:
        assert checker.resolve("nosuchpackage.anything") is False

    def test_private_names_are_out_of_scope(self) -> None:
        """A private name's absence from a release is not a broken promise, so
        the gate must not fail on one."""
        assert checker.resolve("disarm._core._not_real_at_all") is True


class TestTheGateIsPointedAtSomething:
    """A gate that scans nothing passes everything."""

    def test_the_default_roots_exist(self) -> None:
        for root in checker._DEFAULT_ROOTS:
            assert (REPO / root).exists(), root

    def test_it_finds_a_substantial_surface(self) -> None:
        """Guards the failure mode where a regex change silently matches nothing.

        The floor is well under the real count (111 at the time of writing) so
        ordinary docs edits do not move it; it only fires if extraction breaks.
        """
        refs = checker.collect(checker._markdown_files(list(checker._DEFAULT_ROOTS)))
        assert len({r.dotted for r in refs}) > 60

    def test_all_three_sources_contribute(self) -> None:
        refs = checker.collect(checker._markdown_files(list(checker._DEFAULT_ROOTS)))
        assert {r.source for r in refs} == {"code", "mkdocstrings", "prose"}

    def test_record_directories_are_excluded(self) -> None:
        """``docs/reviews/`` and ``docs/plans/`` are dated snapshots of a past
        state. Correcting their API names would falsify the record, so they are
        not scanned — and neither is in mkdocs' nav."""
        scanned = checker._markdown_files(["docs"])
        assert scanned, "docs/ produced no files at all"
        for path in scanned:
            assert not checker._EXCLUDED_DIRS.intersection(path.parts), path


class TestKnownGapsRatchet:
    """The allowlist is where findings go to die unless it is policed."""

    def test_every_gap_cites_an_issue(self) -> None:
        for name, reason in checker._KNOWN_GAPS.items():
            assert re.search(r"#\d+", reason), f"{name} has no issue number: {reason!r}"

    def test_every_gap_is_actually_named_by_the_docs(self) -> None:
        """An entry for a name the docs no longer mention is dead weight, and it
        would mask the name coming back."""
        refs = checker.collect(checker._markdown_files(list(checker._DEFAULT_ROOTS)))
        documented = {r.dotted for r in refs}
        for name in checker._KNOWN_GAPS:
            assert name in documented, f"{name} is allowlisted but no page names it"
