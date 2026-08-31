"""#709 and #714 — the two spellings of one hostname, and what normalization ate.

Both defects come from the same place: `is_suspicious_hostname` normalized before it
analysed, so the analysis never saw the input it is defined on.

- #709: NFKC ran first, so every compatibility form was gone before any per-label check.
  `ｇoogle.com` screened clean while `inspect_anomalies` on the same string returned
  `['compat_fold']`, and `analysis.canonical` differed from the input on every row —
  the analysis proving to itself that a fold had happened.
- #714: the UTS #46 mapping ran on the `xn--` branch only, so a literal-Unicode label
  and its own ACE spelling were two different inputs.
"""

from __future__ import annotations

import pytest

from disarm import inspect_anomalies, is_suspicious_hostname

# ── #709 ─────────────────────────────────────────────────────────────────────

# Every row from the issue's table. `canonical` is what the old code produced while
# reporting the host clean.
COMPAT_ROWS = [
    ("ｇoogle.com", "google.com"),  # fullwidth g
    ("ａdmin.com", "admin.com"),  # fullwidth a
    ("ｅxample.com", "example.com"),  # fullwidth e
    ("ｐａｙｐａｌ.com", "paypal.com"),  # all fullwidth
    ("ﬁle.com", "file.com"),  # fi ligature
    ("ⅠBM.com", "ibm.com"),  # Roman numeral one
    ("\U0001d5c0\U0001d5c8\U0001d5c8\U0001d5c0\U0001d5c5\U0001d5be.com", "google.com"),
    ("⒈2.3.4", "1.2.3.4"),  # digit one full stop
]

# The issue's zero-false-positive table.
LEGITIMATE = [
    "google.com",
    "café.com",  # decomposed é — every code point NFKC-stable
    "간극.kr",  # conjoining jamo
    "日本.jp",
    "GOOGLE.COM",
]


@pytest.mark.parametrize(("host", "canonical"), COMPAT_ROWS, ids=[r[0] for r in COMPAT_ROWS])
def test_a_compatibility_form_is_flagged(host: str, canonical: str) -> None:
    suspicious, d = is_suspicious_hostname(host)
    assert suspicious
    assert d.compat_fold
    assert d.canonical == canonical


@pytest.mark.parametrize("host", LEGITIMATE)
def test_legitimate_hostnames_do_not_trip_it(host: str) -> None:
    assert not is_suspicious_hostname(host)[1].compat_fold


def test_the_predicate_is_per_character_not_per_label() -> None:
    """`한국.kr` in conjoining jamo is NFKC-unstable as a *label* and valid per code point.

    The label-level reading ("NFKC changed the label") is the one that produces a false
    positive here; RFC 5892 §2.1 derives DISALLOWED per code point, and none of these is.
    """
    import unicodedata

    jamo = "간극.kr"
    assert unicodedata.normalize("NFKC", jamo) != jamo  # label-level: would fire
    assert all(unicodedata.normalize("NFKC", c) == c for c in jamo)  # per-character: clean
    assert not is_suspicious_hostname(jamo)[1].compat_fold


def test_it_agrees_with_inspect_anomalies() -> None:
    """The two functions returned opposite verdicts on the same string (#709)."""
    for host, _ in COMPAT_ROWS:
        if "compat_fold" in inspect_anomalies(host).kinds:
            assert is_suspicious_hostname(host)[1].compat_fold, host


def test_the_ascii_alphabetic_gate_is_not_reused() -> None:
    """`ＮＨＫ.jp` is not a registrable hostname, and the gate already fails on it.

    `src/anomalies.rs` gates `compat_fold` on the token also carrying an ASCII letter, to
    keep the rule off `ＮＨＫ` in general text. On hostname-shaped input the TLD supplies
    the ASCII, so the gate is void there anyway — and RFC 5892 needs no heuristic.
    """
    assert inspect_anomalies("ＮＨＫ.jp").kinds == ["compat_fold"]
    assert is_suspicious_hostname("ＮＨＫ.jp")[1].compat_fold


def test_has_confusables_is_correctly_false_on_a_compat_form() -> None:
    """The field cannot see a compatibility form by construction (#709 §6)."""
    _, d = is_suspicious_hostname("ｇoogle.com")
    assert d.compat_fold
    assert not d.has_confusables
    assert d.canonical != "ｇoogle.com"


# ── #714 ─────────────────────────────────────────────────────────────────────

# The worked pairs from the issue, both spellings naming one registered domain.
SPELLING_PAIRS = [
    ("ꭰꭰ.com", "xn--58da.com"),  # Cherokee — the CVE-2026-17084 row (#713)
    ("Ð.com", "xn--hda.com"),
    ("Þ.com", "xn--vda.com"),
    ("ϲ.com", "xn--4xa.com"),  # NFKC and UTS #46 disagree about lunate sigma
]


@pytest.mark.parametrize(("literal", "ace"), SPELLING_PAIRS)
def test_both_spellings_reach_one_analysis(literal: str, ace: str) -> None:
    _, a = is_suspicious_hostname(literal)
    _, b = is_suspicious_hostname(ace)
    assert a.canonical == b.canonical
    assert a.scripts == b.scripts
    assert a.mixed_script == b.mixed_script
    assert a.has_confusables == b.has_confusables
    assert a.whole_script_confusable == b.whole_script_confusable


def test_the_cherokee_row_is_flagged_in_both_spellings() -> None:
    """UTS #46 folds `U+AB70` toward `U+13A0`, which disarm maps to `D`.

    Only the ACE spelling ever reached the whole-script-confusable check, and the literal
    spelling is exactly what a CVE-2026-17084-affected pipeline emits (#713).
    """
    for host in ("ꭰꭰ.com", "xn--58da.com"):
        suspicious, d = is_suspicious_hostname(host)
        assert suspicious, host
        assert d.canonical == "DD.com", host


def test_nfkc_is_not_a_substitute_for_the_uts46_mapping() -> None:
    """NFKC maps `ϲ` U+03F2 to `ς` U+03C2; UTS #46 maps it to `σ` U+03C3.

    Normalizing before the mapping produced a label that was neither spelling's real
    form: `ϲ.com` canonicalized to `ς.com` while `xn--4xa.com` — its own ACE form —
    canonicalized to `o.com`.
    """
    import unicodedata

    assert unicodedata.normalize("NFKC", "ϲ") == "ς"
    assert (
        is_suspicious_hostname("ϲ.com")[1].canonical
        == is_suspicious_hostname("xn--4xa.com")[1].canonical
    )


def test_an_unmappable_label_fails_closed() -> None:
    """The pre-existing ACE behaviour, now reached by every label."""
    assert is_suspicious_hostname("xn--.com")[0]


def test_ordinary_hostnames_still_pass() -> None:
    """UTS #46's WHATWG-mode settings, not the strict ones — `_dmarc` is a real name."""
    for host in ("_dmarc.example.com", "a-b.example.com", "example.com", "1.2.3.4"):
        assert not is_suspicious_hostname(host)[0], host


def test_label_separators_are_the_uts46_set() -> None:
    """Splitting on `'.'` alone would read a fullwidth stop as label *content*.

    The NFKC that used to open the analysis did that job by rewriting them, and that is
    exactly what pre-empted the mapping. The separators are now handled directly.
    """
    for sep in (".", "．", "。", "｡"):
        suspicious, d = is_suspicious_hostname(f"example{sep}com")
        assert d.label_scripts == [["Latin"], ["Latin"]], sep
        assert d.canonical == "example.com", sep
        # A separator is structure, not label content. Three of the four carry a
        # compatibility decomposition (`．` and `｡` do, `。` does not), so a whole-string
        # `compat_fold` scan reported `example．com` suspicious and `example。com` clean —
        # two spellings of one host, two verdicts. RFC 5892 §2.1 is a statement about what
        # may appear *in a label*.
        assert not d.compat_fold, sep
        assert not suspicious, sep


@pytest.mark.parametrize("raw", ["ｇoogle", "ﬁle", "Ⅰbm", "ＮＨＫ"])
def test_a_compat_form_inside_punycode_fails_closed_on_the_mapping(raw: str) -> None:
    """Pins the argument for *not* checking `compat_fold` after the decode.

    The raw-label scan cannot see inside punycode — an ACE label is pure ASCII — so a
    post-decode check looks necessary. It is not: UTS #46 puts the whole compatibility
    repertoire in DISALLOWED, so `domain_to_unicode` errors and the fail-closed branch
    has already set `suspicious`. A check placed after the decode would also run after
    the NFKC and could never fire anyway.

    The punycode here is built by encoding the compatibility form *directly*, bypassing
    the mapping a registrar would apply — which is the only way such a label exists.
    """
    ace = "xn--" + raw.encode("punycode").decode("ascii")
    suspicious, d = is_suspicious_hostname(f"{ace}.com")
    assert suspicious, ace
    # Not via `compat_fold`: the label really is plain ASCII. The mapping caught it.
    assert not d.compat_fold, ace
    assert d.canonical == f"{ace}.com", ace
