"""#570 — ``sanitize_filename`` must be a fixed point.

Found by ``tests/test_adversarial_oracle.py::test_idempotent`` (Hypothesis), which CI
skips. The failing example was ``'0*.0·'``; the mechanism is narrower than it first looks
and is worth stating precisely, because the obvious reading is wrong.

It is **not** "a substituted character at the end of the stem". ``sanitize_filename("0*.0")``
is ``"0.0"`` in one pass and is perfectly idempotent. What breaks is when the extension
**boundary moves between passes**:

1. The input ends with a ``.`` — literally, or via transliteration (``·`` U+00B7 and
   ``…`` U+2026 both produce one).
2. The split takes the *last* dot, so that trailing dot becomes the "extension" and an
   earlier dot stays inside the stem.
3. ``finalize_name`` then trims the trailing dot off the assembled name.
4. On the next pass the earlier dot is now the last one, so the split lands elsewhere,
   and a separator that was mid-stem is suddenly stem-trailing — where the
   trailing-separator rule strips it.

So the defect is ordering: the trailing-dot trim happens after the split that it
invalidates.
"""

from __future__ import annotations

import pytest

import disarm

#: Inputs that move the extension boundary between passes. Each has a trailing dot
#: (direct or transliterated), an earlier dot, and an illegal character before it.
BOUNDARY_MOVERS = [
    pytest.param("0*.0·", id="middle-dot-transliterates-to-dot"),
    pytest.param("a*.b.", id="literal-trailing-dot"),
    pytest.param("a*.b..", id="two-trailing-dots"),
    pytest.param("a*.b…", id="ellipsis-transliterates-to-dots"),
    pytest.param("ab*.c.", id="longer-stem"),
    pytest.param("x<.y·", id="different-illegal-char"),
    pytest.param("a?.b.", id="question-mark"),
    pytest.param('a".b.', id="double-quote"),
]

#: Cases that were already idempotent. Pinned so the fix does not regress them —
#: several were wrongly described as broken in the original issue report.
ALREADY_STABLE = [
    pytest.param("0*.0", id="no-trailing-dot"),
    pytest.param("a*.b", id="simple-illegal"),
    pytest.param("a_.b", id="pre-existing-underscore"),
    pytest.param("a*b·", id="no-earlier-dot"),
    pytest.param("*.b.", id="illegal-leads"),
    pytest.param("a*.b ", id="trailing-space"),
]


@pytest.mark.parametrize("text", BOUNDARY_MOVERS)
def test_boundary_movers_are_idempotent(text: str) -> None:
    once = disarm.sanitize_filename(text)
    twice = disarm.sanitize_filename(once)
    assert twice == once, f"f({text!r})={once!r} but f(f())={twice!r}"


@pytest.mark.parametrize("text", ALREADY_STABLE)
def test_already_stable_cases_stay_stable(text: str) -> None:
    once = disarm.sanitize_filename(text)
    assert disarm.sanitize_filename(once) == once


@pytest.mark.parametrize("text", BOUNDARY_MOVERS)
def test_first_pass_already_gives_the_fixed_point(text: str) -> None:
    """Stronger than idempotence, and the property that actually matters.

    A caller sanitizes once. If pass 1 returns something pass 2 would change, the
    single-pass answer was the wrong one — two systems that sanitize a different number
    of times derive different filenames from the same input, which defeats dedup on
    sanitized names. So pass 1 must already equal the fixed point.
    """
    once = disarm.sanitize_filename(text)
    fixed = once
    for _ in range(5):
        nxt = disarm.sanitize_filename(fixed)
        if nxt == fixed:
            break
        fixed = nxt
    assert once == fixed, f"f({text!r})={once!r} but the fixed point is {fixed!r}"


def test_the_documented_repro_from_the_issue() -> None:
    """The exact Hypothesis falsifying example."""
    assert disarm.sanitize_filename("0*.0·") == "0.0"


@pytest.mark.parametrize("preserve", [True, False])
@pytest.mark.parametrize("platform", ["universal", "windows", "posix"])
def test_idempotent_across_platforms_and_extension_modes(platform: str, preserve: bool) -> None:
    for text in ("a*.b.", "0*.0·", "report...", "CON.", "a*.b"):
        once = disarm.sanitize_filename(text, platform=platform, preserve_extension=preserve)
        assert (
            disarm.sanitize_filename(once, platform=platform, preserve_extension=preserve) == once
        )


def test_no_trailing_dot_or_space_survives() -> None:
    """The existing guarantee must hold through the fix."""
    for text in ("a*.b.", "report...", "trailing ", "0*.0·"):
        out = disarm.sanitize_filename(text)
        assert not out.endswith((".", " ")), out
