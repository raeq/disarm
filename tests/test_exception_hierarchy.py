"""#183: translit exposes a unified exception hierarchy.

`TranslitError` (a `ValueError` subclass) is the base for every error translit
raises; `InvalidArgumentError` / `ResourceLimitError` / `UnsupportedError`
categorise it. The headline fix: the five sites that were previously bare
`ValueError` (mutually-exclusive flags, register limits, reverse unsupported
lang) are now caught by `except TranslitError`. Wrong-argument-*type* errors
stay `TypeError` by design.
"""

from __future__ import annotations

import pytest

import translit
from translit import (
    InvalidArgumentError,
    ResourceLimitError,
    TranslitError,
    UnsupportedError,
)


class TestHierarchyStructure:
    def test_subclasses_of_translit_error_and_value_error(self) -> None:
        for E in (InvalidArgumentError, ResourceLimitError, UnsupportedError):
            assert issubclass(E, TranslitError)
            assert issubclass(E, ValueError)

    def test_translit_error_is_value_error(self) -> None:
        assert issubclass(TranslitError, ValueError)

    def test_all_exported(self) -> None:
        for name in (
            "TranslitError",
            "InvalidArgumentError",
            "ResourceLimitError",
            "UnsupportedError",
        ):
            assert name in translit.__all__
            assert hasattr(translit, name)


# (callable, args, kwargs) triggers, paired with the expected subclass.
INVALID_ARGUMENT = [
    (translit.transliterate, ("x",), {"errors": "bogus"}),
    (translit.normalize, ("x",), {"form": "BOGUS"}),
    (translit.transliterate, ("x",), {"lang": "zz"}),
    (translit.transliterate, ("x",), {"lang": "de", "target": "ru"}),
    (translit.transliterate, ("x",), {"strict_iso9": True, "gost7034": True}),
    (translit.slugify, ("x",), {"max_length": -1}),
    (translit.get_pipeline, ("nope",), {}),
    (translit.register_lang, ("xx", {"ab": "x"}), {}),  # multi-char key
]

UNSUPPORTED = [
    (translit.transliterate, ("x",), {"target": "zz"}),  # no reverse table
]


class TestEveryErrorIsTranslitError:
    @pytest.mark.parametrize("fn,args,kwargs", INVALID_ARGUMENT + UNSUPPORTED)
    def test_caught_via_translit_error(self, fn, args, kwargs) -> None:
        with pytest.raises(TranslitError):
            fn(*args, **kwargs)

    @pytest.mark.parametrize("fn,args,kwargs", INVALID_ARGUMENT + UNSUPPORTED)
    def test_still_caught_via_value_error(self, fn, args, kwargs) -> None:
        # Backward compatibility: TranslitError subclasses ValueError.
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
            translit.transliterate(["x"] * (translit._api._MAX_BATCH_SIZE + 1))

    def test_resource_limit_replacements_cap(self) -> None:
        translit.clear_replacements()
        try:
            with pytest.raises(ResourceLimitError):
                translit.register_replacements({str(i): "x" for i in range(10_001)})
        finally:
            translit.clear_replacements()


class TestPreviouslyBareSitesNowUnified:
    """The five sites #180 flagged as bare ValueError that `except TranslitError`
    silently missed are now part of the hierarchy."""

    def test_mutually_exclusive_flags(self) -> None:
        with pytest.raises(InvalidArgumentError):
            translit.transliterate("x", strict_iso9=True, gost7034=True)

    def test_reverse_unsupported_lang(self) -> None:
        with pytest.raises(UnsupportedError):
            translit.transliterate("x", target="zz")

    def test_register_lang_bad_keys(self) -> None:
        with pytest.raises(InvalidArgumentError):
            translit.register_lang("xx", {"ab": "x"})

    def test_register_replacements_limit(self) -> None:
        translit.clear_replacements()
        try:
            with pytest.raises(ResourceLimitError):
                translit.register_replacements({str(i): "x" for i in range(10_001)})
        finally:
            translit.clear_replacements()


class TestWrongTypeStaysTypeError:
    """Wrong argument *type* is a programming error → plain TypeError, not a
    translit domain error (documented in docs/api/exceptions.md)."""

    @pytest.mark.parametrize(
        "fn,arg",
        [
            (translit.transliterate, 123),
            (translit.slugify, 123),
            (translit.normalize, 123),
            (translit.fold_case, 123),
        ],
    )
    def test_typeerror_not_translit_error(self, fn, arg) -> None:
        with pytest.raises(TypeError):
            fn(arg)
        # And it is specifically NOT a TranslitError.
        try:
            fn(arg)
        except TranslitError:  # pragma: no cover
            pytest.fail("wrong-type error should be TypeError, not TranslitError")
        except TypeError:
            pass
