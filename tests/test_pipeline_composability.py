"""#911 — every step a shipped profile uses must be reachable from `TextPipeline`.

`TextPipeline` is the answer disarm gives to "I need a policy the shipped profiles do
not cover". That answer is only worth anything if a composed pipeline can actually
express what a profile expresses. It could not: `strip_pua` was a `ProfileSpec` field
with no constructor argument, set post-hoc inside `ProfileSpec::build`, so every
composed pipeline silently kept all 137,468 Private Use Area code points that #814
added stripping for.

Four hand-kept lists have to agree for composition to work, and nothing compared them:

1. `ProfileSpec`            (`src/pipeline.rs`)   — what a profile can ask for
2. `_TextPipeline::new`     (`src/py/pipeline.rs`) — what a caller can ask for
3. `TextPipeline.__init__`  (`python/disarm/_api.py`)
4. the `--steps` allowlist  (`python/disarm/__main__.py`)

`strip_bidi` had already gone missing from list 4 once (#250 C6), and `strict_iso9`
and `gost7034` were missing from it when this file was written. So the structural test
below is anchored to the **Rust struct**, parsed from source — comparing two
hand-written Python lists would have stayed green through every one of these.
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_RS = ROOT / "src" / "pipeline.rs"
MAIN_PY = ROOT / "python" / "disarm" / "__main__.py"

#: The three Private Use Areas (#814).
PUA_RANGES = ((0xE000, 0xF8FF), (0xF0000, 0xFFFFD), (0x100000, 0x10FFFD))
PUA_TOTAL = sum(hi - lo + 1 for lo, hi in PUA_RANGES)

#: Every shipped profile, transcribed from `profile_spec()` in `src/pipeline.rs`.
#: If a profile's steps change, this transcription is what fails — deliberately, because
#: the point of the test is that the two surfaces express the same thing.
PROFILE_EQUIVALENTS: dict[str, dict[str, object]] = {
    "scholarly_cyrillic_iso9": dict(
        normalize="NFKC",
        transliterate=True,
        strict_iso9=True,
        fold_case=True,
        collapse_whitespace=True,
        strip_pua=True,
    ),
    "library_catalog_key_eu": dict(
        normalize="NFKC",
        transliterate=True,
        confusables=True,
        strip_accents=True,
        fold_case=True,
        collapse_whitespace=True,
        strip_pua=True,
    ),
    "normalize_web_input": dict(
        normalize="NFKC",
        confusables=True,
        collapse_whitespace=True,
        strip_pua=True,
    ),
    "ml_corpus_normalize": dict(
        normalize="NFKC",
        demojize=True,
        strip_accents=True,
        fold_case=True,
        collapse_whitespace=True,
        strip_pua=True,
    ),
    "search_index": dict(
        normalize="NFKC",
        transliterate=True,
        strip_accents=True,
        fold_case=True,
        collapse_whitespace=True,
        strip_pua=True,
    ),
    "code_context": dict(strip_bidi=True, strip_zero_width=True, strip_control=True),
    "llm_guardrail": dict(
        normalize="NFKC",
        strip_zalgo=0,
        strip_bidi=True,
        strip_zero_width=True,
        strip_control=True,
        demojize=True,
        confusables=True,
        strip_accents=True,
        fold_case=True,
        collapse_whitespace=True,
        strip_pua=True,
    ),
    "rag_ingest": dict(
        normalize="NFKC",
        strip_bidi=True,
        strip_control=True,
        strip_zero_width=True,
        transliterate=True,
        strip_accents=True,
        collapse_whitespace=True,
        strip_pua=True,
    ),
}

#: `ProfileSpec::build` overrides `emoji_name_policy` so a *profile* leaves the 326 code
#: points carrying neither `Emoji` nor `Extended_Pictographic` for later steps, while
#: `demojize` on a hand-built pipeline names everything (#757, #853). That is deliberate
#: and is the one thing composition cannot reproduce, so these two are checked by
#: `test_demojize_profiles_diverge_only_by_naming_more` instead.
NOT_EXACTLY_REPRODUCIBLE = frozenset({"ml_corpus_normalize", "llm_guardrail"})

#: Inputs that exercise each step at least once.
CORPUS = (
    "ab",
    "Москва",
    "café",
    "naïve  café",
    "Ｈello",
    "hello world",
    "a\tb\nc",
    "\u202eabc",  # RIGHT-TO-LEFT OVERRIDE
    "a\u200bb",  # ZERO WIDTH SPACE
    "ﬁle",
    "paypaаl",
    "á́́́́b",
    "\U0001f389 party",
    "☃ snowman",
    "1⁄4",
    "\U000f0000x",
    "¼",
    "‐dash",
)


def _profilespec_fields() -> list[str]:
    """Field names of `struct ProfileSpec`, read from the Rust source.

    Anchored to the struct rather than to a list maintained beside it: a list would
    have to be edited by the same person who added the field, which is exactly what
    did not happen for `strip_pua`.
    """
    src = PIPELINE_RS.read_text(encoding="utf-8")
    body = re.search(r"struct ProfileSpec \{(.*?)\n\}", src, re.DOTALL)
    assert body, "could not locate `struct ProfileSpec` in src/pipeline.rs"
    return re.findall(r"^\s{4}(\w+):\s", body.group(1), re.MULTILINE)


def _cli_steps() -> set[str]:
    """Step names `disarm pipeline --steps` accepts, read from the CLI source."""
    src = MAIN_PY.read_text(encoding="utf-8")
    body = re.search(r"elif step in \((.*?)\n\s*\):", src, re.DOTALL)
    assert body, "could not locate the --steps allowlist in __main__.py"
    # `normalize` and `strip_zalgo` are handled by earlier branches, not the tuple.
    return set(re.findall(r'"(\w+)"', body.group(1))) | {"normalize", "strip_zalgo"}


def test_the_source_parses_found_something() -> None:
    """A regex that matched nothing would make every test below vacuously pass."""
    fields = _profilespec_fields()
    assert len(fields) >= 13, f"parsed only {len(fields)} ProfileSpec fields: {fields}"
    assert "strip_pua" in fields
    assert len(_cli_steps()) >= 12


def test_every_profilespec_field_is_reachable_from_textpipeline() -> None:
    """#911's ask 3. The gate that would have caught `strip_pua` when it was added."""
    constructor = set(inspect.signature(disarm.TextPipeline.__init__).parameters) - {"self"}
    missing = [f for f in _profilespec_fields() if f not in constructor]
    assert not missing, (
        f"ProfileSpec fields with no TextPipeline argument: {missing}. "
        "A profile can ask for something a composed pipeline cannot."
    )


def test_every_boolean_step_is_reachable_from_the_cli() -> None:
    """The fourth list. `lang` is excluded: it takes a value, not a bare step name."""
    params = inspect.signature(disarm.TextPipeline.__init__).parameters
    steps = {n for n in params if n not in {"self", "lang"}}
    missing = sorted(steps - _cli_steps())
    assert not missing, f"TextPipeline flags unreachable from `disarm pipeline --steps`: {missing}"


def test_strip_pua_is_reachable_and_strips_the_whole_pua() -> None:
    """#911 proper: the flag exists, and it does what the profiles do."""
    on = disarm.TextPipeline(strip_pua=True)
    off = disarm.TextPipeline(strip_pua=False)
    stripped = sum(
        1 for lo, hi in PUA_RANGES for cp in range(lo, hi + 1) if on("a" + chr(cp) + "b") == "ab"
    )
    assert stripped == PUA_TOTAL, f"{stripped} of {PUA_TOTAL}"
    # Both halves: the flag has to be doing this, not some other step.
    assert off("a\ue000b") == "a\ue000b"
    assert disarm.TextPipeline()("a\ue000b") == "a\ue000b", "default must not change"


@pytest.mark.parametrize("name", sorted(set(PROFILE_EQUIVALENTS) - NOT_EXACTLY_REPRODUCIBLE))
def test_every_profile_is_reproducible_by_a_composed_pipeline(name: str) -> None:
    """The behavioural half: the flags exist *and* they compose to the same thing."""
    profile = disarm.get_pipeline(name)
    composed = disarm.TextPipeline(**PROFILE_EQUIVALENTS[name])  # type: ignore[arg-type]
    for text in CORPUS:
        assert profile(text) == composed(text), f"{name} diverges on {text!r}"
    for lo, _ in PUA_RANGES:
        probe = "a" + chr(lo) + "b"
        assert profile(probe) == composed(probe), f"{name} diverges on PUA U+{lo:04X}"


#: Where every divergence observed to date lives. Above this the emoji and confusable
#: tables have no entries, so the scan is looking for something unexpected rather than
#: confirming something known — which is worth doing, but not on every local run.
NAMING_RANGE_END = 0x1FFFD


def _wrong_shaped_divergences(name: str, first: int, last: int) -> list[tuple[int, str, str]]:
    """Divergences that are NOT the emoji-naming policy, over ``[first, last]``.

    The policy makes the composed pipeline name a character the profile leaves alone,
    so a legitimate divergence always has the composed output strictly longer. Anything
    else — the profile producing more, or equal-length disagreement — is a different
    bug wearing the exception's clothes.
    """
    profile = disarm.get_pipeline(name)
    composed = disarm.TextPipeline(**PROFILE_EQUIVALENTS[name])  # type: ignore[arg-type]
    out = []
    for cp in range(first, last + 1):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        ch = chr(cp)
        a, b = profile(ch), composed(ch)
        if a != b and len(b) <= len(a):
            out.append((cp, a, b))
    return out


@pytest.mark.parametrize("name", sorted(NOT_EXACTLY_REPRODUCIBLE))
def test_demojize_profiles_diverge_only_by_naming_more(name: str) -> None:
    """The documented exception, bounded so a *new* kind of divergence still fails."""
    wrong = _wrong_shaped_divergences(name, 0x20, NAMING_RANGE_END)
    assert not wrong, (
        f"{name}: {len(wrong)} divergence(s) that are not the emoji-naming policy, e.g. {wrong[:3]}"
    )


@pytest.mark.slow
@pytest.mark.parametrize("name", sorted(NOT_EXACTLY_REPRODUCIBLE))
def test_demojize_divergence_shape_holds_above_the_naming_range(name: str) -> None:
    """The other ~1.05M code points (#912 review).

    Splitting here rather than dropping the tail: above `NAMING_RANGE_END` sit the Tags
    block, Variation Selectors Supplement and **both supplementary Private Use planes**
    — 131,068 PUA code points, which is what this whole change is about. Capping the
    scan would stop asserting anything there.

    It is `slow` because it is ~1.7s of the file's ~2s and confirms a negative. Bare
    `pytest` skips the `slow` tier; CI's `-m "not formal and not hypothesis"` runs it,
    so the codespace stays covered where it counts (#658).
    """
    wrong = _wrong_shaped_divergences(name, NAMING_RANGE_END + 1, sys.maxunicode)
    assert not wrong, (
        f"{name}: {len(wrong)} divergence(s) above U+{NAMING_RANGE_END:04X} that are "
        f"not the emoji-naming policy, e.g. {wrong[:3]}"
    )


@pytest.mark.parametrize("name", sorted(NOT_EXACTLY_REPRODUCIBLE))
def test_the_demojize_exception_is_real_and_not_a_vacuous_pass(name: str) -> None:
    """Guards the test above: if the policies converged, it would pass by finding nothing.

    That would be good news, but it would mean the exception list is stale and the two
    profiles belong in the exact-reproduction test instead.
    """
    profile = disarm.get_pipeline(name)
    composed = disarm.TextPipeline(**PROFILE_EQUIVALENTS[name])  # type: ignore[arg-type]
    assert profile("‐") != composed("‐")


def test_every_shipped_profile_has_a_transcription() -> None:
    """`list_profiles()` is the registry; this file must cover all of it."""
    assert sorted(PROFILE_EQUIVALENTS) == sorted(disarm.list_profiles())
