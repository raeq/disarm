"""The other direction: what a tool costs on text that needed nothing.

Every coverage score in this harness has a degenerate solution. A tool that maps
all input to the empty string folds 100% of UTS #39 onto its target, closes every
equivalence class, and recovers every attack — because both sides of every
comparison become identical. Measured on one axis it is the best tool in the
registry.

So no coverage number here is reported alone. Each is paired with a cost measured
on the same subject:

**Destruction** — assigned code points a surface maps to nothing.

**Injectivity** — distinct outputs over distinct inputs. A tool that merges
aggressively drives this toward zero, and merging is precisely how a coverage
score is faked. Note that *some* merging is the job: folding confusables onto one
form is many-to-one on purpose. Injectivity is not a score to maximise; it is the
number that says how much of the coverage was bought by collapsing.

**Benign alteration** — clean text the tool rewrites anyway. Its ground truth is
external wherever a corpus supplies it: the labelled ``clean`` column of an attack
corpus is, by the corpus author's definition, text that needs no repair.

A collision only counts as coverage when the shared form is non-empty. That rule
alone removes the delete-everything strategy, and the metrics above make a
partially-degenerate one visible.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

#: General categories that carry no identity of their own. Removing one is what
#: a sanitizer is for; keeping one is not a virtue.
_NO_IDENTITY = frozenset({"Cf", "Cc", "Co", "Cs", "Cn", "Zl", "Zp"})


@dataclass
class Damage:
    """What a set of surfaces cost on input that needed no repair."""

    inputs: int = 0
    destroyed: int = 0
    altered: int = 0
    chars_in: int = 0
    chars_out: int = 0
    #: Input characters present in the output, counted as a multiset.
    kept: int = 0
    #: Identity-bearing input characters (letters, digits, symbols) present in
    #: the output. Format, control and private-use code points are excluded:
    #: removing those is the job, and counting it as damage measured a sanitizer
    #: sanitizing. 93.5% of the "damage" in the first census was Private Use.
    kept_identity: int = 0
    chars_in_identity: int = 0
    #: Largest output/input length ratio seen on any single input.
    max_growth: float = 1.0
    distinct_in: int = 0
    distinct_out: int = 0

    @property
    def destruction_rate(self) -> float:
        return self.destroyed / self.inputs if self.inputs else 0.0

    @property
    def alteration_rate(self) -> float:
        return self.altered / self.inputs if self.inputs else 0.0

    @property
    def length_ratio(self) -> float:
        """Output length over input length. **Can exceed 1.**

        Not a retention figure, and named so it cannot be read as one. A
        transliterator maps one code point to several ASCII characters — `¼` to
        `1/4`, `→` to `->`, a CJK ideograph to a whole syllable — so a ratio
        above 1 means expansion, not that more of the input survived.
        """
        return self.chars_out / self.chars_in if self.chars_in else 1.0

    @property
    def retention(self) -> float:
        """Fraction of the input's characters that appear in the output.

        A true retention figure, bounded at 1: a multiset intersection, so
        characters the tool *adds* cannot inflate it. `length_ratio` and this
        disagree exactly when a tool substitutes rather than deletes.
        """
        return self.kept / self.chars_in if self.chars_in else 1.0

    @property
    def identity_retention(self) -> float:
        """Retention counting only characters that carry identity.

        The honest cost measure. Plain `retention` charges a sanitizer for
        removing private-use, format and control code points, which is the one
        thing it exists to do — so it scores "did the job" as "did damage".
        """
        if not self.chars_in_identity:
            return 1.0
        return self.kept_identity / self.chars_in_identity

    @property
    def expansion(self) -> float:
        """Worst single-input amplification seen.

        Its own number because expansion is a finding in this codebase, not a
        curiosity: #768 measured one code point growing 18x through every preset
        with no ceiling, and #747 found presets *manufacturing* chat-template
        delimiters that the input never contained.
        """
        return self.max_growth

    @property
    def injectivity(self) -> float:
        """Distinct outputs per distinct input over the domain measured."""
        return self.distinct_out / self.distinct_in if self.distinct_in else 1.0

    @property
    def degenerate(self) -> bool:
        """Is this tool scoring by destroying rather than by resolving?

        Deliberately blunt, and deliberately not a pass/fail on its own: it flags
        a column so a reader does not read its coverage score as a like-for-like.
        """
        return self.destruction_rate > 0.5 or self.injectivity < 0.1


def apply(fn: Callable[[str], str], text: str) -> str:
    """Run one surface; a refusal counts as leaving the text alone."""
    try:
        return fn(text)
    except Exception:  # noqa: BLE001 - a surface may reject some input
        return text


def collides(surfaces: Iterable[Callable[[str], str]], left: str, right: str) -> bool:
    """Do ``left`` and ``right`` land on one **non-empty** form under any surface?

    The non-empty requirement is the whole guard. Without it, deleting both sides
    of every pair is indistinguishable from resolving every pair.
    """
    for fn in surfaces:
        got = apply(fn, left)
        if got and got == apply(fn, right):
            return True
    return False


def per_surface(
    surfaces: dict[str, Callable[[str], str]], corpus: Sequence[str]
) -> dict[str, Damage]:
    """Cost of every surface over ``corpus``, one :class:`Damage` each."""
    out: dict[str, Damage] = {}
    for name, fn in surfaces.items():
        d = Damage(inputs=len(corpus), distinct_in=len(set(corpus)))
        outputs = []
        for text in corpus:
            got = apply(fn, text)
            outputs.append(got)
            d.chars_in += len(text)
            d.chars_out += len(got)
            # Multiset intersection: characters the tool added cannot count as
            # characters it retained.
            remaining = Counter(got)
            for ch in text:
                bears_identity = unicodedata.category(ch) not in _NO_IDENTITY
                if bears_identity:
                    d.chars_in_identity += 1
                if remaining[ch]:
                    remaining[ch] -= 1
                    d.kept += 1
                    if bears_identity:
                        d.kept_identity += 1
            if text:
                d.max_growth = max(d.max_growth, len(got) / len(text))
            if not got and text:
                d.destroyed += 1
            if got != text:
                d.altered += 1
        d.distinct_out = len(set(outputs))
        out[name] = d
    return out


def worst(damages: dict[str, Damage]) -> tuple[str, Damage]:
    """The costliest surface. Never reported without :func:`gentlest`.

    One end alone misrepresents in either direction: quote only the worst and a
    library is judged by an entry point nobody has to call; quote only the best
    and a destructive default disappears. A caller picks one surface, so the
    honest report is the range, with the name at each end.
    """
    if not damages:
        return "", Damage()
    return max(damages.items(), key=lambda kv: (kv[1].destruction_rate, kv[1].alteration_rate))


def gentlest(damages: dict[str, Damage]) -> tuple[str, Damage]:
    """The least costly surface. Never reported without :func:`worst`."""
    if not damages:
        return "", Damage()
    return min(damages.items(), key=lambda kv: (kv[1].destruction_rate, kv[1].alteration_rate))


def best_surface(
    surfaces: dict[str, Callable[[str], str]],
    pairs: Sequence[tuple[str, str]],
) -> tuple[str, int]:
    """The single surface that merges the most pairs, and how many.

    Coverage must be a *per-surface* score, not a union over every surface a
    library happens to expose. A union asks "did any of your N entry points get
    this one", which rewards shipping many rather than shipping good: disarm
    exposes 19 surfaces and gained 4.9 points from the union, while every tool
    with one or two surfaces gained nothing. A caller picks one entry point, so
    the comparable question is what one entry point achieves.

    It also makes coverage symmetric with cost, which was already measured
    per-surface — the asymmetry is what let coverage be earned by surfaces that
    the cost side had excluded.
    """
    winner, best = "", 0
    for name, fn in surfaces.items():
        hits = sum(1 for left, right in pairs if collides([fn], left, right))
        if hits > best:
            winner, best = name, hits
    return winner, best


def split_by_intent(
    surfaces: dict[str, Callable[[str], str]], collapsing: Iterable[str]
) -> tuple[dict[str, Callable[[str], str]], dict[str, Callable[[str], str]]]:
    """Separate text surfaces from surfaces whose contract is to collapse.

    A key builder is many-to-one **by design**: ``sort_key`` and ``catalog_key``
    exist to make two spellings of one thing compare equal, so low injectivity
    there is the feature working. Scoring them on the same axis as a text
    normalizer makes a library look destructive for doing its job, and would rank
    a tool with no key builder at all as the safer one.

    Returns ``(text_surfaces, collapsing_surfaces)``.
    """
    names = set(collapsing)
    text = {k: v for k, v in surfaces.items() if k not in names}
    keys = {k: v for k, v in surfaces.items() if k in names}
    return text, keys


#: Carrier words that need no repair at all. A lone combining mark is not "clean
#: text", so a code point is measured inside one of these rather than on its own.
CARRIERS = ("order", "confirm", "account", "invoice", "password")


def carried(codepoints: Sequence[int]) -> list[str]:
    """Wrap each code point in a clean ASCII carrier, as the published censuses do.

    Damage measured on isolated code points overstates it: every key builder maps
    a bare combining mark to nothing, which is correct and says nothing about what
    the tool does to text.
    """
    return [f"{CARRIERS[i % len(CARRIERS)]}{chr(cp)}end" for i, cp in enumerate(codepoints)]


def clean_ascii_corpus(size: int = 2000) -> list[str]:
    """Text that provably needs no Unicode repair: printable ASCII.

    Not a benchmark corpus — a floor. Any alteration here is pure cost, because
    there is nothing in the input for a normalizer to fix.
    """
    return [
        f"{CARRIERS[i % len(CARRIERS)]}-{i:04d} ref/{i:03d} v{i % 9}.{i % 7}" for i in range(size)
    ]


#: A carrier of ASCII letters every tool here leaves alone, so the replacement
#: can be recovered by stripping the ends. A lone code point is not enough: the
#: naming behaviour fires on text, and `strip_obfuscation("—")` returns the dash
#: untouched while `strip_obfuscation("a — b")` returned "a em dash b".
_CARRIER = ("aa", "bb")


def _replacement(fn: Callable[[str], str], ch: str) -> str | None:
    """What one code point became, measured inside a stable ASCII carrier."""
    left, right = _CARRIER
    out = apply(fn, f"{left}{ch}{right}")
    if not out.startswith(left) or not out.endswith(right):
        return None  # the carrier moved; cannot attribute the change
    return out[len(left) : len(out) - len(right)]


def classify_removal(fn: Callable[[str], str], ch: str) -> str:
    """Why did this non-ASCII character stop being non-ASCII?

    "Folded", "deleted" and "named" all remove a non-ASCII code point, and a
    metric that only counts what disappeared cannot tell them apart. That is not
    hypothetical: disarm 0.14.1 turned `a — b` into `a em dash b`, and the
    fold-rate metric scored the naming bug (#757) as coverage. When #803 fixed
    it the corpus rate *fell*, and the benchmark reported the fix as a
    regression.

    The line between a fold and a name is words, not length: `½` to `1/2` is a
    compatibility fold, `—` to `em dash` is a description. A replacement counts
    as naming when it carries whitespace or is three or more letters.

    Returns ``folded`` | ``deleted`` | ``named`` | ``survives``.
    """
    got = _replacement(fn, ch)
    if got is None or got == ch:
        return "survives"
    if not got.strip():
        return "deleted"
    if not got.isascii():
        return "survives"
    stripped = got.strip()
    if any(c.isspace() for c in got) or (len(stripped) >= 3 and stripped.isalpha()):
        return "named"
    return "folded"


def assigned_sample(step: int = 97) -> list[int]:
    """A strided sample of assigned code points.

    Strided rather than truncated, for the reason every domain here is: the low
    planes are the best-served part of every tool.
    """
    return [
        cp
        for cp in range(0, 0x110000, step)
        if not (0xD800 <= cp <= 0xDFFF) and unicodedata.category(chr(cp)) != "Cn"
    ]
