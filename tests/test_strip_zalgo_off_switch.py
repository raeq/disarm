"""`strip_zalgo`'s off switch is `None`, and `0` is the opposite of off (#958).

Every other `TextPipeline` step is switched with a boolean. `strip_zalgo` takes a cap
on combining marks per base character, so the falsy-looking `0` permits none and
removes every diacritic in the text. `benchmarks/meta` built three composed subjects
with `strip_zalgo=0` reading it as off, and stripped the accents from 88 of 100
JailbreakBench prompts and from a subject whose declared intent was to change nothing
a reader can see (#959 fixed the harness; this pins the semantics it misread).

The same literal reads the other way in `PRESETS`, where the second position is the
step's parameter rather than a switch: `("strip_zalgo", None)` there is a live step at
its default cap. Both halves are asserted here — a test that only pinned the pipeline
keyword would leave the reading that caused the confusion unstated.
"""

import disarm
from disarm import PRESETS, TextPipeline

# Ordinary accented text in three scripts' worth of Latin diacritics. Nothing here is
# zalgo: every base character carries at most one mark.
ACCENTED = "Čeština, naïve café"
UNACCENTED = "Cestina, naive cafe"


def test_none_omits_the_step_entirely() -> None:
    pipe = TextPipeline(strip_zalgo=None)
    assert pipe.steps == []
    assert pipe(ACCENTED) == ACCENTED


def test_zero_is_a_cap_of_zero_marks_not_off() -> None:
    pipe = TextPipeline(strip_zalgo=0)
    assert [name for name, _ in pipe.steps] == ["strip_zalgo"]
    assert pipe(ACCENTED) == UNACCENTED


def test_a_positive_cap_runs_and_leaves_ordinary_accents_alone() -> None:
    for cap in (1, 2, 3):
        pipe = TextPipeline(strip_zalgo=cap)
        assert [name for name, _ in pipe.steps] == ["strip_zalgo"], cap
        assert pipe(ACCENTED) == ACCENTED, cap


def test_a_positive_cap_still_cuts_a_zalgo_stack() -> None:
    """Otherwise the recommendation above would be to disable the step.

    Counted after NFD, because the step composes what it keeps: a base plus three
    surviving marks comes back as `U+00E1` plus two, not as four separate code points.
    """
    zalgo = "a" + "́" * 12 + "b"
    out = TextPipeline(strip_zalgo=3)(zalgo)
    assert out != zalgo
    assert disarm.normalize(out, form="NFD").count("́") == 3


def test_presets_none_is_a_parameter_and_the_step_runs() -> None:
    """The other reading of the same literal, which is why `0` looked like off."""
    steps = PRESETS["canonicalize"]
    assert ("strip_zalgo", None) in steps
    # The step is in the preset and the preset does not strip accents, so `None` there
    # cannot mean "cap at zero" and cannot mean "absent" either — it is the default cap.
    assert disarm.canonicalize(ACCENTED) == ACCENTED


def test_the_bare_function_defaults_to_a_positive_cap() -> None:
    assert disarm.strip_zalgo(ACCENTED) == ACCENTED
    assert disarm.strip_zalgo(ACCENTED, max_marks=0) == UNACCENTED


def test_no_other_pipeline_flag_takes_zero_as_a_setting() -> None:
    """The trap is specific to the one integer-valued flag; pin that it stays that way.

    A future flag that also takes a count would inherit the same ambiguity, and this
    fails when one is added without a decision about its off switch.
    """
    import inspect

    integer_flags = [
        name
        for name, param in inspect.signature(TextPipeline.__init__).parameters.items()
        if isinstance(param.annotation, str) and param.annotation.startswith("int")
    ]
    assert integer_flags == ["strip_zalgo"], integer_flags
