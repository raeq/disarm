"""The `Script` enum must be able to name every script the core resolves (#775).

`detect_scripts` maps each name the Rust core returns onto a `Script` member. When the
enum has no member for it, `python/disarm/_api.py` warns — telling the user to report a
bug — and **drops the script from the result**. Non-empty input, empty list:

    >>> disarm.detect_scripts("ᯀᯁ")          # BATAK LETTER A, BATAK SIMALUNGUN A
    UserWarning: Rust detected script 'Batak' which is not in the Script enum; ...
    []

Four names were in that state — Batak, Buhid, Hanunoo and Tagbanwa, 160 assigned code
points. The warning already knew it was a bug. Nothing asserted on it, so it shipped.

This walks the code point space with warnings promoted to errors, which is the only way
to catch the class rather than the four instances: a future core table gaining a script
the enum does not know fails here instead of silently shortening someone's result.
"""

from __future__ import annotations

import warnings

import pytest

import disarm
from disarm import Script

#: Skipped in the sweep. Surrogates are not scalar values and `chr()` output for them
#: cannot cross the FFI boundary.
_SURROGATES = range(0xD800, 0xE000)


def _unnameable_scripts() -> dict[str, int]:
    """Script names the core emits that `Script` cannot spell, with a code point count."""
    found: dict[str, int] = {}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for cp in range(0x110000):
            if cp in _SURROGATES:
                continue
            caught.clear()
            disarm.detect_scripts(chr(cp))
            for entry in caught:
                message = str(entry.message)
                if "not in the Script enum" in message:
                    name = message.split("script '")[1].split("'")[0]
                    found[name] = found.get(name, 0) + 1
    return found


@pytest.mark.formal
def test_every_script_the_core_resolves_has_an_enum_member() -> None:
    """Tier 3: one pass over the whole code point space."""
    unnameable = _unnameable_scripts()
    assert not unnameable, (
        "the core resolves scripts the Script enum cannot name, so `detect_scripts` "
        "drops them and returns a shorter list than the input warrants: "
        + ", ".join(f"{name} ({count} code points)" for name, count in sorted(unnameable.items()))
        + ". Add each to Script and SCRIPT_META in python/disarm/_enums.py."
    )


@pytest.mark.parametrize(
    ("sample", "script_name"),
    [("ᯀᯁ", "Batak"), ("ᝀ", "Buhid"), ("ᜠ", "Hanunoo"), ("ᝠ", "Tagbanwa")],
)
def test_the_four_scripts_775_found_resolve(sample: str, script_name: str) -> None:
    """Tier 1 regression for the instances, so the class gate can stay tier 3.

    Parametrised on the script *name* rather than on `Script.BATAK` and friends. An
    attribute reference in the decorator is evaluated at collection, so removing a member
    would break the whole module with an `AttributeError` before either test ran — the
    sweep below included. A name resolves inside the test body and fails as an assertion,
    which is both a better diagnostic and what lets the sweep still report.

    Warnings are errors here: returning the right script while still warning would be a
    different defect wearing the same result.
    """
    assert hasattr(Script, script_name.upper()), (
        f"Script has no member for {script_name!r}, which the core resolves. "
        f"`detect_scripts` will warn and drop it."
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert disarm.detect_scripts(sample) == [Script(script_name)]


def test_every_enum_member_round_trips_through_script_info() -> None:
    """A member the enum can name but `script_info` cannot describe is the same gap one
    step further on. `_enums.py` asserts this at import; this asserts it from outside."""
    for member in Script:
        if member.value in ("Common", "Inherited"):
            continue  # meta-scripts, deliberately absent from SCRIPT_META
        info = disarm.script_info(member.value)
        assert info["name"], f"{member.value} has no display name"
        assert info["example"], f"{member.value} has no native sample"
