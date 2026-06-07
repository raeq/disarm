# Transliteration Provenance

This document records the formal standard or source behind every Unicode block
in translit's transliteration tables. Its purpose is traceability: for any
character→ASCII mapping, a reader should be able to identify which published
romanization system it follows and where to verify it.

## Methodology

Provenance was determined by comparing translit's actual per-character mappings
against published romanization tables. Diagnostic characters — those where
competing standards diverge — were used to identify the source unambiguously.

## Default Table (`translit_default.tsv`)

The default table covers the BMP (U+0080–U+FFFF). Every mapping applies unless
overridden by a language-specific table or the ISO 9 / GOST table.

### Latin Blocks

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| Latin-1 Supplement | U+0080–U+00FF | NFKD decomposition + convention | ~69% match Unicode NFKD; remainder uses conventional ASCII (AE, Th, ss, GBP, JPY) |
| Latin Extended-A | U+0100–U+017F | NFKD decomposition + convention | ~62% NFKD; remainder follows Unidecode-like conventions for stroked/hooked letters |
| Latin Extended-B | U+0180–U+024F | NFKD + Unidecode-like fallback | Letters without NFKD decomposition use phonetic approximation (Ŋ→N, Ə→A, Ʃ→Sh) |
| IPA Extensions | U+0250–U+02AF | Phonetic approximation | 0% NFKD match; maps each IPA symbol to its nearest readable ASCII. Digraphs preferred over Unidecode's uppercase convention (ʃ→sh not S, ʒ→zh not Z) |
| Latin Extended Additional | U+1E00–U+1EFF | NFKD decomposition | 99.6% NFKD match. Single exception: U+1E9E LATIN CAPITAL LETTER SHARP S → SS (no NFKD decomposition exists) |
| Spacing Modifier Letters | U+02B0–U+02FF | Phonetic approximation | Modifier letters mapped to their base letter equivalents |

### Cyrillic

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| Cyrillic | U+0400–U+04FF | **BGN/PCGN Russian (1947, revised 1994)** | Confirmed by Ж→Zh, Х→Kh, Щ→Shch, Ц→Ts, Ю→Yu, Я→Ya. Hard/soft signs map to empty string (BGN/PCGN drops them). Extended Cyrillic (non-Russian letters) uses simplified phonetic approximations consistent with BGN/PCGN conventions |
| Cyrillic Supplement | U+0500–U+052F | BGN/PCGN conventions (extended) | Follows the same digraph/phonetic pattern as base Cyrillic |

### Greek

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| Greek and Coptic | U+0370–U+03FF | **BGN/PCGN Greek (1962, amended 1996)**, modern pronunciation | Confirmed by θ→Th, φ→F, ψ→Ps, η→I (itacist/modern). **Deviation:** χ→Ch (BGN/PCGN uses Kh; Ch matches ISO 843). Coptic range (U+03E2–U+03EF) follows Coptic scholarly convention |
| Greek Extended | U+1F00–U+1FFF | NFKD decomposition to base Greek + default Greek mappings | Polytonic characters decompose then follow the base Greek table |

### Arabic

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| Arabic | U+0600–U+06FF | **BGN/PCGN Arabic (1956)** | Confirmed by ث→th, خ→kh, ذ→dh, ش→sh, غ→gh. Emphatic consonants (ص,ض,ط,ظ) lose underdot diacritics (expected for ASCII output). Definitively not Buckwalter (which uses single ASCII characters: x, v, $, etc.) |
| Arabic Presentation Forms-A | U+FB50–U+FDFF | Derived from base Arabic | Presentation forms map to the same values as their base characters |
| Arabic Presentation Forms-B | U+FE70–U+FEFF | Derived from base Arabic | Same as above |

### South Asian (Indic)

All Indic scripts follow the **UNGEGN/Hunterian** romanization pattern with ASCII
simplification (no underdots or macrons). The diagnostic is the use of "cha"/"chha"
for palatal stops (Hunterian) rather than "ca"/"cha" (IAST).

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| Devanagari | U+0900–U+097F | **UNGEGN/Hunterian** | Confirmed: ka, kha, ga, gha, cha, chha. Retroflex/dental merge (both → ta/tha/da/dha/na). Both श and ष → sha |
| Bengali | U+0980–U+09FF | **UNGEGN/Hunterian** | Mirrors Devanagari pattern. Same aspiration markers |
| Gurmukhi | U+0A00–U+0A7F | **UNGEGN/Hunterian** | Same pattern as Devanagari |
| Gujarati | U+0A80–U+0AFF | **UNGEGN/Hunterian** | Same pattern as Devanagari |
| Oriya | U+0B00–U+0B7F | **UNGEGN/Hunterian** | Same pattern as Devanagari |
| Tamil | U+0B80–U+0BFF | **UNGEGN Tamil** | Fewer consonants (no aspirated series). ழ→zha is diagnostic of UNGEGN Tamil |
| Telugu | U+0C00–U+0C7F | **UNGEGN/Hunterian** | Same Indic pattern |
| Kannada | U+0C80–U+0CFF | **UNGEGN/Hunterian** | Same Indic pattern |
| Malayalam | U+0D00–U+0D7F | **UNGEGN/Hunterian** | Same Indic pattern |
| Sinhala | U+0D80–U+0DFF | **UNGEGN/Indic pattern** | Standard Indic framework extended with Sinhala-specific prenasalized stops (nnga, nndda, mba) and unique vowels (ae, aae) |

### Southeast Asian

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| Thai | U+0E00–U+0E7F | **RTGS (Royal Thai General System)** | Exact match on all consonants and vowels tested. Aspiration distinction (k/kh, t/th, p/ph) matches RTGS precisely |
| Lao | U+0E80–U+0EDF | **BGN/PCGN Lao (1966)** | Confirmed by digraph pattern (kh, ch, th, ph, ng). Vowels ASCII-simplified (ue instead of diacritics) |
| Khmer | U+1780–U+17FF | **UNGEGN Khmer (simplified)** | Two-series consonants collapse to same romanization (expected for ASCII). Vowels heavily simplified. KHR for Riel currency symbol |
| Myanmar | U+1000–U+109F | **MLC (Myanmar Language Commission)** | Confirmed by hsa at U+1006 (diagnostic). Follows Indic aspiration pattern. Medial consonants: y, r, w, h |

### Tibetan

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| Tibetan | U+0F00–U+0FFF | **Indic-phonetic romanization (NOT Wylie)** | U+0F45 ཅ→cha definitively rules out Wylie (which uses ca). Also chha for U+0F46. Follows UNGEGN/Hunterian-style aspiration markers applied to Tibetan consonants. Likely THL Simplified Phonetic or similar. **Note: docs/user-guide/language-support.md incorrectly claims "Wylie-based"** |

### Caucasian

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| Georgian | U+10A0–U+10FF | **BGN/PCGN Georgian (2009)** | Confirmed by base consonant choices (gh, zh, kh, dz). **Deviation:** Ejective apostrophes stripped — t'/k'/p'/ts'/ch' all lose the apostrophe, causing ejective/non-ejective pairs to merge. Expected for ASCII |
| Armenian | U+0530–U+058F | **BGN/PCGN Armenian (1981)** | Confirmed by digraphs (Zh, Kh, Gh, Sh, Ch, Ts) and "yev" for ew ligature (U+0587). **Deviation:** Aspirate apostrophes stripped — Ch'/Ts'/P'/K' lose apostrophes |

### Semitic

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| Hebrew | U+0590–U+05FF | **BGN/PCGN Hebrew (1962/2018)** | Confirmed by: ב→v (spirant default), ש→sh, צ→ts, ק→q. **Deviation:** ח(het)→ch instead of BGN/PCGN kh. The "ch" reflects Ashkenazi/popular convention |
| Syriac | U+0700–U+074F | Phonetic approximation | Follows Arabic-like conventions adapted for Syriac |
| Thaana | U+0780–U+07BF | Phonetic approximation | Maldivian Thaana mapped to phonetic ASCII equivalents |

### African

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| Ethiopic | U+1200–U+137F | **BGN/PCGN Amharic (1967)** | Confirmed by syllabic vowel order (e, u, i, a, e, ∅, o, wa) and bare-consonant 6th order. Digraphs: sh, ch match BGN/PCGN |

### Historic and Specialized

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| Ogham | U+1680–U+169F | Standard scholarly values | Matches Book of Ballymote / modern Celtic studies consensus. Beith-Luis-Nion order |
| Runic | U+16A0–U+16FF | Phonetic values per scholarly consensus | Mixed Elder/Younger Futhark and Anglo-Saxon values. No single published standard; uses commonly accepted sound values per Unicode character names |
| Cherokee | U+13A0–U+13FF | Syllabary phonetic values | Each syllable mapped to its phonetic romanization |
| Canadian Aboriginal Syllabics | U+1400–U+167F | Phonetic decomposition | No single published standard. Each syllabic mapped to its consonant+vowel phonetic value, reflecting the inherent structure of the unified syllabary |

### CJK and East Asian

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| CJK Compatibility Ideographs | U+F900–U+FAFF | **Unicode Unihan kMandarin** | Same source as hanzi_pinyin.tsv. Toneless pinyin |
| Hangul Jamo | U+1100–U+11FF | **Revised Romanization of Korean (RR, 2000)** | Jamo components; full syllable romanization is algorithmic in hangul.rs |
| Hiragana | U+3040–U+309F | **Modified Hepburn** | Standard Hepburn romanization for Japanese kana |
| Katakana | U+30A0–U+30FF | **Modified Hepburn** | Same as Hiragana |
| Halfwidth and Fullwidth Forms | U+FF00–U+FFEF | NFKD to base character | Fullwidth Latin letters decompose to ASCII; halfwidth katakana follows Hepburn |
| Kangxi Radicals | U+2F00–U+2FDF | **Unicode Unihan kMandarin** | Mapped via radical-to-ideograph correspondence |
| Enclosed Alphanumerics | U+2460–U+24FF | Numeric/letter extraction | ① → 1, Ⓐ → A, etc. |

### Symbols and Punctuation

| Block | Range | Source | Notes |
|-------|-------|--------|-------|
| General Punctuation | U+2000–U+206F | Functional ASCII equivalents | —→-, …→..., etc. |
| Currency Symbols | U+20A0–U+20CF | ISO 4217 codes or conventional abbreviations | ₤→GBP, ₹→Rs, ₩→KRW, etc. |
| Number Forms | U+2150–U+218F | Numeric expansion | ⅓→1/3, Ⅳ→IV, etc. |
| Superscripts and Subscripts | U+2070–U+209F | Base digit/letter | ² → 2, ₂ → 2, etc. |
| Letterlike Symbols | U+2100–U+214F | Expansion or abbreviation | ℃→C, №→No, etc. |

## Language Override Tables (`translit_lang_*.tsv`)

These tables override specific characters from the default table when a `lang`
parameter is provided.

| File | Standard | Has header comment? |
|------|----------|:---:|
| `translit_lang_am.tsv` | BGN/PCGN Amharic overrides | Yes |
| `translit_lang_bg.tsv` | BGN/PCGN Bulgarian | No |
| `translit_lang_ca.tsv` | Catalan convention (punt volat removal) | No |
| `translit_lang_de.tsv` | German convention (ä→ae, ö→oe, ü→ue, ß→ss) | No |
| `translit_lang_el.tsv` | BGN/PCGN Greek overrides | No |
| `translit_lang_es.tsv` | Spanish convention (¡→!, ¿→?) | No |
| `translit_lang_et.tsv` | Estonian convention (ä→ae, ö→oe, ü→ue, š→sh, ž→zh) | No |
| `translit_lang_fa.tsv` | BGN/PCGN Persian (1958) | Yes |
| `translit_lang_fr.tsv` | French convention (Œ→OE, œ→oe) | No |
| `translit_lang_is.tsv` | Icelandic convention (Æ→Ae, ð→d, þ→th) | No |
| `translit_lang_it.tsv` | Italian convention | No |
| `translit_lang_ja.tsv` | Modified Hepburn overrides | No |
| `translit_lang_ja_kunrei.tsv` | Kunrei-shiki romanization | Yes |
| `translit_lang_nl.tsv` | Dutch convention (IJ digraph) | No |
| `translit_lang_no.tsv` | Norwegian convention (Å→Aa, Ø→Oe, Æ→Ae) | No |
| `translit_lang_pt.tsv` | Portuguese convention | No |
| `translit_lang_ru.tsv` | BGN/PCGN Russian overrides (Ё→Yo, Й→Y, Ъ→", Ь→') | No |
| `translit_lang_sr.tsv` | BGN/PCGN Serbian overrides | No |
| `translit_lang_sv.tsv` | Swedish convention (Ä→Ae, Ö→Oe, Å→Aa) | No |
| `translit_lang_tr.tsv` | Turkish convention (İ→I, ı→i) | No |
| `translit_lang_uk.tsv` | Ukrainian national romanization (2010) | No |
| `translit_lang_vi.tsv` | Vietnamese NFKD + convention | No |
| `translit_iso9.tsv` | Scholarly ASCII Cyrillic (`strict_iso9`, ISO 9-style) | No |
| `translit_gost7034.tsv` | **GOST R 7.0.34-2014** (simplified Russian) | Yes |

## Alternate Cyrillic Tables

| File | Standard |
|------|----------|
| `translit_iso9.tsv` | Scholarly ASCII Cyrillic transliteration (ISO 9-style digraphs; **not** the diacritic ISO 9:1995 standard — values are ASCII-only by design, so not the standard's reversible diacritic mapping). See #94. |
| `translit_gost7034.tsv` | GOST R 7.0.34-2014 — Russian national standard for simplified transliteration. ASCII-compatible |

## SMP Table (`translit_default_smp.tsv`)

Already annotated with block-level comments in the file itself. Covers:
- Gothic (U+10330–U+1034A) — Wulfila's alphabet, one-to-one Latin correspondence
- Old Persian Cuneiform (U+103A0–U+103D5) — Syllabic values
- Linear B Syllabary (U+10000–U+1005D) — Conventional syllabic values

## Algorithmic Transliteration (not in TSV)

These are computed at runtime, not stored in the default table:

| Script | Source file | Standard |
|--------|-----------|----------|
| Hangul syllables (U+AC00–U+D7A3) | `hangul.rs` | **Revised Romanization of Korean (RR, 2000)** — official South Korean standard. Algorithmic jamo decomposition: 19 initials × 21 vowels × 28 finals = 11,172 syllables |
| CJK Unified Ideographs (U+4E00–U+9FFF) | `hanzi_pinyin.rs` | **Unicode Unihan kMandarin field** — toneless pinyin. 20,924 characters |

## Known Documentation Errors

1. **Tibetan claimed as "Wylie-based"** in `docs/user-guide/language-support.md:100`.
   The actual mapping uses cha for U+0F45 ཅ, ruling out Wylie (which uses ca).
   The system follows an Indic-phonetic romanization with Hunterian-style aspiration
   markers. This should be corrected in the docs.

## Design Principles

The audit reveals a consistent set of design decisions across all blocks:

1. **BGN/PCGN is the primary standard family** for non-Latin scripts (Cyrillic,
   Greek, Arabic, Armenian, Georgian, Hebrew, Lao, Ethiopic). This is the system
   used by the US Board on Geographic Names and the UK Permanent Committee on
   Geographical Names.

2. **UNGEGN/Hunterian for South Asian scripts.** BGN/PCGN defers to UNGEGN for
   Indic romanization, and UNGEGN's system is based on the Hunterian scheme.

3. **National/official standards where they exist:** RTGS for Thai, RR for Korean,
   MLC for Myanmar.

4. **Unicode data for CJK:** Unihan kMandarin for Chinese, algorithmic RR for
   Korean, Hepburn for Japanese kana.

5. **ASCII simplification is applied uniformly:** Diacritics are dropped, underdots
   removed, apostrophe modifiers stripped. This is documented as an explicit design
   constraint, not an oversight.

6. **NFKD decomposition for Latin extensions:** Where Unicode provides a
   decomposition to ASCII-range characters, it is used. Where NFKD fails (IPA,
   stroked letters, ligatures), phonetic approximation fills the gap.
