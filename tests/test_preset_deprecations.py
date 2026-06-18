"""#430: the renamed presets keep working under their old names for one
deprecation cycle (removed in 1.0), each emitting a ``DeprecationWarning`` and
returning byte-identical output to the new name.

    security_clean       -> canonicalize
    display_clean        -> strip_format
    normalize_user_input -> canonicalize_strict
"""

from __future__ import annotations

import warnings

import pytest

import disarm
from disarm import Text

# (deprecated name, new name) for the module-level preset functions.
RENAMES = [
    ("security_clean", "canonicalize"),
    ("display_clean", "strip_format"),
    ("normalize_user_input", "canonicalize_strict"),
]

SAMPLES = ["pаypal", "admin‮user", "  Héllo  wörld  ", "ç̧", "plain"]


@pytest.mark.parametrize("old,new", RENAMES)
@pytest.mark.parametrize("text", SAMPLES)
def test_deprecated_alias_matches_new_name(old: str, new: str, text: str) -> None:
    old_fn = getattr(disarm, old)
    new_fn = getattr(disarm, new)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert old_fn(text) == new_fn(text)


@pytest.mark.parametrize("old,new", RENAMES)
def test_deprecated_alias_warns(old: str, new: str) -> None:
    old_fn = getattr(disarm, old)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        old_fn("test")
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecations, f"{old} did not emit a DeprecationWarning"
    assert new in str(deprecations[0].message), f"{old} should point at {new}"


@pytest.mark.parametrize(
    "old,new",
    [("security_clean", "canonicalize"), ("display_clean", "strip_format")],
)
def test_deprecated_text_builder_method(old: str, new: str) -> None:
    """The Text builder's renamed methods warn and match the new method."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        old_out = str(getattr(Text("pаypal‮"), old)())
    new_out = str(getattr(Text("pаypal‮"), new)())
    assert old_out == new_out

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        getattr(Text("test"), old)()
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
