"""Tests for dedup_batch: same result as per-element transliterate, but each
distinct value processed once. Stateless — no cache to invalidate."""

from __future__ import annotations

from translit import dedup_batch, transliterate


def test_matches_plain_loop() -> None:
    data = ["café", "café", "naïve", "Москва", "café", "北京市"]
    assert dedup_batch(data) == [transliterate(x) for x in data]


def test_equals_batch_call() -> None:
    data = ["café", "Москва", "café", "naïve"]
    assert dedup_batch(data) == transliterate(data)


def test_order_and_repeats_preserved() -> None:
    data = ["b", "a", "b", "c", "a", "b"]
    assert dedup_batch(data) == ["b", "a", "b", "c", "a", "b"]


def test_empty() -> None:
    assert dedup_batch([]) == []


def test_single() -> None:
    assert dedup_batch(["café"]) == ["cafe"]


def test_kwargs_passthrough() -> None:
    data = ["Ärger", "Ärger"]
    assert dedup_batch(data, lang="de") == [transliterate(x, lang="de") for x in data]
    assert dedup_batch(["Юрий"], strict_iso9=True) == [transliterate("Юрий", strict_iso9=True)]


def test_chunking_over_batch_cap() -> None:
    # > 100,000 distinct values must be chunked at the batch cap and still align.
    data = [f"café{i}" for i in range(100_005)]
    out = dedup_batch(data)
    assert len(out) == len(data)
    assert out[0] == transliterate(data[0])
    assert out[-1] == transliterate(data[-1])
