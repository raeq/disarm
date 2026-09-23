"""The findings of the Lean model of the presets, `formal/lean/Presets` (Findings 2 to 7).

Finding 1, `skeleton_key` not being a fixed point, is fixed and tested with the confusable
fold's own findings (`tests/test_skeleton_key.py`). The rest:

2. `search_key` and `sort_key` were not fixed points under `digit_policy="tr39"` or
   `"preserve"`. Their only fold is a pre-fold on the raw text, and the case fold and
   transliteration make new sources after it.
3. `llm_guardrail` and `ml_corpus_normalize` kept a negation overlay on a symbol base and
   then orphaned it: the mark strip runs before the fold and before `strip_pua`.
4. A character stripped after the last normalization separated two characters that
   compose, in `strip_obfuscation`, `ml_normalize` and three profiles.
5. `PRESETS` was not what the presets run.
6. The preset output ceiling was an absolute size test on NFKC alone.
7. Documentation claims that did not hold.

Every test string is built from code points with `w(...)`, so no invisible or unusual
character appears in this file.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest
from conftest import PRESET_STEP_FUNCTIONS

import disarm

ROOT = Path(__file__).resolve().parent.parent

POLICIES = ("tr39", "preserve")

#: Ten mebibytes, the preset output ceiling (`MAX_NORMALIZE_OUTPUT_BYTES`).
CEILING = 10 * 1024 * 1024


def w(*cps: int) -> str:
    return "".join(map(chr, cps))


# ---------------------------------------------------------------------------
# Finding 2: the key builders under a digit policy
# ---------------------------------------------------------------------------

#: (builder, input, key under both non-default policies). U+A760 has no row and case-folds
#: to U+A761, which folds to `w`. U+01C1 transliterates to `||`, and `|` is a source.
#: U+0100 case-folds to U+0101, whose `tr39` row is U+00E3 (and `preserve`'s, measured).
POLICY_WITNESSES = [
    ("search_key", w(0xA760), "w"),
    ("search_key", w(0x1C1), "ll"),
    ("sort_key", w(0xA760), "w"),
    ("sort_key", w(0x100), w(0xE3)),
]


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize(("builder", "text", "key"), POLICY_WITNESSES)
def test_a_policy_key_is_a_fixed_point_on_the_lean_witnesses(
    builder: str, text: str, key: str, policy: str
) -> None:
    f = getattr(disarm, builder)
    once = f(text, digit_policy=policy)
    assert once == key
    assert f(once, digit_policy=policy) == once


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("builder", ["search_key", "sort_key", "catalog_key"])
def test_a_policy_key_is_a_fixed_point_over_every_bmp_scalar(builder: str, policy: str) -> None:
    """The library sweep found 62 `search_key` and 171/172 `sort_key` scalars.

    `catalog_key` never failed, because its own fold sits inside its fixed point; it is
    here so it cannot start.
    """
    f = getattr(disarm, builder)
    moved = []
    for cp in range(0x10000):
        if 0xD800 <= cp < 0xE000:
            continue
        once = f(chr(cp), digit_policy=policy)
        if f(once, digit_policy=policy) != once:
            moved.append(hex(cp))
    assert not moved, f"{builder}[{policy}]: {len(moved)} scalars move; {moved[:10]}"


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("builder", ["search_key", "sort_key"])
def test_a_policy_key_is_a_fixed_point_on_pair_strings(builder: str, policy: str) -> None:
    """The `pairs` family: a scalar beside a removable character or a mark, either side."""
    f = getattr(disarm, builder)
    glue = (0x8, 0x200B, 0x34F, 0x301, 0x20, 0x338)
    moved = []
    for cp in list(range(0x20, 0x250)) + list(range(0x370, 0x530)) + list(range(0xA720, 0xA800)):
        for g in glue:
            for text in (w(cp, g), w(g, cp)):
                once = f(text, digit_policy=policy)
                if f(once, digit_policy=policy) != once:
                    moved.append(ascii(text))
    assert not moved, f"{builder}[{policy}]: {len(moved)} strings move; {moved[:10]}"


@pytest.mark.parametrize("builder", ["search_key", "sort_key", "catalog_key"])
def test_the_default_policy_keys_do_not_move(builder: str) -> None:
    """The iteration is for the non-default policies only: the default key is untouched."""
    f = getattr(disarm, builder)
    for text in (w(0xA760), w(0x1C1), w(0x100), "|" + chr(0x22) + "`", "paypal"):
        assert f(text) == f(text, digit_policy="numeric")
    assert disarm.sort_key(w(0xA760)) == w(0xA761)
    assert disarm.search_key(w(0x1C1)) == "||"


# ---------------------------------------------------------------------------
# Findings 3 and 4: the profiles
# ---------------------------------------------------------------------------

#: (profile, input, first output). Finding 3: the overlay on a symbol the fold turns into a
#: letter, or on a PUA code point `strip_pua` deletes. Finding 4: a character removed after
#: `normalize` between two that compose.
PROFILE_WITNESSES = [
    ("llm_guardrail", w(0xA2, 0x338), "c"),
    ("llm_guardrail", w(0x222A, 0x338), "u"),
    ("llm_guardrail", w(0x2200, 0x20D2), "a"),
    ("llm_guardrail", w(0xE000, 0x338), ""),
    ("ml_corpus_normalize", w(0xE000, 0x338), ""),
    ("ml_corpus_normalize", w(0xF0000, 0x20D2), ""),
    ("ml_corpus_normalize", w(0x1100, 0x0, 0x1161), w(0xAC00)),
    ("ml_corpus_normalize", w(0x1100, 0x8, 0x1161), w(0xAC00)),
    ("llm_guardrail", w(0x1100, 0x200B, 0x1161), w(0xAC00)),
    ("normalize_web_input", w(0x1100, 0x200B, 0x1161), w(0xAC00)),
    ("normalize_web_input", w(0x65, 0x8, 0x301), w(0xE9)),
    ("normalize_web_input", w(0x63, 0x0, 0x327), "c"),
    ("normalize_web_input", w(0x49, 0xE000, 0x301), w(0xCD)),
]


@pytest.mark.parametrize(("profile", "text", "key"), PROFILE_WITNESSES)
def test_a_profile_is_a_fixed_point_on_the_lean_witnesses(
    profile: str, text: str, key: str
) -> None:
    p = disarm.get_pipeline(profile)
    once = p(text)
    assert once == key
    assert p(once) == once


def test_the_digit_policy_keeps_the_iteration() -> None:
    """A profile given a policy is still a profile, and still iterates."""
    p = disarm.get_pipeline("llm_guardrail", digit_policy="tr39")
    assert p(w(0xA2, 0x338)) == "c"


def test_a_hand_built_pipeline_runs_its_steps_once() -> None:
    """The iteration is the profiles', not `TextPipeline`'s.

    A caller who composes steps gets those steps once. A `demojize` replacement that is
    itself two emoji would otherwise double on every pass.
    """
    pipe = disarm.TextPipeline(demojize=w(0x1F600, 0x1F600))
    assert pipe(w(0x1F600)) == w(0x1F600, 0x1F600)


# ---------------------------------------------------------------------------
# Finding 4: the presets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("glue", [0x0, 0x1, 0x200B])
def test_a_stripped_character_between_two_jamo_does_not_keep_them_apart(glue: int) -> None:
    text = w(0x1100, glue, 0x1161)
    for policy in ("numeric", *POLICIES):
        assert disarm.strip_obfuscation(text, digit_policy=policy) == w(0xAC00)
    for fold_case in (True, False):
        assert disarm.ml_normalize(text, fold_case=fold_case) == w(0xAC00)


def test_the_jamo_family_is_a_fixed_point_through_both_presets() -> None:
    """The `F3` family, without the trailing consonant: every leading consonant and vowel
    with each removable character between."""
    glue = [0x200B, 0x34F, 0x8, 0x7F, 0xFE0F, 0xAD, 0x202E, 0x0, 0x2060, 0x200D, 0xFDD0]
    moved = []
    for lead in range(0x1100, 0x1113):
        for vowel in range(0x1161, 0x1176):
            for g in glue:
                text = w(lead, g, vowel)
                for f in (disarm.strip_obfuscation, disarm.ml_normalize):
                    once = f(text)
                    if f(once) != once:
                        moved.append((f.__name__, ascii(text)))
    assert not moved, f"{len(moved)} move; {moved[:10]}"


# ---------------------------------------------------------------------------
# Finding 5: PRESETS is what the presets run
# ---------------------------------------------------------------------------


def _drop_repeated_marks(s: str) -> str:
    out: list[str] = []
    previous = None
    for ch in unicodedata.normalize("NFD", s):
        if unicodedata.category(ch).startswith("M") and unicodedata.combining(ch):
            if ch == previous:
                continue
            previous = ch
        else:
            previous = None
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def _script(ch: str) -> str | None:
    scripts = [x.value for x in disarm.detect_scripts(ch)]
    return scripts[0] if scripts else None


def _strip_cross_script_marks(s: str) -> str:
    out = []
    base = None
    for ch in s:
        if unicodedata.category(ch).startswith("M"):
            mark = _script(ch)
            if mark is not None and base is not None and mark != base:
                continue
            out.append(ch)
            continue
        base = _script(ch) or base
        out.append(ch)
    return "".join(out)


def _strip_invisibles(policy: str, s: str) -> str:
    s = disarm.strip_noncharacters(disarm.strip_tags(s)).replace(chr(0x34F), "")
    if policy == "comparison":
        return disarm.strip_variation_selectors(disarm.strip_pua(s))
    # Rendering: VS15/VS16 stay after a base; every other selector goes.
    out = []
    for i, ch in enumerate(s):
        is_vs = disarm.strip_variation_selectors(ch) == ""
        if is_vs and not (ch in (chr(0xFE0E), chr(0xFE0F)) and i > 0):
            continue
        out.append(ch)
    return "".join(out)


def _transliterate(preset: str, param: str | None, s: str) -> str:
    if preset == "ml_normalize":
        return s  # only when a `lang` is given, and these probes give none
    if param != "non_latin":
        return disarm.transliterate(s, errors="preserve")
    out = []
    for ch in s:
        keep = ch.isascii() or [x.value for x in disarm.detect_scripts(ch)] in ([], ["Latin"])
        out.append(ch if keep else disarm.transliterate(ch, errors="preserve"))
    return "".join(out)


def _split_top_level(spec: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    i = 0
    while i < len(spec):
        if spec.startswith(" -> ", i) and depth == 0:
            parts.append(cur)
            cur = ""
            i += 4
            continue
        depth += {"(": 1, ")": -1}.get(spec[i], 0)
        cur += spec[i]
        i += 1
    return [*parts, cur]


def _parse_item(item: str) -> tuple[str, str | None]:
    if "(" not in item:
        return item, None
    name, rest = item.split("(", 1)
    return name, rest[:-1]


def _run_step(preset: str, name: str, param: str | None, s: str) -> str:
    """One `PRESETS` step, executed with the public function it names (default policy)."""
    if name == "fixed_point":
        assert param is not None
        inner = [_parse_item(item) for item in _split_top_level(param)]
        for _ in range(8):
            nxt = s
            for n, p in inner:
                nxt = _run_step(preset, n, p, nxt)
            if nxt == s:
                break
            s = nxt
        return s
    steps = {
        "resolve_deletions": lambda: disarm.TextPipeline(resolve_deletions=True)(s),
        "policy_pre_fold": lambda: s,  # a no-op under the default policy
        "normalize": lambda: disarm.normalize(s, form=param),
        "strip_bidi": lambda: disarm.strip_bidi(s),
        "strip_invisibles": lambda: _strip_invisibles(str(param), s),
        "strip_control": lambda: disarm.strip_control_chars(s),
        "strip_zero_width": lambda: disarm.strip_zero_width_chars(s),
        "collapse_whitespace": lambda: disarm.collapse_whitespace(s),
        "strip_zalgo": lambda: disarm.strip_zalgo(s, max_marks=0 if param == "max_marks=0" else 3),
        "drop_repeated_marks": lambda: _drop_repeated_marks(s),
        "strip_cross_script_marks": lambda: _strip_cross_script_marks(s),
        # The single pass, as the Rust `ConfusablesCtx` step: a TextPipeline with no
        # normalization step does not iterate its fold.
        "confusables": lambda: disarm.TextPipeline(confusables=True)(s),
        "prototype_fold": lambda: s.replace("I", "l"),
        "fold_case": lambda: disarm.fold_case(s),
        "strip_accents": lambda: disarm.strip_accents(s),
        "transliterate": lambda: _transliterate(preset, param, s),
        "demojize": lambda: disarm.TextPipeline(demojize=True)(s),
    }
    return steps[name]()


def _run_presets_list(preset: str, s: str) -> str:
    for name, param in disarm.PRESETS[preset]:
        s = _run_step(preset, name, param, s)
    return s


#: The model's probes (`repro/f5_presets_mirror.py`), and the witnesses of Findings 1 and 4.
MIRROR_PROBES = [
    w(0x61, 0x8, 0x62),
    w(0x1F600),
    w(0x61, 0x301, 0x301, 0x301, 0x301),
    w(0x1EF2, 0x301),
    w(0x61, 0x62, 0xE000),
    w(0x61, 0x62, 0xFE0F),
    w(0x70, 0x61, 0x79, 0x70, 0x61, 0x49),
    w(0x1100, 0x0, 0x1161),
    w(0x61, 0x1, 0x300),
    w(0x430, 0x489),
    "Hello World",
]


@pytest.mark.parametrize("preset", sorted(PRESET_STEP_FUNCTIONS))
def test_executing_the_listed_steps_reproduces_the_preset(preset: str) -> None:
    """`docs/api/pipelines.md` says to use `PRESETS` to build an equivalent pipeline.

    Before, 15 of the model's 48 (probe, preset) cells disagreed: a missing
    `resolve_deletions`, `drop_repeated_marks` or `strip_invisibles`, and a `demojize`
    `strip_obfuscation` no longer runs.
    """
    f = getattr(disarm, preset)
    for probe in MIRROR_PROBES:
        assert _run_presets_list(preset, probe) == f(probe), (preset, ascii(probe))


def test_the_mirror_carries_what_it_missed() -> None:
    assert "skeleton_key" in disarm.PRESETS
    for preset in PRESET_STEP_FUNCTIONS:
        names = [name for name, _ in disarm.PRESETS[preset]]
        if preset != "strip_format":
            assert "resolve_deletions" in names, preset
    for preset in ("search_key", "catalog_key", "sort_key"):
        assert ("strip_invisibles", "comparison") in disarm.PRESETS[preset], preset
    assert ("demojize", "cldr") not in disarm.PRESETS["strip_obfuscation"]
    strict = [name for name, _ in disarm.PRESETS["canonicalize_strict"]]
    assert strict.index("strip_zalgo") > strict.index("fixed_point")


def test_is_canonical_takes_every_preset_the_mirror_lists() -> None:
    """`is_canonical`'s `preset` is documented as any `PRESETS` name, so `skeleton_key` too."""
    assert disarm.is_canonical("paypal", preset="skeleton_key")
    assert not disarm.is_canonical("paypaI", preset="skeleton_key")


# ---------------------------------------------------------------------------
# Finding 6: the output ceiling bounds growth, whichever step grows the text
# ---------------------------------------------------------------------------


def test_a_large_input_no_step_grows_is_accepted_with_or_without_an_actionable_byte() -> None:
    """11 MiB of `a` was accepted, and the same text after one quote was refused as having
    "expanded": the quote made the fast path decline, and NFKC then saw 11 MiB."""
    big = "a" * (11 * 1024 * 1024)
    assert disarm.canonicalize(big) == big
    assert disarm.canonicalize(chr(0x22) + big) == "''" + big
    assert disarm.search_key("A" + big) == "a" + big


def test_growth_after_nfkc_is_bounded() -> None:
    """`ml_normalize` names U+1FAF0 in 40 bytes after NFKC has passed it: 10.4 MB of it came
    back as 106.6 MB with no error."""
    text = w(0x1FAF0) * 300_000  # 1.2 MB in, 12 MB of names out
    with pytest.raises(disarm.ResourceLimitError) as excinfo:
        disarm.ml_normalize(text)
    message = str(excinfo.value)
    assert str(len(text.encode())) in message
    assert str(CEILING) in message
    # Growth under the ceiling still succeeds.
    assert disarm.ml_normalize(w(0x1FAF0) * 1_000)


def test_the_ceiling_is_one_rule_for_every_preset() -> None:
    """Growth past the allowance is refused wherever it happens; the size alone is not."""
    ligature = chr(0xFDFA)  # 3 bytes, NFKC to 33
    for name in PRESET_STEP_FUNCTIONS:
        if name == "strip_format":
            continue  # strips only; it cannot grow
        with pytest.raises(disarm.ResourceLimitError):
            getattr(disarm, name)(ligature * 400_000)  # grows by 12 MB
        assert getattr(disarm, name)(ligature * 300_000)  # grows by 9 MB


# ---------------------------------------------------------------------------
# Finding 7: documentation
# ---------------------------------------------------------------------------


def test_the_empty_key_claim_excepts_regional_indicators_in_ml_normalize() -> None:
    """Each regional indicator keys to "" alone; a pair names a flag. The docstring must not
    say that every string built from the empty-keying characters keys empty."""
    u, s = w(0x1F1FA), w(0x1F1F8)
    assert disarm.ml_normalize(u) == disarm.ml_normalize(s) == ""
    assert disarm.ml_normalize(u + s) == "flag: united states"
    doc = " ".join((disarm.ml_normalize.__doc__ or "").split())
    assert "regional indicator" in doc
    assert "so does every string built from them" not in doc


@pytest.mark.parametrize("builder", ["catalog_key", "search_key", "sort_key"])
def test_the_key_builders_do_not_claim_private_use_survives(builder: str) -> None:
    f = getattr(disarm, builder)
    assert f(w(0x61, 0x62, 0xE000)) == "ab"
    assert "survive into" not in " ".join((f.__doc__ or "").split())


def test_ml_corpus_normalize_is_not_documented_as_ascii() -> None:
    assert disarm.get_pipeline("ml_corpus_normalize")(w(0x4E2D, 0x6587)) == w(0x4E2D, 0x6587)
    page = (ROOT / "docs" / "api" / "pipelines.md").read_text(encoding="utf-8")
    row = next(line for line in page.splitlines() if line.startswith("| `ml_corpus_normalize`"))
    assert not row.rstrip().endswith("| ASCII |")


@pytest.mark.parametrize("builder", ["search_key", "sort_key"])
def test_the_policy_note_says_what_the_policy_folds(builder: str) -> None:
    """Under `tr39` and `preserve` the pre-fold is the whole confusable table: Cyrillic
    `paypal` folds to `paypal` and `|`, `"` and the backtick are rewritten."""
    f = getattr(disarm, builder)
    cyrillic = w(0x440, 0x430, 0x443, 0x440, 0x430, 0x6C)
    for policy in POLICIES:
        assert f(cyrillic, digit_policy=policy) == "paypal"
    assert f("|", digit_policy="tr39") == "l"
    assert f("|") == "|"
    doc = " ".join((f.__doc__ or "").split())
    assert "folds digit variants" not in doc
    assert "whole confusable table" in doc


def test_limitations_lists_the_policy_rewrite_of_printable_ascii() -> None:
    page = (ROOT / "docs" / "limitations.md").read_text(encoding="utf-8")
    assert "digit_policy" in page[page.index("rewrite printable ASCII") :][:4000]
