"""Grapheme clusters and display width."""

from __future__ import annotations

from disarm._api_common import (
    _MAX_GRAPHEME_SPLIT_INPUT,
    _checked_i64_max,
)
from disarm._boundary import (
    ResourceLimitError,
    _grapheme_len,
    _grapheme_split,
    _grapheme_truncate,
    _grapheme_width,
    _terminal_width,
)

# --- Grapheme cluster functions ---


def grapheme_len(text: str) -> int:
    """Count the number of user-perceived characters (extended grapheme clusters).

    This is the correct answer to "how many characters does the user see?"
    A single grapheme cluster may span multiple codepoints (e.g., flag emoji,
    skin-toned emoji, Hangul syllables with combining jamo, Zalgo text).

    Args:
        text: Input string.

    Returns:
        Number of extended grapheme clusters.

    Examples:
        >>> grapheme_len("café")
        4
        >>> grapheme_len("👨‍👩‍👧‍👦")  # family emoji = 1 grapheme cluster
        1
    """
    return _grapheme_len(text)


def grapheme_split(text: str) -> list[str]:
    """Split text into a list of extended grapheme clusters.

    Each element is a user-perceived character.

    Args:
        text: Input string.

    Returns:
        List of grapheme cluster strings.

    Examples:
        >>> grapheme_split("café")
        ['c', 'a', 'f', 'é']
        >>> len(grapheme_split("👨‍👩‍👧‍👦!"))  # family emoji + "!"
        2
    """
    # `len(text)` counts codepoints, not bytes; the guard and message both speak
    # in characters so the reported unit matches what is measured (#200). (An
    # O(1) codepoint count, rather than encoding the whole string to count bytes.)
    if len(text) > _MAX_GRAPHEME_SPLIT_INPUT:
        raise ResourceLimitError(
            f"input too large ({len(text)} characters); maximum for grapheme_split() "
            f"is {_MAX_GRAPHEME_SPLIT_INPUT} characters"
        )
    return _grapheme_split(text)


def grapheme_truncate(text: str, max_graphemes: int) -> str:
    """Truncate text to at most max_graphemes user-perceived characters.

    Unlike byte-level or codepoint-level truncation, this never splits
    a grapheme cluster (which could corrupt emoji, combining sequences,
    or Hangul syllables).

    Args:
        text: Input string.
        max_graphemes: Maximum number of grapheme clusters to keep.

    Returns:
        Truncated string containing at most max_graphemes grapheme clusters.

    Examples:
        >>> grapheme_truncate("Hello World", 5)
        'Hello'
        >>> grapheme_truncate("café", 3)
        'caf'
    """
    # max_graphemes's non-negative contract is enforced by the Rust core (#231).
    return _grapheme_truncate(text, _checked_i64_max(max_graphemes, "max_graphemes"))  # #255


def terminal_width(text: str, *, ambiguous_wide: bool = False) -> int:
    """Total terminal column width of ``text``, summed over grapheme clusters.

    Measures **terminal cells** (UAX #11 East Asian Width per UAX #29 cluster),
    not pixels or font metrics. Wide/fullwidth characters and emoji-presented
    clusters are 2 columns; combining marks, controls, and zero-width characters
    are 0 — including tab (U+0009) and other C0/C1 control characters, which each
    contribute **0 columns** (they are not expanded to tab stops). A zero-width
    character that opens a cluster does not hide the one it attaches to:
    ``"\\u0600" + "1"`` is one cluster and 1 column. Newlines are
    not modelled either; layout that depends on tab stops or wrapping is the
    caller's responsibility.

    Args:
        text: Input string.
        ambiguous_wide: Treat East Asian *Ambiguous* characters as 2 columns
            (for legacy double-width CJK terminals). Default ``False`` (1 column),
            matching modern UTF-8 terminals.

    Returns:
        Non-negative column count.

    Examples:
        >>> terminal_width("hello")
        5
        >>> terminal_width("世界")  # two wide CJK characters
        4
        >>> terminal_width("a😀")  # ASCII + emoji (2 cells)
        3
    """
    return _terminal_width(text, ambiguous_wide=ambiguous_wide)


def grapheme_width(cluster: str, *, ambiguous_wide: bool = False) -> int:
    """Column width of a single grapheme cluster (see `terminal_width`).

    Pass a single grapheme cluster. The width is that of the **base**: the first
    scalar, after any zero-width ``Grapheme_Cluster_Break=Prepend`` prefix such as
    ``U+0600 ARABIC NUMBER SIGN``, which UAX #29 attaches to the character after it.
    It is 0 for a combining/zero-width base, 2 for a wide or emoji-presentation
    base, otherwise 1. Trailing scalars are then inspected for presentation
    selectors that adjust this — a variation selector U+FE0F on an emoji base (or a
    keycap ``U+20E3`` on a ``0``–``9``/``#``/``*`` base) forces emoji
    presentation (width 2), and U+FE0E forces text presentation (width 1 for an
    emoji base). A stray selector of either kind on a base that is not an emoji,
    such as ``"a\\ufe0f"``, is ignored and the base's own width applies.

    It does **not** segment or sum grapheme clusters. If ``cluster`` contains
    more than the leading cluster, the extra scalars are *not* added to the
    width — but they are not blindly discarded either: a trailing presentation
    selector or keycap anywhere in the argument still affects the result per the
    rule above. For arbitrary (multi-cluster) strings use `terminal_width`.

    Args:
        cluster: A single grapheme cluster.
        ambiguous_wide: Treat East Asian *Ambiguous* characters as 2 columns.

    Returns:
        Non-negative column count.

    Examples:
        >>> grapheme_width("A")
        1
        >>> grapheme_width("世")
        2
        >>> grapheme_width("👨‍👩‍👧‍👦")  # ZWJ family emoji = 1 cluster, 2 cells
        2
    """
    return _grapheme_width(cluster, ambiguous_wide=ambiguous_wide)
