"""#701 — decode what a smuggled run spells, rather than naming one code point of it.

disarm strips the three ASCII-smuggling carriers and, since #700, reports that invisible
characters are present. Neither answer tells the caller that the run reads
`tracked-by:acct-99213`.

Presence and decode are different strengths of evidence. An invisible character can arrive
by accident — a copy-paste artefact, a BOM, an editor quirk. A run that decodes to readable
text cannot: random damage does not spell words. A successful decode is the one signal in
this area that needs no threshold and no policy to interpret.

The three schemes and the printable-only rule follow `juriku/untrace`'s `internal/decode`.
"""

from __future__ import annotations

import pytest

import disarm

TAG_BASE = 0xE0000
CANCEL_TAG = "\U000e007f"
FLAG_BASE = "\U0001f3f4"
# Escapes, never literals: an invisible in a source file is unreviewable, and the tree
# gate rejects them outright (#802).
ZWSP, ZWNJ, ZWJ, WJ, BOM = "\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"
#: Two variation selectors whose bytes (0x00, 0x01) are not printable UTF-8.
VS_00_01 = "\ufe00\ufe01"


def tags(s: str) -> str:
    """`s` as Unicode Tags characters — the channel, not the flag."""
    return "".join(chr(ord(c) + TAG_BASE) for c in s)


def zero_width(s: str) -> str:
    """`s` as MSB-first zero-width binary."""
    return "".join(ZWNJ if (b >> (7 - i)) & 1 else ZWSP for b in s.encode() for i in range(8))


def variation(s: str) -> str:
    """`s` as variation-selector bytes."""
    return "".join(chr(0xFE00 + b) if b < 16 else chr(0xE0100 + b - 16) for b in s.encode())


ENCODERS = {"tag_ascii": tags, "zero_width_binary": zero_width, "variation_bytes": variation}
PAYLOAD = "tracked-by:acct-99213"


@pytest.mark.parametrize(("scheme", "encode"), ENCODERS.items())
def test_each_scheme_decodes_to_what_it_spells(scheme: str, encode) -> None:
    found = disarm.decode_smuggled(f"invoice{encode(PAYLOAD)}")
    assert len(found) == 1, found
    assert found[0].scheme == scheme
    assert found[0].text == PAYLOAD


@pytest.mark.parametrize(("scheme", "encode"), ENCODERS.items())
def test_the_span_is_a_byte_offset_into_the_input(scheme: str, encode) -> None:
    """A caller has to be able to slice the run back out of the string they passed.

    The offsets are **bytes**, matching `Finding.start`/`end`, so a Python caller
    encodes first. Slicing the `str` directly works only while everything before the
    run is ASCII, which is exactly the kind of thing that passes in a test and fails
    on real input.
    """
    text = f"hello{encode('hi')}world"
    raw = text.encode()
    found = disarm.decode_smuggled(text)
    assert len(found) == 1, scheme
    assert raw[: found[0].start].decode() == "hello"
    assert raw[found[0].end :].decode() == "world"


def test_the_offsets_are_bytes_and_it_matters() -> None:
    """Pinned with a non-ASCII prefix, where character and byte offsets diverge."""
    text = f"café{tags('hi')}"
    found = disarm.decode_smuggled(text)
    assert found[0].start == len("café".encode()) == 5
    assert found[0].start != len("café"), "if these were equal the test would prove nothing"


def test_ordinary_text_decodes_to_nothing() -> None:
    for s in ["hello world", "", "café", "Москва", "日本語", "🎉", "a\nb\tc"]:
        assert disarm.decode_smuggled(s) == [], repr(s)


class TestTheDecodeStaysTrustworthy:
    """`text` is populated only for valid, wholly printable UTF-8."""

    def test_undecodable_bytes_get_no_string(self) -> None:
        found = disarm.decode_smuggled(VS_00_01)
        assert len(found) == 1
        assert found[0].data == b"\x00\x01"
        assert found[0].text is None, "a garbage decode must not be reported as text"

    def test_control_bytes_are_not_printable(self) -> None:
        """Valid UTF-8 is not enough — a run of controls is not recovered text."""
        found = disarm.decode_smuggled(tags("\x1b[31m") if False else zero_width("\x07\x07"))
        assert found and found[0].text is None

    def test_a_lone_variation_selector_is_not_a_payload(self) -> None:
        """VS16 asking for emoji presentation is the common legitimate use."""
        assert disarm.decode_smuggled("\u2602\ufe0f") == []
        assert disarm.decode_smuggled("text\ufe0e") == []

    def test_a_bit_short_zero_width_run_yields_nothing(self) -> None:
        assert disarm.decode_smuggled(f"a{ZWSP}{ZWNJ}{ZWSP}b") == []

    def test_trailing_bits_are_dropped_never_padded(self) -> None:
        """Padding would invent bits the carrier did not contain."""
        found = disarm.decode_smuggled(zero_width("A") + ZWNJ + ZWNJ)
        assert len(found) == 1
        assert found[0].data == b"A"


class TestTheSubdivisionFlagAllowlist:
    """A valid flag is an emoji, not a channel — and the allowlist is #700's, not a copy."""

    @pytest.mark.parametrize("region", ["gbeng", "gbsct", "gbwls"])
    def test_a_valid_flag_is_not_a_payload(self, region: str) -> None:
        assert disarm.decode_smuggled(f"{FLAG_BASE}{tags(region)}{CANCEL_TAG}") == []

    def test_the_same_base_with_another_tail_still_decodes(self) -> None:
        """Otherwise the channel just wears a flag base."""
        found = disarm.decode_smuggled(f"{FLAG_BASE}{tags('ushi')}{CANCEL_TAG}")
        assert len(found) == 1
        assert found[0].text == "ushi"


class TestTheDetectorIntegration:
    """#701 §3: a decode outranks every other kind for the same span."""

    def test_a_decoding_run_reports_smuggled_first(self) -> None:
        report = disarm.inspect_anomalies(f"hello{tags('hi')}")
        assert report.kinds[0] == "smuggled", report.kinds
        assert "decodes to" in (report.reason or "")

    def test_it_does_not_remove_the_invisible_kind(self) -> None:
        """Outranking by ORDER, not by suppression — a caller matching `invisible` keeps working."""
        report = disarm.inspect_anomalies(f"hello{tags('hi')}")
        assert "invisible" in report.kinds

    def test_a_non_decoding_run_is_left_to_invisible(self) -> None:
        """The kind fires only where the evidence needs no threshold."""
        report = disarm.inspect_anomalies(VS_00_01)
        assert "smuggled" not in report.kinds

    def test_has_anomalies_agrees_with_inspect(self) -> None:
        """The two share one helper; this is what would catch them drifting."""
        for probe in [
            f"a{tags('hi')}",
            f"b{zero_width('hi')}",
            "plain",
            f"{FLAG_BASE}{tags('gbsct')}{CANCEL_TAG}",
        ]:
            assert disarm.has_anomalies(probe) == disarm.inspect_anomalies(probe).anomalous, repr(
                probe
            )

    def test_a_valid_flag_is_still_clean(self) -> None:
        assert disarm.has_anomalies(f"{FLAG_BASE}{tags('gbsct')}{CANCEL_TAG}") is False


def test_an_invisible_payload_is_not_recovered_text() -> None:
    """Raised in review on #940: "printable" meant "no C0 control", which is not enough.

    `U+202E` + `U+200B` is valid UTF-8 with no control character in it, and was reported
    as recovered text that renders as nothing at all.
    """
    for payload in ["\u202e\u200b", "\u200b\u200c", "\ufe00", "\u3164", "\ufffe"]:
        found = disarm.decode_smuggled(zero_width(payload))
        assert len(found) == 1, payload
        assert found[0].text is None, f"{payload!r} reported as readable text"
    assert disarm.decode_smuggled(zero_width("hi there"))[0].text == "hi there"


def test_a_terminated_tag_run_is_one_span() -> None:
    """Raised in review on #940: the scan stopped before CANCEL TAG, splitting one run."""
    text = f"x{tags('hi')}{CANCEL_TAG}y"
    found = disarm.decode_smuggled(text)
    assert len(found) == 1, found
    assert found[0].text == "hi"
    assert found[0].units == 3, "two letters and the terminator"
    assert len(found[0].data) == 2, "the terminator carries no byte"
    assert text.encode()[found[0].end :].decode() == "y", "nothing left between two runs"


def test_units_counts_what_the_run_consumed_not_what_carried_a_byte() -> None:
    """The two differ, which is why both `units` and `data` are reported (#940)."""
    zw = disarm.decode_smuggled(zero_width("hi"))[0]
    assert (zw.units, len(zw.data)) == (16, 2)
    terminated = disarm.decode_smuggled(f"{tags('hi')}{CANCEL_TAG}")[0]
    assert (terminated.units, len(terminated.data)) == (3, 2)


def test_several_runs_are_reported_in_order() -> None:
    text = f"a{tags('one')}b{zero_width('hi')}c"
    found = disarm.decode_smuggled(text)
    assert [f.text for f in found] == ["one", "hi"]
    assert found[0].start < found[1].start


def test_units_counts_carriers_not_bytes() -> None:
    """They differ per scheme, which is why both are reported."""
    tag = disarm.decode_smuggled(tags("hi"))[0]
    assert (tag.units, len(tag.data)) == (2, 2)
    zw = disarm.decode_smuggled(zero_width("hi"))[0]
    assert (zw.units, len(zw.data)) == (16, 2), "eight carriers per byte"


def test_the_repr_is_python_not_rust() -> None:
    """`{:?}` on an Option renders `Some("x")`, which is not a Python repr."""
    text = repr(disarm.decode_smuggled(tags("hi"))[0])
    assert "Some(" not in text
    assert "text=None" in repr(disarm.decode_smuggled(VS_00_01)[0])
