"""#183: disarm exposes a unified exception hierarchy.

`DisarmError` (a `ValueError` subclass) is the base for every error disarm
raises; `InvalidArgumentError` / `ResourceLimitError` / `UnsupportedError`
categorise it. The headline fix: the five sites that were previously bare
`ValueError` (mutually-exclusive flags, register limits, reverse unsupported
lang) are now caught by `except DisarmError`. Wrong-argument-*type* errors
stay `TypeError` by design.
"""

from __future__ import annotations

import pytest

import disarm
from disarm import (
    DisarmError,
    InvalidArgumentError,
    ResourceLimitError,
    UnsupportedError,
)


class TestHierarchyStructure:
    def test_subclasses_of_translit_error_and_value_error(self) -> None:
        for E in (InvalidArgumentError, ResourceLimitError, UnsupportedError):
            assert issubclass(E, DisarmError)
            assert issubclass(E, ValueError)

    def test_translit_error_is_value_error(self) -> None:
        assert issubclass(DisarmError, ValueError)

    def test_all_exported(self) -> None:
        for name in (
            "DisarmError",
            "InvalidArgumentError",
            "ResourceLimitError",
            "UnsupportedError",
        ):
            assert name in disarm.__all__
            assert hasattr(disarm, name)


# (callable, args, kwargs) triggers, paired with the expected subclass.
INVALID_ARGUMENT = [
    (disarm.transliterate, ("x",), {"errors": "bogus"}),
    (disarm.normalize, ("x",), {"form": "BOGUS"}),
    (disarm.transliterate, ("x",), {"lang": "zz"}),
    (disarm.transliterate, ("x",), {"lang": "de", "target": "ru"}),
    (disarm.transliterate, ("x",), {"strict_iso9": True, "gost7034": True}),
    (disarm.slugify, ("x",), {"max_length": -1}),
    (disarm.get_pipeline, ("nope",), {}),
    (disarm.register_lang, ("xx", {"ab": "x"}), {}),  # multi-char key
]

UNSUPPORTED = [
    (disarm.transliterate, ("x",), {"target": "zz"}),  # no reverse table
]


class TestEveryErrorIsDisarmError:
    @pytest.mark.parametrize("fn,args,kwargs", INVALID_ARGUMENT + UNSUPPORTED)
    def test_caught_via_translit_error(self, fn, args, kwargs) -> None:
        with pytest.raises(DisarmError):
            fn(*args, **kwargs)

    @pytest.mark.parametrize("fn,args,kwargs", INVALID_ARGUMENT + UNSUPPORTED)
    def test_still_caught_via_value_error(self, fn, args, kwargs) -> None:
        # Backward compatibility: DisarmError subclasses ValueError.
        with pytest.raises(ValueError):
            fn(*args, **kwargs)


class TestCategoryMapping:
    @pytest.mark.parametrize("fn,args,kwargs", INVALID_ARGUMENT)
    def test_invalid_argument(self, fn, args, kwargs) -> None:
        with pytest.raises(InvalidArgumentError):
            fn(*args, **kwargs)

    @pytest.mark.parametrize("fn,args,kwargs", UNSUPPORTED)
    def test_unsupported(self, fn, args, kwargs) -> None:
        with pytest.raises(UnsupportedError):
            fn(*args, **kwargs)

    def test_resource_limit_batch(self) -> None:
        with pytest.raises(ResourceLimitError):
            disarm.transliterate(["x"] * (disarm._api._MAX_BATCH_SIZE + 1))

    def test_resource_limit_replacements_cap(self) -> None:
        disarm.clear_replacements()
        try:
            with pytest.raises(ResourceLimitError):
                disarm.register_replacements({str(i): "x" for i in range(10_001)})
        finally:
            disarm.clear_replacements()


class TestPreviouslyBareSitesNowUnified:
    """The five sites #180 flagged as bare ValueError that `except DisarmError`
    silently missed are now part of the hierarchy."""

    def test_mutually_exclusive_flags(self) -> None:
        with pytest.raises(InvalidArgumentError):
            disarm.transliterate("x", strict_iso9=True, gost7034=True)

    def test_reverse_unsupported_lang(self) -> None:
        with pytest.raises(UnsupportedError):
            disarm.transliterate("x", target="zz")

    def test_register_lang_bad_keys(self) -> None:
        with pytest.raises(InvalidArgumentError):
            disarm.register_lang("xx", {"ab": "x"})

    def test_register_replacements_limit(self) -> None:
        disarm.clear_replacements()
        try:
            with pytest.raises(ResourceLimitError):
                disarm.register_replacements({str(i): "x" for i in range(10_001)})
        finally:
            disarm.clear_replacements()


class TestWrongTypeStaysTypeError:
    """Wrong argument *type* is a programming error → plain TypeError, not a
    disarm domain error (documented in docs/api/exceptions.md)."""

    @pytest.mark.parametrize(
        "fn,arg",
        [
            (disarm.transliterate, 123),
            (disarm.slugify, 123),
            (disarm.normalize, 123),
            (disarm.fold_case, 123),
        ],
    )
    def test_typeerror_not_translit_error(self, fn, arg) -> None:
        with pytest.raises(TypeError):
            fn(arg)
        # And it is specifically NOT a DisarmError.
        try:
            fn(arg)
        except DisarmError:  # pragma: no cover
            pytest.fail("wrong-type error should be TypeError, not DisarmError")
        except TypeError:
            pass
