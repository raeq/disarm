"""Guards on the constants/enum values the wrapper shares with the Rust core.

- ``_MAX_BATCH_SIZE`` is imported from the Rust extension (single source of
  truth, #200); these tests pin that wiring so a future edit cannot quietly
  re-declare a diverging literal.
- The ``errors=`` / ``form=`` enum values are now validated *only* in the Rust
  core (#185) — the Python wrapper no longer keeps a copy. These tests assert the
  core still accepts the full canonical set and rejects an unknown value, so a
  regression in the core's validation is caught here.
"""

from __future__ import annotations

import pytest

import translit
from translit import _api
from translit._translit import _MAX_BATCH_SIZE as _RUST_MAX_BATCH_SIZE

# Canonical sets, defined once in the Rust core. Listed here only so this test
# can assert the core accepts every one of them (not as a wrapper-side copy).
_ERROR_MODES = ("replace", "ignore", "preserve")
_NORM_FORMS = ("NFC", "NFD", "NFKC", "NFKD")


class TestResourceLimitParity:
    def test_max_batch_size_sourced_from_rust(self) -> None:
        # The wrapper must read the Rust value, not a re-declared literal.
        assert _api._MAX_BATCH_SIZE == _RUST_MAX_BATCH_SIZE
        assert _api._MAX_BATCH_SIZE > 0

    def test_batch_guard_reports_the_rust_limit(self) -> None:
        over = ["x"] * (_api._MAX_BATCH_SIZE + 1)
        with pytest.raises((translit.TranslitError, ValueError)) as exc:
            translit.transliterate(over)
        assert str(_api._MAX_BATCH_SIZE) in str(exc.value)


class TestCoreEnumValidation:
    def test_every_error_mode_accepted_by_core(self) -> None:
        # Non-ASCII input reaches the Rust transliteration path for each mode.
        for mode in _ERROR_MODES:
            translit.transliterate("é", errors=mode)

    def test_bogus_error_mode_rejected(self) -> None:
        with pytest.raises(translit.InvalidArgumentError):
            translit.transliterate("é", errors="bogus")  # type: ignore[arg-type]

    def test_every_norm_form_accepted_by_core(self) -> None:
        for form in _NORM_FORMS:
            translit.normalize("é", form=form)

    def test_bogus_norm_form_rejected(self) -> None:
        with pytest.raises(translit.InvalidArgumentError):
            translit.normalize("é", form="BOGUS")  # type: ignore[arg-type]

    def test_validation_runs_on_pure_ascii_input(self) -> None:
        # #185 / #210 review: the deleted Python fast paths short-circuited ASCII
        # input *before* validating, so the core must reject an invalid form /
        # errors even when the input is all-ASCII. This guards against a
        # regression that reintroduces an ASCII short-circuit ahead of validation
        # (which non-ASCII test inputs above would not catch).
        with pytest.raises(translit.InvalidArgumentError):
            translit.normalize("abc", form="BOGUS")  # type: ignore[arg-type]
        with pytest.raises(translit.InvalidArgumentError):
            translit.transliterate("abc", errors="bogus")  # type: ignore[arg-type]
        # ...while valid all-ASCII calls still take the fast identity path.
        assert translit.normalize("abc", form="NFC") == "abc"
