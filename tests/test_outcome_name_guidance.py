"""#654 — a reader who asks for `disarm.clean` gets the naming rule, not a bare error.

CONTRIBUTING.md's rule is that a public name describes the operation and never the
outcome, so `clean`, `sanitize` and `safe` will never exist. That leaves the reader who
reaches for one holding an `AttributeError` at exactly the moment they are asking the
question the threat model answers.

The hook refuses and explains in the same breath. It promises nothing, so it is compatible
with the rule it teaches.

The issue named two things to check before this lands, and both are tests here: that no
tooling needs `dir()` and `getattr()` to agree, and that the hook cannot mask a genuine
`AttributeError` raised from inside an import.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

import disarm
from disarm import _OUTCOME_NAMES


@pytest.mark.parametrize("name", sorted(_OUTCOME_NAMES))
def test_each_outcome_name_explains_itself(name: str) -> None:
    with pytest.raises(AttributeError) as excinfo:
        getattr(disarm, name)
    message = str(excinfo.value)
    assert name in message
    assert "never the outcome" in message
    assert "canonicalize()" in message
    assert "encode at the sink" in message, "the threat model pointer is the point"


@pytest.mark.parametrize("name", sorted(_OUTCOME_NAMES))
def test_the_exception_still_carries_its_name_and_obj(name: str) -> None:
    """`AttributeError.name` is what `did-you-mean` tooling and REPLs read.

    Raising a bare message would work for a human and break every tool that introspects
    the exception, which is a worse trade than the one this hook is making.
    """
    with pytest.raises(AttributeError) as excinfo:
        getattr(disarm, name)
    assert excinfo.value.name == name
    assert excinfo.value.obj is disarm


def test_an_unrelated_missing_name_gets_the_ordinary_message() -> None:
    """The hook must be invisible for every name it is not about."""
    with pytest.raises(AttributeError) as excinfo:
        disarm.definitely_not_a_real_attribute  # noqa: B018
    message = str(excinfo.value)
    assert message == ("module 'disarm' has no attribute 'definitely_not_a_real_attribute'")
    assert "never the outcome" not in message


def test_hasattr_and_getattr_with_a_default_still_work() -> None:
    """The first of the two checks #654 asked for.

    Nothing may require `dir()` and `getattr()` to agree — but the ordinary protocols
    that build on `__getattr__` must keep working, or the hook breaks callers rather than
    teaching them.
    """
    for name in _OUTCOME_NAMES:
        assert not hasattr(disarm, name)
        assert getattr(disarm, name, "fallback") == "fallback"
    assert hasattr(disarm, "canonicalize")


def test_no_outcome_name_is_in_dir_or_all() -> None:
    """`dir()` and `__all__` do not advertise what the hook refuses."""
    exported = set(disarm.__all__) | set(dir(disarm))
    assert not (exported & _OUTCOME_NAMES)


def test_the_hook_does_not_mask_an_attributeerror_from_an_import() -> None:
    """The second check #654 asked for.

    A module-level `__getattr__` that swallowed an `AttributeError` raised *during* an
    import would turn a real failure into "no such attribute". This one re-raises for
    every name outside the set, so an import error surfaces as itself. Checked in a
    subprocess, since it needs a genuinely failing import against the real package.
    """
    script = (
        "import disarm, importlib\n"
        "try:\n"
        "    importlib.import_module('disarm.does_not_exist')\n"
        "except ModuleNotFoundError as exc:\n"
        "    print('ModuleNotFoundError:', exc.name)\n"
        "except AttributeError as exc:\n"
        "    print('MASKED:', exc)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    ).stdout
    assert out.startswith("ModuleNotFoundError:"), out
    assert "MASKED" not in out


def test_the_callable_module_still_works() -> None:
    """`__class__` is reassigned to a custom type; the hook must not disturb that.

    An earlier version of this was called "picklable" and pickled the *return value* of
    `canonicalize` — a plain `str`, which proves nothing about the module (#861 review).
    What is worth asserting is that reassigned `__class__`: `disarm(...)` is shorthand for
    `transliterate`, and adding `__getattr__` to that class must not break it.
    """
    assert disarm("Привет") == disarm.transliterate("Привет")
    assert type(disarm).__name__ == "_CallableModule", (
        "the module's __class__ is no longer the callable type the hook lives on"
    )
    assert "__getattr__" in vars(type(disarm)), (
        "the hook is not on _CallableModule, so it is not reached by attribute lookup"
    )


def test_the_guidance_names_only_things_that_exist() -> None:
    """A pointer to a function that has been renamed is worse than no pointer."""
    from disarm import _OUTCOME_GUIDANCE

    for named in ("canonicalize", "strip_format", "get_pipeline", "sanitize_filename"):
        assert named in _OUTCOME_GUIDANCE
        assert hasattr(disarm, named), f"the guidance points at a missing {named}"
