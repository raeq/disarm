"""#469: the malformed-Unicode (surrogate) contract for the Python binding.

A Python ``str`` may carry unpaired (lone) surrogates — U+D800..U+DFFF — and may
also carry a UTF-16 surrogate *pair* as two lone code points (what
``surrogatepass`` / WTF-8 / JS- or Java-origin data decodes to). Neither can become
a Rust ``&str`` at the PyO3 boundary, so today every entrypoint raises
``UnicodeEncodeError``.

Contract (uniform with the Node binding, whose napi boundary already does this):
the input is interpreted as **WTF-8 → UTF-8** —

  * a well-formed high+low pair is recombined into its astral scalar (so Python
    matches a UTF-16-native binding, which reads the pair as one character), and
  * each genuinely lone surrogate code unit is replaced with **one** ``U+FFFD``.

The substituted ``U+FFFD`` is **terminal** (neutralize-only): a surrogate that was
splitting ``bad`` becomes a still-split ``ba�d`` — the bytes are not recovered.
No entrypoint raises; the output equals the call on the WTF-8→UTF-8 reference.

Until the boundary adapter lands these FAIL (the calls raise), which is the point.
"""

from __future__ import annotations

import contextlib
import inspect
import warnings
from collections.abc import Callable, Iterator

import pytest
from hypothesis import given
from hypothesis import strategies as st

import disarm


def _canonical(s: str) -> str:
    """The contract's reference: WTF-8 → UTF-8. Round-tripping through UTF-16
    recombines well-formed pairs into astral scalars and maps each remaining lone
    surrogate code unit to one U+FFFD. No regex; one U+FFFD per code unit."""
    return s.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


@contextlib.contextmanager
def _no_deprecation() -> Iterator[None]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield


# str -> str preset entrypoints, for the output-equality matrix (an optional lang
# is left at the default).
PRESETS: list[tuple[str, Callable[[str], str]]] = [
    ("canonicalize", disarm.canonicalize),
    ("canonicalize_strict", disarm.canonicalize_strict),
    ("strip_format", disarm.strip_format),
    ("strip_obfuscation", disarm.strip_obfuscation),
    ("transliterate", disarm.transliterate),
    ("strip_accents", disarm.strip_accents),
    ("fold_case", disarm.fold_case),
    ("collapse_whitespace", disarm.collapse_whitespace),
    ("search_key", disarm.search_key),
    ("sort_key", disarm.sort_key),
    ("catalog_key", disarm.catalog_key),
    ("ml_normalize", disarm.ml_normalize),
    ("security_clean", disarm.security_clean),
    ("normalize_user_input", disarm.normalize_user_input),
]

HI = "\ud83d"  # lone high surrogate
LO = "\udca0"  # lone low surrogate
# A *well-formed* high+low pair as TWO lone code points (what surrogatepass / WTF-8
# decoding yields) — NOT the single astral scalar. `len(PAIR) == 2`; it must
# recombine to U+1F600, not become two U+FFFD.
PAIR = chr(0xD83D) + chr(0xDE00)

# criterion-3 matrix, extended per the #469 review with the well-formed-pair rows
# (Gap 1) that force the recombine-vs-scrub choice:
SURROGATE_INPUTS = [
    HI,  # lone high
    LO,  # lone low
    "abc" + HI,  # adjacent to text
    HI + "abc",
    "a" + HI + "b" + LO + "c",  # two lone surrogates around text
    f"PаyPal{HI}  ‮ ẃ́́rld{LO}",  # embedded in an otherwise-actionable string
    PAIR,  # well-formed pair → must recombine to the astral, not become "��"
    "x" + PAIR + "y",  # pair embedded in text
    HI + PAIR,  # a lone high *then* a pair → "�😀"
]


@pytest.mark.parametrize("name,fn", PRESETS)
@pytest.mark.parametrize("text", SURROGATE_INPUTS)
def test_preset_matches_wtf8_reference(name: str, fn: Callable[[str], str], text: str) -> None:
    """No raise, and the output equals the call on the WTF-8→UTF-8 reference —
    which recombines pairs and replaces lone surrogates with one U+FFFD each."""
    with _no_deprecation():
        got = fn(text)  # must not raise UnicodeEncodeError
        want = fn(_canonical(text))
    assert got == want, f"{name}: surrogate input must behave like its WTF-8→UTF-8 form"


@pytest.mark.parametrize("name,fn", PRESETS)
def test_valid_astral_is_unaffected(name: str, fn: Callable[[str], str]) -> None:
    """criterion 4: valid astral input is unchanged (the reference is identity on it)."""
    astral = "\U0001f600 grin \U000103ff"
    with _no_deprecation():
        assert fn(astral) == fn(_canonical(astral))


def _public_text_entrypoints() -> list[tuple[str, Callable[..., object]]]:
    """Every public callable whose first parameter is ``text`` and which is callable
    with the text alone (the rest optional). Enumerated dynamically so a future
    entrypoint is covered without editing a list."""
    out: list[tuple[str, Callable[..., object]]] = []
    for name in disarm.__all__:
        obj = getattr(disarm, name)
        if inspect.isclass(obj) or not callable(obj):
            continue
        try:
            params = list(inspect.signature(obj).parameters.values())
        except (TypeError, ValueError):
            continue
        if not params or params[0].name != "text":
            continue
        # Exclude anything with a *required* further argument (positional or
        # keyword-only, e.g. `percent_encode(text, *, component)`) — those are not
        # "call with text alone" entrypoints and are covered by the matrix instead.
        needs_more = any(
            p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY, p.KEYWORD_ONLY)
            for p in params[1:]
        )
        if not needs_more:
            out.append((name, obj))
    return out


@pytest.mark.parametrize("name,fn", _public_text_entrypoints())
def test_every_text_entrypoint_is_surrogate_safe(name: str, fn: Callable[..., object]) -> None:
    """Dynamic audit (#469 review note 2): EVERY public text-first entrypoint — not
    just the presets — tolerates a lone surrogate without raising. Catches a future
    entrypoint that nobody wired through the boundary adapter, mirroring the #458
    mask-audit. (Totality only; return types vary, so no output assertion here.)"""
    with _no_deprecation():
        fn("a" + HI + "b")  # must not raise


# Arbitrary text interleaved with surrogates — including adjacent high/low that form
# pairs, so the property exercises recombination as well as lone-surrogate scrubbing.
_surrogate_text = st.lists(
    st.one_of(st.text(max_size=12), st.integers(min_value=0xD800, max_value=0xDFFF).map(chr)),
    max_size=10,
).map("".join)


def test_container_string_args_are_scrubbed() -> None:
    """#469 review: the guard scrubs strings inside containers too — a `set` passed
    as a lexicon (`has_anomalies`) must not raise on a surrogate element and behaves
    as its WTF-8→UTF-8 scrubbed form."""
    bad = "a" + HI + "b"
    with _no_deprecation():
        assert disarm.has_anomalies("hi", {bad}) == disarm.has_anomalies("hi", {_canonical(bad)})


@pytest.mark.hypothesis
@given(s=_surrogate_text)
def test_surrogate_totality_matches_reference(s: str) -> None:
    """Property: for every preset and any surrogate-laced input, the call does not
    raise and equals the call on the WTF-8→UTF-8 reference."""
    for _name, fn in PRESETS:
        with _no_deprecation():
            assert fn(s) == fn(_canonical(s))
