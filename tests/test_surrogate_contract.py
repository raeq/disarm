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


# ── #476: class-based entrypoints (the boundary adapter wraps only module-level
# callables, so PyO3/Python classes that cross the str->Rust boundary on construction
# or in a method are covered here). ──

# Fresh-instance factories so the per-call comparison is not polluted by stateful
# instances (UniqueSlugifier dedups across calls on the same instance).
_CLASS_CALLABLES: list[tuple[str, Callable[[], Callable[[str], str]]]] = [
    ("Slugifier", lambda: disarm.Slugifier()),
    ("UniqueSlugifier", lambda: disarm.UniqueSlugifier()),
    ("TextPipeline", lambda: disarm.TextPipeline(transliterate=True)),
    # awesome-slugify compat shims (#473-guarded): exercise them so a regression in their
    # __call__ fails here rather than slipping past the function-level audit (#476 review).
    ("Slugify", lambda: disarm.Slugify()),
    ("UniqueSlugify", lambda: disarm.UniqueSlugify()),
]


@pytest.mark.parametrize("label,make", _CLASS_CALLABLES, ids=[n for n, _ in _CLASS_CALLABLES])
@pytest.mark.parametrize("text", SURROGATE_INPUTS)
def test_class_callable_matches_wtf8_reference(
    label: str, make: Callable[[], Callable[[str], str]], text: str
) -> None:
    """A callable class instance (Slugifier/UniqueSlugifier/TextPipeline) must not raise
    on a surrogate and must equal the call on the WTF-8->UTF-8 reference (#476)."""
    with _no_deprecation():
        assert make()(text) == make()(_canonical(text)), f"{label}() not surrogate-safe on {text!r}"


# The two classes whose `__init__` takes a `default=` empty-slug fallback that crosses
# the str->Rust boundary (#193) — the surface review L-1 covers.
_DEFAULT_KWARG_CLASSES = [
    ("Slugifier", disarm.Slugifier),
    ("UniqueSlugifier", disarm.UniqueSlugifier),
]


@pytest.mark.parametrize(
    "label,factory", _DEFAULT_KWARG_CLASSES, ids=[n for n, _ in _DEFAULT_KWARG_CLASSES]
)
@pytest.mark.parametrize("text", SURROGATE_INPUTS)
def test_slugifier_default_kwarg_is_surrogate_safe(
    label: str, factory: Callable[..., Callable[[str], str]], text: str
) -> None:
    """The `default=` kwarg crosses the str->Rust boundary in `__init__` (not the
    `@_surrogate_safe`-guarded `__call__`), so a lone surrogate there must be scrubbed,
    not raise (#476 follow-up / review L-1). The empty input routes to that default, so
    the result must equal the instance built from the WTF-8->UTF-8 reference default."""
    with _no_deprecation():
        got = factory(default="x" + text + "y")("")  # construction must not raise
        want = factory(default="x" + _canonical(text) + "y")("")
    assert got == want, f"{label}(default=…) not surrogate-safe on {text!r}"


@pytest.mark.parametrize("text", SURROGATE_INPUTS)
def test_lexicon_construction_is_surrogate_safe(text: str) -> None:
    """`Lexicon([...])` must scrub its words at construction rather than raise (#476),
    and behave as the lexicon built from the WTF-8->UTF-8 reference words."""
    with _no_deprecation():
        lex = disarm.Lexicon(["free", "m" + text + "oney"])  # must not raise
        clean = disarm.Lexicon(["free", "m" + _canonical(text) + "oney"])
    probe = "get free m" + text + "oney"
    assert disarm.has_anomalies(probe, lex) == disarm.has_anomalies(_canonical(probe), clean)


def test_lexicon_from_generator_is_not_truncated_on_retry() -> None:
    """#476 review: a generator of words is consumed by the first construction attempt;
    the scrub-and-retry must see the snapshot, not an exhausted iterator (a silently
    truncated lexicon)."""
    words = ["free", "m" + HI + "oney", "cash"]
    with _no_deprecation():
        lex = disarm.Lexicon(w for w in words)  # one-shot generator
        clean = disarm.Lexicon([_canonical(w) for w in words])
    # every word (including the one after the surrogate) must still match
    for probe in words:
        assert disarm.has_anomalies(_canonical(probe), lex) == disarm.has_anomalies(
            _canonical(probe), clean
        )


def test_text_builder_is_surrogate_safe() -> None:
    """The `Text` builder (already routes through the wrapped functions) tolerates a
    surrogate and equals the reference; pinned so it stays covered."""
    with _no_deprecation():
        assert disarm.Text("a" + HI + "b").transliterate().value == disarm.transliterate(
            _canonical("a" + HI + "b")
        )


# Exported classes with no text-accepting boundary surface: typing Protocols, value/
# result objects (returned, never constructed from user text), enum (meta)classes, and
# the exception hierarchy. Reviewed so a NEW exported class defaults to *in*-scope.
_SURROGATE_EXEMPT_CLASSES = {
    "CachedTransliterator",  # typing.Protocol
    "EmojiProvider",  # typing.Protocol
    "AnomalyReport",  # result object
    "Finding",  # result object
    "HostnameAnalysis",  # result object
    "LangMeta",
    "ScriptMeta",
    "Component",
    "Script",
    "NF",  # enums / enum metaclasses
    "DisarmError",
    "InvalidArgumentError",
    "ResourceLimitError",
    "UnsupportedError",  # exceptions
}
# Classes given explicit behavioral coverage above (or already guarded in #469/#473).
_SURROGATE_COVERED_CLASSES = {
    "Lexicon",
    "Slugifier",
    "UniqueSlugifier",
    "TextPipeline",
    "Text",
    "Slugify",
    "UniqueSlugify",  # compat wrappers, guarded in #473
}


def test_every_exported_class_is_surrogate_audited() -> None:
    """Dynamic guard (#476): every exported class is either covered by the contract above
    or on the reviewed exempt list — so a future exported class with a text surface fails
    here rather than silently skipping the boundary, mirroring the function-level audit."""
    exported = {n for n in disarm.__all__ if inspect.isclass(getattr(disarm, n, None))}
    accounted = _SURROGATE_COVERED_CLASSES | _SURROGATE_EXEMPT_CLASSES
    missing = exported - accounted
    assert not missing, (
        f"exported classes neither covered nor exempt from the surrogate contract: {missing}"
    )
    stale = accounted - exported
    assert not stale, f"covered/exempt names that are not exported classes: {stale}"
