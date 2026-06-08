"""#186: error messages are enriched into actionable feedback.

- Unknown lang / encoding get a "did you mean …?" hint for a near miss (and
  none for a wildly-wrong input).
- A failed regex echoes the offending pattern.
- The reverse unsupported-lang message quotes the lang plainly ('xx', not the
  `{:?}` `"xx"`).
"""

from __future__ import annotations

import pytest

import translit
from translit import InvalidArgumentError, UnsupportedError


class TestDidYouMean:
    def test_unknown_lang_near_miss_suggests(self) -> None:
        with pytest.raises(InvalidArgumentError) as exc:
            translit.transliterate("x", lang="ge")  # meant "de"
        assert "did you mean 'de'?" in str(exc.value)

    def test_unknown_lang_far_gets_no_suggestion(self) -> None:
        with pytest.raises(InvalidArgumentError) as exc:
            translit.transliterate("x", lang="zzzz")
        assert "did you mean" not in str(exc.value)
        # ...but the full list of valid codes is still offered.
        assert "one of:" in str(exc.value)

    def test_unknown_encoding_near_miss_suggests(self) -> None:
        with pytest.raises(InvalidArgumentError) as exc:
            translit.decode_to_utf8(b"x", "shift_jus")  # meant "shift_jis"
        assert "did you mean 'shift_jis'?" in str(exc.value)

    def test_unknown_encoding_far_gets_no_suggestion(self) -> None:
        with pytest.raises(InvalidArgumentError) as exc:
            translit.decode_to_utf8(b"x", "qwertyuiop")
        assert "did you mean" not in str(exc.value)


class TestEnrichedDetail:
    def test_regex_error_echoes_pattern(self) -> None:
        with pytest.raises(InvalidArgumentError) as exc:
            translit.slugify("x", regex_pattern="[")
        msg = str(exc.value)
        assert 'regex_pattern "["' in msg  # the offending pattern is echoed

    def test_reverse_unsupported_lang_quotes_plainly(self) -> None:
        with pytest.raises(UnsupportedError) as exc:
            translit.transliterate("x", target="zz")
        msg = str(exc.value)
        assert "lang 'zz'" in msg  # not lang="zz"
        assert 'lang="zz"' not in msg


class TestCauseChains:
    """#188: an error that wraps an underlying failure surfaces it as __cause__,
    instead of only flattening it into the message."""

    def test_regex_compile_chains_cause(self) -> None:
        try:
            translit.slugify("x", regex_pattern="[")
        except InvalidArgumentError as e:
            assert e.__cause__ is not None, "expected a chained cause"
            assert isinstance(e.__cause__, ValueError)
            assert "regex parse error" in str(e.__cause__)
        else:  # pragma: no cover
            pytest.fail("expected InvalidArgumentError")

    def test_non_wrapping_error_has_no_cause(self) -> None:
        # A plain validation error wraps nothing — no spurious __cause__.
        try:
            translit.transliterate("x", lang="zz")
        except InvalidArgumentError as e:
            assert e.__cause__ is None
        else:  # pragma: no cover
            pytest.fail("expected InvalidArgumentError")
