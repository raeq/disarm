"""Regression tests for slugify correctness.

Pin exact expected outputs. Tests for numeric HTML entity decoding
and regex_pattern behavior.
"""

from __future__ import annotations

from disarm import slugify


class TestHtmlEntityDecoding:
    """HTML entity decoding in slugify."""

    def test_named_entity_amp(self) -> None:
        """&amp; should decode to & which becomes empty after transliteration."""
        result = slugify("&amp; test")
        assert "test" in result

    def test_numeric_decimal_entity(self) -> None:
        """&#38; is numeric decimal for &, which is non-alnum and dropped."""
        result = slugify("&#38; test")
        assert "test" in result

    def test_numeric_hex_entity(self) -> None:
        """&#x26; is numeric hex for &, which is non-alnum and dropped."""
        result = slugify("&#x26; test")
        assert "test" in result

    def test_numeric_decimal_eacute(self) -> None:
        """&#233; is decimal for é → transliterates to e."""
        result = slugify("caf&#233;")
        assert result == "cafe"

    def test_numeric_hex_eacute(self) -> None:
        """&#xe9; is hex for é → transliterates to e."""
        result = slugify("caf&#xe9;")
        assert result == "cafe"

    def test_numeric_entity_uppercase_x(self) -> None:
        """&#X26; with uppercase X should also decode."""
        result = slugify("&#X41;bc")
        assert "abc" in result.lower()

    def test_named_entity_lt(self) -> None:
        assert slugify("&lt;tag&gt;") == "tag"

    def test_named_entity_quot(self) -> None:
        result = slugify("&quot;hello&quot;")
        assert "hello" in result


class TestRegexPattern:
    """regex_pattern filters characters from the slug."""

    def test_regex_removes_digits(self) -> None:
        result = slugify("hello 123 world", regex_pattern=r"[^a-z]+")
        # After transliteration: "hello 123 world"
        # After lowercase: "hello 123 world"
        # After regex removes non-[a-z]: "helloworld"
        # After separator logic: no separators left to insert
        assert result == "helloworld"

    def test_regex_basic(self) -> None:
        result = slugify("abc-123-def", regex_pattern=r"[0-9]+")
        assert "123" not in result


class TestControlCharEntityDecoding:
    """Regression: fix #2 — entities that decode to control chars must not appear in slugs.

    Before the fix, &#0; decoded to U+0000 (NUL) which passed through the
    slugify pipeline. Now control chars are filtered at the entity decode step.
    """

    def test_nul_entity_decimal_not_in_slug(self) -> None:
        """&#0; must not produce a NUL byte in the slug output."""
        result = slugify("hello&#0;world")
        assert "\x00" not in result

    def test_nul_entity_hex_not_in_slug(self) -> None:
        """&#x0; (hex NUL) must not produce a NUL byte in the slug output."""
        result = slugify("&#x0;")
        assert "\x00" not in result

    def test_backspace_entity_not_in_slug(self) -> None:
        """&#8; (U+0008 backspace) is a control char — must not appear in slug."""
        result = slugify("hello&#8;world")
        assert "\x08" not in result

    def test_tab_entity_not_in_slug(self) -> None:
        """&#9; (U+0009 tab) is a control char — must not appear in slug."""
        result = slugify("hello&#9;world")
        assert "\x09" not in result

    def test_valid_entity_still_decodes(self) -> None:
        """Regression guard: the filter must not break valid entity decoding."""
        assert slugify("caf&#233;") == "cafe"
        assert slugify("caf&#xe9;") == "cafe"
        assert slugify("&#65;BC") == "abc"


class TestUniqueSlugifierAmortized:
    """#242 item 3: UniqueSlugifier caches a per-base counter hint so the k-th
    duplicate no longer re-walks suffixes 1..k (O(n²) → amortized O(n)). The hint
    must not change output: same suffix sequence, uniqueness, check-path, reset."""

    def test_bulk_duplicates_unique_and_sequenced(self) -> None:
        from disarm import UniqueSlugifier

        u = UniqueSlugifier()
        out = [u("Hello World") for _ in range(3000)]
        assert len(set(out)) == 3000  # all unique
        assert out[0] == "hello-world"
        assert out[1] == "hello-world-1"
        assert out[2999] == "hello-world-2999"

    def test_interleaved_bases(self) -> None:
        from disarm import UniqueSlugifier

        u = UniqueSlugifier()
        got = [u("a"), u("b"), u("a"), u("b"), u("a")]
        assert got == ["a", "b", "a-1", "b-1", "a-2"]

    def test_check_callback_path_unchanged(self) -> None:
        from disarm import UniqueSlugifier

        seen: set[str] = set()
        u = UniqueSlugifier(check=lambda s: s in seen)
        for _ in range(5):
            s = u("x")
            assert s not in seen
            seen.add(s)
        assert seen == {"x", "x-1", "x-2", "x-3", "x-4"}

    def test_reset_clears_hint(self) -> None:
        from disarm import UniqueSlugifier

        u = UniqueSlugifier()
        assert u("Hello World") == "hello-world"
        assert u("Hello World") == "hello-world-1"
        u.reset()
        # After reset the bare base must be free again (stale hint must be cleared).
        assert u("Hello World") == "hello-world"


class _FullWalk:
    """The loop of 0.17.2: each call walks the suffixes of its base from counter 0 and
    asks `check` about every candidate it has not given out. The reference for #1100."""

    def __init__(self, check) -> None:  # noqa: ANN001
        self.seen: set[str] = set()
        self.check = check

    def __call__(self, text: str) -> str:
        base = slugify(text)
        if not base:
            return base
        counter = 0
        while True:
            candidate = base if counter == 0 else f"{base}-{counter}"
            if candidate not in self.seen and not self.check(candidate):
                self.seen.add(candidate)
                return candidate
            counter += 1

    def reset(self) -> None:
        self.seen.clear()


class TestUniqueSlugifierCheckWalk:
    """#1100: with a `check`, every call walked the suffixes of its base from 0, a
    `format!` and a set lookup for each slug already given out, so n equal slugs cost
    n²/2 of them. The walk of a base is now resumed where it stopped, and the counters
    `check` refused are kept and asked about again. Slugs, callbacks and errors are
    the ones the full walk gave."""

    def test_time_follows_the_calls_and_not_the_base(self) -> None:
        """8,000 calls take the same time on one base as on eight: 5.4 times as long
        on 0.17.2, where the one base walked 32 million suffixes."""
        import time

        from disarm import UniqueSlugifier

        def seconds(bases: int, per_base: int) -> float:
            unique = UniqueSlugifier(check=lambda slug: False)
            texts = [f"Total {chr(ord('a') + i)}" for i in range(bases)]
            start = time.perf_counter()
            for text in texts:
                for _ in range(per_base):
                    unique(text)
            return time.perf_counter() - start

        one = min(seconds(1, 8000) for _ in range(5))
        eight = min(seconds(8, 1000) for _ in range(5))
        assert one < 3 * eight, f"one base {one * 1e3:.1f} ms, eight bases {eight * 1e3:.1f} ms"

    def test_a_refused_slug_is_asked_about_again_and_given_out_when_free(self) -> None:
        from disarm import UniqueSlugifier

        taken = {"total-1"}
        asked: list[str] = []
        unique = UniqueSlugifier(check=lambda slug: asked.append(slug) or slug in taken)
        assert [unique("Total"), unique("Total")] == ["total", "total-2"]
        taken.clear()
        assert [unique("Total"), unique("Total")] == ["total-1", "total-3"]
        assert asked == ["total", "total-1", "total-2", "total-1", "total-3"]

    def test_a_refused_slug_is_asked_about_on_every_call(self) -> None:
        from disarm import UniqueSlugifier

        taken = {"total-1"}
        asked: list[str] = []
        unique = UniqueSlugifier(check=lambda slug: asked.append(slug) or slug in taken)
        assert [unique("Total") for _ in range(5)] == [
            "total",
            "total-2",
            "total-3",
            "total-4",
            "total-5",
        ]
        assert asked == [
            "total",
            "total-1",
            "total-2",
            "total-1",
            "total-3",
            "total-1",
            "total-4",
            "total-1",
            "total-5",
        ]

    def test_a_slug_of_another_base_is_passed_without_a_callback(self) -> None:
        from disarm import UniqueSlugifier

        asked: list[str] = []
        unique = UniqueSlugifier(check=lambda slug: asked.append(slug) or False)
        texts = ("Total", "Total 1", "Total", "Total")
        assert [unique(text) for text in texts] == ["total", "total-1", "total-2", "total-3"]
        assert asked == ["total", "total-1", "total-2", "total-3"]

    def test_a_refused_slug_another_base_took_is_not_asked_about_again(self) -> None:
        """`total-1` is refused, then freed, then produced by `Total 1`: it is in the
        set of given slugs from then on, and `Total` passes it without a callback."""
        from disarm import UniqueSlugifier

        taken = {"total-1"}
        asked: list[str] = []
        unique = UniqueSlugifier(check=lambda slug: asked.append(slug) or slug in taken)
        assert [unique("Total"), unique("Total")] == ["total", "total-2"]
        taken.clear()
        assert unique("Total 1") == "total-1"
        del asked[:]
        assert unique("Total") == "total-3"
        assert asked == ["total-3"]

    def test_reset_gives_the_state_of_a_new_instance(self) -> None:
        from disarm import UniqueSlugifier

        taken = {"total-1"}
        asked: list[str] = []
        unique = UniqueSlugifier(check=lambda slug: asked.append(slug) or slug in taken)
        first = [unique("Total") for _ in range(3)]
        calls = len(asked)
        unique.reset()
        assert [unique("Total") for _ in range(3)] == first == ["total", "total-2", "total-3"]
        assert asked[calls:] == asked[:calls]

    def test_a_check_that_raises_leaves_the_instance_as_it_was(self) -> None:
        import pytest

        from disarm import UniqueSlugifier

        calls: list[str] = []
        down = [True]

        def check(slug: str) -> bool:
            calls.append(slug)
            if slug == "total-1" and down[0]:
                raise ValueError("database is down")
            return False

        unique = UniqueSlugifier(check=check)
        assert unique("Total") == "total"
        with pytest.raises(ValueError, match="database is down"):
            unique("Total")
        down[0] = False
        assert unique("Total") == "total-1"
        assert calls == ["total", "total-1", "total-1"]

    def test_the_limit_stays_where_it_is(self) -> None:
        import pytest

        from disarm import ResourceLimitError, UniqueSlugifier

        asked: list[str] = []
        unique = UniqueSlugifier(check=lambda slug: asked.append(slug) or True)
        with pytest.raises(ResourceLimitError):
            unique("Total")
        assert len(asked) == 10_001
        assert asked[-1] == "total-10000"
        # Every refused slug is asked about again, in the same order.
        with pytest.raises(ResourceLimitError):
            unique("Total")
        assert asked[10_001:] == asked[:10_001]

    def test_call_10_002_for_one_base_raises_with_and_without_a_check(self) -> None:
        import pytest

        from disarm import ResourceLimitError, UniqueSlugifier

        for options in ({}, {"check": lambda slug: False}):
            unique = UniqueSlugifier(**options)
            slugs = [unique("Total") for _ in range(10_001)]
            assert slugs[-1] == "total-10000"
            with pytest.raises(ResourceLimitError):
                unique("Total")

    def test_max_length_cuts_the_base_as_before(self) -> None:
        from disarm import UniqueSlugifier

        taken = {"tot-1"}
        asked: list[str] = []
        unique = UniqueSlugifier(
            max_length=5, check=lambda slug: asked.append(slug) or slug in taken
        )
        assert [unique("Total") for _ in range(12)] == [
            "total",
            "tot-2",
            "tot-3",
            "tot-4",
            "tot-5",
            "tot-6",
            "tot-7",
            "tot-8",
            "tot-9",
            "to-10",
            "to-11",
            "to-12",
        ]
        assert len(asked) == 23

    def test_slugs_callbacks_and_errors_are_those_of_the_full_walk(self) -> None:
        """300 random sequences against `_FullWalk`. Between the calls slugs are taken
        and freed, `check` starts and stops raising for a slug, and both sides are
        reset; `Total 1` and `Total 1 1` produce slugs that `Total` reaches by suffix."""
        import random

        from disarm import UniqueSlugifier

        texts = ("Total", "Total 1", "Total 2", "Total 1 1", "Other", "Other 1", "!!!")
        pool = [
            f"{base}{suffix}"
            for base in ("total", "total-1", "total-2", "other", "other-1")
            for suffix in ("", "-1", "-2", "-3", "-4", "-5")
        ]
        for seed in range(300):
            rng = random.Random(seed)
            taken: set[str] = set()
            failing: set[str] = set()
            logs: tuple[list[str], list[str]] = ([], [])

            def checker(log: list[str], taken=taken, failing=failing):  # noqa: ANN001, ANN202
                def check(slug: str) -> bool:
                    log.append(slug)
                    if slug in failing:
                        raise LookupError(slug)
                    return slug in taken

                return check

            unique = UniqueSlugifier(check=checker(logs[0]))
            reference = _FullWalk(checker(logs[1]))
            for step in range(80):
                roll = rng.random()
                if roll < 0.30:
                    taken ^= {rng.choice(pool)}
                elif roll < 0.36:
                    failing ^= {rng.choice(pool)}
                elif roll < 0.38:
                    unique.reset()
                    reference.reset()
                text = rng.choice(texts)
                got = []
                for subject in (unique, reference):
                    try:
                        got.append(subject(text))
                    except LookupError as error:
                        got.append(f"raised for {error}")
                where = f"seed {seed}, step {step}, text {text!r}"
                assert got[0] == got[1], where
                assert logs[0] == logs[1], where
