"""Regression tests for the bindings harness findings (``formal/bindings/README.md``).

The Python binding already behaved as the other bindings now do for most of these; what
moved is where the behaviour lives. These pin the Python surface to the core it now
reads from, and cover what did change here (E2, the sealed-registration class).
"""

from __future__ import annotations

import inspect
import subprocess
import sys

import pytest

import disarm
from disarm import _core


class TestB1ZalgoDefaultsFromTheCore:
    def test_the_defaults_are_the_core_constants(self):
        assert _core._DEFAULT_ZALGO_MAX_MARKS == 3
        assert _core._DEFAULT_ZALGO_THRESHOLD == 3
        strip = inspect.signature(disarm.strip_zalgo).parameters["max_marks"].default
        zalgo = inspect.signature(disarm.is_zalgo).parameters["threshold"].default
        assert strip == _core._DEFAULT_ZALGO_MAX_MARKS
        assert zalgo == _core._DEFAULT_ZALGO_THRESHOLD

    def test_strip_never_removes_what_is_zalgo_declines(self):
        three = "a\u0316\u0317\u0318"
        assert not disarm.is_zalgo(three)
        assert disarm.strip_zalgo(three) == three


class TestB2UnknownLang:
    @pytest.mark.parametrize(
        "call",
        [
            lambda: disarm.transliterate("x", lang="UK"),
            lambda: disarm.transliterate(["x"], lang="UK"),
            lambda: disarm.find_untranslatable("x", lang="UK"),
            lambda: disarm.slugify("x", lang="dee"),
            lambda: disarm.search_key("x", lang="zz"),
        ],
    )
    def test_is_invalid_argument(self, call):
        with pytest.raises(disarm.InvalidArgumentError, match="unknown language code"):
            call()


class TestE1ReplacementsThroughTheSharedCore:
    """Python's transliterate now runs the core body `Transliterate::try_run` runs."""

    KEY = "zqxformalfindings"

    @pytest.fixture(autouse=True)
    def _registered(self):
        disarm.register_replacements({self.KEY: "bar"})
        yield
        disarm.remove_replacement(self.KEY)

    def test_every_transliterate_shape_applies_them(self):
        text = f"a {self.KEY} b"
        assert disarm.transliterate(text) == "a bar b"
        assert disarm.transliterate([text, text]) == ["a bar b", "a bar b"]
        assert disarm.transliterate(text, errors="strict") == "a bar b"

    def test_find_untranslatable_reports_post_replacement_offsets(self):
        assert disarm.find_untranslatable(f"{self.KEY}\ue000") == [("\ue000", 3)]

    def test_an_unchanged_string_is_returned_as_is(self):
        text = "".join(["plain", " ascii"])
        assert disarm.transliterate(text) is text


class TestS1StripAccentsPerCharacter:
    @pytest.mark.parametrize(
        ("ch", "folded"),
        [("\u037e", ";"), ("\u2126", "\u03a9"), ("\uf900", "\u8c48")],
    )
    def test_alone_and_beside_a_mark(self, ch, folded):
        assert disarm.strip_accents(ch) == folded
        assert disarm.strip_accents(f"{ch}e\u0301") == f"{folded}e"
        assert disarm.strip_accents([ch]) == [folded]


class TestD1Demojize:
    """The documented default is kept; every other binding now agrees with it."""

    def test_the_documented_default_is_the_sentinel(self):
        assert disarm.demojize("\U0001f1e6") == "[?]"
        assert disarm.demojize("x\U0001f1e6!") == "x[?]!"

    @pytest.mark.parametrize(
        ("errors", "expected"),
        [("replace", "x[?]!"), ("ignore", "x!"), ("preserve", "x\U0001f1e6!")],
    )
    def test_the_policy(self, errors, expected):
        assert disarm.demojize("x\U0001f1e6!", errors=errors) == expected


class TestE2SealedIsUnsupported:
    def test_every_sealed_mutator_raises_unsupported_error(self):
        code = (
            "import disarm as t\n"
            "t.seal_registrations()\n"
            "for fn, args in [(t.register_lang, ('yy', {})),\n"
            "                 (t.register_replacements, ({'#': 'h'},)),\n"
            "                 (t.remove_replacement, ('@',)),\n"
            "                 (t.clear_replacements, ())]:\n"
            "    try:\n"
            "        fn(*args)\n"
            "    except t.UnsupportedError:\n"
            "        continue\n"
            "    raise SystemExit(f'{fn.__name__} did not raise UnsupportedError')\n"
            "print('OK')\n"
        )
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert r.returncode == 0 and "OK" in r.stdout, f"stdout={r.stdout!r} stderr={r.stderr!r}"

    def test_unsupported_error_is_still_a_disarm_error(self):
        assert issubclass(disarm.UnsupportedError, disarm.DisarmError)
