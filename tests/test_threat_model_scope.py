"""#729/#743/#747/#748/#753/#755/#756/#758/#804 — the scope entries stay true.

`THREAT_MODEL.md`'s *Out of scope* section is the page a reader consults to decide whether
a class is disarm's problem. An entry that quietly stops being true is worse than a missing
one: it is a claim the library no longer honours, and nothing in CI reads prose.

So the entries that rest on a measurement are measured here. The rest — the ones that are
definitional, like "a synonym substitution has nothing character-level in it" — are checked
only for presence, because there is nothing to run.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "THREAT_MODEL.md"
PROFILES = disarm.list_profiles()


def page() -> str:
    return PAGE.read_text(encoding="utf-8")


#: Sweep bound. The figure in THREAT_MODEL was measured over U+0020..U+2FFFF; a test that
#: sweeps a smaller range finds fewer spellings and "fails" a page that is correct, which
#: is a worse outcome than a slower test. Computed once for the module.
SWEEP_END = 0x30000


@functools.lru_cache(maxsize=1)
def ascii_letter_folds() -> dict[str, tuple[str, ...]]:
    """Every code point that folds to a single ASCII letter, keyed by that letter."""
    out: dict[str, list[str]] = {}
    for cp in range(0x20, SWEEP_END):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        ch = chr(cp)
        folded = disarm.normalize_confusables(ch)
        if len(folded) == 1 and folded.isascii() and folded.isalpha():
            out.setdefault(folded.lower(), []).append(ch)
    return {k: tuple(v) for k, v in out.items()}


def spellings_reaching_one_key(trigger: str) -> list[str]:
    """Single-position substitutions of `trigger` that land on its own `search_key`."""
    folds = ascii_letter_folds()
    variants = {
        trigger[:i] + alt + trigger[i + 1 :]
        for i, letter in enumerate(trigger)
        for alt in folds.get(letter, ())
    } - {trigger}
    base = disarm.search_key(trigger)
    return [v for v in variants if disarm.search_key(v) == base]


@pytest.mark.parametrize(
    ("issue", "phrase"),
    [
        ("#729", "Textual encoding obfuscation"),
        ("#755/#804", "Word fragmentation by a *visible* separator"),
        ("#753", "many-to-one fold widens"),
        ("#756", "identical transform on both sides of training"),
        ("#758", "Word-substitution adversarial examples"),
        ("#748", "agent state / tool-result record"),
        ("#743", "Optimized jailbreak suffixes"),
        ("#747", "manufactures model-context delimiters"),
    ],
)
def test_the_entry_is_present(issue: str, phrase: str) -> None:
    """A gate over a missing entry passes for the wrong reason."""
    assert phrase in page(), f"{issue}: the scope entry is gone"


def test_the_encoding_family_is_still_undecoded() -> None:
    """#729 — if disarm ever grows a decoder, this entry becomes wrong, not stale."""
    encoded = "PHNjcmlwdD4="  # base64 of "<script>"
    for name in PROFILES:
        out = disarm.get_pipeline(name)(encoded)
        assert "<script>" not in out, (
            f"{name} decoded base64; THREAT_MODEL says disarm does not, and the entry "
            "now has to say what it does instead"
        )


def test_the_fragmentation_asymmetry_still_holds() -> None:
    """#755/#804 — the table in the entry, as an assertion.

    The invisible separator is recovered *and* reported; the visible one is neither. If
    either half changes, the entry's whole argument changes with it.
    """
    base = disarm.search_key("Confirm")
    for sep in ("\u200b", "\u200c"):  # escapes, per #802
        joined = f"Con{sep}firm"
        assert disarm.search_key(joined) == base, f"{sep!r} is no longer rejoined"
        assert disarm.inspect_anomalies(joined).anomalous, f"{sep!r} is no longer reported"
    for sep in (" ", ".", "-"):
        split = f"Con{sep}firm"
        assert disarm.search_key(split) != base, (
            f"{sep!r} is now recovered — THREAT_MODEL says it is not"
        )
        assert not disarm.inspect_anomalies(split).anomalous, (
            f"{sep!r} is now reported — THREAT_MODEL says it is not"
        )


def test_nfkc_still_manufactures_the_delimiters() -> None:
    """#747 — the counts in the entry's table, derived rather than typed.

    Asserted as a floor per row: the point is that this happens at all and in most
    profiles, and a profile added later should not fail the page.
    """
    table = {
        "＜/state＞＜system＞": ("</state><system>", 7),
        "＜script＞": ("<script>", 7),
        "＜｜im_start｜＞": ("<|im_start|>", 4),
        "＜＜SYS＞＞": ("<<SYS>>", 2),
    }
    for src, (live, floor) in table.items():
        hits = sum(1 for name in PROFILES if disarm.get_pipeline(name)(src) == live)
        assert hits >= floor, (
            f"{src!r} → {live!r} now happens in {hits} profiles, not {floor}; the table in "
            "THREAT_MODEL.md overstates it"
        )
        # Anchored on the source cell, then the last "N of M" on that line. A cell-count
        # regex does not survive the `<\|im_start\|>` row, whose output contains an
        # escaped pipe.
        row = next(line for line in page().splitlines() if f"`{src}`" in line and "of" in line)
        documented = int(re.findall(r"(\d+) of \d+", row)[-1])
        assert documented <= hits, (
            f"the page says {documented} profiles for {src!r}, measured {hits}"
        )


def test_the_fold_still_widens_what_reaches_one_key() -> None:
    """#753 — the mechanism, and the figure the entry publishes.

    Checked as a floor rather than an equality: a table regeneration moves it, and the
    entry's claim is that the number is *large*, not that it is exactly 227. Also checked
    against the page, so the published figure cannot drift above the truth unnoticed.
    """
    same = spellings_reaching_one_key("admin")
    assert len(same) > 50, (
        f"only {len(same)} spellings reach one key; THREAT_MODEL's argument is that a "
        "many-to-one fold widens the reaching set substantially"
    )
    documented = int(re.search(r"\*\*(\d+) of \d+ spellings reach", page()).group(1))
    assert documented <= len(same), (
        f"the page says {documented} spellings, this sweep found {len(same)}"
    )


def test_the_detector_still_catches_most_of_them() -> None:
    """#753 — the parenthetical mitigation, which is the part a reader may act on.

    The entry says `inspect_anomalies` flags 97.8% of that set. If that collapses, the
    entry reads as more reassuring than the library is.
    """
    same = spellings_reaching_one_key("admin")
    flagged = sum(1 for v in same if disarm.inspect_anomalies(v).anomalous)
    assert flagged / len(same) > 0.90, (
        f"the detector now reports {100 * flagged / len(same):.1f}% of the widened set; "
        "THREAT_MODEL cites 97.8% as a partial mitigation"
    )
