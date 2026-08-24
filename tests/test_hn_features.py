"""Tests for features inspired by HN Unicode discussion: grapheme clusters,
hostname safety, NFC in filenames, and encoding detection."""

import re
import unicodedata
from pathlib import Path

import pytest

from disarm import (
    DisarmError,
    decode_to_utf8,
    detect_encoding,
    grapheme_len,
    grapheme_split,
    grapheme_truncate,
    is_suspicious_hostname,
    sanitize_filename,
)

# ===== Grapheme Cluster Functions =====


class TestGraphemeLen:
    def test_ascii(self) -> None:
        assert grapheme_len("hello") == 5

    def test_empty(self) -> None:
        assert grapheme_len("") == 0

    def test_nfc_accented(self) -> None:
        assert grapheme_len("caf\u00e9") == 4  # precomposed é

    def test_nfd_accented(self) -> None:
        assert grapheme_len("cafe\u0301") == 4  # base e + combining accent = 1 grapheme

    def test_family_emoji(self) -> None:
        # 👩‍👩‍👧‍👦 = 4 person codepoints + 3 ZWJ
        family = "\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
        assert grapheme_len(family) == 1

    def test_flag_emoji(self) -> None:
        # 🇬🇧 = 2 regional indicators, 1 grapheme
        assert grapheme_len("\U0001f1ec\U0001f1e7") == 1

    def test_skin_tone_emoji(self) -> None:
        # 👋🏽 = wave + skin tone modifier = 1 grapheme
        assert grapheme_len("\U0001f44b\U0001f3fd") == 1

    def test_hangul_precomposed(self) -> None:
        assert grapheme_len("\uac01") == 1  # precomposed syllable

    def test_hangul_decomposed(self) -> None:
        # ㄱ + ㅏ + ㄱ (jamo) should form 1 grapheme cluster
        assert grapheme_len("\u1100\u1161\u11a8") == 1

    def test_zalgo_text(self) -> None:
        # h + 10 combining marks = still 1 grapheme
        zalgo = "h" + "\u0335" * 10
        assert grapheme_len(zalgo) == 1

    def test_cuneiform(self) -> None:
        # 𒈙 is a single SMP character = 1 grapheme, 4 UTF-8 bytes
        assert grapheme_len("\U00012219") == 1

    def test_mixed_emoji_and_text(self) -> None:
        assert grapheme_len("hi 👋") == 4  # h, i, space, wave


class TestGraphemeSplit:
    def test_ascii(self) -> None:
        assert grapheme_split("abc") == ["a", "b", "c"]

    def test_nfd_keeps_cluster(self) -> None:
        parts = grapheme_split("cafe\u0301")
        assert len(parts) == 4
        assert parts[3] == "e\u0301"  # combining accent stays with base

    def test_emoji_family_is_one(self) -> None:
        family = "\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
        parts = grapheme_split(family)
        assert len(parts) == 1

    def test_flag_is_one(self) -> None:
        parts = grapheme_split("\U0001f1ec\U0001f1e7")
        assert len(parts) == 1

    def test_empty(self) -> None:
        assert grapheme_split("") == []


class TestGraphemeTruncate:
    def test_basic_truncation(self) -> None:
        assert grapheme_truncate("hello world", 5) == "hello"

    def test_within_limit_unchanged(self) -> None:
        assert grapheme_truncate("hi", 10) == "hi"

    def test_zero_limit(self) -> None:
        assert grapheme_truncate("hello", 0) == ""

    def test_nfd_preserves_cluster(self) -> None:
        # "cafés" in NFD = 5 graphemes; truncate to 4 should keep accent with e
        nfd = "cafe\u0301s"
        result = grapheme_truncate(nfd, 4)
        assert result == "cafe\u0301"

    def test_emoji_not_split(self) -> None:
        family = "\U0001f469\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
        text = family + " family"
        result = grapheme_truncate(text, 1)
        assert result == family

    def test_flag_not_split(self) -> None:
        text = "\U0001f1ec\U0001f1e7 UK"
        result = grapheme_truncate(text, 1)
        assert result == "\U0001f1ec\U0001f1e7"

    def test_hangul_not_split(self) -> None:
        # Decomposed Hangul should not be split mid-syllable
        jamo = "\u1100\u1161\u11a8"  # 1 grapheme
        text = jamo + "x"
        result = grapheme_truncate(text, 1)
        assert result == jamo


# ===== Hostname Safety =====


class TestIsSuspiciousHostname:
    def test_clean_ascii_domain_not_suspicious(self) -> None:
        suspicious, details = is_suspicious_hostname("paypal.com")
        assert not suspicious
        assert not details.has_confusables
        assert not details.mixed_script

    def test_cyrillic_homoglyph_attack(self) -> None:
        suspicious, details = is_suspicious_hostname("\u0440\u0430ypal.com")
        assert suspicious
        assert details.has_confusables
        assert details.mixed_script
        assert details.canonical == "paypal.com"

    def test_full_cyrillic_google(self) -> None:
        # gооgle with Cyrillic о
        suspicious, details = is_suspicious_hostname("g\u043e\u043egle.com")
        assert suspicious
        assert details.has_confusables

    def test_punycode_not_suspicious(self) -> None:
        suspicious, _ = is_suspicious_hostname("xn--n3h.com")
        assert not suspicious

    def test_subdomain_checked(self) -> None:
        suspicious, details = is_suspicious_hostname("www.\u0440\u0430ypal.com")
        assert suspicious

    def test_all_latin_not_suspicious(self) -> None:
        suspicious, details = is_suspicious_hostname("example.org")
        assert not suspicious
        assert details.scripts == ["Latin"]

    def test_mixed_non_latin_scripts_suspicious(self) -> None:
        # #254: a label mixing two non-Latin scripts (Cyrillic я + Greek ψ) with
        # no Latin confusable used to report not-suspicious. The conservative
        # policy now flags any mixed-script label as suspicious.
        suspicious, details = is_suspicious_hostname("яψ.com")
        assert suspicious
        assert details.mixed_script
        # The mixed-script rule, not the confusable check, is what catches this.
        assert not details.has_confusables

    def test_analysis_attributes(self) -> None:
        _, details = is_suspicious_hostname("test.com")
        assert hasattr(details, "suspicious")
        assert hasattr(details, "scripts")
        assert hasattr(details, "mixed_script")
        assert hasattr(details, "has_confusables")
        assert hasattr(details, "canonical")

    # --- Regression: fix #3 — IPv6 literals must not trigger script analysis ---

    def test_ipv6_loopback_not_suspicious(self) -> None:
        """[::1] is an IPv6 literal — not an IDN hostname, must not be flagged."""
        suspicious, details = is_suspicious_hostname("[::1]")
        assert not suspicious
        assert not details.mixed_script
        assert not details.has_confusables

    def test_ipv6_full_address_not_suspicious(self) -> None:
        """[2001:db8::1] must be treated as not-suspicious without script analysis."""
        suspicious, details = is_suspicious_hostname("[2001:db8::1]")
        assert not suspicious
        assert details.scripts == []

    def test_ipv6_with_port_like_syntax_not_suspicious(self) -> None:
        """Bracket + colon is the distinguishing pattern for IPv6 literals."""
        suspicious, _ = is_suspicious_hostname("[fe80::1%eth0]")
        assert not suspicious


# ===== Encoding Detection =====


class TestDetectEncoding:
    def test_utf8_detection(self) -> None:
        enc, conf = detect_encoding("café résumé".encode())
        assert enc == "UTF-8"
        assert conf > 0.0

    def test_utf8_bom(self) -> None:
        enc, _ = detect_encoding(b"\xef\xbb\xbfhello")
        assert enc == "UTF-8"

    def test_ascii_detection(self) -> None:
        enc, _ = detect_encoding(b"hello world")
        # Pure ASCII may be detected as windows-1252 or UTF-8
        assert enc in ("UTF-8", "windows-1252")

    def test_returns_tuple(self) -> None:
        result = detect_encoding(b"test")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], float)


class TestDecodeToUtf8:
    def test_utf8_explicit(self) -> None:
        text, had_errors = decode_to_utf8("café".encode(), encoding="UTF-8")
        assert text == "café"
        assert not had_errors

    def test_latin1_explicit(self) -> None:
        latin1 = bytes([0x63, 0x61, 0x66, 0xE9])  # café in ISO-8859-1
        text, had_errors = decode_to_utf8(latin1, encoding="ISO-8859-1")
        assert text == "café"
        assert not had_errors

    def test_windows1252_explicit(self) -> None:
        # "smart quotes" in windows-1252: \x93 = ", \x94 = "
        data = bytes([0x93, 0x68, 0x65, 0x6C, 0x6C, 0x6F, 0x94])
        text, had_errors = decode_to_utf8(data, encoding="windows-1252")
        assert "\u201c" in text  # left double quote
        assert "hello" in text

    def test_shift_jis_explicit(self) -> None:
        # "テスト" in Shift-JIS
        sjis = "テスト".encode("shift_jis")
        text, had_errors = decode_to_utf8(sjis, encoding="Shift_JIS")
        assert text == "テスト"
        assert not had_errors

    def test_auto_detect(self) -> None:
        text, _ = decode_to_utf8(b"hello world")
        assert text == "hello world"

    def test_unknown_encoding_raises(self) -> None:
        with pytest.raises(DisarmError):
            decode_to_utf8(b"test", encoding="FAKE-999")

    def test_lossy_decode(self) -> None:
        # Invalid UTF-8 byte sequence decoded as UTF-8 should flag errors
        bad_utf8 = bytes([0x63, 0x61, 0x66, 0xC3])  # truncated UTF-8
        text, had_errors = decode_to_utf8(bad_utf8, encoding="UTF-8")
        assert had_errors  # replacement character used


# ===== sanitize_filename NFC normalization =====


class TestFilenameNFC:
    def test_nfd_input_produces_consistent_output(self) -> None:
        """NFD and NFC input should produce the same filename."""
        nfc = "r\u00e9sum\u00e9.pdf"  # NFC: precomposed é
        nfd = "re\u0301sume\u0301.pdf"  # NFD: e + combining accent
        assert sanitize_filename(nfc) == sanitize_filename(nfd)

    def test_macos_nfd_filename(self) -> None:
        """macOS APFS stores filenames in NFD; NFC normalization prevents mismatches."""
        # Simulated macOS NFD filename
        nfd_name = "cafe\u0301.txt"
        result = sanitize_filename(nfd_name)
        # Should produce the same result as NFC input
        nfc_name = "caf\u00e9.txt"
        assert sanitize_filename(nfc_name) == result


class TestBidiDirectionConflict:
    """#412: bidi-direction conflict fields on HostnameAnalysis."""

    def test_bidi_swap_hostname(self):
        # "varonis.com.ו.קום" — Latin subdomain on a Hebrew (RTL) domain.
        suspicious, d = is_suspicious_hostname("varonis.com.ו.קום")
        assert suspicious
        assert d.bidi_conflict
        assert d.cross_label_script
        assert not d.mixed_script  # each label is single-script
        assert d.label_scripts[0] == ["Latin"]
        assert d.label_scripts[3] == ["Hebrew"]

    def test_benign_idn_cctld_not_direction_conflict(self):
        # google.рф — Latin under a Cyrillic ccTLD; both LTR, no reorder risk.
        _, d = is_suspicious_hostname("google.рф")
        assert not d.bidi_conflict
        assert d.cross_label_script  # broader fact, not folded into suspicious

    def test_all_rtl_no_conflict(self):
        _, d = is_suspicious_hostname("אתר.קום")
        assert not d.bidi_conflict
        assert not d.cross_label_script

    def test_ascii_clean(self):
        suspicious, d = is_suspicious_hostname("example.com")
        assert not suspicious
        assert not d.bidi_conflict and not d.cross_label_script


class TestInvisibleCharacters:
    """#605: has_invisible — zero-width and format characters that carry no
    direction, so #603's bidi_control cannot see them either."""

    def test_zero_width_space_is_flagged(self):
        suspicious, d = is_suspicious_hostname("paypal\u200b.evil.com")
        assert suspicious
        assert d.has_invisible

    def test_zero_width_space_never_survives_into_canonical(self):
        _, d = is_suspicious_hostname("paypal\u200b.evil.com")
        assert d.canonical == "paypal.evil.com"

    # ZWNJ/ZWJ are flagged unconditionally: IDNA2008 CONTEXTJ permits them only in
    # narrow joining contexts a spoof screen has no reason to honour.
    INVISIBLES = [
        "\u200b",  # ZWSP
        "\u200c",  # ZWNJ
        "\u200d",  # ZWJ
        "\u2060",  # WJ
        "\u2061",  # FUNCTION APPLICATION
        "\u2062",  # INVISIBLE TIMES
        "\u2063",  # INVISIBLE SEPARATOR
        "\u2064",  # INVISIBLE PLUS
        "\ufeff",  # BOM
    ]

    @pytest.mark.parametrize("invisible", INVISIBLES)
    def test_every_invisible_is_flagged(self, invisible):
        suspicious, d = is_suspicious_hostname(f"paypal{invisible}.evil.com")
        assert suspicious
        assert d.has_invisible

    @pytest.mark.parametrize("invisible", INVISIBLES)
    def test_no_invisible_survives_into_canonical(self, invisible):
        _, d = is_suspicious_hostname(f"paypal{invisible}.evil.com")
        assert invisible not in d.canonical

    def test_mongolian_vowel_separator_is_invisible_not_a_script(self):
        # U+180E was reclassified Zs -> Cf in Unicode 6.3. It is invisible, and it
        # is not evidence that a hostname contains Mongolian.
        suspicious, d = is_suspicious_hostname("paypal\u180e.evil.com")
        assert suspicious
        assert d.has_invisible
        assert "\u180e" not in d.canonical

    @pytest.mark.parametrize(
        ("host", "misread_as"),
        [("paypal\ufeff.evil.com", "Arabic"), ("paypal\u180e.evil.com", "Mongolian")],
    )
    def test_invisible_is_not_reported_as_a_script(self, host, misread_as):
        # #605: U+FEFF sits in the Arabic Presentation Forms block and U+180E in the
        # Mongolian block, so the script detector read each as a letter and
        # mixed_script fired. A caller keying policy on `scripts` was told this
        # ASCII-looking host contained Arabic.
        _, d = is_suspicious_hostname(host)
        assert misread_as not in d.scripts
        assert d.scripts == ["Latin"]
        assert not d.mixed_script


class TestInvisibleSetDoesNotDriftFromItsDocs:
    """Drift gate: the set is spelled out in prose in three places (#605 review).

    ``src/api/safety.rs``, ``python/disarm/_api.py`` and ``docs/api/predicates.md``
    each enumerate the code points ``has_invisible`` covers, and none of them was
    checked against the implementation. Review caught the Rust doc comment
    omitting ``U+180E`` after ``is_zero_width`` had already gained it — the
    documentation and the behaviour disagreed and the suite stayed green.

    So the set is *derived* from behaviour here, then compared to what each file
    claims. Probing every ``Cf``/``Zs`` code point costs ~0.3s, which buys an
    exhaustive gate rather than a sampled one.
    """

    #: The set as documented. Kept literal so a change has to be deliberate.
    DOCUMENTED = frozenset(
        {0x200B, 0x200C, 0x200D, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF, 0x180E}
    )

    ROOT = Path(__file__).resolve().parent.parent
    #: Every file whose prose enumerates the set.
    PROSE = (
        ROOT / "src" / "api" / "safety.rs",
        ROOT / "python" / "disarm" / "_api.py",
        ROOT / "docs" / "api" / "predicates.md",
    )

    @staticmethod
    def _derive() -> frozenset:
        """Every code point the hostname screen actually reports as invisible."""
        found = set()
        for cp in range(0x110000):
            ch = chr(cp)
            if unicodedata.category(ch) not in ("Cf", "Zs"):
                continue
            try:
                _, analysis = is_suspicious_hostname(f"paypal{ch}.evil.com")
            except DisarmError:
                continue
            if analysis.has_invisible:
                found.add(cp)
        return frozenset(found)

    def test_behaviour_matches_the_documented_set(self):
        derived = self._derive()
        assert derived == self.DOCUMENTED, {
            "flagged but undocumented": sorted(f"U+{c:04X}" for c in derived - self.DOCUMENTED),
            "documented but not flagged": sorted(f"U+{c:04X}" for c in self.DOCUMENTED - derived),
        }

    @pytest.mark.parametrize("path", PROSE, ids=lambda p: p.name)
    def test_prose_enumerates_the_whole_set(self, path):
        """Each file must name every code point, ranges expanded.

        ``U+200B``–``U+200D`` and ``U+2060``–``U+2064`` are written as ranges, so
        the endpoints are what appear literally; the interior points are covered
        by the range and are not required to appear on their own.
        """
        text = path.read_text(encoding="utf-8")
        named = {int(m, 16) for m in re.findall(r"U\+([0-9A-Fa-f]{4,6})", text)}
        # Endpoints of the two documented ranges, plus the two singletons.
        required = {0x200B, 0x200D, 0x2060, 0x2064, 0xFEFF, 0x180E}
        missing = sorted(f"U+{c:04X}" for c in required - named)
        assert not missing, f"{path.name} omits {missing}"

    def test_invisibles_and_bidi_controls_do_not_overlap(self):
        """The two fields are documented as disjoint. Checked, not asserted in prose."""
        for cp in sorted(self.DOCUMENTED):
            _, analysis = is_suspicious_hostname(f"paypal{chr(cp)}.evil.com")
            assert analysis.has_invisible, f"U+{cp:04X}"
            assert not analysis.bidi_control, f"U+{cp:04X} claimed by both fields"


class TestBidiControlCharacters:
    """#603: bidi_control — the UAX #9 format characters bidi_conflict cannot see."""

    # Overrides, embeddings, isolates and directional marks. IDNA2008 (RFC 5892)
    # disallows every one, so the screen fails closed on the whole set.
    CONTROLS = [
        "\u200e",
        "\u200f",
        "\u061c",  # LRM, RLM, ALM
        "\u202a",
        "\u202b",
        "\u202c",  # LRE, RLE, PDF
        "\u202d",
        "\u202e",  # LRO, RLO
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",  # LRI, RLI, FSI, PDI
    ]

    @pytest.mark.parametrize("control", CONTROLS)
    def test_control_is_flagged(self, control):
        suspicious, d = is_suspicious_hostname(f"paypal{control}moc.evil.com")
        assert suspicious
        assert d.bidi_control

    @pytest.mark.parametrize("control", CONTROLS)
    def test_control_never_survives_into_canonical(self, control):
        # The sharper half of #603: a caller told the name was clean must not be
        # handed a canonical form that still renders the spoof.
        _, d = is_suspicious_hostname(f"paypal{control}moc.evil.com")
        assert control not in d.canonical

    def test_rlo_extension_spoof(self):
        # The exact report from #603.
        suspicious, d = is_suspicious_hostname("paypal\u202emoc.evil.com")
        assert suspicious
        assert d.bidi_control
        assert d.canonical == "paypalmoc.evil.com"

    def test_disjoint_from_bidi_conflict(self):
        # The RLO spoof has a control and no direction conflict; the "BiDi Swap"
        # has a direction conflict and no control. Neither field subsumes the other.
        _, rlo = is_suspicious_hostname("paypal\u202emoc.evil.com")
        assert rlo.bidi_control and not rlo.bidi_conflict

        _, swap = is_suspicious_hostname("varonis.com.ו.קום")
        assert swap.bidi_conflict and not swap.bidi_control

    # Canonical forms pinned to their measured values: the confusable fold still
    # runs on a clean host (`рф` -> `pф`, `קום` -> `קlם`), so this also guards
    # against the #603 strip being applied where nothing should change.
    CLEAN = [
        ("paypal.com", "paypal.com"),
        ("example.co.uk", "example.co.uk"),
        ("google.рф", "google.pф"),
        ("אתר.קום", "אתר.קlם"),
    ]

    @pytest.mark.parametrize(("host", "expected_canonical"), CLEAN)
    def test_clean_hostnames_unaffected(self, host, expected_canonical):
        _, d = is_suspicious_hostname(host)
        assert not d.bidi_control
        assert d.canonical == expected_canonical

    def test_ace_path_still_fails_closed(self):
        # The wire form was never the gap — the decode already rejected it. Guard
        # against a fix that accidentally relaxes it.
        suspicious, _ = is_suspicious_hostname("xn--paypalmoc-lh0e.evil.com")
        assert suspicious


class TestWholeScriptConfusable:
    """#545: whole_script_confusable / label_whole_script_confusable — a graded
    signal (NOT folded into suspicious) naming the whole-script-spoof mechanism."""

    def test_attack_flagged(self):
        # аррӏе.com: every letter of the non-Latin label is a confusable → skeleton
        # "apple"; the non-TLD label is whole-script-confusable under a Latin TLD.
        _, d = is_suspicious_hostname("аррӏе.com")
        assert d.whole_script_confusable
        assert d.label_whole_script_confusable == [True, False]
        assert d.canonical == "apple.com"

    def test_legit_non_latin_not_flagged(self):
        # Genuine non-Latin domains: at least one letter survives the Latin skeleton
        # in every label, so no label qualifies.
        for host in ("москва.рф", "почта.рф", "госуслуги.рф", "αθήνα.gr", "אתר.קום", "例え.jp"):
            _, d = is_suspicious_hostname(host)
            assert not d.whole_script_confusable, (host, d.label_whole_script_confusable)

    def test_known_fp_cctld(self):
        # яндекс.ру — the short Cyrillic ccTLD `ру` skeletons to Latin `py`, so the
        # top-level (any-label) bool over-fires. Documented graded-signal FP: the wsc
        # label is the TLD, which a `wsc(non-TLD) ∧ latin-TLD` caller policy excludes.
        _, d = is_suspicious_hostname("яндекс.ру")
        assert d.label_whole_script_confusable == [False, True]
        assert d.whole_script_confusable

    def test_known_fp_real_word(self):
        # оса.рф ("wasp") → skeleton `oca`: an irreducible label-level FP (signal-
        # identical to a spoof). Pinned. The Cyrillic `.рф` TLD clears it under the
        # caller policy.
        _, d = is_suspicious_hostname("оса.рф")
        assert d.label_whole_script_confusable == [True, False]
        assert d.whole_script_confusable

    def test_caller_policy_discriminates(self):
        # The documented precise policy: a non-TLD label is whole-script-confusable
        # AND the TLD (rightmost label) is Latin/ASCII. True only for the real attack.
        def spoofs_latin_brand(host: str) -> bool:
            _, d = is_suspicious_hostname(host)
            tld_scripts = d.label_scripts[-1]
            latin_tld = tld_scripts in ([], ["Latin"])
            return latin_tld and any(d.label_whole_script_confusable[:-1])

        assert spoofs_latin_brand("аррӏе.com")
        for legit in ("москва.рф", "яндекс.ру", "оса.рф", "αθήνα.gr", "аррӏе.рф", "example.com"):
            assert not spoofs_latin_brand(legit), legit
