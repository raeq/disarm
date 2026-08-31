"""#660 — `LANG_AUTO` was the one `LANG_*` constant of eighty-four Python never exported.

The constants are declared in `_enums.pyi` and re-exported through `disarm/__init__.py`,
by hand, twice: once in the import list and once in `__all__`. `LANG_AUTO` was in neither,
so `disarm.LANG_AUTO` raised `AttributeError` while three doc blocks told the reader to
import it. Nothing checked, because eighty-three of eighty-four were right and no test
enumerated the set.

The gate is the enumeration: every `LANG_*` name the stub declares must be reachable on
the package and listed in `__all__`. It costs one import and it cannot be satisfied by
adding the next constant to only one of the two places.
"""

from __future__ import annotations

import pathlib
import re

import pytest

import disarm

STUB = pathlib.Path(disarm.__file__).parent / "_enums.pyi"

#: Every `LANG_*` the type stub declares — the authority, because it is what a typed
#: caller sees. Reading the stub rather than `dir(disarm)` is what makes this a gate:
#: a name missing from the runtime is exactly the defect, so the runtime cannot be
#: the source of the expected set.
DECLARED = sorted(set(re.findall(r"^(LANG_[A-Z0-9_]+)\s*:", STUB.read_text(), re.M)))


def test_the_stub_declares_the_constants() -> None:
    """A gate over an empty set passes for the wrong reason."""
    assert len(DECLARED) > 80, len(DECLARED)
    assert "LANG_AUTO" in DECLARED


@pytest.mark.parametrize("name", DECLARED)
def test_every_declared_constant_is_reachable(name: str) -> None:
    assert hasattr(disarm, name), f"disarm.{name} raises AttributeError"


@pytest.mark.parametrize("name", DECLARED)
def test_every_declared_constant_is_in_dunder_all(name: str) -> None:
    """`from disarm import *` and the docs both read `__all__`."""
    assert name in disarm.__all__, f"{name} is importable but absent from __all__"


def test_lang_auto_is_the_documented_sentinel() -> None:
    """Not merely present — it has to be the value the docs promise."""
    assert disarm.LANG_AUTO == "auto"
