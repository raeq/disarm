"""The harness scores a named surface, not a hardcoded one (#903).

`benchmarks/adversarial_eval` imported `strip_obfuscation` at module level and applied it
to both the perturbed text and the clean target. It could not answer "how does
`canonicalize` recover this corpus compared with `strip_obfuscation`", which is the first
question the README's pipeline section invites — and it scored the wrong surface for any
consumer whose declared sanitise entry point is not `strip_obfuscation`.

The transform is a **dotted string**, not a callable, because the scan runs in a process
pool: a function object cannot cross that boundary and a name can. It is resolved inside
each worker, beside the confusables table.

The default is unchanged, deliberately. Every committed report and the pre-release
BitAbuse cadence were produced with `strip_obfuscation`, and a default that moved would
silently reinterpret all of them.
"""

from __future__ import annotations

import pytest

from benchmarks.adversarial_eval.corpora import Record
from benchmarks.adversarial_eval.metrics import (
    DEFAULT_TRANSFORM,
    evaluate,
    resolve_transform,
)

#: Rows chosen so the surfaces disagree: a Cyrillic homoglyph, an accent, an em dash and
#: a Cyrillic dze. If every transform scored these the same the test would prove nothing.
ROWS = [
    Record(text="pаypal", clean="paypal"),
    Record(text="café", clean="cafe"),
    Record(text="—dash", clean="-dash"),
    Record(text="ѕecure", clean="secure"),
]


def test_the_default_is_still_strip_obfuscation() -> None:
    """Load-bearing: the committed reports are `strip_obfuscation` figures."""
    assert DEFAULT_TRANSFORM == "disarm.strip_obfuscation"
    result = evaluate(list(ROWS), corpus="t", labeled=True, processes=1)
    assert result.transform == "disarm.strip_obfuscation"


def test_naming_a_surface_scores_that_surface() -> None:
    """And the surfaces must actually differ, or the parameter is untested."""
    scores = {}
    for name in ("disarm.strip_obfuscation", "disarm.canonicalize", "disarm.search_key"):
        result = evaluate(list(ROWS), corpus="t", labeled=True, processes=1, transform=name)
        assert result.transform == name
        scores[name] = result.folded_fraction
    assert len(set(scores.values())) > 1, f"every transform scored the same: {scores}"


def test_the_result_records_which_surface_it_describes() -> None:
    """So a report is never read as a `strip_obfuscation` figure when it is not."""
    result = evaluate(
        list(ROWS), corpus="t", labeled=True, processes=1, transform="disarm.canonicalize"
    )
    from benchmarks.adversarial_eval.__main__ import render_markdown

    report = render_markdown(result, None)
    assert "disarm.canonicalize" in report
    assert "`strip_obfuscation`" not in report


@pytest.mark.parametrize(
    ("dotted", "why"),
    [
        ("nope", "no module part"),
        ("disarm.does_not_exist", "attribute missing"),
        ("disarm.__version__", "not callable"),
        # An unimportable module used to escape as ImportError rather than ValueError,
        # so a caller could not catch one type — and inside a pool the traceback came
        # from the initializer (#904 review).
        ("no_such_module.thing", "module cannot be imported"),
    ],
)
def test_a_bad_transform_is_rejected(dotted: str, why: str) -> None:
    with pytest.raises(ValueError) as caught:
        resolve_transform(dotted)
    # `why` in the message, so a failure says which rejection path was expected rather
    # than only that some ValueError did not arrive (#904 review).
    assert dotted in str(caught.value), (
        f"the {why!r} case must name the path it rejected, got: {caught.value}"
    )


def test_a_bad_transform_fails_before_the_pool_starts() -> None:
    """Resolved once in `evaluate` as well as in each worker.

    Without that, the failure surfaces inside the pool initializer, where the traceback
    names `_init_worker` rather than the argument the caller got wrong.
    """
    with pytest.raises(ValueError):
        evaluate(list(ROWS), corpus="t", labeled=True, processes=4, transform="disarm.nope")
