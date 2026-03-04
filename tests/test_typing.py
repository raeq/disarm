"""Verify that translit's type stubs satisfy mypy and pyright.

These tests shell out to mypy --strict and verify that valid usage
passes and invalid usage is rejected.
"""

import subprocess
import textwrap
import tempfile

import pytest


def _check_mypy(code: str) -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        f.flush()
        return subprocess.run(
            ["mypy", "--strict", f.name],
            capture_output=True,
            text=True,
        )


@pytest.mark.slow
class TestMypy:
    """mypy validation tests."""

    def test_transliterate_types(self) -> None:
        result = _check_mypy(
            textwrap.dedent("""\
            from translit import transliterate
            x: str = transliterate("café")
            y: str = transliterate("München", lang="de", errors="preserve")
        """)
        )
        assert result.returncode == 0, result.stdout

    def test_slugify_types(self) -> None:
        result = _check_mypy(
            textwrap.dedent("""\
            from translit import slugify
            x: str = slugify("Hello World", separator="_", max_length=50)
        """)
        )
        assert result.returncode == 0, result.stdout

    def test_bad_literal_rejected(self) -> None:
        result = _check_mypy(
            textwrap.dedent("""\
            from translit import transliterate
            transliterate("test", errors="explode")  # should fail
        """)
        )
        assert result.returncode != 0  # mypy rejects invalid Literal

    def test_script_enum(self) -> None:
        result = _check_mypy(
            textwrap.dedent("""\
            from translit import detect_scripts, Script
            scripts: list[Script] = detect_scripts("Hello мир")
            assert Script.LATIN in scripts
        """)
        )
        assert result.returncode == 0, result.stdout

    def test_pipeline_callable(self) -> None:
        result = _check_mypy(
            textwrap.dedent("""\
            from translit import TextPipeline
            pipe = TextPipeline(normalize="NFKC", transliterate=True)
            result: str = pipe("Hello")
        """)
        )
        assert result.returncode == 0, result.stdout

    def test_unique_slugifier_callback(self) -> None:
        result = _check_mypy(
            textwrap.dedent("""\
            from translit import UniqueSlugifier
            def exists_in_db(slug: str) -> bool:
                return False
            s = UniqueSlugifier(check=exists_in_db)
            result: str = s("Hello World")
        """)
        )
        assert result.returncode == 0, result.stdout
