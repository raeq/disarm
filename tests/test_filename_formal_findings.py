"""`sanitize_filename` findings of the Lean model of the sanitizers (1, 2, 3 and 15).

The model (`formal/lean/Sanitizers/`) checked the documented postconditions of
`sanitize_filename` against a line-by-line model of `src/filename.rs`, differentially
tested against the built library, and cut every failed property down to a minimal input.
These are those inputs, through the binding:

* Finding 1: a stem that sanitizes to nothing left the extension as the whole name, and
  the trim that removed its dot ran after both reserved-name checks. `"*.con"` returned
  `"con"`, a Windows device name.
* Finding 2: the separator was never validated. `separator="/"` rebuilt an absolute path,
  `"\\x00"` put NUL in the name, `" "` let a truncation end in a bare `"con"`.
* Finding 3: outputs that a second call changed, after #570 had fixed one such way.
* Finding 15: one typed `%` let every `%` compatibility folding manufactured through.

Non-ASCII test data is built with `chr()`, never written literally.
"""

from __future__ import annotations

import pytest

from disarm import InvalidArgumentError, sanitize_filename

RESERVED = {"CON", "PRN", "AUX", "NUL", "CLOCK$", "KEYBD$", "SCREEN$"}
RESERVED |= {f"COM{i}" for i in range(10)} | {f"LPT{i}" for i in range(10)}

RLO = chr(0x202E)
ZWSP = chr(0x200B)
NBSP = chr(0xA0)
E_ACUTE = chr(0xE9)
FULLWIDTH_PERCENT = chr(0xFF05)
PERCENT_SOURCES = [chr(0x609), chr(0x60A), chr(0x66A), chr(0xFE6A), chr(0xFF05)]


def device_stem(name: str) -> str:
    """What Windows matches against the device list: before the first dot, spaces trimmed."""
    return name.split(".", 1)[0].rstrip(" ").upper()


# -- Finding 1 ----------------------------------------------------------------------------

FINDING_1 = ["_.con", "*.con", " .nul", "/.aux", "../.con", "\x00.com1", "?.LPT1"]


@pytest.mark.parametrize("platform", ["universal", "windows"])
@pytest.mark.parametrize("text", FINDING_1)
def test_a_stem_that_sanitizes_away_leaves_no_device_name(text: str, platform: str) -> None:
    out = sanitize_filename(text, platform=platform)
    assert device_stem(out) not in RESERVED, out
    assert sanitize_filename(out, platform=platform) == out


def test_finding_1_pinned_values() -> None:
    assert sanitize_filename("*.con") == "_con"
    assert sanitize_filename("*.NUL", platform="windows") == "_NUL"
    assert sanitize_filename("../.con") == "_con"
    assert sanitize_filename("_.con") == "_.con"  # a typed separator is a stem of its own
    assert sanitize_filename("/.con", platform="posix") == "con"  # POSIX has no devices
    # Windows reads the device name before the FIRST dot; the extension split is at the last.
    assert sanitize_filename("nul.tar.gz") == "_nul.tar.gz"
    assert sanitize_filename("*.con.tar.gz", platform="windows") == "_con.tar.gz"


@pytest.mark.parametrize("platform", ["universal", "windows"])
def test_no_character_before_a_device_extension_exposes_it(platform: str) -> None:
    """The model's sweep found 185 scalars `c` for which `c + ".con"` returned `"con"`."""
    for cp in range(0x3000):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        for ext in (".con", ".NUL", ".aux"):
            out = sanitize_filename(chr(cp) + ext, platform=platform)
            assert device_stem(out) not in RESERVED, (hex(cp), ext, out)


# -- Finding 2 ----------------------------------------------------------------------------

REJECTED_EVERYWHERE = ["/", "\\", " ", "\t", "\n", "\x00", "\x1b", "\x7f", "-\x00"]
REJECTED_EVERYWHERE += [NBSP, RLO, ZWSP, E_ACUTE, chr(0x3000)]


@pytest.mark.parametrize("platform", ["universal", "windows", "posix"])
@pytest.mark.parametrize("separator", REJECTED_EVERYWHERE, ids=ascii)
def test_a_separator_a_filename_cannot_carry_is_rejected(separator: str, platform: str) -> None:
    with pytest.raises(InvalidArgumentError, match="separator"):
        sanitize_filename("../etc/passwd", separator=separator, platform=platform)


@pytest.mark.parametrize("separator", [":", "*", "?", '"', "<", ">", "|"])
def test_what_is_illegal_follows_the_platform(separator: str) -> None:
    for platform in ("universal", "windows"):
        with pytest.raises(InvalidArgumentError):
            sanitize_filename("a b", separator=separator, platform=platform)
    assert sanitize_filename("a b", separator=separator, platform="posix") == f"a{separator}b"


@pytest.mark.parametrize("separator", ["", "_", "-", ".", "--", "~", "+"])
def test_ordinary_separators_are_accepted(separator: str) -> None:
    assert sanitize_filename("a b.txt", separator=separator) == f"a{separator}b.txt"


def test_the_pathvalidate_alias_is_validated_too() -> None:
    with pytest.raises(InvalidArgumentError):
        sanitize_filename("a b", replacement_text="/")


def test_finding_2_reproductions_are_refused() -> None:
    """Each of these used to return an unsafe name instead of raising."""
    with pytest.raises(InvalidArgumentError):
        sanitize_filename("../etc/passwd", separator="/")  # was '/etc/passwd'
    with pytest.raises(InvalidArgumentError):
        sanitize_filename("a b", separator="\x00")  # was 'a\x00b'
    with pytest.raises(InvalidArgumentError):
        sanitize_filename("con _", separator=" ", max_length=4, preserve_extension=False)
    with pytest.raises(InvalidArgumentError):
        sanitize_filename("AUX .txt", separator=" ", preserve_extension=False)


# -- Finding 3 ----------------------------------------------------------------------------

FINDING_3 = [
    ("_.x.*", {}, "_.x"),
    ("ab_cd", {"max_length": 3, "preserve_extension": False}, "ab"),
    ("a.bcd.txt", {"max_length": 6}, "a.txt"),
    ("a. .b", {"separator": "", "preserve_extension": False}, "a.b"),
    (". ./", {"separator": "-", "preserve_extension": False}, "-"),
    ("PRN.txt", {"max_length": 5}, "_.txt"),
    ("../../../etc/passwd", {}, "_.etcpasswd"),
]


@pytest.mark.parametrize(("text", "kwargs", "want"), FINDING_3, ids=[r[0] for r in FINDING_3])
def test_a_sanitized_name_is_a_fixed_point(text: str, kwargs: dict, want: str) -> None:
    once = sanitize_filename(text, **kwargs)
    assert once == want
    assert sanitize_filename(once, **kwargs) == once


def test_fixed_point_over_a_small_grid() -> None:
    """The model's grid, cut to words of up to three characters (Rust runs all of it)."""
    alphabet = [".", " ", "/", "*", "_", "c", "o", "n", "x"]
    words = [""]
    frontier = [""]
    for _ in range(3):
        frontier = [w + c for w in frontier for c in alphabet]
        words += frontier
    for word in words:
        for separator in ("_", "", "-", "."):
            for max_length in (0, 1, 2, 3, 4, 5, 6, 8):
                for platform in ("universal", "posix"):
                    for keep in (True, False):
                        kw = {
                            "separator": separator,
                            "max_length": max_length,
                            "platform": platform,
                            "preserve_extension": keep,
                        }
                        out = sanitize_filename(word, **kw)
                        assert sanitize_filename(out, **kw) == out, (word, kw, out)
                        assert ".." not in out, (word, kw, out)
                        if platform == "universal":
                            assert device_stem(out) not in RESERVED, (word, kw, out)


# -- Finding 15 ---------------------------------------------------------------------------


def test_a_typed_percent_does_not_license_a_manufactured_one() -> None:
    fw = "".join(chr(c) for c in (0xFF05, 0xFF12, 0xFF25) * 2 + (0xFF05, 0xFF12, 0xFF26))
    assert sanitize_filename("%" + fw + "etc.txt") == "%_2E_2E_2Fetc.txt"  # was '%%2E%2E%2F...'
    assert sanitize_filename(fw + "%etc.txt") == "_2E_2E_2F%etc.txt"
    assert sanitize_filename(fw + "etc.txt") == "_2E_2E_2Fetc.txt"  # #721, unchanged


@pytest.mark.parametrize(
    "source", PERCENT_SOURCES, ids=[f"U+{ord(c):04X}" for c in PERCENT_SOURCES]
)
def test_every_percent_in_the_output_was_typed(source: str) -> None:
    out = sanitize_filename(f"%a{source}b%.txt")
    assert out.count("%") == 2, out


def test_typed_percents_stay_where_they_were() -> None:
    assert sanitize_filename("100%.txt") == "100%.txt"
    assert sanitize_filename("..%2Fetc") == "%2Fetc"
    assert (
        sanitize_filename("50%-" + FULLWIDTH_PERCENT + "off.png", separator="-") == "50%--off.png"
    )
