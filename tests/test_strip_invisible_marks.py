"""A composable step that removes what hides between letters and leaves every other mark (#1137).

`strip_zalgo=0` and `strip_accents=True` removed variation selectors and `U+034F`, and both also
took every diacritic, so a pipeline that had to keep accents kept the carriers too. `strip_format`
is a preset whose policy is private, so it cannot be composed.

Three decisions, all from scope item 2:

* `U+FE0E` and `U+FE0F` stay directly after a base Unicode registers them for, where they change
  the glyph. That is the rule `strip_format` follows since #1135.
* Mongolian free variation selectors stay directly after a Mongolian letter. That is the reason
  `docs/limitations.md` gives for keeping them, and it holds nowhere else.
* An ideographic selector goes, even after an ideograph: the IVD is not shipped, so nothing here
  can say which are registered, and a caller who names this step is asking to lose the variant.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

import pytest

import disarm
from disarm import TextPipeline

ROOT = Path(__file__).resolve().parents[1]

CGJ = chr(0x034F)
VS1, VS2, VS15, VS16 = chr(0xFE00), chr(0xFE01), chr(0xFE0E), chr(0xFE0F)
VS17 = chr(0xE0100)
FVS1, FVS2, FVS3, FVS4 = chr(0x180B), chr(0x180C), chr(0x180D), chr(0x180F)
ACUTE = chr(0x0301)
TAG_A = chr(0xE0041)
HEART = chr(0x2764)
MONGOLIAN_A = chr(0x1820)
GE = chr(0x845B)


def marks(text: str) -> str:
    return TextPipeline(strip_invisible_marks=True)(text)


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("a" + VS2 + "b", "ab"),
        ("a" + VS17 + "b", "ab"),
        ("a" + CGJ + "b", "ab"),
        ("a" + VS16 + "b", "ab"),
        ("a" + VS15 + "b", "ab"),
    ],
    ids=["U+FE01", "U+E0100", "U+034F", "U+FE0F", "U+FE0E"],
)
def test_a_carrier_between_letters_goes(text: str, want: str) -> None:
    assert marks(text) == want


@pytest.mark.parametrize("mark", [ACUTE, chr(0x0323), chr(0x05B8), chr(0x20E3)])
def test_every_other_mark_stays(mark: str) -> None:
    assert marks("e" + mark) == "e" + mark


def test_a_tag_stays_because_strip_plane14_owns_that_block() -> None:
    assert marks("a" + TAG_A + "b") == "a" + TAG_A + "b"


def test_the_step_is_off_by_default() -> None:
    assert TextPipeline()("a" + VS2 + "b") == "a" + VS2 + "b"


@pytest.mark.parametrize("mark", [FVS1, FVS2, FVS3, FVS4])
def test_a_mongolian_selector_after_anything_else_goes(mark: str) -> None:
    assert marks("a" + mark + "b") == "ab"


@pytest.mark.parametrize("mark", [FVS1, FVS2, FVS3, FVS4])
def test_a_mongolian_selector_after_a_mongolian_letter_stays(mark: str) -> None:
    assert marks(MONGOLIAN_A + mark) == MONGOLIAN_A + mark


def test_a_second_mongolian_selector_is_not_after_a_letter() -> None:
    assert marks(MONGOLIAN_A + FVS1 + FVS1) == MONGOLIAN_A + FVS1


@pytest.mark.parametrize("selector", [VS15, VS16])
def test_a_presentation_selector_stays_after_a_registered_base(selector: str) -> None:
    assert marks(HEART + selector) == HEART + selector
    assert marks("1" + selector) == "1" + selector


def test_a_presentation_selector_stays_in_a_keycap() -> None:
    keycap = "1" + VS16 + chr(0x20E3)
    assert marks(keycap) == keycap


def test_a_second_presentation_selector_goes() -> None:
    assert marks(HEART + VS16 + VS16) == HEART + VS16


def test_a_selector_removed_first_does_not_cost_the_registered_one_after_it() -> None:
    assert marks(HEART + VS2 + VS16) == HEART + VS16


@pytest.mark.parametrize("registered", ["0" + VS1, GE + VS17])
def test_only_the_two_presentation_selectors_have_the_carve_out(registered: str) -> None:
    assert marks(registered) == registered[0]


@pytest.mark.parametrize(
    "text",
    [
        "a" + VS2 + "b",
        HEART + VS16 + VS16,
        HEART + VS2 + VS16,
        MONGOLIAN_A + FVS1 + FVS1,
        "a" + CGJ + ACUTE,
        "1" + VS16 + chr(0x20E3),
        VS16,
        "",
    ],
)
def test_the_step_alone_is_a_fixed_point(text: str) -> None:
    once = marks(text)
    assert marks(once) == once


@pytest.mark.parametrize("form", ["NFC", "NFKC", "NFD", "NFKD"])
def test_removing_a_joiner_from_before_a_mark_does_not_leave_the_text_unnormalized(
    form: str,
) -> None:
    """`a` `U+034F` `U+0301` is in normal form, and `a` `U+0301` is not."""
    pipe = TextPipeline(normalize=form, strip_invisible_marks=True)
    once = pipe("a" + CGJ + ACUTE)
    assert once == disarm.normalize("a" + ACUTE, form=form)
    assert pipe(once) == once


def test_a_base_compatibility_normalization_replaced_loses_its_selector_on_the_first_pass() -> None:
    """NFKC turns U+2122 into `TM`, and a selector after `M` is no sequence at all."""
    pipe = TextPipeline(normalize="NFKC", strip_invisible_marks=True)
    assert pipe(chr(0x2122) + VS16) == "TM"


def _step_names(pipe: TextPipeline) -> list[str]:
    return [name for name, _ in pipe.steps]


def test_the_step_is_reported_where_it_runs() -> None:
    steps = _step_names(TextPipeline(normalize="NFC", strip_invisible_marks=True, strip_zalgo=3))
    assert steps.index("normalize") < steps.index("strip_invisible_marks")
    assert steps.index("strip_invisible_marks") < steps.index("strip_zalgo")


def test_the_second_normalization_is_reported_only_where_it_runs() -> None:
    assert _step_names(TextPipeline(strip_invisible_marks=True)) == ["strip_invisible_marks"]
    assert _step_names(TextPipeline(normalize="NFC", strip_invisible_marks=True)) == [
        "normalize",
        "strip_invisible_marks",
        "normalize",
    ]
    assert _step_names(TextPipeline(normalize="NFC")) == ["normalize"]


def test_a_mark_count_no_longer_includes_what_the_step_took() -> None:
    text = "a" + ACUTE + chr(0x0323) + CGJ + VS2 + VS2
    pipe = TextPipeline(strip_invisible_marks=True, strip_zalgo=2)
    assert sorted(disarm.normalize(pipe(text), form="NFD")) == sorted("a" + ACUTE + chr(0x0323))


def test_it_keeps_accents_where_the_two_older_steps_do_not() -> None:
    text = "caf" + "e" + ACUTE + VS2
    assert marks(text) == "caf" + "e" + ACUTE
    assert TextPipeline(strip_zalgo=0)(text) == "cafe"


def test_no_preset_key_moves_when_the_step_exists() -> None:
    for name in disarm.list_profiles():
        assert "strip_invisible_marks" not in _step_names(disarm.get_pipeline(name)), name


def test_the_python_signature_declares_it() -> None:
    assert (
        inspect.signature(TextPipeline.__init__).parameters["strip_invisible_marks"].default
        is False
    )


def test_the_type_stub_declares_it() -> None:
    assert "strip_invisible_marks: bool = False" in (ROOT / "python/disarm/_core.pyi").read_text(
        encoding="utf-8"
    )


def test_the_command_line_can_name_it() -> None:
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "disarm",
            "pipeline",
            "--steps",
            "strip_invisible_marks",
            "a" + VS2 + "b",
        ],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    assert done.stdout.strip() == "ab"


@pytest.mark.parametrize("page", ["docs/cli.md", "docs/api/pipelines.md", "docs/limitations.md"])
def test_the_pages_name_it(page: str) -> None:
    assert "strip_invisible_marks" in (ROOT / page).read_text(encoding="utf-8")
