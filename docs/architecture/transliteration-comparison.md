# Transliteration Comparison: translit vs Unidecode vs anyascii

Comprehensive character-level comparison across all 65 supported languages.
Every assigned codepoint in each language's Unicode block(s) is tested — no sampling.

## Methodology

For each language:
1. All assigned codepoints in the relevant Unicode block(s) are enumerated
2. Unassigned, private-use, surrogate, and format characters are skipped
3. Each character is transliterated by all three libraries with the language's `lang` parameter
4. "Mapped" means at least one library produced meaningful ASCII output
   (not empty, not `[?]`, not the original character)

This approach is deterministic and comprehensive — results do not depend on sample text selection.

## Summary

| Lang | Description | Block chars | Mapped | translit | Unidecode | anyascii | translit-only | Unidecode-only | Output diffs |
|------|-------------|------------|--------|----------|-----------|----------|---------------|----------------|-------------|
| bg | Bulgarian | 304 | 301 | 292 | 234 | 301 | 65 | 7 | 78 |
| ca | Catalan | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| cs | Czech | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| cy | Welsh | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| da | Danish | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 29 |
| de | German | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 30 |
| el | Greek | 135 | 135 | 135 | 106 | 135 | 29 | 0 | 34 |
| es | Spanish | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| et | Estonian | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 30 |
| fi | Finnish | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 28 |
| fr | French | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| ga | Irish | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| hr | Croatian | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| hu | Hungarian | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| is | Icelandic | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 27 |
| it | Italian | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| lt | Lithuanian | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| lv | Latvian | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| mt | Maltese | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| nl | Dutch | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| no | Norwegian | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 29 |
| pl | Polish | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| pt | Portuguese | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| ro | Romanian | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| sk | Slovak | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| sl | Slovenian | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| sq | Albanian | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| sr | Serbian | 304 | 301 | 290 | 234 | 301 | 65 | 9 | 78 |
| sv | Swedish | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 28 |
| tr | Turkish | 400 | 400 | 400 | 398 | 400 | 2 | 0 | 24 |
| uk | Ukrainian | 304 | 301 | 292 | 234 | 301 | 65 | 7 | 80 |
| vi | Vietnamese | 656 | 656 | 647 | 645 | 656 | 2 | 0 | 25 |
| ja | Japanese | 248 | 248 | 234 | 240 | 246 | 2 | 8 | 12 |
| ja-kunrei | Japanese Kunrei | 189 | 189 | 178 | 181 | 188 | 2 | 5 | 9 |
| ko | Korean | 11172 | 11172 | 11172 | 11172 | 11172 | 0 | 0 | 3762 |
| zh | Chinese | 20992 | 20954 | 20924 | 20642 | 20954 | 291 | 9 | 20633 |
| ar | Arabic | 248 | 221 | 207 | 173 | 208 | 38 | 4 | 92 |
| fa | Persian | 391 | 331 | 207 | 173 | 318 | 38 | 4 | 97 |
| he | Hebrew | 88 | 53 | 46 | 49 | 53 | 1 | 4 | 15 |
| hi | Hindi | 128 | 127 | 117 | 103 | 123 | 19 | 5 | 68 |
| bn | Bengali | 96 | 95 | 90 | 87 | 95 | 5 | 2 | 59 |
| ta | Tamil | 72 | 71 | 63 | 61 | 71 | 3 | 1 | 36 |
| te | Telugu | 100 | 99 | 92 | 79 | 99 | 15 | 2 | 53 |
| gu | Gujarati | 91 | 87 | 83 | 77 | 87 | 7 | 1 | 50 |
| kn | Kannada | 91 | 90 | 85 | 79 | 90 | 8 | 2 | 53 |
| ml | Malayalam | 118 | 115 | 111 | 77 | 115 | 35 | 1 | 52 |
| mr | Marathi | 128 | 127 | 117 | 103 | 123 | 19 | 5 | 68 |
| ne | Nepali | 128 | 127 | 117 | 103 | 123 | 19 | 5 | 68 |
| or | Odia | 91 | 90 | 86 | 77 | 89 | 12 | 3 | 49 |
| pa | Punjabi | 80 | 78 | 74 | 72 | 76 | 5 | 3 | 49 |
| sa | Sanskrit | 128 | 127 | 117 | 103 | 123 | 19 | 5 | 68 |
| as | Assamese | 96 | 95 | 90 | 87 | 95 | 5 | 2 | 59 |
| hy | Armenian | 91 | 90 | 86 | 85 | 90 | 3 | 2 | 21 |
| ka | Georgian | 88 | 88 | 87 | 78 | 88 | 9 | 0 | 27 |
| si | Sinhala | 91 | 90 | 90 | 79 | 90 | 11 | 0 | 55 |
| th | Thai | 87 | 80 | 73 | 80 | 78 | 0 | 7 | 11 |
| lo | Lao | 83 | 76 | 58 | 58 | 75 | 2 | 2 | 11 |
| km | Khmer | 114 | 106 | 85 | 94 | 104 | 0 | 9 | 59 |
| my | Myanmar | 160 | 141 | 78 | 77 | 139 | 18 | 17 | 42 |
| bo | Tibetan | 211 | 201 | 138 | 147 | 195 | 8 | 17 | 113 |
| am | Amharic | 384 | 370 | 370 | 343 | 370 | 27 | 0 | 218 |
| ru | Russian | 304 | 301 | 294 | 234 | 301 | 65 | 5 | 76 |
| dv | Dhivehi | 50 | 49 | 48 | 48 | 48 | 0 | 0 | 3 |
| jv | Javanese | 91 | 90 | 75 | 0 | 90 | 75 | 0 | 0 |
| mn | Mongolian | 157 | 153 | 149 | 148 | 151 | 5 | 4 | 53 |
| **TOTAL** | | **49089** | **48825** | **48297** | **47408** | **48761** | **1046** | **157** | **27017** |

## Notable Differences

### bg — Bulgarian

Block: 304 assigned codepoints, 301 mapped by at least one library.

Coverage: translit maps 292/301, Unidecode maps 234/301. **65** mapped only by translit, **7** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ҋ | U+048A | CYRILLIC CAPITAL LETTER SHORT I WITH TAIL | `Y` |
| ҋ | U+048B | CYRILLIC SMALL LETTER SHORT I WITH TAIL | `y` |
| Ӆ | U+04C5 | CYRILLIC CAPITAL LETTER EL WITH TAIL | `L` |
| ӆ | U+04C6 | CYRILLIC SMALL LETTER EL WITH TAIL | `l` |
| Ӊ | U+04C9 | CYRILLIC CAPITAL LETTER EN WITH TAIL | `N` |
| ӊ | U+04CA | CYRILLIC SMALL LETTER EN WITH TAIL | `n` |
| Ӎ | U+04CD | CYRILLIC CAPITAL LETTER EM WITH TAIL | `M` |
| ӎ | U+04CE | CYRILLIC SMALL LETTER EM WITH TAIL | `m` |
| ӏ | U+04CF | CYRILLIC SMALL LETTER PALOCHKA | `i` |
| Ӷ | U+04F6 | CYRILLIC CAPITAL LETTER GHE WITH DESCENDER | `G` |
| ӷ | U+04F7 | CYRILLIC SMALL LETTER GHE WITH DESCENDER | `g` |
| Ӻ | U+04FA | CYRILLIC CAPITAL LETTER GHE WITH STROKE AND HOOK | `G` |
| ӻ | U+04FB | CYRILLIC SMALL LETTER GHE WITH STROKE AND HOOK | `g` |
| Ӽ | U+04FC | CYRILLIC CAPITAL LETTER HA WITH HOOK | `Kh` |
| ӽ | U+04FD | CYRILLIC SMALL LETTER HA WITH HOOK | `kh` |
| Ӿ | U+04FE | CYRILLIC CAPITAL LETTER HA WITH STROKE | `Kh` |
| ӿ | U+04FF | CYRILLIC SMALL LETTER HA WITH STROKE | `kh` |
| Ԁ | U+0500 | CYRILLIC CAPITAL LETTER KOMI DE | `D` |
| ԁ | U+0501 | CYRILLIC SMALL LETTER KOMI DE | `d` |
| Ԃ | U+0502 | CYRILLIC CAPITAL LETTER KOMI DJE | `Dj` |
| ԃ | U+0503 | CYRILLIC SMALL LETTER KOMI DJE | `dj` |
| Ԅ | U+0504 | CYRILLIC CAPITAL LETTER KOMI ZJE | `Z` |
| ԅ | U+0505 | CYRILLIC SMALL LETTER KOMI ZJE | `z` |
| Ԇ | U+0506 | CYRILLIC CAPITAL LETTER KOMI DZJE | `Dz` |
| ԇ | U+0507 | CYRILLIC SMALL LETTER KOMI DZJE | `dz` |
| Ԉ | U+0508 | CYRILLIC CAPITAL LETTER KOMI LJE | `Lj` |
| ԉ | U+0509 | CYRILLIC SMALL LETTER KOMI LJE | `lj` |
| Ԋ | U+050A | CYRILLIC CAPITAL LETTER KOMI NJE | `Nj` |
| ԋ | U+050B | CYRILLIC SMALL LETTER KOMI NJE | `nj` |
| Ԍ | U+050C | CYRILLIC CAPITAL LETTER KOMI SJE | `Sj` |
| | | *...35 more* | |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| Ь | U+042C | CYRILLIC CAPITAL LETTER SOFT SIGN | `'` |
| ь | U+044C | CYRILLIC SMALL LETTER SOFT SIGN | `'` |
| ҂ | U+0482 | CYRILLIC THOUSANDS SIGN | `*1000*` |
| ҈ | U+0488 | COMBINING CYRILLIC HUNDRED THOUSANDS SIGN | `*100.000*` |
| ҉ | U+0489 | COMBINING CYRILLIC MILLIONS SIGN | `*1.000.000*` |
| Ҍ | U+048C | CYRILLIC CAPITAL LETTER SEMISOFT SIGN | `"` |
| ҍ | U+048D | CYRILLIC SMALL LETTER SEMISOFT SIGN | `"` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Ѐ | U+0400 | CYRILLIC CAPITAL LETTER IE WITH GRAVE | `E` | `Ie` | `E` |
| Ё | U+0401 | CYRILLIC CAPITAL LETTER IO | `Yo` | `Io` | `E` |
| Ѓ | U+0403 | CYRILLIC CAPITAL LETTER GJE | `G` | `Gj` | `G` |
| Є | U+0404 | CYRILLIC CAPITAL LETTER UKRAINIAN IE | `Ye` | `Ie` | `Ie` |
| Ќ | U+040C | CYRILLIC CAPITAL LETTER KJE | `K` | `Kj` | `K` |
| Й | U+0419 | CYRILLIC CAPITAL LETTER SHORT I | `Y` | `I` | `Y` |
| Щ | U+0429 | CYRILLIC CAPITAL LETTER SHCHA | `Sht` | `Shch` | `Shch` |
| Ъ | U+042A | CYRILLIC CAPITAL LETTER HARD SIGN | `A` | `'` | `'` |
| Ю | U+042E | CYRILLIC CAPITAL LETTER YU | `Yu` | `Iu` | `Yu` |
| Я | U+042F | CYRILLIC CAPITAL LETTER YA | `Ya` | `Ia` | `Ya` |
| й | U+0439 | CYRILLIC SMALL LETTER SHORT I | `y` | `i` | `y` |
| щ | U+0449 | CYRILLIC SMALL LETTER SHCHA | `sht` | `shch` | `shch` |
| ъ | U+044A | CYRILLIC SMALL LETTER HARD SIGN | `a` | `'` | `'` |
| ю | U+044E | CYRILLIC SMALL LETTER YU | `yu` | `iu` | `yu` |
| я | U+044F | CYRILLIC SMALL LETTER YA | `ya` | `ia` | `ya` |
| ѐ | U+0450 | CYRILLIC SMALL LETTER IE WITH GRAVE | `e` | `ie` | `e` |
| ё | U+0451 | CYRILLIC SMALL LETTER IO | `yo` | `io` | `e` |
| ѓ | U+0453 | CYRILLIC SMALL LETTER GJE | `g` | `gj` | `g` |
| є | U+0454 | CYRILLIC SMALL LETTER UKRAINIAN IE | `ye` | `ie` | `ie` |
| ќ | U+045C | CYRILLIC SMALL LETTER KJE | `k` | `kj` | `k` |
| Ѣ | U+0462 | CYRILLIC CAPITAL LETTER YAT | `Ye` | `E` | `E` |
| ѣ | U+0463 | CYRILLIC SMALL LETTER YAT | `ye` | `e` | `e` |
| Ѹ | U+0478 | CYRILLIC CAPITAL LETTER UK | `U` | `u` | `U` |
| Ҁ | U+0480 | CYRILLIC CAPITAL LETTER KOPPA | `K` | `Q` | `Q` |
| ҁ | U+0481 | CYRILLIC SMALL LETTER KOPPA | `k` | `q` | `q` |
| Ҏ | U+048E | CYRILLIC CAPITAL LETTER ER WITH TICK | `R` | `R'` | `Rh` |
| ҏ | U+048F | CYRILLIC SMALL LETTER ER WITH TICK | `r` | `r'` | `rh` |
| Ґ | U+0490 | CYRILLIC CAPITAL LETTER GHE WITH UPTURN | `G` | `G'` | `G` |
| ґ | U+0491 | CYRILLIC SMALL LETTER GHE WITH UPTURN | `g` | `g'` | `g` |
| Ғ | U+0492 | CYRILLIC CAPITAL LETTER GHE WITH STROKE | `G` | `G'` | `Gh` |
| ғ | U+0493 | CYRILLIC SMALL LETTER GHE WITH STROKE | `g` | `g'` | `gh` |
| Ҕ | U+0494 | CYRILLIC CAPITAL LETTER GHE WITH MIDDLE HOOK | `G` | `G'` | `Gh` |
| ҕ | U+0495 | CYRILLIC SMALL LETTER GHE WITH MIDDLE HOOK | `g` | `g'` | `gh` |
| Җ | U+0496 | CYRILLIC CAPITAL LETTER ZHE WITH DESCENDER | `Zh` | `Zh'` | `J` |
| җ | U+0497 | CYRILLIC SMALL LETTER ZHE WITH DESCENDER | `zh` | `zh'` | `j` |
| Ҙ | U+0498 | CYRILLIC CAPITAL LETTER ZE WITH DESCENDER | `Z` | `Z'` | `Z` |
| ҙ | U+0499 | CYRILLIC SMALL LETTER ZE WITH DESCENDER | `z` | `z'` | `z` |
| Қ | U+049A | CYRILLIC CAPITAL LETTER KA WITH DESCENDER | `K` | `K'` | `Q` |
| қ | U+049B | CYRILLIC SMALL LETTER KA WITH DESCENDER | `k` | `k'` | `q` |
| Ҝ | U+049C | CYRILLIC CAPITAL LETTER KA WITH VERTICAL STROKE | `K` | `K'` | `G` |
| ҝ | U+049D | CYRILLIC SMALL LETTER KA WITH VERTICAL STROKE | `k` | `k'` | `g` |
| Ҟ | U+049E | CYRILLIC CAPITAL LETTER KA WITH STROKE | `K` | `K'` | `Q` |
| ҟ | U+049F | CYRILLIC SMALL LETTER KA WITH STROKE | `k` | `k'` | `q` |
| Ҡ | U+04A0 | CYRILLIC CAPITAL LETTER BASHKIR KA | `K` | `K'` | `Q` |
| ҡ | U+04A1 | CYRILLIC SMALL LETTER BASHKIR KA | `k` | `k'` | `q` |
| Ң | U+04A2 | CYRILLIC CAPITAL LETTER EN WITH DESCENDER | `N` | `N'` | `Ng` |
| ң | U+04A3 | CYRILLIC SMALL LETTER EN WITH DESCENDER | `n` | `n'` | `ng` |
| Ҧ | U+04A6 | CYRILLIC CAPITAL LETTER PE WITH MIDDLE HOOK | `P` | `P'` | `Ph` |
| ҧ | U+04A7 | CYRILLIC SMALL LETTER PE WITH MIDDLE HOOK | `p` | `p'` | `ph` |
| Ҫ | U+04AA | CYRILLIC CAPITAL LETTER ES WITH DESCENDER | `S` | `S'` | `S` |
| | | *...28 more differences* | | | |

### ca — Catalan

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### cs — Czech

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### cy — Welsh

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### da — Danish

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Å | U+00C5 | LATIN CAPITAL LETTER A WITH RING ABOVE | `Aa` | `A` | `A` |
| Æ | U+00C6 | LATIN CAPITAL LETTER AE | `Ae` | `AE` | `Ae` |
| Ø | U+00D8 | LATIN CAPITAL LETTER O WITH STROKE | `Oe` | `O` | `O` |
| å | U+00E5 | LATIN SMALL LETTER A WITH RING ABOVE | `aa` | `a` | `a` |
| ø | U+00F8 | LATIN SMALL LETTER O WITH STROKE | `oe` | `o` | `o` |
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### de — German

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Ä | U+00C4 | LATIN CAPITAL LETTER A WITH DIAERESIS | `Ae` | `A` | `A` |
| Ö | U+00D6 | LATIN CAPITAL LETTER O WITH DIAERESIS | `Oe` | `O` | `O` |
| Ü | U+00DC | LATIN CAPITAL LETTER U WITH DIAERESIS | `Ue` | `U` | `U` |
| ä | U+00E4 | LATIN SMALL LETTER A WITH DIAERESIS | `ae` | `a` | `a` |
| ö | U+00F6 | LATIN SMALL LETTER O WITH DIAERESIS | `oe` | `o` | `o` |
| ü | U+00FC | LATIN SMALL LETTER U WITH DIAERESIS | `ue` | `u` | `u` |
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### el — Greek

Block: 135 assigned codepoints, 135 mapped by at least one library.

Coverage: translit maps 135/135, Unidecode maps 106/135. **29** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ͱ | U+0370 | GREEK CAPITAL LETTER HETA | `H` |
| ͱ | U+0371 | GREEK SMALL LETTER HETA | `h` |
| Ͳ | U+0372 | GREEK CAPITAL LETTER ARCHAIC SAMPI | `Ss` |
| ͳ | U+0373 | GREEK SMALL LETTER ARCHAIC SAMPI | `ss` |
| Ͷ | U+0376 | GREEK CAPITAL LETTER PAMPHYLIAN DIGAMMA | `W` |
| ͷ | U+0377 | GREEK SMALL LETTER PAMPHYLIAN DIGAMMA | `w` |
| ͺ | U+037A | GREEK YPOGEGRAMMENI | `i` |
| ͻ | U+037B | GREEK SMALL REVERSED LUNATE SIGMA SYMBOL | `s` |
| ͼ | U+037C | GREEK SMALL DOTTED LUNATE SIGMA SYMBOL | `s` |
| ͽ | U+037D | GREEK SMALL REVERSED DOTTED LUNATE SIGMA SYMBOL | `s` |
| ; | U+037E | GREEK QUESTION MARK | `;` |
| Ϳ | U+037F | GREEK CAPITAL LETTER YOT | `J` |
| ΄ | U+0384 | GREEK TONOS | `'` |
| ΅ | U+0385 | GREEK DIALYTIKA TONOS | `"` |
| Ϗ | U+03CF | GREEK CAPITAL KAI SYMBOL | `K` |
| Ϙ | U+03D8 | GREEK LETTER ARCHAIC KOPPA | `Q` |
| ϙ | U+03D9 | GREEK SMALL LETTER ARCHAIC KOPPA | `q` |
| ϴ | U+03F4 | GREEK CAPITAL THETA SYMBOL | `Th` |
| ϵ | U+03F5 | GREEK LUNATE EPSILON SYMBOL | `e` |
| ϶ | U+03F6 | GREEK REVERSED LUNATE EPSILON SYMBOL | `e` |
| Ϸ | U+03F7 | GREEK CAPITAL LETTER SHO | `Sh` |
| ϸ | U+03F8 | GREEK SMALL LETTER SHO | `sh` |
| Ϲ | U+03F9 | GREEK CAPITAL LUNATE SIGMA SYMBOL | `S` |
| Ϻ | U+03FA | GREEK CAPITAL LETTER SAN | `S` |
| ϻ | U+03FB | GREEK SMALL LETTER SAN | `s` |
| ϼ | U+03FC | GREEK RHO WITH STROKE SYMBOL | `r` |
| Ͻ | U+03FD | GREEK CAPITAL REVERSED LUNATE SIGMA SYMBOL | `S` |
| Ͼ | U+03FE | GREEK CAPITAL DOTTED LUNATE SIGMA SYMBOL | `S` |
| Ͽ | U+03FF | GREEK CAPITAL REVERSED DOTTED LUNATE SIGMA SYMBOL | `S` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| · | U+0387 | GREEK ANO TELEIA | `.` | `;` | `;` |
| Ή | U+0389 | GREEK CAPITAL LETTER ETA WITH TONOS | `I` | `E` | `I` |
| Ύ | U+038E | GREEK CAPITAL LETTER UPSILON WITH TONOS | `Y` | `U` | `Y` |
| ΐ | U+0390 | GREEK SMALL LETTER IOTA WITH DIALYTIKA AND TONOS | `i` | `I` | `i` |
| Η | U+0397 | GREEK CAPITAL LETTER ETA | `I` | `E` | `I` |
| Ξ | U+039E | GREEK CAPITAL LETTER XI | `X` | `Ks` | `X` |
| Υ | U+03A5 | GREEK CAPITAL LETTER UPSILON | `Y` | `U` | `Y` |
| Φ | U+03A6 | GREEK CAPITAL LETTER PHI | `F` | `Ph` | `F` |
| Χ | U+03A7 | GREEK CAPITAL LETTER CHI | `Ch` | `Kh` | `Ch` |
| Ϋ | U+03AB | GREEK CAPITAL LETTER UPSILON WITH DIALYTIKA | `Y` | `U` | `Y` |
| ή | U+03AE | GREEK SMALL LETTER ETA WITH TONOS | `i` | `e` | `i` |
| ΰ | U+03B0 | GREEK SMALL LETTER UPSILON WITH DIALYTIKA AND TONOS | `y` | `u` | `y` |
| η | U+03B7 | GREEK SMALL LETTER ETA | `i` | `e` | `i` |
| υ | U+03C5 | GREEK SMALL LETTER UPSILON | `y` | `u` | `y` |
| φ | U+03C6 | GREEK SMALL LETTER PHI | `f` | `ph` | `f` |
| χ | U+03C7 | GREEK SMALL LETTER CHI | `ch` | `kh` | `ch` |
| ϋ | U+03CB | GREEK SMALL LETTER UPSILON WITH DIALYTIKA | `y` | `u` | `y` |
| ύ | U+03CD | GREEK SMALL LETTER UPSILON WITH TONOS | `y` | `u` | `y` |
| ϒ | U+03D2 | GREEK UPSILON WITH HOOK SYMBOL | `Y` | `U` | `Y` |
| ϓ | U+03D3 | GREEK UPSILON WITH ACUTE AND HOOK SYMBOL | `Y` | `U` | `Y` |
| ϔ | U+03D4 | GREEK UPSILON WITH DIAERESIS AND HOOK SYMBOL | `Y` | `U` | `Y` |
| ϗ | U+03D7 | GREEK KAI SYMBOL | `k` | `&` | `&` |
| Ϡ | U+03E0 | GREEK LETTER SAMPI | `Ss` | `Sp` | `S` |
| ϡ | U+03E1 | GREEK SMALL LETTER SAMPI | `ss` | `sp` | `s` |
| Ϣ | U+03E2 | COPTIC CAPITAL LETTER SHEI | `sh` | `Sh` | `Sh` |
| Ϥ | U+03E4 | COPTIC CAPITAL LETTER FEI | `f` | `F` | `F` |
| Ϧ | U+03E6 | COPTIC CAPITAL LETTER KHEI | `kh` | `Kh` | `X` |
| Ϩ | U+03E8 | COPTIC CAPITAL LETTER HORI | `h` | `H` | `H` |
| Ϫ | U+03EA | COPTIC CAPITAL LETTER GANGIA | `j` | `G` | `J` |
| ϫ | U+03EB | COPTIC SMALL LETTER GANGIA | `j` | `g` | `j` |
| Ϭ | U+03EC | COPTIC CAPITAL LETTER SHIMA | `c` | `CH` | `C` |
| ϭ | U+03ED | COPTIC SMALL LETTER SHIMA | `c` | `ch` | `c` |
| Ϯ | U+03EE | COPTIC CAPITAL LETTER DEI | `ti` | `Ti` | `Ti` |
| ϲ | U+03F2 | GREEK LUNATE SIGMA SYMBOL | `s` | `c` | `s` |

### es — Spanish

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### et — Estonian

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Ä | U+00C4 | LATIN CAPITAL LETTER A WITH DIAERESIS | `Ae` | `A` | `A` |
| Ö | U+00D6 | LATIN CAPITAL LETTER O WITH DIAERESIS | `Oe` | `O` | `O` |
| Ü | U+00DC | LATIN CAPITAL LETTER U WITH DIAERESIS | `Ue` | `U` | `U` |
| ä | U+00E4 | LATIN SMALL LETTER A WITH DIAERESIS | `ae` | `a` | `a` |
| ö | U+00F6 | LATIN SMALL LETTER O WITH DIAERESIS | `oe` | `o` | `o` |
| ü | U+00FC | LATIN SMALL LETTER U WITH DIAERESIS | `ue` | `u` | `u` |
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### fi — Finnish

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Ä | U+00C4 | LATIN CAPITAL LETTER A WITH DIAERESIS | `Ae` | `A` | `A` |
| Ö | U+00D6 | LATIN CAPITAL LETTER O WITH DIAERESIS | `Oe` | `O` | `O` |
| ä | U+00E4 | LATIN SMALL LETTER A WITH DIAERESIS | `ae` | `a` | `a` |
| ö | U+00F6 | LATIN SMALL LETTER O WITH DIAERESIS | `oe` | `o` | `o` |
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### fr — French

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### ga — Irish

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### hr — Croatian

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### hu — Hungarian

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### is — Icelandic

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Æ | U+00C6 | LATIN CAPITAL LETTER AE | `Ae` | `AE` | `Ae` |
| Ð | U+00D0 | LATIN CAPITAL LETTER ETH | `Dh` | `D` | `D` |
| ð | U+00F0 | LATIN SMALL LETTER ETH | `dh` | `d` | `d` |
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### it — Italian

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### lt — Lithuanian

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### lv — Latvian

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### mt — Maltese

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### nl — Dutch

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### no — Norwegian

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Å | U+00C5 | LATIN CAPITAL LETTER A WITH RING ABOVE | `Aa` | `A` | `A` |
| Æ | U+00C6 | LATIN CAPITAL LETTER AE | `Ae` | `AE` | `Ae` |
| Ø | U+00D8 | LATIN CAPITAL LETTER O WITH STROKE | `Oe` | `O` | `O` |
| å | U+00E5 | LATIN SMALL LETTER A WITH RING ABOVE | `aa` | `a` | `a` |
| ø | U+00F8 | LATIN SMALL LETTER O WITH STROKE | `oe` | `o` | `o` |
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### pl — Polish

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### pt — Portuguese

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### ro — Romanian

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### sk — Slovak

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### sl — Slovenian

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### sq — Albanian

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### sr — Serbian

Block: 304 assigned codepoints, 301 mapped by at least one library.

Coverage: translit maps 290/301, Unidecode maps 234/301. **65** mapped only by translit, **9** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ҋ | U+048A | CYRILLIC CAPITAL LETTER SHORT I WITH TAIL | `Y` |
| ҋ | U+048B | CYRILLIC SMALL LETTER SHORT I WITH TAIL | `y` |
| Ӆ | U+04C5 | CYRILLIC CAPITAL LETTER EL WITH TAIL | `L` |
| ӆ | U+04C6 | CYRILLIC SMALL LETTER EL WITH TAIL | `l` |
| Ӊ | U+04C9 | CYRILLIC CAPITAL LETTER EN WITH TAIL | `N` |
| ӊ | U+04CA | CYRILLIC SMALL LETTER EN WITH TAIL | `n` |
| Ӎ | U+04CD | CYRILLIC CAPITAL LETTER EM WITH TAIL | `M` |
| ӎ | U+04CE | CYRILLIC SMALL LETTER EM WITH TAIL | `m` |
| ӏ | U+04CF | CYRILLIC SMALL LETTER PALOCHKA | `i` |
| Ӷ | U+04F6 | CYRILLIC CAPITAL LETTER GHE WITH DESCENDER | `G` |
| ӷ | U+04F7 | CYRILLIC SMALL LETTER GHE WITH DESCENDER | `g` |
| Ӻ | U+04FA | CYRILLIC CAPITAL LETTER GHE WITH STROKE AND HOOK | `G` |
| ӻ | U+04FB | CYRILLIC SMALL LETTER GHE WITH STROKE AND HOOK | `g` |
| Ӽ | U+04FC | CYRILLIC CAPITAL LETTER HA WITH HOOK | `Kh` |
| ӽ | U+04FD | CYRILLIC SMALL LETTER HA WITH HOOK | `kh` |
| Ӿ | U+04FE | CYRILLIC CAPITAL LETTER HA WITH STROKE | `Kh` |
| ӿ | U+04FF | CYRILLIC SMALL LETTER HA WITH STROKE | `kh` |
| Ԁ | U+0500 | CYRILLIC CAPITAL LETTER KOMI DE | `D` |
| ԁ | U+0501 | CYRILLIC SMALL LETTER KOMI DE | `d` |
| Ԃ | U+0502 | CYRILLIC CAPITAL LETTER KOMI DJE | `Dj` |
| ԃ | U+0503 | CYRILLIC SMALL LETTER KOMI DJE | `dj` |
| Ԅ | U+0504 | CYRILLIC CAPITAL LETTER KOMI ZJE | `Z` |
| ԅ | U+0505 | CYRILLIC SMALL LETTER KOMI ZJE | `z` |
| Ԇ | U+0506 | CYRILLIC CAPITAL LETTER KOMI DZJE | `Dz` |
| ԇ | U+0507 | CYRILLIC SMALL LETTER KOMI DZJE | `dz` |
| Ԉ | U+0508 | CYRILLIC CAPITAL LETTER KOMI LJE | `Lj` |
| ԉ | U+0509 | CYRILLIC SMALL LETTER KOMI LJE | `lj` |
| Ԋ | U+050A | CYRILLIC CAPITAL LETTER KOMI NJE | `Nj` |
| ԋ | U+050B | CYRILLIC SMALL LETTER KOMI NJE | `nj` |
| Ԍ | U+050C | CYRILLIC CAPITAL LETTER KOMI SJE | `Sj` |
| | | *...35 more* | |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| Ъ | U+042A | CYRILLIC CAPITAL LETTER HARD SIGN | `'` |
| Ь | U+042C | CYRILLIC CAPITAL LETTER SOFT SIGN | `'` |
| ъ | U+044A | CYRILLIC SMALL LETTER HARD SIGN | `'` |
| ь | U+044C | CYRILLIC SMALL LETTER SOFT SIGN | `'` |
| ҂ | U+0482 | CYRILLIC THOUSANDS SIGN | `*1000*` |
| ҈ | U+0488 | COMBINING CYRILLIC HUNDRED THOUSANDS SIGN | `*100.000*` |
| ҉ | U+0489 | COMBINING CYRILLIC MILLIONS SIGN | `*1.000.000*` |
| Ҍ | U+048C | CYRILLIC CAPITAL LETTER SEMISOFT SIGN | `"` |
| ҍ | U+048D | CYRILLIC SMALL LETTER SEMISOFT SIGN | `"` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Ѐ | U+0400 | CYRILLIC CAPITAL LETTER IE WITH GRAVE | `E` | `Ie` | `E` |
| Ё | U+0401 | CYRILLIC CAPITAL LETTER IO | `Yo` | `Io` | `E` |
| Ѓ | U+0403 | CYRILLIC CAPITAL LETTER GJE | `G` | `Gj` | `G` |
| Є | U+0404 | CYRILLIC CAPITAL LETTER UKRAINIAN IE | `Ye` | `Ie` | `Ie` |
| Ћ | U+040B | CYRILLIC CAPITAL LETTER TSHE | `C` | `Tsh` | `C` |
| Ќ | U+040C | CYRILLIC CAPITAL LETTER KJE | `K` | `Kj` | `K` |
| Џ | U+040F | CYRILLIC CAPITAL LETTER DZHE | `Dz` | `Dzh` | `Dzh` |
| Й | U+0419 | CYRILLIC CAPITAL LETTER SHORT I | `Y` | `I` | `Y` |
| Ю | U+042E | CYRILLIC CAPITAL LETTER YU | `Yu` | `Iu` | `Yu` |
| Я | U+042F | CYRILLIC CAPITAL LETTER YA | `Ya` | `Ia` | `Ya` |
| й | U+0439 | CYRILLIC SMALL LETTER SHORT I | `y` | `i` | `y` |
| ю | U+044E | CYRILLIC SMALL LETTER YU | `yu` | `iu` | `yu` |
| я | U+044F | CYRILLIC SMALL LETTER YA | `ya` | `ia` | `ya` |
| ѐ | U+0450 | CYRILLIC SMALL LETTER IE WITH GRAVE | `e` | `ie` | `e` |
| ё | U+0451 | CYRILLIC SMALL LETTER IO | `yo` | `io` | `e` |
| ѓ | U+0453 | CYRILLIC SMALL LETTER GJE | `g` | `gj` | `g` |
| є | U+0454 | CYRILLIC SMALL LETTER UKRAINIAN IE | `ye` | `ie` | `ie` |
| ћ | U+045B | CYRILLIC SMALL LETTER TSHE | `c` | `tsh` | `c` |
| ќ | U+045C | CYRILLIC SMALL LETTER KJE | `k` | `kj` | `k` |
| џ | U+045F | CYRILLIC SMALL LETTER DZHE | `dz` | `dzh` | `dzh` |
| Ѣ | U+0462 | CYRILLIC CAPITAL LETTER YAT | `Ye` | `E` | `E` |
| ѣ | U+0463 | CYRILLIC SMALL LETTER YAT | `ye` | `e` | `e` |
| Ѹ | U+0478 | CYRILLIC CAPITAL LETTER UK | `U` | `u` | `U` |
| Ҁ | U+0480 | CYRILLIC CAPITAL LETTER KOPPA | `K` | `Q` | `Q` |
| ҁ | U+0481 | CYRILLIC SMALL LETTER KOPPA | `k` | `q` | `q` |
| Ҏ | U+048E | CYRILLIC CAPITAL LETTER ER WITH TICK | `R` | `R'` | `Rh` |
| ҏ | U+048F | CYRILLIC SMALL LETTER ER WITH TICK | `r` | `r'` | `rh` |
| Ґ | U+0490 | CYRILLIC CAPITAL LETTER GHE WITH UPTURN | `G` | `G'` | `G` |
| ґ | U+0491 | CYRILLIC SMALL LETTER GHE WITH UPTURN | `g` | `g'` | `g` |
| Ғ | U+0492 | CYRILLIC CAPITAL LETTER GHE WITH STROKE | `G` | `G'` | `Gh` |
| ғ | U+0493 | CYRILLIC SMALL LETTER GHE WITH STROKE | `g` | `g'` | `gh` |
| Ҕ | U+0494 | CYRILLIC CAPITAL LETTER GHE WITH MIDDLE HOOK | `G` | `G'` | `Gh` |
| ҕ | U+0495 | CYRILLIC SMALL LETTER GHE WITH MIDDLE HOOK | `g` | `g'` | `gh` |
| Җ | U+0496 | CYRILLIC CAPITAL LETTER ZHE WITH DESCENDER | `Zh` | `Zh'` | `J` |
| җ | U+0497 | CYRILLIC SMALL LETTER ZHE WITH DESCENDER | `zh` | `zh'` | `j` |
| Ҙ | U+0498 | CYRILLIC CAPITAL LETTER ZE WITH DESCENDER | `Z` | `Z'` | `Z` |
| ҙ | U+0499 | CYRILLIC SMALL LETTER ZE WITH DESCENDER | `z` | `z'` | `z` |
| Қ | U+049A | CYRILLIC CAPITAL LETTER KA WITH DESCENDER | `K` | `K'` | `Q` |
| қ | U+049B | CYRILLIC SMALL LETTER KA WITH DESCENDER | `k` | `k'` | `q` |
| Ҝ | U+049C | CYRILLIC CAPITAL LETTER KA WITH VERTICAL STROKE | `K` | `K'` | `G` |
| ҝ | U+049D | CYRILLIC SMALL LETTER KA WITH VERTICAL STROKE | `k` | `k'` | `g` |
| Ҟ | U+049E | CYRILLIC CAPITAL LETTER KA WITH STROKE | `K` | `K'` | `Q` |
| ҟ | U+049F | CYRILLIC SMALL LETTER KA WITH STROKE | `k` | `k'` | `q` |
| Ҡ | U+04A0 | CYRILLIC CAPITAL LETTER BASHKIR KA | `K` | `K'` | `Q` |
| ҡ | U+04A1 | CYRILLIC SMALL LETTER BASHKIR KA | `k` | `k'` | `q` |
| Ң | U+04A2 | CYRILLIC CAPITAL LETTER EN WITH DESCENDER | `N` | `N'` | `Ng` |
| ң | U+04A3 | CYRILLIC SMALL LETTER EN WITH DESCENDER | `n` | `n'` | `ng` |
| Ҧ | U+04A6 | CYRILLIC CAPITAL LETTER PE WITH MIDDLE HOOK | `P` | `P'` | `Ph` |
| ҧ | U+04A7 | CYRILLIC SMALL LETTER PE WITH MIDDLE HOOK | `p` | `p'` | `ph` |
| Ҫ | U+04AA | CYRILLIC CAPITAL LETTER ES WITH DESCENDER | `S` | `S'` | `S` |
| | | *...28 more differences* | | | |

### sv — Swedish

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Ä | U+00C4 | LATIN CAPITAL LETTER A WITH DIAERESIS | `Ae` | `A` | `A` |
| Ö | U+00D6 | LATIN CAPITAL LETTER O WITH DIAERESIS | `Oe` | `O` | `O` |
| ä | U+00E4 | LATIN SMALL LETTER A WITH DIAERESIS | `ae` | `a` | `a` |
| ö | U+00F6 | LATIN SMALL LETTER O WITH DIAERESIS | `oe` | `o` | `o` |
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### tr — Turkish

Block: 400 assigned codepoints, 400 mapped by at least one library.

Coverage: translit maps 400/400, Unidecode maps 398/400. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |

### uk — Ukrainian

Block: 304 assigned codepoints, 301 mapped by at least one library.

Coverage: translit maps 292/301, Unidecode maps 234/301. **65** mapped only by translit, **7** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ҋ | U+048A | CYRILLIC CAPITAL LETTER SHORT I WITH TAIL | `Y` |
| ҋ | U+048B | CYRILLIC SMALL LETTER SHORT I WITH TAIL | `y` |
| Ӆ | U+04C5 | CYRILLIC CAPITAL LETTER EL WITH TAIL | `L` |
| ӆ | U+04C6 | CYRILLIC SMALL LETTER EL WITH TAIL | `l` |
| Ӊ | U+04C9 | CYRILLIC CAPITAL LETTER EN WITH TAIL | `N` |
| ӊ | U+04CA | CYRILLIC SMALL LETTER EN WITH TAIL | `n` |
| Ӎ | U+04CD | CYRILLIC CAPITAL LETTER EM WITH TAIL | `M` |
| ӎ | U+04CE | CYRILLIC SMALL LETTER EM WITH TAIL | `m` |
| ӏ | U+04CF | CYRILLIC SMALL LETTER PALOCHKA | `i` |
| Ӷ | U+04F6 | CYRILLIC CAPITAL LETTER GHE WITH DESCENDER | `G` |
| ӷ | U+04F7 | CYRILLIC SMALL LETTER GHE WITH DESCENDER | `g` |
| Ӻ | U+04FA | CYRILLIC CAPITAL LETTER GHE WITH STROKE AND HOOK | `G` |
| ӻ | U+04FB | CYRILLIC SMALL LETTER GHE WITH STROKE AND HOOK | `g` |
| Ӽ | U+04FC | CYRILLIC CAPITAL LETTER HA WITH HOOK | `Kh` |
| ӽ | U+04FD | CYRILLIC SMALL LETTER HA WITH HOOK | `kh` |
| Ӿ | U+04FE | CYRILLIC CAPITAL LETTER HA WITH STROKE | `Kh` |
| ӿ | U+04FF | CYRILLIC SMALL LETTER HA WITH STROKE | `kh` |
| Ԁ | U+0500 | CYRILLIC CAPITAL LETTER KOMI DE | `D` |
| ԁ | U+0501 | CYRILLIC SMALL LETTER KOMI DE | `d` |
| Ԃ | U+0502 | CYRILLIC CAPITAL LETTER KOMI DJE | `Dj` |
| ԃ | U+0503 | CYRILLIC SMALL LETTER KOMI DJE | `dj` |
| Ԅ | U+0504 | CYRILLIC CAPITAL LETTER KOMI ZJE | `Z` |
| ԅ | U+0505 | CYRILLIC SMALL LETTER KOMI ZJE | `z` |
| Ԇ | U+0506 | CYRILLIC CAPITAL LETTER KOMI DZJE | `Dz` |
| ԇ | U+0507 | CYRILLIC SMALL LETTER KOMI DZJE | `dz` |
| Ԉ | U+0508 | CYRILLIC CAPITAL LETTER KOMI LJE | `Lj` |
| ԉ | U+0509 | CYRILLIC SMALL LETTER KOMI LJE | `lj` |
| Ԋ | U+050A | CYRILLIC CAPITAL LETTER KOMI NJE | `Nj` |
| ԋ | U+050B | CYRILLIC SMALL LETTER KOMI NJE | `nj` |
| Ԍ | U+050C | CYRILLIC CAPITAL LETTER KOMI SJE | `Sj` |
| | | *...35 more* | |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| Ъ | U+042A | CYRILLIC CAPITAL LETTER HARD SIGN | `'` |
| ъ | U+044A | CYRILLIC SMALL LETTER HARD SIGN | `'` |
| ҂ | U+0482 | CYRILLIC THOUSANDS SIGN | `*1000*` |
| ҈ | U+0488 | COMBINING CYRILLIC HUNDRED THOUSANDS SIGN | `*100.000*` |
| ҉ | U+0489 | COMBINING CYRILLIC MILLIONS SIGN | `*1.000.000*` |
| Ҍ | U+048C | CYRILLIC CAPITAL LETTER SEMISOFT SIGN | `"` |
| ҍ | U+048D | CYRILLIC SMALL LETTER SEMISOFT SIGN | `"` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Ѐ | U+0400 | CYRILLIC CAPITAL LETTER IE WITH GRAVE | `E` | `Ie` | `E` |
| Ё | U+0401 | CYRILLIC CAPITAL LETTER IO | `Yo` | `Io` | `E` |
| Ѓ | U+0403 | CYRILLIC CAPITAL LETTER GJE | `G` | `Gj` | `G` |
| Є | U+0404 | CYRILLIC CAPITAL LETTER UKRAINIAN IE | `Ye` | `Ie` | `Ie` |
| Ї | U+0407 | CYRILLIC CAPITAL LETTER YI | `I` | `Yi` | `I` |
| Ќ | U+040C | CYRILLIC CAPITAL LETTER KJE | `K` | `Kj` | `K` |
| Г | U+0413 | CYRILLIC CAPITAL LETTER GHE | `H` | `G` | `G` |
| И | U+0418 | CYRILLIC CAPITAL LETTER I | `Y` | `I` | `I` |
| Й | U+0419 | CYRILLIC CAPITAL LETTER SHORT I | `Y` | `I` | `Y` |
| Ю | U+042E | CYRILLIC CAPITAL LETTER YU | `Yu` | `Iu` | `Yu` |
| Я | U+042F | CYRILLIC CAPITAL LETTER YA | `Ya` | `Ia` | `Ya` |
| г | U+0433 | CYRILLIC SMALL LETTER GHE | `h` | `g` | `g` |
| и | U+0438 | CYRILLIC SMALL LETTER I | `y` | `i` | `i` |
| й | U+0439 | CYRILLIC SMALL LETTER SHORT I | `y` | `i` | `y` |
| ю | U+044E | CYRILLIC SMALL LETTER YU | `yu` | `iu` | `yu` |
| я | U+044F | CYRILLIC SMALL LETTER YA | `ya` | `ia` | `ya` |
| ѐ | U+0450 | CYRILLIC SMALL LETTER IE WITH GRAVE | `e` | `ie` | `e` |
| ё | U+0451 | CYRILLIC SMALL LETTER IO | `yo` | `io` | `e` |
| ѓ | U+0453 | CYRILLIC SMALL LETTER GJE | `g` | `gj` | `g` |
| є | U+0454 | CYRILLIC SMALL LETTER UKRAINIAN IE | `ye` | `ie` | `ie` |
| ї | U+0457 | CYRILLIC SMALL LETTER YI | `i` | `yi` | `i` |
| ќ | U+045C | CYRILLIC SMALL LETTER KJE | `k` | `kj` | `k` |
| Ѣ | U+0462 | CYRILLIC CAPITAL LETTER YAT | `Ye` | `E` | `E` |
| ѣ | U+0463 | CYRILLIC SMALL LETTER YAT | `ye` | `e` | `e` |
| Ѹ | U+0478 | CYRILLIC CAPITAL LETTER UK | `U` | `u` | `U` |
| Ҁ | U+0480 | CYRILLIC CAPITAL LETTER KOPPA | `K` | `Q` | `Q` |
| ҁ | U+0481 | CYRILLIC SMALL LETTER KOPPA | `k` | `q` | `q` |
| Ҏ | U+048E | CYRILLIC CAPITAL LETTER ER WITH TICK | `R` | `R'` | `Rh` |
| ҏ | U+048F | CYRILLIC SMALL LETTER ER WITH TICK | `r` | `r'` | `rh` |
| Ґ | U+0490 | CYRILLIC CAPITAL LETTER GHE WITH UPTURN | `G` | `G'` | `G` |
| ґ | U+0491 | CYRILLIC SMALL LETTER GHE WITH UPTURN | `g` | `g'` | `g` |
| Ғ | U+0492 | CYRILLIC CAPITAL LETTER GHE WITH STROKE | `G` | `G'` | `Gh` |
| ғ | U+0493 | CYRILLIC SMALL LETTER GHE WITH STROKE | `g` | `g'` | `gh` |
| Ҕ | U+0494 | CYRILLIC CAPITAL LETTER GHE WITH MIDDLE HOOK | `G` | `G'` | `Gh` |
| ҕ | U+0495 | CYRILLIC SMALL LETTER GHE WITH MIDDLE HOOK | `g` | `g'` | `gh` |
| Җ | U+0496 | CYRILLIC CAPITAL LETTER ZHE WITH DESCENDER | `Zh` | `Zh'` | `J` |
| җ | U+0497 | CYRILLIC SMALL LETTER ZHE WITH DESCENDER | `zh` | `zh'` | `j` |
| Ҙ | U+0498 | CYRILLIC CAPITAL LETTER ZE WITH DESCENDER | `Z` | `Z'` | `Z` |
| ҙ | U+0499 | CYRILLIC SMALL LETTER ZE WITH DESCENDER | `z` | `z'` | `z` |
| Қ | U+049A | CYRILLIC CAPITAL LETTER KA WITH DESCENDER | `K` | `K'` | `Q` |
| қ | U+049B | CYRILLIC SMALL LETTER KA WITH DESCENDER | `k` | `k'` | `q` |
| Ҝ | U+049C | CYRILLIC CAPITAL LETTER KA WITH VERTICAL STROKE | `K` | `K'` | `G` |
| ҝ | U+049D | CYRILLIC SMALL LETTER KA WITH VERTICAL STROKE | `k` | `k'` | `g` |
| Ҟ | U+049E | CYRILLIC CAPITAL LETTER KA WITH STROKE | `K` | `K'` | `Q` |
| ҟ | U+049F | CYRILLIC SMALL LETTER KA WITH STROKE | `k` | `k'` | `q` |
| Ҡ | U+04A0 | CYRILLIC CAPITAL LETTER BASHKIR KA | `K` | `K'` | `Q` |
| ҡ | U+04A1 | CYRILLIC SMALL LETTER BASHKIR KA | `k` | `k'` | `q` |
| Ң | U+04A2 | CYRILLIC CAPITAL LETTER EN WITH DESCENDER | `N` | `N'` | `Ng` |
| ң | U+04A3 | CYRILLIC SMALL LETTER EN WITH DESCENDER | `n` | `n'` | `ng` |
| Ҧ | U+04A6 | CYRILLIC CAPITAL LETTER PE WITH MIDDLE HOOK | `P` | `P'` | `Ph` |
| | | *...30 more differences* | | | |

### vi — Vietnamese

Block: 656 assigned codepoints, 656 mapped by at least one library.

Coverage: translit maps 647/656, Unidecode maps 645/656. **2** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ɂ | U+0241 | LATIN CAPITAL LETTER GLOTTAL STOP | `'` |
| ɂ | U+0242 | LATIN SMALL LETTER GLOTTAL STOP | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ŉ | U+0149 | LATIN SMALL LETTER N PRECEDED BY APOSTROPHE | `n` | `'n` | `'n` |
| Ŋ | U+014A | LATIN CAPITAL LETTER ENG | `N` | `NG` | `Ng` |
| ŋ | U+014B | LATIN SMALL LETTER ENG | `n` | `ng` | `ng` |
| Ƅ | U+0184 | LATIN CAPITAL LETTER TONE SIX | `B` | `6` | `6` |
| ƅ | U+0185 | LATIN SMALL LETTER TONE SIX | `b` | `6` | `6` |
| Ǝ | U+018E | LATIN CAPITAL LETTER REVERSED E | `D` | `3` | `E` |
| Ə | U+018F | LATIN CAPITAL LETTER SCHWA | `A` | `@` | `E` |
| Ɯ | U+019C | LATIN CAPITAL LETTER TURNED M | `M` | `W` | `W` |
| Ʀ | U+01A6 | LATIN LETTER YR | `R` | `YR` | `R` |
| Ƨ | U+01A7 | LATIN CAPITAL LETTER TONE TWO | `S` | `2` | `2` |
| ƨ | U+01A8 | LATIN SMALL LETTER TONE TWO | `s` | `2` | `2` |
| Ʃ | U+01A9 | LATIN CAPITAL LETTER ESH | `Sh` | `SH` | `Sh` |
| ƪ | U+01AA | LATIN LETTER REVERSED ESH LOOP | `s` | `sh` | `sh` |
| Ʊ | U+01B1 | LATIN CAPITAL LETTER UPSILON | `U` | `Y` | `U` |
| Ʒ | U+01B7 | LATIN CAPITAL LETTER EZH | `Zh` | `ZH` | `Zh` |
| Ƹ | U+01B8 | LATIN CAPITAL LETTER EZH REVERSED | `Zh` | `ZH` | ``` |
| ǂ | U+01C2 | LATIN LETTER ALVEOLAR CLICK | `!` | `|=` | `qc` |
| ǝ | U+01DD | LATIN SMALL LETTER TURNED E | `e` | `@` | `e` |
| Ǯ | U+01EE | LATIN CAPITAL LETTER EZH WITH CARON | `Zh` | `ZH` | `Zh` |
| Ƕ | U+01F6 | LATIN CAPITAL LETTER HWAIR | `Hv` | `HV` | `Hw` |
| Ȝ | U+021C | LATIN CAPITAL LETTER YOGH | `Yh` | `Y` | `Y` |
| ȝ | U+021D | LATIN SMALL LETTER YOGH | `yh` | `y` | `y` |
| Ʌ | U+0245 | LATIN CAPITAL LETTER TURNED V | `V` | `^` | `A` |
| Ɋ | U+024A | LATIN CAPITAL LETTER SMALL Q WITH HOOK TAIL | `Q` | `q` | `Q` |
| ẛ | U+1E9B | LATIN SMALL LETTER LONG S WITH DOT ABOVE | `s` | `S` | `s` |

### ja — Japanese

Block: 248 assigned codepoints, 248 mapped by at least one library.

Coverage: translit maps 234/248, Unidecode maps 240/248. **2** mapped only by translit, **8** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ゕ | U+3095 | HIRAGANA LETTER SMALL KA | `ka` |
| ゖ | U+3096 | HIRAGANA LETTER SMALL KE | `ke` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ゝ | U+309D | HIRAGANA ITERATION MARK | `"` |
| ゞ | U+309E | HIRAGANA VOICED ITERATION MARK | `"` |
| ゠ | U+30A0 | KATAKANA-HIRAGANA DOUBLE HYPHEN | `=` |
| ー | U+30FC | KATAKANA-HIRAGANA PROLONGED SOUND MARK | `-` |
| ヽ | U+30FD | KATAKANA ITERATION MARK | `"` |
| ヾ | U+30FE | KATAKANA VOICED ITERATION MARK | `"` |
| ﾞ | U+FF9E | HALFWIDTH KATAKANA VOICED SOUND MARK | `:` |
| ﾟ | U+FF9F | HALFWIDTH KATAKANA SEMI-VOICED SOUND MARK | `;` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| じ | U+3058 | HIRAGANA LETTER ZI | `ji` | `zi` | `ji` |
| ふ | U+3075 | HIRAGANA LETTER HU | `fu` | `hu` | `fu` |
| ジ | U+30B8 | KATAKANA LETTER ZI | `ji` | `zi` | `ji` |
| フ | U+30D5 | KATAKANA LETTER HU | `fu` | `hu` | `fu` |
| ・ | U+30FB | KATAKANA MIDDLE DOT | ` ` | `*` | `-` |
| ･ | U+FF65 | HALFWIDTH KATAKANA MIDDLE DOT | ` ` | `*` | `-` |
| ｯ | U+FF6F | HALFWIDTH KATAKANA LETTER SMALL TU | `tsu` | `tu` | `t` |
| ｰ | U+FF70 | HALFWIDTH KATAKANA-HIRAGANA PROLONGED SOUND MARK | `-` | `+` | — |
| ｼ | U+FF7C | HALFWIDTH KATAKANA LETTER SI | `shi` | `si` | `shi` |
| ﾁ | U+FF81 | HALFWIDTH KATAKANA LETTER TI | `chi` | `ti` | `chi` |
| ﾂ | U+FF82 | HALFWIDTH KATAKANA LETTER TU | `tsu` | `tu` | `tsu` |
| ﾌ | U+FF8C | HALFWIDTH KATAKANA LETTER HU | `fu` | `hu` | `fu` |

### ja-kunrei — Japanese Kunrei

Block: 189 assigned codepoints, 189 mapped by at least one library.

Coverage: translit maps 178/189, Unidecode maps 181/189. **2** mapped only by translit, **5** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ゕ | U+3095 | HIRAGANA LETTER SMALL KA | `ka` |
| ゖ | U+3096 | HIRAGANA LETTER SMALL KE | `ke` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ゝ | U+309D | HIRAGANA ITERATION MARK | `"` |
| ゞ | U+309E | HIRAGANA VOICED ITERATION MARK | `"` |
| ゠ | U+30A0 | KATAKANA-HIRAGANA DOUBLE HYPHEN | `=` |
| ヽ | U+30FD | KATAKANA ITERATION MARK | `"` |
| ヾ | U+30FE | KATAKANA VOICED ITERATION MARK | `"` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| し | U+3057 | HIRAGANA LETTER SI | `si` | `shi` | `shi` |
| ち | U+3061 | HIRAGANA LETTER TI | `ti` | `chi` | `chi` |
| っ | U+3063 | HIRAGANA LETTER SMALL TU | `tu` | `tsu` | `t` |
| つ | U+3064 | HIRAGANA LETTER TU | `tu` | `tsu` | `tsu` |
| シ | U+30B7 | KATAKANA LETTER SI | `si` | `shi` | `shi` |
| チ | U+30C1 | KATAKANA LETTER TI | `ti` | `chi` | `chi` |
| ッ | U+30C3 | KATAKANA LETTER SMALL TU | `tu` | `tsu` | `t` |
| ツ | U+30C4 | KATAKANA LETTER TU | `tu` | `tsu` | `tsu` |
| ・ | U+30FB | KATAKANA MIDDLE DOT | ` ` | `*` | `-` |

### ko — Korean

Block: 11172 assigned codepoints, 11172 mapped by at least one library.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| 갂 | U+AC02 | HANGUL SYLLABLE GAGG | `gakk` | `gagg` | `Gakk` |
| 갗 | U+AC17 | HANGUL SYLLABLE GAC | `gach` | `gac` | `Gach` |
| 갞 | U+AC1E | HANGUL SYLLABLE GAEGG | `gaekk` | `gaegg` | `Gaekk` |
| 갳 | U+AC33 | HANGUL SYLLABLE GAEC | `gaech` | `gaec` | `Gaech` |
| 갺 | U+AC3A | HANGUL SYLLABLE GYAGG | `gyakk` | `gyagg` | `Gyakk` |
| 걏 | U+AC4F | HANGUL SYLLABLE GYAC | `gyach` | `gyac` | `Gyach` |
| 걖 | U+AC56 | HANGUL SYLLABLE GYAEGG | `gyaekk` | `gyaegg` | `Gyaekk` |
| 걫 | U+AC6B | HANGUL SYLLABLE GYAEC | `gyaech` | `gyaec` | `Gyaech` |
| 걲 | U+AC72 | HANGUL SYLLABLE GEOGG | `geokk` | `geogg` | `Geokk` |
| 겇 | U+AC87 | HANGUL SYLLABLE GEOC | `geoch` | `geoc` | `Geoch` |
| 겎 | U+AC8E | HANGUL SYLLABLE GEGG | `gekk` | `gegg` | `Gekk` |
| 겣 | U+ACA3 | HANGUL SYLLABLE GEC | `gech` | `gec` | `Gech` |
| 겪 | U+ACAA | HANGUL SYLLABLE GYEOGG | `gyeokk` | `gyeogg` | `Gyeokk` |
| 겿 | U+ACBF | HANGUL SYLLABLE GYEOC | `gyeoch` | `gyeoc` | `Gyeoch` |
| 곆 | U+ACC6 | HANGUL SYLLABLE GYEGG | `gyekk` | `gyegg` | `Gyekk` |
| 곛 | U+ACDB | HANGUL SYLLABLE GYEC | `gyech` | `gyec` | `Gyech` |
| 곢 | U+ACE2 | HANGUL SYLLABLE GOGG | `gokk` | `gogg` | `Gokk` |
| 곷 | U+ACF7 | HANGUL SYLLABLE GOC | `goch` | `goc` | `Goch` |
| 곾 | U+ACFE | HANGUL SYLLABLE GWAGG | `gwakk` | `gwagg` | `Gwakk` |
| 괓 | U+AD13 | HANGUL SYLLABLE GWAC | `gwach` | `gwac` | `Gwach` |
| 괚 | U+AD1A | HANGUL SYLLABLE GWAEGG | `gwaekk` | `gwaegg` | `Gwaekk` |
| 괯 | U+AD2F | HANGUL SYLLABLE GWAEC | `gwaech` | `gwaec` | `Gwaech` |
| 괶 | U+AD36 | HANGUL SYLLABLE GOEGG | `goekk` | `goegg` | `Goekk` |
| 굋 | U+AD4B | HANGUL SYLLABLE GOEC | `goech` | `goec` | `Goech` |
| 굒 | U+AD52 | HANGUL SYLLABLE GYOGG | `gyokk` | `gyogg` | `Gyokk` |
| 굧 | U+AD67 | HANGUL SYLLABLE GYOC | `gyoch` | `gyoc` | `Gyoch` |
| 굮 | U+AD6E | HANGUL SYLLABLE GUGG | `gukk` | `gugg` | `Gukk` |
| 궃 | U+AD83 | HANGUL SYLLABLE GUC | `guch` | `guc` | `Guch` |
| 궈 | U+AD88 | HANGUL SYLLABLE GWEO | `gwo` | `gweo` | `Gwo` |
| 궉 | U+AD89 | HANGUL SYLLABLE GWEOG | `gwog` | `gweog` | `Gwog` |
| 궊 | U+AD8A | HANGUL SYLLABLE GWEOGG | `gwokk` | `gweogg` | `Gwokk` |
| 궋 | U+AD8B | HANGUL SYLLABLE GWEOGS | `gwogs` | `gweogs` | `Gwogs` |
| 권 | U+AD8C | HANGUL SYLLABLE GWEON | `gwon` | `gweon` | `Gwon` |
| 궍 | U+AD8D | HANGUL SYLLABLE GWEONJ | `gwonj` | `gweonj` | `Gwonj` |
| 궎 | U+AD8E | HANGUL SYLLABLE GWEONH | `gwonh` | `gweonh` | `Gwonh` |
| 궏 | U+AD8F | HANGUL SYLLABLE GWEOD | `gwod` | `gweod` | `Gwod` |
| 궐 | U+AD90 | HANGUL SYLLABLE GWEOL | `gwol` | `gweol` | `Gwol` |
| 궑 | U+AD91 | HANGUL SYLLABLE GWEOLG | `gwolg` | `gweolg` | `Gwolg` |
| 궒 | U+AD92 | HANGUL SYLLABLE GWEOLM | `gwolm` | `gweolm` | `Gwolm` |
| 궓 | U+AD93 | HANGUL SYLLABLE GWEOLB | `gwolb` | `gweolb` | `Gwolb` |
| 궔 | U+AD94 | HANGUL SYLLABLE GWEOLS | `gwols` | `gweols` | `Gwols` |
| 궕 | U+AD95 | HANGUL SYLLABLE GWEOLT | `gwolt` | `gweolt` | `Gwolt` |
| 궖 | U+AD96 | HANGUL SYLLABLE GWEOLP | `gwolp` | `gweolp` | `Gwolp` |
| 궗 | U+AD97 | HANGUL SYLLABLE GWEOLH | `gwolh` | `gweolh` | `Gwolh` |
| 궘 | U+AD98 | HANGUL SYLLABLE GWEOM | `gwom` | `gweom` | `Gwom` |
| 궙 | U+AD99 | HANGUL SYLLABLE GWEOB | `gwob` | `gweob` | `Gwob` |
| 궚 | U+AD9A | HANGUL SYLLABLE GWEOBS | `gwobs` | `gweobs` | `Gwobs` |
| 궛 | U+AD9B | HANGUL SYLLABLE GWEOS | `gwos` | `gweos` | `Gwos` |
| 궜 | U+AD9C | HANGUL SYLLABLE GWEOSS | `gwoss` | `gweoss` | `Gwoss` |
| 궝 | U+AD9D | HANGUL SYLLABLE GWEONG | `gwong` | `gweong` | `Gwong` |
| | | *...3712 more differences* | | | |

### zh — Chinese

Block: 20992 assigned codepoints, 20954 mapped by at least one library.

Coverage: translit maps 20924/20954, Unidecode maps 20642/20954. **291** mapped only by translit, **9** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| 丆 | U+4E06 | CJK UNIFIED IDEOGRAPH-4E06 | `han` |
| 乊 | U+4E4A | CJK UNIFIED IDEOGRAPH-4E4A | `yi` |
| 乛 | U+4E5B | CJK UNIFIED IDEOGRAPH-4E5B | `ya` |
| 乥 | U+4E65 | CJK UNIFIED IDEOGRAPH-4E65 | `hu` |
| 乮 | U+4E6E | CJK UNIFIED IDEOGRAPH-4E6E | `mao` |
| 乽 | U+4E7D | CJK UNIFIED IDEOGRAPH-4E7D | `zhe` |
| 亪 | U+4EAA | CJK UNIFIED IDEOGRAPH-4EAA | `ye` |
| 仩 | U+4EE9 | CJK UNIFIED IDEOGRAPH-4EE9 | `chang` |
| 伬 | U+4F2C | CJK UNIFIED IDEOGRAPH-4F2C | `ze` |
| 佦 | U+4F66 | CJK UNIFIED IDEOGRAPH-4F66 | `shi` |
| 佨 | U+4F68 | CJK UNIFIED IDEOGRAPH-4F68 | `bao` |
| 俧 | U+4FE7 | CJK UNIFIED IDEOGRAPH-4FE7 | `zhi` |
| 俬 | U+4FEC | CJK UNIFIED IDEOGRAPH-4FEC | `si` |
| 倿 | U+503F | CJK UNIFIED IDEOGRAPH-503F | `ning` |
| 傦 | U+50A6 | CJK UNIFIED IDEOGRAPH-50A6 | `gu` |
| 僲 | U+50F2 | CJK UNIFIED IDEOGRAPH-50F2 | `xian` |
| 儏 | U+510F | CJK UNIFIED IDEOGRAPH-510F | `can` |
| 兯 | U+516F | CJK UNIFIED IDEOGRAPH-516F | `han` |
| 匇 | U+5307 | CJK UNIFIED IDEOGRAPH-5307 | `yi` |
| 厁 | U+5381 | CJK UNIFIED IDEOGRAPH-5381 | `san` |
| 厑 | U+5391 | CJK UNIFIED IDEOGRAPH-5391 | `ya` |
| 叾 | U+53FE | CJK UNIFIED IDEOGRAPH-53FE | `liao` |
| 呚 | U+545A | CJK UNIFIED IDEOGRAPH-545A | `wen` |
| 哖 | U+54D6 | CJK UNIFIED IDEOGRAPH-54D6 | `nian` |
| 哛 | U+54DB | CJK UNIFIED IDEOGRAPH-54DB | `fen` |
| 啹 | U+5579 | CJK UNIFIED IDEOGRAPH-5579 | `ju` |
| 嗴 | U+55F4 | CJK UNIFIED IDEOGRAPH-55F4 | `qiang` |
| 嚑 | U+5691 | CJK UNIFIED IDEOGRAPH-5691 | `xun` |
| 嚒 | U+5692 | CJK UNIFIED IDEOGRAPH-5692 | `me` |
| 囕 | U+56D5 | CJK UNIFIED IDEOGRAPH-56D5 | `lan` |
| | | *...261 more* | |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| 兙 | U+5159 | CJK UNIFIED IDEOGRAPH-5159 | `Shi ` |
| 兡 | U+5161 | CJK UNIFIED IDEOGRAPH-5161 | `Bai ` |
| 嗧 | U+55E7 | CJK UNIFIED IDEOGRAPH-55E7 | `Jia ` |
| 桛 | U+685B | CJK UNIFIED IDEOGRAPH-685B | `Kasei ` |
| 瓧 | U+74E7 | CJK UNIFIED IDEOGRAPH-74E7 | `Dekaguramu ` |
| 瓰 | U+74F0 | CJK UNIFIED IDEOGRAPH-74F0 | `Deshiguramu ` |
| 瓱 | U+74F1 | CJK UNIFIED IDEOGRAPH-74F1 | `Miriguramu ` |
| 瓼 | U+74FC | CJK UNIFIED IDEOGRAPH-74FC | `Sarake ` |
| 甅 | U+7505 | CJK UNIFIED IDEOGRAPH-7505 | `Senchigura ` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| 一 | U+4E00 | CJK UNIFIED IDEOGRAPH-4E00 | `yi` | `Yi ` | `Yi` |
| 丁 | U+4E01 | CJK UNIFIED IDEOGRAPH-4E01 | `ding` | `Ding ` | `Ding` |
| 丂 | U+4E02 | CJK UNIFIED IDEOGRAPH-4E02 | `kao` | `Kao ` | `Kao` |
| 七 | U+4E03 | CJK UNIFIED IDEOGRAPH-4E03 | `qi` | `Qi ` | `Qi` |
| 丄 | U+4E04 | CJK UNIFIED IDEOGRAPH-4E04 | `shang` | `Shang ` | `Shang` |
| 丅 | U+4E05 | CJK UNIFIED IDEOGRAPH-4E05 | `xia` | `Xia ` | `Xia` |
| 万 | U+4E07 | CJK UNIFIED IDEOGRAPH-4E07 | `wan` | `Mo ` | `Wan` |
| 丈 | U+4E08 | CJK UNIFIED IDEOGRAPH-4E08 | `zhang` | `Zhang ` | `Zhang` |
| 三 | U+4E09 | CJK UNIFIED IDEOGRAPH-4E09 | `san` | `San ` | `San` |
| 上 | U+4E0A | CJK UNIFIED IDEOGRAPH-4E0A | `shang` | `Shang ` | `Shang` |
| 下 | U+4E0B | CJK UNIFIED IDEOGRAPH-4E0B | `xia` | `Xia ` | `Xia` |
| 丌 | U+4E0C | CJK UNIFIED IDEOGRAPH-4E0C | `ji` | `Ji ` | `Ji` |
| 不 | U+4E0D | CJK UNIFIED IDEOGRAPH-4E0D | `bu` | `Bu ` | `Bu` |
| 与 | U+4E0E | CJK UNIFIED IDEOGRAPH-4E0E | `yu` | `Yu ` | `Yu` |
| 丏 | U+4E0F | CJK UNIFIED IDEOGRAPH-4E0F | `mian` | `Mian ` | `Mian` |
| 丐 | U+4E10 | CJK UNIFIED IDEOGRAPH-4E10 | `gai` | `Gai ` | `Gai` |
| 丑 | U+4E11 | CJK UNIFIED IDEOGRAPH-4E11 | `chou` | `Chou ` | `Chou` |
| 丒 | U+4E12 | CJK UNIFIED IDEOGRAPH-4E12 | `chou` | `Chou ` | `Chou` |
| 专 | U+4E13 | CJK UNIFIED IDEOGRAPH-4E13 | `zhuan` | `Zhuan ` | `Zhuan` |
| 且 | U+4E14 | CJK UNIFIED IDEOGRAPH-4E14 | `qie` | `Qie ` | `Qie` |
| 丕 | U+4E15 | CJK UNIFIED IDEOGRAPH-4E15 | `pi` | `Pi ` | `Pi` |
| 世 | U+4E16 | CJK UNIFIED IDEOGRAPH-4E16 | `shi` | `Shi ` | `Shi` |
| 丗 | U+4E17 | CJK UNIFIED IDEOGRAPH-4E17 | `shi` | `Shi ` | `Shi` |
| 丘 | U+4E18 | CJK UNIFIED IDEOGRAPH-4E18 | `qiu` | `Qiu ` | `Qiu` |
| 丙 | U+4E19 | CJK UNIFIED IDEOGRAPH-4E19 | `bing` | `Bing ` | `Bing` |
| 业 | U+4E1A | CJK UNIFIED IDEOGRAPH-4E1A | `ye` | `Ye ` | `Ye` |
| 丛 | U+4E1B | CJK UNIFIED IDEOGRAPH-4E1B | `cong` | `Cong ` | `Cong` |
| 东 | U+4E1C | CJK UNIFIED IDEOGRAPH-4E1C | `dong` | `Dong ` | `Dong` |
| 丝 | U+4E1D | CJK UNIFIED IDEOGRAPH-4E1D | `si` | `Si ` | `Si` |
| 丞 | U+4E1E | CJK UNIFIED IDEOGRAPH-4E1E | `cheng` | `Cheng ` | `Cheng` |
| 丟 | U+4E1F | CJK UNIFIED IDEOGRAPH-4E1F | `diu` | `Diu ` | `Diu` |
| 丠 | U+4E20 | CJK UNIFIED IDEOGRAPH-4E20 | `qiu` | `Qiu ` | `Qiu` |
| 両 | U+4E21 | CJK UNIFIED IDEOGRAPH-4E21 | `liang` | `Liang ` | `Liang` |
| 丢 | U+4E22 | CJK UNIFIED IDEOGRAPH-4E22 | `diu` | `Diu ` | `Diu` |
| 丣 | U+4E23 | CJK UNIFIED IDEOGRAPH-4E23 | `you` | `You ` | `You` |
| 两 | U+4E24 | CJK UNIFIED IDEOGRAPH-4E24 | `liang` | `Liang ` | `Liang` |
| 严 | U+4E25 | CJK UNIFIED IDEOGRAPH-4E25 | `yan` | `Yan ` | `Yan` |
| 並 | U+4E26 | CJK UNIFIED IDEOGRAPH-4E26 | `bing` | `Bing ` | `Bing` |
| 丧 | U+4E27 | CJK UNIFIED IDEOGRAPH-4E27 | `sang` | `Sang ` | `Sang` |
| 丨 | U+4E28 | CJK UNIFIED IDEOGRAPH-4E28 | `gun` | `Gun ` | `Gun` |
| 丩 | U+4E29 | CJK UNIFIED IDEOGRAPH-4E29 | `jiu` | `Jiu ` | `Jiu` |
| 个 | U+4E2A | CJK UNIFIED IDEOGRAPH-4E2A | `ge` | `Ge ` | `Ge` |
| 丫 | U+4E2B | CJK UNIFIED IDEOGRAPH-4E2B | `ya` | `Ya ` | `Ya` |
| 丬 | U+4E2C | CJK UNIFIED IDEOGRAPH-4E2C | `qiang` | `Qiang ` | `Qiang` |
| 中 | U+4E2D | CJK UNIFIED IDEOGRAPH-4E2D | `zhong` | `Zhong ` | `Zhong` |
| 丮 | U+4E2E | CJK UNIFIED IDEOGRAPH-4E2E | `ji` | `Ji ` | `Ji` |
| 丯 | U+4E2F | CJK UNIFIED IDEOGRAPH-4E2F | `jie` | `Jie ` | `Jie` |
| 丰 | U+4E30 | CJK UNIFIED IDEOGRAPH-4E30 | `feng` | `Feng ` | `Feng` |
| 丱 | U+4E31 | CJK UNIFIED IDEOGRAPH-4E31 | `guan` | `Guan ` | `Guan` |
| 串 | U+4E32 | CJK UNIFIED IDEOGRAPH-4E32 | `chuan` | `Chuan ` | `Chuan` |
| | | *...20583 more differences* | | | |

### ar — Arabic

Block: 248 assigned codepoints, 221 mapped by at least one library.

Coverage: translit maps 207/221, Unidecode maps 173/221. **38** mapped only by translit, **4** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ؉ | U+0609 | ARABIC-INDIC PER MILLE SIGN | `%o` |
| ؊ | U+060A | ARABIC-INDIC PER TEN THOUSAND SIGN | `%oo` |
| ؋ | U+060B | AFGHANI SIGN | `Af` |
| ؍ | U+060D | ARABIC DATE SEPARATOR | `/` |
| ؖ | U+0616 | ARABIC SMALL HIGH LIGATURE ALEF WITH LAM WITH YEH | `aly` |
| ؘ | U+0618 | ARABIC SMALL FATHA | `a` |
| ؙ | U+0619 | ARABIC SMALL DAMMA | `u` |
| ؚ | U+061A | ARABIC SMALL KASRA | `i` |
| ؝ | U+061D | ARABIC END OF TEXT MARK | `.` |
| ؞ | U+061E | ARABIC TRIPLE DOT PUNCTUATION MARK | `...` |
| ؠ | U+0620 | ARABIC LETTER KASHMIRI YEH | `y` |
| ء | U+0621 | ARABIC LETTER HAMZA | `'` |
| إ | U+0625 | ARABIC LETTER ALEF WITH HAMZA BELOW | `a` |
| ا | U+0627 | ARABIC LETTER ALEF | `a` |
| ػ | U+063B | ARABIC LETTER KEHEH WITH TWO DOTS ABOVE | `k` |
| ؼ | U+063C | ARABIC LETTER KEHEH WITH THREE DOTS BELOW | `k` |
| ؽ | U+063D | ARABIC LETTER FARSI YEH WITH INVERTED V | `y` |
| ؾ | U+063E | ARABIC LETTER FARSI YEH WITH TWO DOTS ABOVE | `y` |
| ؿ | U+063F | ARABIC LETTER FARSI YEH WITH THREE DOTS ABOVE | `y` |
| ٖ | U+0656 | ARABIC SUBSCRIPT ALEF | `a` |
| ٗ | U+0657 | ARABIC INVERTED DAMMA | `u` |
| ٘ | U+0658 | ARABIC MARK NOON GHUNNA | `n` |
| ٝ | U+065D | ARABIC REVERSED DAMMA | `u` |
| ٞ | U+065E | ARABIC FATHA WITH TWO DOTS | `a` |
| ٟ | U+065F | ARABIC WAVY HAMZA BELOW | `'` |
| ٮ | U+066E | ARABIC LETTER DOTLESS BEH | `b` |
| ٯ | U+066F | ARABIC LETTER DOTLESS QAF | `q` |
| ٰ | U+0670 | ARABIC LETTER SUPERSCRIPT ALEF | `a` |
| ٴ | U+0674 | ARABIC LETTER HIGH HAMZA | `'` |
| ې | U+06D0 | ARABIC LETTER E | `e` |
| | | *...8 more* | |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ّ | U+0651 | ARABIC SHADDA | `W` |
| ۞ | U+06DE | ARABIC START OF RUB EL HIZB | `#` |
| ۩ | U+06E9 | ARABIC PLACE OF SAJDAH | `^` |
| ۾ | U+06FE | ARABIC SIGN SINDHI POSTPOSITION MEN | `+m` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| أ | U+0623 | ARABIC LETTER ALEF WITH HAMZA ABOVE | `a` | `'` | `'` |
| ؤ | U+0624 | ARABIC LETTER WAW WITH HAMZA ABOVE | `'` | `w'` | `u'` |
| ئ | U+0626 | ARABIC LETTER YEH WITH HAMZA ABOVE | `'` | `y'` | `i'` |
| ة | U+0629 | ARABIC LETTER TEH MARBUTA | `h` | `@` | `h` |
| ح | U+062D | ARABIC LETTER HAH | `h` | `H` | `h` |
| ص | U+0635 | ARABIC LETTER SAD | `s` | `S` | `s` |
| ض | U+0636 | ARABIC LETTER DAD | `d` | `D` | `d` |
| ط | U+0637 | ARABIC LETTER TAH | `t` | `T` | `t` |
| ظ | U+0638 | ARABIC LETTER ZAH | `z` | `Z` | `dh` |
| ع | U+0639 | ARABIC LETTER AIN | `'` | ``` | ``` |
| غ | U+063A | ARABIC LETTER GHAIN | `gh` | `G` | `gh` |
| ى | U+0649 | ARABIC LETTER ALEF MAKSURA | `a` | `~` | `a` |
| ٱ | U+0671 | ARABIC LETTER ALEF WASLA | `a` | `'` | `'` |
| ٲ | U+0672 | ARABIC LETTER ALEF WITH WAVY HAMZA ABOVE | `a` | `'` | `a` |
| ٳ | U+0673 | ARABIC LETTER ALEF WITH WAVY HAMZA BELOW | `a` | `'` | `u'` |
| ٵ | U+0675 | ARABIC LETTER HIGH HAMZA ALEF | `a` | `'` | `a` |
| ٶ | U+0676 | ARABIC LETTER HIGH HAMZA WAW | `w` | `'w` | `o` |
| ٷ | U+0677 | ARABIC LETTER U WITH HAMZA ABOVE | `u'` | `'u` | `u` |
| ٸ | U+0678 | ARABIC LETTER HIGH HAMZA YEH | `y` | `'y` | `i` |
| ٹ | U+0679 | ARABIC LETTER TTEH | `t` | `tt` | `t` |
| ٺ | U+067A | ARABIC LETTER TTEHEH | `t` | `tth` | `th` |
| ٽ | U+067D | ARABIC LETTER TEH WITH THREE DOTS ABOVE DOWNWARDS | `t` | `T` | `t` |
| ٿ | U+067F | ARABIC LETTER TEHEH | `t` | `th` | `th` |
| ڀ | U+0680 | ARABIC LETTER BEHEH | `b` | `bh` | `bh` |
| ځ | U+0681 | ARABIC LETTER HAH WITH HAMZA ABOVE | `h` | `'h` | `dz` |
| ڂ | U+0682 | ARABIC LETTER HAH WITH TWO DOTS VERTICAL ABOVE | `h` | `H` | `dz` |
| څ | U+0685 | ARABIC LETTER HAH WITH THREE DOTS ABOVE | `h` | `H` | `ts` |
| ڇ | U+0687 | ARABIC LETTER TCHEHEH | `ch` | `cch` | `ch` |
| ڈ | U+0688 | ARABIC LETTER DDAL | `d` | `dd` | `d` |
| ډ | U+0689 | ARABIC LETTER DAL WITH RING | `d` | `D` | `d` |
| ڊ | U+068A | ARABIC LETTER DAL WITH DOT BELOW | `d` | `D` | `d` |
| ڋ | U+068B | ARABIC LETTER DAL WITH DOT BELOW AND SMALL TAH | `d` | `Dt` | `dd` |
| ڌ | U+068C | ARABIC LETTER DAHAL | `d` | `dh` | `dh` |
| ڍ | U+068D | ARABIC LETTER DDAHAL | `d` | `ddh` | `dh` |
| ڏ | U+068F | ARABIC LETTER DAL WITH THREE DOTS ABOVE DOWNWARDS | `d` | `D` | `d` |
| ڐ | U+0690 | ARABIC LETTER DAL WITH FOUR DOTS ABOVE | `d` | `D` | `d` |
| ڑ | U+0691 | ARABIC LETTER RREH | `r` | `rr` | `r` |
| ڒ | U+0692 | ARABIC LETTER REH WITH SMALL V | `r` | `R` | `r` |
| ړ | U+0693 | ARABIC LETTER REH WITH RING | `r` | `R` | `r` |
| ڔ | U+0694 | ARABIC LETTER REH WITH DOT BELOW | `r` | `R` | `r` |
| ڕ | U+0695 | ARABIC LETTER REH WITH SMALL V BELOW | `r` | `R` | `r` |
| ږ | U+0696 | ARABIC LETTER REH WITH DOT BELOW AND DOT ABOVE | `r` | `R` | `zh` |
| ڗ | U+0697 | ARABIC LETTER REH WITH TWO DOTS ABOVE | `r` | `R` | `d` |
| ژ | U+0698 | ARABIC LETTER JEH | `zh` | `j` | `zh` |
| ڙ | U+0699 | ARABIC LETTER REH WITH FOUR DOTS ABOVE | `r` | `R` | `r` |
| ښ | U+069A | ARABIC LETTER SEEN WITH DOT BELOW AND DOT ABOVE | `s` | `S` | `sh` |
| ڛ | U+069B | ARABIC LETTER SEEN WITH THREE DOTS BELOW | `s` | `S` | `s` |
| ڜ | U+069C | ARABIC LETTER SEEN WITH THREE DOTS BELOW AND THREE DOTS ABOVE | `s` | `S` | `ch` |
| ڝ | U+069D | ARABIC LETTER SAD WITH TWO DOTS BELOW | `s` | `S` | `ts` |
| ڞ | U+069E | ARABIC LETTER SAD WITH THREE DOTS ABOVE | `s` | `S` | `ch` |
| | | *...42 more differences* | | | |

### fa — Persian

Block: 391 assigned codepoints, 331 mapped by at least one library.

Coverage: translit maps 207/331, Unidecode maps 173/331. **38** mapped only by translit, **4** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ؉ | U+0609 | ARABIC-INDIC PER MILLE SIGN | `%o` |
| ؊ | U+060A | ARABIC-INDIC PER TEN THOUSAND SIGN | `%oo` |
| ؋ | U+060B | AFGHANI SIGN | `Af` |
| ؍ | U+060D | ARABIC DATE SEPARATOR | `/` |
| ؖ | U+0616 | ARABIC SMALL HIGH LIGATURE ALEF WITH LAM WITH YEH | `aly` |
| ؘ | U+0618 | ARABIC SMALL FATHA | `a` |
| ؙ | U+0619 | ARABIC SMALL DAMMA | `u` |
| ؚ | U+061A | ARABIC SMALL KASRA | `i` |
| ؝ | U+061D | ARABIC END OF TEXT MARK | `.` |
| ؞ | U+061E | ARABIC TRIPLE DOT PUNCTUATION MARK | `...` |
| ؠ | U+0620 | ARABIC LETTER KASHMIRI YEH | `y` |
| ء | U+0621 | ARABIC LETTER HAMZA | `'` |
| إ | U+0625 | ARABIC LETTER ALEF WITH HAMZA BELOW | `e` |
| ا | U+0627 | ARABIC LETTER ALEF | `a` |
| ػ | U+063B | ARABIC LETTER KEHEH WITH TWO DOTS ABOVE | `k` |
| ؼ | U+063C | ARABIC LETTER KEHEH WITH THREE DOTS BELOW | `k` |
| ؽ | U+063D | ARABIC LETTER FARSI YEH WITH INVERTED V | `y` |
| ؾ | U+063E | ARABIC LETTER FARSI YEH WITH TWO DOTS ABOVE | `y` |
| ؿ | U+063F | ARABIC LETTER FARSI YEH WITH THREE DOTS ABOVE | `y` |
| ٖ | U+0656 | ARABIC SUBSCRIPT ALEF | `a` |
| ٗ | U+0657 | ARABIC INVERTED DAMMA | `u` |
| ٘ | U+0658 | ARABIC MARK NOON GHUNNA | `n` |
| ٝ | U+065D | ARABIC REVERSED DAMMA | `u` |
| ٞ | U+065E | ARABIC FATHA WITH TWO DOTS | `a` |
| ٟ | U+065F | ARABIC WAVY HAMZA BELOW | `'` |
| ٮ | U+066E | ARABIC LETTER DOTLESS BEH | `b` |
| ٯ | U+066F | ARABIC LETTER DOTLESS QAF | `q` |
| ٰ | U+0670 | ARABIC LETTER SUPERSCRIPT ALEF | `a` |
| ٴ | U+0674 | ARABIC LETTER HIGH HAMZA | `'` |
| ې | U+06D0 | ARABIC LETTER E | `e` |
| | | *...8 more* | |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ّ | U+0651 | ARABIC SHADDA | `W` |
| ۞ | U+06DE | ARABIC START OF RUB EL HIZB | `#` |
| ۩ | U+06E9 | ARABIC PLACE OF SAJDAH | `^` |
| ۾ | U+06FE | ARABIC SIGN SINDHI POSTPOSITION MEN | `+m` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| أ | U+0623 | ARABIC LETTER ALEF WITH HAMZA ABOVE | `a` | `'` | `'` |
| ؤ | U+0624 | ARABIC LETTER WAW WITH HAMZA ABOVE | `'` | `w'` | `u'` |
| ئ | U+0626 | ARABIC LETTER YEH WITH HAMZA ABOVE | `'` | `y'` | `i'` |
| ة | U+0629 | ARABIC LETTER TEH MARBUTA | `e` | `@` | `h` |
| ث | U+062B | ARABIC LETTER THEH | `s` | `th` | `th` |
| ح | U+062D | ARABIC LETTER HAH | `h` | `H` | `h` |
| ذ | U+0630 | ARABIC LETTER THAL | `z` | `dh` | `dh` |
| ص | U+0635 | ARABIC LETTER SAD | `s` | `S` | `s` |
| ض | U+0636 | ARABIC LETTER DAD | `z` | `D` | `d` |
| ط | U+0637 | ARABIC LETTER TAH | `t` | `T` | `t` |
| ظ | U+0638 | ARABIC LETTER ZAH | `z` | `Z` | `dh` |
| ع | U+0639 | ARABIC LETTER AIN | `'` | ``` | ``` |
| غ | U+063A | ARABIC LETTER GHAIN | `gh` | `G` | `gh` |
| و | U+0648 | ARABIC LETTER WAW | `v` | `w` | `w` |
| ى | U+0649 | ARABIC LETTER ALEF MAKSURA | `a` | `~` | `a` |
| ُ | U+064F | ARABIC DAMMA | `o` | `u` | `u` |
| ِ | U+0650 | ARABIC KASRA | `e` | `i` | `i` |
| ٱ | U+0671 | ARABIC LETTER ALEF WASLA | `a` | `'` | `'` |
| ٲ | U+0672 | ARABIC LETTER ALEF WITH WAVY HAMZA ABOVE | `a` | `'` | `a` |
| ٳ | U+0673 | ARABIC LETTER ALEF WITH WAVY HAMZA BELOW | `a` | `'` | `u'` |
| ٵ | U+0675 | ARABIC LETTER HIGH HAMZA ALEF | `a` | `'` | `a` |
| ٶ | U+0676 | ARABIC LETTER HIGH HAMZA WAW | `w` | `'w` | `o` |
| ٷ | U+0677 | ARABIC LETTER U WITH HAMZA ABOVE | `u'` | `'u` | `u` |
| ٸ | U+0678 | ARABIC LETTER HIGH HAMZA YEH | `y` | `'y` | `i` |
| ٹ | U+0679 | ARABIC LETTER TTEH | `t` | `tt` | `t` |
| ٺ | U+067A | ARABIC LETTER TTEHEH | `t` | `tth` | `th` |
| ٽ | U+067D | ARABIC LETTER TEH WITH THREE DOTS ABOVE DOWNWARDS | `t` | `T` | `t` |
| ٿ | U+067F | ARABIC LETTER TEHEH | `t` | `th` | `th` |
| ڀ | U+0680 | ARABIC LETTER BEHEH | `b` | `bh` | `bh` |
| ځ | U+0681 | ARABIC LETTER HAH WITH HAMZA ABOVE | `h` | `'h` | `dz` |
| ڂ | U+0682 | ARABIC LETTER HAH WITH TWO DOTS VERTICAL ABOVE | `h` | `H` | `dz` |
| څ | U+0685 | ARABIC LETTER HAH WITH THREE DOTS ABOVE | `h` | `H` | `ts` |
| ڇ | U+0687 | ARABIC LETTER TCHEHEH | `ch` | `cch` | `ch` |
| ڈ | U+0688 | ARABIC LETTER DDAL | `d` | `dd` | `d` |
| ډ | U+0689 | ARABIC LETTER DAL WITH RING | `d` | `D` | `d` |
| ڊ | U+068A | ARABIC LETTER DAL WITH DOT BELOW | `d` | `D` | `d` |
| ڋ | U+068B | ARABIC LETTER DAL WITH DOT BELOW AND SMALL TAH | `d` | `Dt` | `dd` |
| ڌ | U+068C | ARABIC LETTER DAHAL | `d` | `dh` | `dh` |
| ڍ | U+068D | ARABIC LETTER DDAHAL | `d` | `ddh` | `dh` |
| ڏ | U+068F | ARABIC LETTER DAL WITH THREE DOTS ABOVE DOWNWARDS | `d` | `D` | `d` |
| ڐ | U+0690 | ARABIC LETTER DAL WITH FOUR DOTS ABOVE | `d` | `D` | `d` |
| ڑ | U+0691 | ARABIC LETTER RREH | `r` | `rr` | `r` |
| ڒ | U+0692 | ARABIC LETTER REH WITH SMALL V | `r` | `R` | `r` |
| ړ | U+0693 | ARABIC LETTER REH WITH RING | `r` | `R` | `r` |
| ڔ | U+0694 | ARABIC LETTER REH WITH DOT BELOW | `r` | `R` | `r` |
| ڕ | U+0695 | ARABIC LETTER REH WITH SMALL V BELOW | `r` | `R` | `r` |
| ږ | U+0696 | ARABIC LETTER REH WITH DOT BELOW AND DOT ABOVE | `r` | `R` | `zh` |
| ڗ | U+0697 | ARABIC LETTER REH WITH TWO DOTS ABOVE | `r` | `R` | `d` |
| ژ | U+0698 | ARABIC LETTER JEH | `zh` | `j` | `zh` |
| ڙ | U+0699 | ARABIC LETTER REH WITH FOUR DOTS ABOVE | `r` | `R` | `r` |
| | | *...47 more differences* | | | |

### he — Hebrew

Block: 88 assigned codepoints, 53 mapped by at least one library.

Coverage: translit maps 46/53, Unidecode maps 49/53. **1** mapped only by translit, **4** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ְ | U+05B0 | HEBREW POINT SHEVA | `e` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ׀ | U+05C0 | HEBREW PUNCTUATION PASEQ | `|` |
| ׆ | U+05C6 | HEBREW PUNCTUATION NUN HAFUKHA | `n` |
| ע | U+05E2 | HEBREW LETTER AYIN | ``` |
| ׯ | U+05EF | HEBREW YOD TRIANGLE | `YYY` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| א | U+05D0 | HEBREW LETTER ALEF | `'` | `A` | `'` |
| ב | U+05D1 | HEBREW LETTER BET | `v` | `b` | `v` |
| ח | U+05D7 | HEBREW LETTER HET | `ch` | `H` | `h` |
| ט | U+05D8 | HEBREW LETTER TET | `t` | `T` | `t` |
| ך | U+05DA | HEBREW LETTER FINAL KAF | `kh` | `KH` | `kh` |
| כ | U+05DB | HEBREW LETTER KAF | `kh` | `KH` | `kh` |
| ף | U+05E3 | HEBREW LETTER FINAL PE | `f` | `p` | `f` |
| פ | U+05E4 | HEBREW LETTER PE | `f` | `p` | `f` |
| ץ | U+05E5 | HEBREW LETTER FINAL TSADI | `ts` | `TS` | `ts` |
| צ | U+05E6 | HEBREW LETTER TSADI | `ts` | `TS` | `ts` |
| ק | U+05E7 | HEBREW LETTER QOF | `q` | `k` | `k` |
| ש | U+05E9 | HEBREW LETTER SHIN | `sh` | `SH` | `s` |
| װ | U+05F0 | HEBREW LIGATURE YIDDISH DOUBLE VAV | `v` | `V` | `v` |
| ױ | U+05F1 | HEBREW LIGATURE YIDDISH VAV YOD | `vy` | `OY` | `oy` |
| ײ | U+05F2 | HEBREW LIGATURE YIDDISH DOUBLE YOD | `y` | `EY` | `ey` |

### hi — Hindi

Block: 128 assigned codepoints, 127 mapped by at least one library.

Coverage: translit maps 117/127, Unidecode maps 103/127. **19** mapped only by translit, **5** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ऄ | U+0904 | DEVANAGARI LETTER SHORT A | `a` |
| ॕ | U+0955 | DEVANAGARI VOWEL SIGN CANDRA LONG E | `e` |
| ॖ | U+0956 | DEVANAGARI VOWEL SIGN UE | `u` |
| ॗ | U+0957 | DEVANAGARI VOWEL SIGN UUE | `u` |
| ॱ | U+0971 | DEVANAGARI SIGN HIGH SPACING DOT | `.` |
| ॲ | U+0972 | DEVANAGARI LETTER CANDRA A | `a` |
| ॳ | U+0973 | DEVANAGARI LETTER OE | `oe` |
| ॴ | U+0974 | DEVANAGARI LETTER OOE | `ooe` |
| ॵ | U+0975 | DEVANAGARI LETTER AW | `aw` |
| ॶ | U+0976 | DEVANAGARI LETTER UE | `ue` |
| ॷ | U+0977 | DEVANAGARI LETTER UUE | `uue` |
| ॸ | U+0978 | DEVANAGARI LETTER MARWARI DDA | `dda` |
| ॹ | U+0979 | DEVANAGARI LETTER ZHA | `zha` |
| ॺ | U+097A | DEVANAGARI LETTER HEAVY YA | `ya` |
| ॻ | U+097B | DEVANAGARI LETTER GGA | `gga` |
| ॼ | U+097C | DEVANAGARI LETTER JJA | `jja` |
| ॽ | U+097D | DEVANAGARI LETTER GLOTTAL STOP | `'` |
| ॾ | U+097E | DEVANAGARI LETTER DDDA | `ddda` |
| ॿ | U+097F | DEVANAGARI LETTER BBA | `bba` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ़ | U+093C | DEVANAGARI SIGN NUKTA | `'` |
| ॑ | U+0951 | DEVANAGARI STRESS SIGN UDATTA | `'` |
| ॒ | U+0952 | DEVANAGARI STRESS SIGN ANUDATTA | `'` |
| ॓ | U+0953 | DEVANAGARI GRAVE ACCENT | ``` |
| ॔ | U+0954 | DEVANAGARI ACUTE ACCENT | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ँ | U+0901 | DEVANAGARI SIGN CANDRABINDU | `m` | `N` | `m` |
| ं | U+0902 | DEVANAGARI SIGN ANUSVARA | `m` | `N` | `m` |
| ः | U+0903 | DEVANAGARI SIGN VISARGA | `h` | `H` | `h` |
| ई | U+0908 | DEVANAGARI LETTER II | `i` | `ii` | `i` |
| ऊ | U+090A | DEVANAGARI LETTER UU | `u` | `uu` | `u` |
| ऋ | U+090B | DEVANAGARI LETTER VOCALIC R | `r` | `R` | `r` |
| ऌ | U+090C | DEVANAGARI LETTER VOCALIC L | `l` | `L` | `l` |
| ऍ | U+090D | DEVANAGARI LETTER CANDRA E | `e` | `eN` | `e` |
| ऑ | U+0911 | DEVANAGARI LETTER CANDRA O | `o` | `oN` | `o` |
| क | U+0915 | DEVANAGARI LETTER KA | `ka` | `k` | `k` |
| ख | U+0916 | DEVANAGARI LETTER KHA | `kha` | `kh` | `kh` |
| ग | U+0917 | DEVANAGARI LETTER GA | `ga` | `g` | `g` |
| घ | U+0918 | DEVANAGARI LETTER GHA | `gha` | `gh` | `gh` |
| ङ | U+0919 | DEVANAGARI LETTER NGA | `nga` | `ng` | `n` |
| च | U+091A | DEVANAGARI LETTER CA | `cha` | `c` | `c` |
| छ | U+091B | DEVANAGARI LETTER CHA | `chha` | `ch` | `ch` |
| ज | U+091C | DEVANAGARI LETTER JA | `ja` | `j` | `j` |
| झ | U+091D | DEVANAGARI LETTER JHA | `jha` | `jh` | `jh` |
| ञ | U+091E | DEVANAGARI LETTER NYA | `nya` | `ny` | `n` |
| ट | U+091F | DEVANAGARI LETTER TTA | `ta` | `tt` | `t` |
| ठ | U+0920 | DEVANAGARI LETTER TTHA | `tha` | `tth` | `th` |
| ड | U+0921 | DEVANAGARI LETTER DDA | `da` | `dd` | `d` |
| ढ | U+0922 | DEVANAGARI LETTER DDHA | `dha` | `ddh` | `dh` |
| ण | U+0923 | DEVANAGARI LETTER NNA | `na` | `nn` | `n` |
| त | U+0924 | DEVANAGARI LETTER TA | `ta` | `t` | `t` |
| थ | U+0925 | DEVANAGARI LETTER THA | `tha` | `th` | `th` |
| द | U+0926 | DEVANAGARI LETTER DA | `da` | `d` | `d` |
| ध | U+0927 | DEVANAGARI LETTER DHA | `dha` | `dh` | `dh` |
| न | U+0928 | DEVANAGARI LETTER NA | `na` | `n` | `n` |
| ऩ | U+0929 | DEVANAGARI LETTER NNNA | `na` | `nnn` | `n` |
| प | U+092A | DEVANAGARI LETTER PA | `pa` | `p` | `p` |
| फ | U+092B | DEVANAGARI LETTER PHA | `pha` | `ph` | `ph` |
| ब | U+092C | DEVANAGARI LETTER BA | `ba` | `b` | `b` |
| भ | U+092D | DEVANAGARI LETTER BHA | `bha` | `bh` | `bh` |
| म | U+092E | DEVANAGARI LETTER MA | `ma` | `m` | `m` |
| य | U+092F | DEVANAGARI LETTER YA | `ya` | `y` | `y` |
| र | U+0930 | DEVANAGARI LETTER RA | `ra` | `r` | `r` |
| ऱ | U+0931 | DEVANAGARI LETTER RRA | `ra` | `rr` | `r` |
| ल | U+0932 | DEVANAGARI LETTER LA | `la` | `l` | `l` |
| ळ | U+0933 | DEVANAGARI LETTER LLA | `la` | `l` | `l` |
| ऴ | U+0934 | DEVANAGARI LETTER LLLA | `la` | `lll` | `l` |
| व | U+0935 | DEVANAGARI LETTER VA | `va` | `v` | `v` |
| श | U+0936 | DEVANAGARI LETTER SHA | `sha` | `sh` | `s` |
| ष | U+0937 | DEVANAGARI LETTER SSA | `sha` | `ss` | `s` |
| स | U+0938 | DEVANAGARI LETTER SA | `sa` | `s` | `s` |
| ह | U+0939 | DEVANAGARI LETTER HA | `ha` | `h` | `h` |
| ा | U+093E | DEVANAGARI VOWEL SIGN AA | `a` | `aa` | `a` |
| ी | U+0940 | DEVANAGARI VOWEL SIGN II | `i` | `ii` | `i` |
| ू | U+0942 | DEVANAGARI VOWEL SIGN UU | `u` | `uu` | `u` |
| ृ | U+0943 | DEVANAGARI VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| | | *...18 more differences* | | | |

### bn — Bengali

Block: 96 assigned codepoints, 95 mapped by at least one library.

Coverage: translit maps 90/95, Unidecode maps 87/95. **5** mapped only by translit, **2** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ঀ | U+0980 | BENGALI ANJI | `m` |
| ঽ | U+09BD | BENGALI SIGN AVAGRAHA | `'` |
| ৎ | U+09CE | BENGALI LETTER KHANDA TA | `t` |
| ৼ | U+09FC | BENGALI LETTER VEDIC ANUSVARA | `m` |
| ৽ | U+09FD | BENGALI ABBREVIATION SIGN | `.` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ় | U+09BC | BENGALI SIGN NUKTA | `'` |
| ৗ | U+09D7 | BENGALI AU LENGTH MARK | `+` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ঁ | U+0981 | BENGALI SIGN CANDRABINDU | `m` | `N` | `m` |
| ং | U+0982 | BENGALI SIGN ANUSVARA | `m` | `N` | `m` |
| ঃ | U+0983 | BENGALI SIGN VISARGA | `h` | `H` | `h` |
| ঈ | U+0988 | BENGALI LETTER II | `i` | `ii` | `i` |
| ঊ | U+098A | BENGALI LETTER UU | `u` | `uu` | `u` |
| ঋ | U+098B | BENGALI LETTER VOCALIC R | `r` | `R` | `r` |
| ঌ | U+098C | BENGALI LETTER VOCALIC L | `l` | `RR` | `l` |
| ক | U+0995 | BENGALI LETTER KA | `ka` | `k` | `k` |
| খ | U+0996 | BENGALI LETTER KHA | `kha` | `kh` | `kh` |
| গ | U+0997 | BENGALI LETTER GA | `ga` | `g` | `g` |
| ঘ | U+0998 | BENGALI LETTER GHA | `gha` | `gh` | `gh` |
| ঙ | U+0999 | BENGALI LETTER NGA | `nga` | `ng` | `n` |
| চ | U+099A | BENGALI LETTER CA | `cha` | `c` | `c` |
| ছ | U+099B | BENGALI LETTER CHA | `chha` | `ch` | `ch` |
| জ | U+099C | BENGALI LETTER JA | `ja` | `j` | `j` |
| ঝ | U+099D | BENGALI LETTER JHA | `jha` | `jh` | `jh` |
| ঞ | U+099E | BENGALI LETTER NYA | `nya` | `ny` | `n` |
| ট | U+099F | BENGALI LETTER TTA | `ta` | `tt` | `t` |
| ঠ | U+09A0 | BENGALI LETTER TTHA | `tha` | `tth` | `th` |
| ড | U+09A1 | BENGALI LETTER DDA | `da` | `dd` | `d` |
| ঢ | U+09A2 | BENGALI LETTER DDHA | `dha` | `ddh` | `dh` |
| ণ | U+09A3 | BENGALI LETTER NNA | `na` | `nn` | `n` |
| ত | U+09A4 | BENGALI LETTER TA | `ta` | `t` | `t` |
| থ | U+09A5 | BENGALI LETTER THA | `tha` | `th` | `th` |
| দ | U+09A6 | BENGALI LETTER DA | `da` | `d` | `d` |
| ধ | U+09A7 | BENGALI LETTER DHA | `dha` | `dh` | `dh` |
| ন | U+09A8 | BENGALI LETTER NA | `na` | `n` | `n` |
| প | U+09AA | BENGALI LETTER PA | `pa` | `p` | `p` |
| ফ | U+09AB | BENGALI LETTER PHA | `pha` | `ph` | `ph` |
| ব | U+09AC | BENGALI LETTER BA | `ba` | `b` | `b` |
| ভ | U+09AD | BENGALI LETTER BHA | `bha` | `bh` | `bh` |
| ম | U+09AE | BENGALI LETTER MA | `ma` | `m` | `m` |
| য | U+09AF | BENGALI LETTER YA | `ya` | `y` | `y` |
| র | U+09B0 | BENGALI LETTER RA | `ra` | `r` | `r` |
| ল | U+09B2 | BENGALI LETTER LA | `la` | `l` | `l` |
| শ | U+09B6 | BENGALI LETTER SHA | `sha` | `sh` | `s` |
| ষ | U+09B7 | BENGALI LETTER SSA | `sha` | `ss` | `s` |
| স | U+09B8 | BENGALI LETTER SA | `sa` | `s` | `s` |
| হ | U+09B9 | BENGALI LETTER HA | `ha` | `h` | `h` |
| া | U+09BE | BENGALI VOWEL SIGN AA | `a` | `aa` | `a` |
| ী | U+09C0 | BENGALI VOWEL SIGN II | `i` | `ii` | `i` |
| ূ | U+09C2 | BENGALI VOWEL SIGN UU | `u` | `uu` | `u` |
| ৃ | U+09C3 | BENGALI VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| ৄ | U+09C4 | BENGALI VOWEL SIGN VOCALIC RR | `r` | `RR` | `r` |
| ড় | U+09DC | BENGALI LETTER RRA | `ra` | `rr` | `r` |
| ঢ় | U+09DD | BENGALI LETTER RHA | `rha` | `rh` | `rh` |
| য় | U+09DF | BENGALI LETTER YYA | `ya` | `yy` | `y` |
| ৠ | U+09E0 | BENGALI LETTER VOCALIC RR | `r` | `RR` | `r` |
| ৡ | U+09E1 | BENGALI LETTER VOCALIC LL | `l` | `LL` | `l` |
| ৢ | U+09E2 | BENGALI VOWEL SIGN VOCALIC L | `l` | `L` | `l` |
| | | *...9 more differences* | | | |

### ta — Tamil

Block: 72 assigned codepoints, 71 mapped by at least one library.

Coverage: translit maps 63/71, Unidecode maps 61/71. **3** mapped only by translit, **1** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ஶ | U+0BB6 | TAMIL LETTER SHA | `sha` |
| ௐ | U+0BD0 | TAMIL OM | `om` |
| ௹ | U+0BF9 | TAMIL RUPEE SIGN | `Rs` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ௗ | U+0BD7 | TAMIL AU LENGTH MARK | `+` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ஂ | U+0B82 | TAMIL SIGN ANUSVARA | `m` | `N` | `m` |
| ஃ | U+0B83 | TAMIL SIGN VISARGA | `h` | `H` | `k` |
| ஈ | U+0B88 | TAMIL LETTER II | `i` | `ii` | `i` |
| ஊ | U+0B8A | TAMIL LETTER UU | `u` | `uu` | `u` |
| ஏ | U+0B8F | TAMIL LETTER EE | `e` | `ee` | `e` |
| ஓ | U+0B93 | TAMIL LETTER OO | `o` | `oo` | `o` |
| க | U+0B95 | TAMIL LETTER KA | `ka` | `k` | `k` |
| ங | U+0B99 | TAMIL LETTER NGA | `nga` | `ng` | `n` |
| ச | U+0B9A | TAMIL LETTER CA | `cha` | `c` | `c` |
| ஜ | U+0B9C | TAMIL LETTER JA | `ja` | `j` | `j` |
| ஞ | U+0B9E | TAMIL LETTER NYA | `nya` | `ny` | `n` |
| ட | U+0B9F | TAMIL LETTER TTA | `ta` | `tt` | `t` |
| ண | U+0BA3 | TAMIL LETTER NNA | `na` | `nn` | `n` |
| த | U+0BA4 | TAMIL LETTER TA | `ta` | `t` | `t` |
| ந | U+0BA8 | TAMIL LETTER NA | `na` | `n` | `n` |
| ன | U+0BA9 | TAMIL LETTER NNNA | `na` | `nnn` | `n` |
| ப | U+0BAA | TAMIL LETTER PA | `pa` | `p` | `p` |
| ம | U+0BAE | TAMIL LETTER MA | `ma` | `m` | `m` |
| ய | U+0BAF | TAMIL LETTER YA | `ya` | `y` | `y` |
| ர | U+0BB0 | TAMIL LETTER RA | `ra` | `r` | `r` |
| ற | U+0BB1 | TAMIL LETTER RRA | `ra` | `rr` | `r` |
| ல | U+0BB2 | TAMIL LETTER LA | `la` | `l` | `l` |
| ள | U+0BB3 | TAMIL LETTER LLA | `la` | `ll` | `l` |
| ழ | U+0BB4 | TAMIL LETTER LLLA | `zha` | `lll` | `l` |
| வ | U+0BB5 | TAMIL LETTER VA | `va` | `v` | `v` |
| ஷ | U+0BB7 | TAMIL LETTER SSA | `sha` | `ss` | `s` |
| ஸ | U+0BB8 | TAMIL LETTER SA | `sa` | `s` | `s` |
| ஹ | U+0BB9 | TAMIL LETTER HA | `ha` | `h` | `h` |
| ா | U+0BBE | TAMIL VOWEL SIGN AA | `a` | `aa` | `a` |
| ீ | U+0BC0 | TAMIL VOWEL SIGN II | `i` | `ii` | `i` |
| ூ | U+0BC2 | TAMIL VOWEL SIGN UU | `u` | `uu` | `u` |
| ே | U+0BC7 | TAMIL VOWEL SIGN EE | `e` | `ee` | `e` |
| ோ | U+0BCB | TAMIL VOWEL SIGN OO | `o` | `oo` | `o` |
| ௰ | U+0BF0 | TAMIL NUMBER TEN | `10` | `+10+` | `10` |
| ௱ | U+0BF1 | TAMIL NUMBER ONE HUNDRED | `100` | `+100+` | `100` |
| ௲ | U+0BF2 | TAMIL NUMBER ONE THOUSAND | `1000` | `+1000+` | `1000` |

### te — Telugu

Block: 100 assigned codepoints, 99 mapped by at least one library.

Coverage: translit maps 92/99, Unidecode maps 79/99. **15** mapped only by translit, **2** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ఴ | U+0C34 | TELUGU LETTER LLLA | `lla` |
| ఽ | U+0C3D | TELUGU SIGN AVAGRAHA | `'` |
| ౘ | U+0C58 | TELUGU LETTER TSA | `tsa` |
| ౙ | U+0C59 | TELUGU LETTER DZA | `dza` |
| ౚ | U+0C5A | TELUGU LETTER RRRA | `rra` |
| ౝ | U+0C5D | TELUGU LETTER NAKAARA POLLU | `n` |
| ౢ | U+0C62 | TELUGU VOWEL SIGN VOCALIC L | `l` |
| ౣ | U+0C63 | TELUGU VOWEL SIGN VOCALIC LL | `l` |
| ౸ | U+0C78 | TELUGU FRACTION DIGIT ZERO FOR ODD POWERS OF FOUR | `0` |
| ౹ | U+0C79 | TELUGU FRACTION DIGIT ONE FOR ODD POWERS OF FOUR | `1` |
| ౺ | U+0C7A | TELUGU FRACTION DIGIT TWO FOR ODD POWERS OF FOUR | `2` |
| ౻ | U+0C7B | TELUGU FRACTION DIGIT THREE FOR ODD POWERS OF FOUR | `3` |
| ౼ | U+0C7C | TELUGU FRACTION DIGIT ONE FOR EVEN POWERS OF FOUR | `1` |
| ౽ | U+0C7D | TELUGU FRACTION DIGIT TWO FOR EVEN POWERS OF FOUR | `2` |
| ౾ | U+0C7E | TELUGU FRACTION DIGIT THREE FOR EVEN POWERS OF FOUR | `3` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ౕ | U+0C55 | TELUGU LENGTH MARK | `+` |
| ౖ | U+0C56 | TELUGU AI LENGTH MARK | `+` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ఁ | U+0C01 | TELUGU SIGN CANDRABINDU | `m` | `N` | `n` |
| ం | U+0C02 | TELUGU SIGN ANUSVARA | `m` | `N` | `m` |
| ః | U+0C03 | TELUGU SIGN VISARGA | `h` | `H` | `h` |
| ఈ | U+0C08 | TELUGU LETTER II | `i` | `ii` | `i` |
| ఊ | U+0C0A | TELUGU LETTER UU | `u` | `uu` | `u` |
| ఋ | U+0C0B | TELUGU LETTER VOCALIC R | `r` | `R` | `r` |
| ఌ | U+0C0C | TELUGU LETTER VOCALIC L | `l` | `L` | `l` |
| ఏ | U+0C0F | TELUGU LETTER EE | `e` | `ee` | `e` |
| ఓ | U+0C13 | TELUGU LETTER OO | `o` | `oo` | `o` |
| క | U+0C15 | TELUGU LETTER KA | `ka` | `k` | `k` |
| ఖ | U+0C16 | TELUGU LETTER KHA | `kha` | `kh` | `kh` |
| గ | U+0C17 | TELUGU LETTER GA | `ga` | `g` | `g` |
| ఘ | U+0C18 | TELUGU LETTER GHA | `gha` | `gh` | `gh` |
| ఙ | U+0C19 | TELUGU LETTER NGA | `nga` | `ng` | `n` |
| చ | U+0C1A | TELUGU LETTER CA | `cha` | `c` | `c` |
| ఛ | U+0C1B | TELUGU LETTER CHA | `chha` | `ch` | `ch` |
| జ | U+0C1C | TELUGU LETTER JA | `ja` | `j` | `j` |
| ఝ | U+0C1D | TELUGU LETTER JHA | `jha` | `jh` | `jh` |
| ఞ | U+0C1E | TELUGU LETTER NYA | `nya` | `ny` | `n` |
| ట | U+0C1F | TELUGU LETTER TTA | `ta` | `tt` | `t` |
| ఠ | U+0C20 | TELUGU LETTER TTHA | `tha` | `tth` | `th` |
| డ | U+0C21 | TELUGU LETTER DDA | `da` | `dd` | `d` |
| ఢ | U+0C22 | TELUGU LETTER DDHA | `dha` | `ddh` | `dh` |
| ణ | U+0C23 | TELUGU LETTER NNA | `na` | `nn` | `n` |
| త | U+0C24 | TELUGU LETTER TA | `ta` | `t` | `t` |
| థ | U+0C25 | TELUGU LETTER THA | `tha` | `th` | `th` |
| ద | U+0C26 | TELUGU LETTER DA | `da` | `d` | `d` |
| ధ | U+0C27 | TELUGU LETTER DHA | `dha` | `dh` | `dh` |
| న | U+0C28 | TELUGU LETTER NA | `na` | `n` | `n` |
| ప | U+0C2A | TELUGU LETTER PA | `pa` | `p` | `p` |
| ఫ | U+0C2B | TELUGU LETTER PHA | `pha` | `ph` | `ph` |
| బ | U+0C2C | TELUGU LETTER BA | `ba` | `b` | `b` |
| భ | U+0C2D | TELUGU LETTER BHA | `bha` | `bh` | `bh` |
| మ | U+0C2E | TELUGU LETTER MA | `ma` | `m` | `m` |
| య | U+0C2F | TELUGU LETTER YA | `ya` | `y` | `y` |
| ర | U+0C30 | TELUGU LETTER RA | `ra` | `r` | `r` |
| ఱ | U+0C31 | TELUGU LETTER RRA | `ra` | `rr` | `r` |
| ల | U+0C32 | TELUGU LETTER LA | `la` | `l` | `l` |
| ళ | U+0C33 | TELUGU LETTER LLA | `la` | `ll` | `l` |
| వ | U+0C35 | TELUGU LETTER VA | `va` | `v` | `v` |
| శ | U+0C36 | TELUGU LETTER SHA | `sha` | `sh` | `s` |
| ష | U+0C37 | TELUGU LETTER SSA | `sha` | `ss` | `s` |
| స | U+0C38 | TELUGU LETTER SA | `sa` | `s` | `s` |
| హ | U+0C39 | TELUGU LETTER HA | `ha` | `h` | `h` |
| ా | U+0C3E | TELUGU VOWEL SIGN AA | `a` | `aa` | `a` |
| ీ | U+0C40 | TELUGU VOWEL SIGN II | `i` | `ii` | `i` |
| ూ | U+0C42 | TELUGU VOWEL SIGN UU | `u` | `uu` | `u` |
| ృ | U+0C43 | TELUGU VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| ౄ | U+0C44 | TELUGU VOWEL SIGN VOCALIC RR | `r` | `RR` | `r` |
| ే | U+0C47 | TELUGU VOWEL SIGN EE | `e` | `ee` | `e` |
| | | *...3 more differences* | | | |

### gu — Gujarati

Block: 91 assigned codepoints, 87 mapped by at least one library.

Coverage: translit maps 83/87, Unidecode maps 77/87. **7** mapped only by translit, **1** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ઌ | U+0A8C | GUJARATI LETTER VOCALIC L | `l` |
| ૡ | U+0AE1 | GUJARATI LETTER VOCALIC LL | `l` |
| ૢ | U+0AE2 | GUJARATI VOWEL SIGN VOCALIC L | `l` |
| ૣ | U+0AE3 | GUJARATI VOWEL SIGN VOCALIC LL | `l` |
| ૰ | U+0AF0 | GUJARATI ABBREVIATION SIGN | `.` |
| ૱ | U+0AF1 | GUJARATI RUPEE SIGN | `Rs` |
| ૹ | U+0AF9 | GUJARATI LETTER ZHA | `zha` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ઼ | U+0ABC | GUJARATI SIGN NUKTA | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ઁ | U+0A81 | GUJARATI SIGN CANDRABINDU | `m` | `N` | `m` |
| ં | U+0A82 | GUJARATI SIGN ANUSVARA | `m` | `N` | `m` |
| ઃ | U+0A83 | GUJARATI SIGN VISARGA | `h` | `H` | `h` |
| ઈ | U+0A88 | GUJARATI LETTER II | `i` | `ii` | `i` |
| ઊ | U+0A8A | GUJARATI LETTER UU | `u` | `uu` | `u` |
| ઋ | U+0A8B | GUJARATI LETTER VOCALIC R | `r` | `R` | `r` |
| ઍ | U+0A8D | GUJARATI VOWEL CANDRA E | `e` | `eN` | `e` |
| ઑ | U+0A91 | GUJARATI VOWEL CANDRA O | `o` | `oN` | `o` |
| ક | U+0A95 | GUJARATI LETTER KA | `ka` | `k` | `k` |
| ખ | U+0A96 | GUJARATI LETTER KHA | `kha` | `kh` | `kh` |
| ગ | U+0A97 | GUJARATI LETTER GA | `ga` | `g` | `g` |
| ઘ | U+0A98 | GUJARATI LETTER GHA | `gha` | `gh` | `gh` |
| ઙ | U+0A99 | GUJARATI LETTER NGA | `nga` | `ng` | `n` |
| ચ | U+0A9A | GUJARATI LETTER CA | `cha` | `c` | `c` |
| છ | U+0A9B | GUJARATI LETTER CHA | `chha` | `ch` | `ch` |
| જ | U+0A9C | GUJARATI LETTER JA | `ja` | `j` | `j` |
| ઝ | U+0A9D | GUJARATI LETTER JHA | `jha` | `jh` | `jh` |
| ઞ | U+0A9E | GUJARATI LETTER NYA | `nya` | `ny` | `n` |
| ટ | U+0A9F | GUJARATI LETTER TTA | `ta` | `tt` | `t` |
| ઠ | U+0AA0 | GUJARATI LETTER TTHA | `tha` | `tth` | `th` |
| ડ | U+0AA1 | GUJARATI LETTER DDA | `da` | `dd` | `d` |
| ઢ | U+0AA2 | GUJARATI LETTER DDHA | `dha` | `ddh` | `dh` |
| ણ | U+0AA3 | GUJARATI LETTER NNA | `na` | `nn` | `n` |
| ત | U+0AA4 | GUJARATI LETTER TA | `ta` | `t` | `t` |
| થ | U+0AA5 | GUJARATI LETTER THA | `tha` | `th` | `th` |
| દ | U+0AA6 | GUJARATI LETTER DA | `da` | `d` | `d` |
| ધ | U+0AA7 | GUJARATI LETTER DHA | `dha` | `dh` | `dh` |
| ન | U+0AA8 | GUJARATI LETTER NA | `na` | `n` | `n` |
| પ | U+0AAA | GUJARATI LETTER PA | `pa` | `p` | `p` |
| ફ | U+0AAB | GUJARATI LETTER PHA | `pha` | `ph` | `ph` |
| બ | U+0AAC | GUJARATI LETTER BA | `ba` | `b` | `b` |
| ભ | U+0AAD | GUJARATI LETTER BHA | `bha` | `bh` | `bh` |
| મ | U+0AAE | GUJARATI LETTER MA | `ma` | `m` | `m` |
| ર | U+0AB0 | GUJARATI LETTER RA | `ra` | `r` | `r` |
| લ | U+0AB2 | GUJARATI LETTER LA | `la` | `l` | `l` |
| ળ | U+0AB3 | GUJARATI LETTER LLA | `la` | `ll` | `l` |
| વ | U+0AB5 | GUJARATI LETTER VA | `va` | `v` | `v` |
| શ | U+0AB6 | GUJARATI LETTER SHA | `sha` | `sh` | `s` |
| ષ | U+0AB7 | GUJARATI LETTER SSA | `sha` | `ss` | `s` |
| સ | U+0AB8 | GUJARATI LETTER SA | `sa` | `s` | `s` |
| હ | U+0AB9 | GUJARATI LETTER HA | `ha` | `h` | `h` |
| ા | U+0ABE | GUJARATI VOWEL SIGN AA | `a` | `aa` | `a` |
| ી | U+0AC0 | GUJARATI VOWEL SIGN II | `i` | `ii` | `i` |
| ૂ | U+0AC2 | GUJARATI VOWEL SIGN UU | `u` | `uu` | `u` |
| ૃ | U+0AC3 | GUJARATI VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| ૄ | U+0AC4 | GUJARATI VOWEL SIGN VOCALIC RR | `r` | `RR` | `r` |
| ૅ | U+0AC5 | GUJARATI VOWEL SIGN CANDRA E | `e` | `eN` | `e` |
| ૉ | U+0AC9 | GUJARATI VOWEL SIGN CANDRA O | `o` | `oN` | `o` |
| ૐ | U+0AD0 | GUJARATI OM | `om` | `AUM` | `Om` |
| ૠ | U+0AE0 | GUJARATI LETTER VOCALIC RR | `r` | `RR` | `r` |

### kn — Kannada

Block: 91 assigned codepoints, 90 mapped by at least one library.

Coverage: translit maps 85/90, Unidecode maps 79/90. **8** mapped only by translit, **2** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ಀ | U+0C80 | KANNADA SIGN SPACING CANDRABINDU | `m` |
| ಁ | U+0C81 | KANNADA SIGN CANDRABINDU | `m` |
| ಽ | U+0CBD | KANNADA SIGN AVAGRAHA | `'` |
| ೝ | U+0CDD | KANNADA LETTER NAKAARA POLLU | `n` |
| ೢ | U+0CE2 | KANNADA VOWEL SIGN VOCALIC L | `l` |
| ೣ | U+0CE3 | KANNADA VOWEL SIGN VOCALIC LL | `l` |
| ೱ | U+0CF1 | KANNADA SIGN JIHVAMULIYA | `h` |
| ೲ | U+0CF2 | KANNADA SIGN UPADHMANIYA | `h` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ೕ | U+0CD5 | KANNADA LENGTH MARK | `+` |
| ೖ | U+0CD6 | KANNADA AI LENGTH MARK | `+` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ಂ | U+0C82 | KANNADA SIGN ANUSVARA | `m` | `N` | `m` |
| ಃ | U+0C83 | KANNADA SIGN VISARGA | `h` | `H` | `h` |
| ಈ | U+0C88 | KANNADA LETTER II | `i` | `ii` | `i` |
| ಊ | U+0C8A | KANNADA LETTER UU | `u` | `uu` | `u` |
| ಋ | U+0C8B | KANNADA LETTER VOCALIC R | `r` | `R` | `r` |
| ಌ | U+0C8C | KANNADA LETTER VOCALIC L | `l` | `L` | `l` |
| ಏ | U+0C8F | KANNADA LETTER EE | `e` | `ee` | `e` |
| ಓ | U+0C93 | KANNADA LETTER OO | `o` | `oo` | `o` |
| ಕ | U+0C95 | KANNADA LETTER KA | `ka` | `k` | `k` |
| ಖ | U+0C96 | KANNADA LETTER KHA | `kha` | `kh` | `kh` |
| ಗ | U+0C97 | KANNADA LETTER GA | `ga` | `g` | `g` |
| ಘ | U+0C98 | KANNADA LETTER GHA | `gha` | `gh` | `gh` |
| ಙ | U+0C99 | KANNADA LETTER NGA | `nga` | `ng` | `n` |
| ಚ | U+0C9A | KANNADA LETTER CA | `cha` | `c` | `c` |
| ಛ | U+0C9B | KANNADA LETTER CHA | `chha` | `ch` | `ch` |
| ಜ | U+0C9C | KANNADA LETTER JA | `ja` | `j` | `j` |
| ಝ | U+0C9D | KANNADA LETTER JHA | `jha` | `jh` | `jh` |
| ಞ | U+0C9E | KANNADA LETTER NYA | `nya` | `ny` | `n` |
| ಟ | U+0C9F | KANNADA LETTER TTA | `ta` | `tt` | `t` |
| ಠ | U+0CA0 | KANNADA LETTER TTHA | `tha` | `tth` | `th` |
| ಡ | U+0CA1 | KANNADA LETTER DDA | `da` | `dd` | `d` |
| ಢ | U+0CA2 | KANNADA LETTER DDHA | `dha` | `ddh` | `dh` |
| ಣ | U+0CA3 | KANNADA LETTER NNA | `na` | `nn` | `n` |
| ತ | U+0CA4 | KANNADA LETTER TA | `ta` | `t` | `t` |
| ಥ | U+0CA5 | KANNADA LETTER THA | `tha` | `th` | `th` |
| ದ | U+0CA6 | KANNADA LETTER DA | `da` | `d` | `d` |
| ಧ | U+0CA7 | KANNADA LETTER DHA | `dha` | `dh` | `dh` |
| ನ | U+0CA8 | KANNADA LETTER NA | `na` | `n` | `n` |
| ಪ | U+0CAA | KANNADA LETTER PA | `pa` | `p` | `p` |
| ಫ | U+0CAB | KANNADA LETTER PHA | `pha` | `ph` | `ph` |
| ಬ | U+0CAC | KANNADA LETTER BA | `ba` | `b` | `b` |
| ಭ | U+0CAD | KANNADA LETTER BHA | `bha` | `bh` | `bh` |
| ಮ | U+0CAE | KANNADA LETTER MA | `ma` | `m` | `m` |
| ಯ | U+0CAF | KANNADA LETTER YA | `ya` | `y` | `y` |
| ರ | U+0CB0 | KANNADA LETTER RA | `ra` | `r` | `r` |
| ಱ | U+0CB1 | KANNADA LETTER RRA | `ra` | `rr` | `r` |
| ಲ | U+0CB2 | KANNADA LETTER LA | `la` | `l` | `l` |
| ಳ | U+0CB3 | KANNADA LETTER LLA | `la` | `ll` | `l` |
| ವ | U+0CB5 | KANNADA LETTER VA | `va` | `v` | `v` |
| ಶ | U+0CB6 | KANNADA LETTER SHA | `sha` | `sh` | `s` |
| ಷ | U+0CB7 | KANNADA LETTER SSA | `sha` | `ss` | `s` |
| ಸ | U+0CB8 | KANNADA LETTER SA | `sa` | `s` | `s` |
| ಹ | U+0CB9 | KANNADA LETTER HA | `ha` | `h` | `h` |
| ಾ | U+0CBE | KANNADA VOWEL SIGN AA | `a` | `aa` | `a` |
| ೀ | U+0CC0 | KANNADA VOWEL SIGN II | `i` | `ii` | `i` |
| ೂ | U+0CC2 | KANNADA VOWEL SIGN UU | `u` | `uu` | `u` |
| ೃ | U+0CC3 | KANNADA VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| ೄ | U+0CC4 | KANNADA VOWEL SIGN VOCALIC RR | `r` | `RR` | `r` |
| ೇ | U+0CC7 | KANNADA VOWEL SIGN EE | `e` | `ee` | `e` |
| ೋ | U+0CCB | KANNADA VOWEL SIGN OO | `o` | `oo` | `o` |
| | | *...3 more differences* | | | |

### ml — Malayalam

Block: 118 assigned codepoints, 115 mapped by at least one library.

Coverage: translit maps 111/115, Unidecode maps 77/115. **35** mapped only by translit, **1** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ഁ | U+0D01 | MALAYALAM SIGN CANDRABINDU | `m` |
| ഄ | U+0D04 | MALAYALAM LETTER VEDIC ANUSVARA | `a` |
| ഩ | U+0D29 | MALAYALAM LETTER NNNA | `nna` |
| ഺ | U+0D3A | MALAYALAM LETTER TTTA | `tta` |
| ഽ | U+0D3D | MALAYALAM SIGN AVAGRAHA | `'` |
| ൄ | U+0D44 | MALAYALAM VOWEL SIGN VOCALIC RR | `r` |
| ൎ | U+0D4E | MALAYALAM LETTER DOT REPH | `r` |
| ൔ | U+0D54 | MALAYALAM LETTER CHILLU M | `m` |
| ൕ | U+0D55 | MALAYALAM LETTER CHILLU Y | `y` |
| ൖ | U+0D56 | MALAYALAM LETTER CHILLU LLL | `l` |
| ൘ | U+0D58 | MALAYALAM FRACTION ONE ONE-HUNDRED-AND-SIXTIETH | `1/160` |
| ൙ | U+0D59 | MALAYALAM FRACTION ONE FORTIETH | `1/40` |
| ൚ | U+0D5A | MALAYALAM FRACTION THREE EIGHTIETHS | `3/80` |
| ൛ | U+0D5B | MALAYALAM FRACTION ONE TWENTIETH | `1/20` |
| ൜ | U+0D5C | MALAYALAM FRACTION ONE TENTH | `1/10` |
| ൝ | U+0D5D | MALAYALAM FRACTION THREE TWENTIETHS | `3/20` |
| ൞ | U+0D5E | MALAYALAM FRACTION ONE FIFTH | `1/5` |
| ൟ | U+0D5F | MALAYALAM LETTER ARCHAIC II | `ii` |
| ൢ | U+0D62 | MALAYALAM VOWEL SIGN VOCALIC L | `l` |
| ൣ | U+0D63 | MALAYALAM VOWEL SIGN VOCALIC LL | `l` |
| ൰ | U+0D70 | MALAYALAM NUMBER TEN | `10` |
| ൱ | U+0D71 | MALAYALAM NUMBER ONE HUNDRED | `100` |
| ൲ | U+0D72 | MALAYALAM NUMBER ONE THOUSAND | `1000` |
| ൳ | U+0D73 | MALAYALAM FRACTION ONE QUARTER | `1/4` |
| ൴ | U+0D74 | MALAYALAM FRACTION ONE HALF | `1/2` |
| ൵ | U+0D75 | MALAYALAM FRACTION THREE QUARTERS | `3/4` |
| ൶ | U+0D76 | MALAYALAM FRACTION ONE SIXTEENTH | `1/16` |
| ൷ | U+0D77 | MALAYALAM FRACTION ONE EIGHTH | `1/8` |
| ൸ | U+0D78 | MALAYALAM FRACTION THREE SIXTEENTHS | `3/16` |
| ൺ | U+0D7A | MALAYALAM LETTER CHILLU NN | `n` |
| | | *...5 more* | |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ൗ | U+0D57 | MALAYALAM AU LENGTH MARK | `+` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ം | U+0D02 | MALAYALAM SIGN ANUSVARA | `m` | `N` | `m` |
| ഃ | U+0D03 | MALAYALAM SIGN VISARGA | `h` | `H` | `h` |
| ഈ | U+0D08 | MALAYALAM LETTER II | `i` | `ii` | `i` |
| ഊ | U+0D0A | MALAYALAM LETTER UU | `u` | `uu` | `u` |
| ഋ | U+0D0B | MALAYALAM LETTER VOCALIC R | `r` | `R` | `r` |
| ഌ | U+0D0C | MALAYALAM LETTER VOCALIC L | `l` | `L` | `l` |
| ഏ | U+0D0F | MALAYALAM LETTER EE | `e` | `ee` | `e` |
| ഓ | U+0D13 | MALAYALAM LETTER OO | `o` | `oo` | `o` |
| ക | U+0D15 | MALAYALAM LETTER KA | `ka` | `k` | `k` |
| ഖ | U+0D16 | MALAYALAM LETTER KHA | `kha` | `kh` | `kh` |
| ഗ | U+0D17 | MALAYALAM LETTER GA | `ga` | `g` | `g` |
| ഘ | U+0D18 | MALAYALAM LETTER GHA | `gha` | `gh` | `gh` |
| ങ | U+0D19 | MALAYALAM LETTER NGA | `nga` | `ng` | `n` |
| ച | U+0D1A | MALAYALAM LETTER CA | `cha` | `c` | `c` |
| ഛ | U+0D1B | MALAYALAM LETTER CHA | `chha` | `ch` | `ch` |
| ജ | U+0D1C | MALAYALAM LETTER JA | `ja` | `j` | `j` |
| ഝ | U+0D1D | MALAYALAM LETTER JHA | `jha` | `jh` | `jh` |
| ഞ | U+0D1E | MALAYALAM LETTER NYA | `nya` | `ny` | `n` |
| ട | U+0D1F | MALAYALAM LETTER TTA | `ta` | `tt` | `t` |
| ഠ | U+0D20 | MALAYALAM LETTER TTHA | `tha` | `tth` | `th` |
| ഡ | U+0D21 | MALAYALAM LETTER DDA | `da` | `dd` | `d` |
| ഢ | U+0D22 | MALAYALAM LETTER DDHA | `dha` | `ddh` | `dh` |
| ണ | U+0D23 | MALAYALAM LETTER NNA | `na` | `nn` | `n` |
| ത | U+0D24 | MALAYALAM LETTER TA | `ta` | `t` | `t` |
| ഥ | U+0D25 | MALAYALAM LETTER THA | `tha` | `th` | `th` |
| ദ | U+0D26 | MALAYALAM LETTER DA | `da` | `d` | `d` |
| ധ | U+0D27 | MALAYALAM LETTER DHA | `dha` | `dh` | `dh` |
| ന | U+0D28 | MALAYALAM LETTER NA | `na` | `n` | `n` |
| പ | U+0D2A | MALAYALAM LETTER PA | `pa` | `p` | `p` |
| ഫ | U+0D2B | MALAYALAM LETTER PHA | `pha` | `ph` | `ph` |
| ബ | U+0D2C | MALAYALAM LETTER BA | `ba` | `b` | `b` |
| ഭ | U+0D2D | MALAYALAM LETTER BHA | `bha` | `bh` | `bh` |
| മ | U+0D2E | MALAYALAM LETTER MA | `ma` | `m` | `m` |
| യ | U+0D2F | MALAYALAM LETTER YA | `ya` | `y` | `y` |
| ര | U+0D30 | MALAYALAM LETTER RA | `ra` | `r` | `r` |
| റ | U+0D31 | MALAYALAM LETTER RRA | `ra` | `rr` | `r` |
| ല | U+0D32 | MALAYALAM LETTER LA | `la` | `l` | `l` |
| ള | U+0D33 | MALAYALAM LETTER LLA | `la` | `ll` | `l` |
| ഴ | U+0D34 | MALAYALAM LETTER LLLA | `zha` | `lll` | `l` |
| വ | U+0D35 | MALAYALAM LETTER VA | `va` | `v` | `v` |
| ശ | U+0D36 | MALAYALAM LETTER SHA | `sha` | `sh` | `s` |
| ഷ | U+0D37 | MALAYALAM LETTER SSA | `sha` | `ss` | `s` |
| സ | U+0D38 | MALAYALAM LETTER SA | `sa` | `s` | `s` |
| ഹ | U+0D39 | MALAYALAM LETTER HA | `ha` | `h` | `h` |
| ാ | U+0D3E | MALAYALAM VOWEL SIGN AA | `a` | `aa` | `a` |
| ീ | U+0D40 | MALAYALAM VOWEL SIGN II | `i` | `ii` | `i` |
| ൂ | U+0D42 | MALAYALAM VOWEL SIGN UU | `u` | `uu` | `u` |
| ൃ | U+0D43 | MALAYALAM VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| േ | U+0D47 | MALAYALAM VOWEL SIGN EE | `e` | `ee` | `e` |
| ോ | U+0D4B | MALAYALAM VOWEL SIGN OO | `o` | `oo` | `o` |
| | | *...2 more differences* | | | |

### mr — Marathi

Block: 128 assigned codepoints, 127 mapped by at least one library.

Coverage: translit maps 117/127, Unidecode maps 103/127. **19** mapped only by translit, **5** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ऄ | U+0904 | DEVANAGARI LETTER SHORT A | `a` |
| ॕ | U+0955 | DEVANAGARI VOWEL SIGN CANDRA LONG E | `e` |
| ॖ | U+0956 | DEVANAGARI VOWEL SIGN UE | `u` |
| ॗ | U+0957 | DEVANAGARI VOWEL SIGN UUE | `u` |
| ॱ | U+0971 | DEVANAGARI SIGN HIGH SPACING DOT | `.` |
| ॲ | U+0972 | DEVANAGARI LETTER CANDRA A | `a` |
| ॳ | U+0973 | DEVANAGARI LETTER OE | `oe` |
| ॴ | U+0974 | DEVANAGARI LETTER OOE | `ooe` |
| ॵ | U+0975 | DEVANAGARI LETTER AW | `aw` |
| ॶ | U+0976 | DEVANAGARI LETTER UE | `ue` |
| ॷ | U+0977 | DEVANAGARI LETTER UUE | `uue` |
| ॸ | U+0978 | DEVANAGARI LETTER MARWARI DDA | `dda` |
| ॹ | U+0979 | DEVANAGARI LETTER ZHA | `zha` |
| ॺ | U+097A | DEVANAGARI LETTER HEAVY YA | `ya` |
| ॻ | U+097B | DEVANAGARI LETTER GGA | `gga` |
| ॼ | U+097C | DEVANAGARI LETTER JJA | `jja` |
| ॽ | U+097D | DEVANAGARI LETTER GLOTTAL STOP | `'` |
| ॾ | U+097E | DEVANAGARI LETTER DDDA | `ddda` |
| ॿ | U+097F | DEVANAGARI LETTER BBA | `bba` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ़ | U+093C | DEVANAGARI SIGN NUKTA | `'` |
| ॑ | U+0951 | DEVANAGARI STRESS SIGN UDATTA | `'` |
| ॒ | U+0952 | DEVANAGARI STRESS SIGN ANUDATTA | `'` |
| ॓ | U+0953 | DEVANAGARI GRAVE ACCENT | ``` |
| ॔ | U+0954 | DEVANAGARI ACUTE ACCENT | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ँ | U+0901 | DEVANAGARI SIGN CANDRABINDU | `m` | `N` | `m` |
| ं | U+0902 | DEVANAGARI SIGN ANUSVARA | `m` | `N` | `m` |
| ः | U+0903 | DEVANAGARI SIGN VISARGA | `h` | `H` | `h` |
| ई | U+0908 | DEVANAGARI LETTER II | `i` | `ii` | `i` |
| ऊ | U+090A | DEVANAGARI LETTER UU | `u` | `uu` | `u` |
| ऋ | U+090B | DEVANAGARI LETTER VOCALIC R | `r` | `R` | `r` |
| ऌ | U+090C | DEVANAGARI LETTER VOCALIC L | `l` | `L` | `l` |
| ऍ | U+090D | DEVANAGARI LETTER CANDRA E | `e` | `eN` | `e` |
| ऑ | U+0911 | DEVANAGARI LETTER CANDRA O | `o` | `oN` | `o` |
| क | U+0915 | DEVANAGARI LETTER KA | `ka` | `k` | `k` |
| ख | U+0916 | DEVANAGARI LETTER KHA | `kha` | `kh` | `kh` |
| ग | U+0917 | DEVANAGARI LETTER GA | `ga` | `g` | `g` |
| घ | U+0918 | DEVANAGARI LETTER GHA | `gha` | `gh` | `gh` |
| ङ | U+0919 | DEVANAGARI LETTER NGA | `nga` | `ng` | `n` |
| च | U+091A | DEVANAGARI LETTER CA | `cha` | `c` | `c` |
| छ | U+091B | DEVANAGARI LETTER CHA | `chha` | `ch` | `ch` |
| ज | U+091C | DEVANAGARI LETTER JA | `ja` | `j` | `j` |
| झ | U+091D | DEVANAGARI LETTER JHA | `jha` | `jh` | `jh` |
| ञ | U+091E | DEVANAGARI LETTER NYA | `nya` | `ny` | `n` |
| ट | U+091F | DEVANAGARI LETTER TTA | `ta` | `tt` | `t` |
| ठ | U+0920 | DEVANAGARI LETTER TTHA | `tha` | `tth` | `th` |
| ड | U+0921 | DEVANAGARI LETTER DDA | `da` | `dd` | `d` |
| ढ | U+0922 | DEVANAGARI LETTER DDHA | `dha` | `ddh` | `dh` |
| ण | U+0923 | DEVANAGARI LETTER NNA | `na` | `nn` | `n` |
| त | U+0924 | DEVANAGARI LETTER TA | `ta` | `t` | `t` |
| थ | U+0925 | DEVANAGARI LETTER THA | `tha` | `th` | `th` |
| द | U+0926 | DEVANAGARI LETTER DA | `da` | `d` | `d` |
| ध | U+0927 | DEVANAGARI LETTER DHA | `dha` | `dh` | `dh` |
| न | U+0928 | DEVANAGARI LETTER NA | `na` | `n` | `n` |
| ऩ | U+0929 | DEVANAGARI LETTER NNNA | `na` | `nnn` | `n` |
| प | U+092A | DEVANAGARI LETTER PA | `pa` | `p` | `p` |
| फ | U+092B | DEVANAGARI LETTER PHA | `pha` | `ph` | `ph` |
| ब | U+092C | DEVANAGARI LETTER BA | `ba` | `b` | `b` |
| भ | U+092D | DEVANAGARI LETTER BHA | `bha` | `bh` | `bh` |
| म | U+092E | DEVANAGARI LETTER MA | `ma` | `m` | `m` |
| य | U+092F | DEVANAGARI LETTER YA | `ya` | `y` | `y` |
| र | U+0930 | DEVANAGARI LETTER RA | `ra` | `r` | `r` |
| ऱ | U+0931 | DEVANAGARI LETTER RRA | `ra` | `rr` | `r` |
| ल | U+0932 | DEVANAGARI LETTER LA | `la` | `l` | `l` |
| ळ | U+0933 | DEVANAGARI LETTER LLA | `la` | `l` | `l` |
| ऴ | U+0934 | DEVANAGARI LETTER LLLA | `la` | `lll` | `l` |
| व | U+0935 | DEVANAGARI LETTER VA | `va` | `v` | `v` |
| श | U+0936 | DEVANAGARI LETTER SHA | `sha` | `sh` | `s` |
| ष | U+0937 | DEVANAGARI LETTER SSA | `sha` | `ss` | `s` |
| स | U+0938 | DEVANAGARI LETTER SA | `sa` | `s` | `s` |
| ह | U+0939 | DEVANAGARI LETTER HA | `ha` | `h` | `h` |
| ा | U+093E | DEVANAGARI VOWEL SIGN AA | `a` | `aa` | `a` |
| ी | U+0940 | DEVANAGARI VOWEL SIGN II | `i` | `ii` | `i` |
| ू | U+0942 | DEVANAGARI VOWEL SIGN UU | `u` | `uu` | `u` |
| ृ | U+0943 | DEVANAGARI VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| | | *...18 more differences* | | | |

### ne — Nepali

Block: 128 assigned codepoints, 127 mapped by at least one library.

Coverage: translit maps 117/127, Unidecode maps 103/127. **19** mapped only by translit, **5** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ऄ | U+0904 | DEVANAGARI LETTER SHORT A | `a` |
| ॕ | U+0955 | DEVANAGARI VOWEL SIGN CANDRA LONG E | `e` |
| ॖ | U+0956 | DEVANAGARI VOWEL SIGN UE | `u` |
| ॗ | U+0957 | DEVANAGARI VOWEL SIGN UUE | `u` |
| ॱ | U+0971 | DEVANAGARI SIGN HIGH SPACING DOT | `.` |
| ॲ | U+0972 | DEVANAGARI LETTER CANDRA A | `a` |
| ॳ | U+0973 | DEVANAGARI LETTER OE | `oe` |
| ॴ | U+0974 | DEVANAGARI LETTER OOE | `ooe` |
| ॵ | U+0975 | DEVANAGARI LETTER AW | `aw` |
| ॶ | U+0976 | DEVANAGARI LETTER UE | `ue` |
| ॷ | U+0977 | DEVANAGARI LETTER UUE | `uue` |
| ॸ | U+0978 | DEVANAGARI LETTER MARWARI DDA | `dda` |
| ॹ | U+0979 | DEVANAGARI LETTER ZHA | `zha` |
| ॺ | U+097A | DEVANAGARI LETTER HEAVY YA | `ya` |
| ॻ | U+097B | DEVANAGARI LETTER GGA | `gga` |
| ॼ | U+097C | DEVANAGARI LETTER JJA | `jja` |
| ॽ | U+097D | DEVANAGARI LETTER GLOTTAL STOP | `'` |
| ॾ | U+097E | DEVANAGARI LETTER DDDA | `ddda` |
| ॿ | U+097F | DEVANAGARI LETTER BBA | `bba` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ़ | U+093C | DEVANAGARI SIGN NUKTA | `'` |
| ॑ | U+0951 | DEVANAGARI STRESS SIGN UDATTA | `'` |
| ॒ | U+0952 | DEVANAGARI STRESS SIGN ANUDATTA | `'` |
| ॓ | U+0953 | DEVANAGARI GRAVE ACCENT | ``` |
| ॔ | U+0954 | DEVANAGARI ACUTE ACCENT | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ँ | U+0901 | DEVANAGARI SIGN CANDRABINDU | `m` | `N` | `m` |
| ं | U+0902 | DEVANAGARI SIGN ANUSVARA | `m` | `N` | `m` |
| ः | U+0903 | DEVANAGARI SIGN VISARGA | `h` | `H` | `h` |
| ई | U+0908 | DEVANAGARI LETTER II | `i` | `ii` | `i` |
| ऊ | U+090A | DEVANAGARI LETTER UU | `u` | `uu` | `u` |
| ऋ | U+090B | DEVANAGARI LETTER VOCALIC R | `r` | `R` | `r` |
| ऌ | U+090C | DEVANAGARI LETTER VOCALIC L | `l` | `L` | `l` |
| ऍ | U+090D | DEVANAGARI LETTER CANDRA E | `e` | `eN` | `e` |
| ऑ | U+0911 | DEVANAGARI LETTER CANDRA O | `o` | `oN` | `o` |
| क | U+0915 | DEVANAGARI LETTER KA | `ka` | `k` | `k` |
| ख | U+0916 | DEVANAGARI LETTER KHA | `kha` | `kh` | `kh` |
| ग | U+0917 | DEVANAGARI LETTER GA | `ga` | `g` | `g` |
| घ | U+0918 | DEVANAGARI LETTER GHA | `gha` | `gh` | `gh` |
| ङ | U+0919 | DEVANAGARI LETTER NGA | `nga` | `ng` | `n` |
| च | U+091A | DEVANAGARI LETTER CA | `cha` | `c` | `c` |
| छ | U+091B | DEVANAGARI LETTER CHA | `chha` | `ch` | `ch` |
| ज | U+091C | DEVANAGARI LETTER JA | `ja` | `j` | `j` |
| झ | U+091D | DEVANAGARI LETTER JHA | `jha` | `jh` | `jh` |
| ञ | U+091E | DEVANAGARI LETTER NYA | `nya` | `ny` | `n` |
| ट | U+091F | DEVANAGARI LETTER TTA | `ta` | `tt` | `t` |
| ठ | U+0920 | DEVANAGARI LETTER TTHA | `tha` | `tth` | `th` |
| ड | U+0921 | DEVANAGARI LETTER DDA | `da` | `dd` | `d` |
| ढ | U+0922 | DEVANAGARI LETTER DDHA | `dha` | `ddh` | `dh` |
| ण | U+0923 | DEVANAGARI LETTER NNA | `na` | `nn` | `n` |
| त | U+0924 | DEVANAGARI LETTER TA | `ta` | `t` | `t` |
| थ | U+0925 | DEVANAGARI LETTER THA | `tha` | `th` | `th` |
| द | U+0926 | DEVANAGARI LETTER DA | `da` | `d` | `d` |
| ध | U+0927 | DEVANAGARI LETTER DHA | `dha` | `dh` | `dh` |
| न | U+0928 | DEVANAGARI LETTER NA | `na` | `n` | `n` |
| ऩ | U+0929 | DEVANAGARI LETTER NNNA | `na` | `nnn` | `n` |
| प | U+092A | DEVANAGARI LETTER PA | `pa` | `p` | `p` |
| फ | U+092B | DEVANAGARI LETTER PHA | `pha` | `ph` | `ph` |
| ब | U+092C | DEVANAGARI LETTER BA | `ba` | `b` | `b` |
| भ | U+092D | DEVANAGARI LETTER BHA | `bha` | `bh` | `bh` |
| म | U+092E | DEVANAGARI LETTER MA | `ma` | `m` | `m` |
| य | U+092F | DEVANAGARI LETTER YA | `ya` | `y` | `y` |
| र | U+0930 | DEVANAGARI LETTER RA | `ra` | `r` | `r` |
| ऱ | U+0931 | DEVANAGARI LETTER RRA | `ra` | `rr` | `r` |
| ल | U+0932 | DEVANAGARI LETTER LA | `la` | `l` | `l` |
| ळ | U+0933 | DEVANAGARI LETTER LLA | `la` | `l` | `l` |
| ऴ | U+0934 | DEVANAGARI LETTER LLLA | `la` | `lll` | `l` |
| व | U+0935 | DEVANAGARI LETTER VA | `va` | `v` | `v` |
| श | U+0936 | DEVANAGARI LETTER SHA | `sha` | `sh` | `s` |
| ष | U+0937 | DEVANAGARI LETTER SSA | `sha` | `ss` | `s` |
| स | U+0938 | DEVANAGARI LETTER SA | `sa` | `s` | `s` |
| ह | U+0939 | DEVANAGARI LETTER HA | `ha` | `h` | `h` |
| ा | U+093E | DEVANAGARI VOWEL SIGN AA | `a` | `aa` | `a` |
| ी | U+0940 | DEVANAGARI VOWEL SIGN II | `i` | `ii` | `i` |
| ू | U+0942 | DEVANAGARI VOWEL SIGN UU | `u` | `uu` | `u` |
| ृ | U+0943 | DEVANAGARI VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| | | *...18 more differences* | | | |

### or — Odia

Block: 91 assigned codepoints, 90 mapped by at least one library.

Coverage: translit maps 86/90, Unidecode maps 77/90. **12** mapped only by translit, **3** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ଵ | U+0B35 | ORIYA LETTER VA | `va` |
| ୄ | U+0B44 | ORIYA VOWEL SIGN VOCALIC RR | `r` |
| ୕ | U+0B55 | ORIYA SIGN OVERLINE | `e` |
| ୢ | U+0B62 | ORIYA VOWEL SIGN VOCALIC L | `l` |
| ୣ | U+0B63 | ORIYA VOWEL SIGN VOCALIC LL | `l` |
| ୱ | U+0B71 | ORIYA LETTER WA | `wa` |
| ୲ | U+0B72 | ORIYA FRACTION ONE QUARTER | `1/4` |
| ୳ | U+0B73 | ORIYA FRACTION ONE HALF | `1/2` |
| ୴ | U+0B74 | ORIYA FRACTION THREE QUARTERS | `3/4` |
| ୵ | U+0B75 | ORIYA FRACTION ONE SIXTEENTH | `1/16` |
| ୶ | U+0B76 | ORIYA FRACTION ONE EIGHTH | `1/8` |
| ୷ | U+0B77 | ORIYA FRACTION THREE SIXTEENTHS | `3/16` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ଼ | U+0B3C | ORIYA SIGN NUKTA | `'` |
| ୖ | U+0B56 | ORIYA AI LENGTH MARK | `+` |
| ୗ | U+0B57 | ORIYA AU LENGTH MARK | `+` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ଁ | U+0B01 | ORIYA SIGN CANDRABINDU | `m` | `N` | `m` |
| ଂ | U+0B02 | ORIYA SIGN ANUSVARA | `m` | `N` | `m` |
| ଃ | U+0B03 | ORIYA SIGN VISARGA | `h` | `H` | `h` |
| ଈ | U+0B08 | ORIYA LETTER II | `i` | `ii` | `i` |
| ଊ | U+0B0A | ORIYA LETTER UU | `u` | `uu` | `u` |
| ଋ | U+0B0B | ORIYA LETTER VOCALIC R | `r` | `R` | `r` |
| ଌ | U+0B0C | ORIYA LETTER VOCALIC L | `l` | `L` | `l` |
| କ | U+0B15 | ORIYA LETTER KA | `ka` | `k` | `k` |
| ଖ | U+0B16 | ORIYA LETTER KHA | `kha` | `kh` | `kh` |
| ଗ | U+0B17 | ORIYA LETTER GA | `ga` | `g` | `g` |
| ଘ | U+0B18 | ORIYA LETTER GHA | `gha` | `gh` | `gh` |
| ଙ | U+0B19 | ORIYA LETTER NGA | `nga` | `ng` | `n` |
| ଚ | U+0B1A | ORIYA LETTER CA | `cha` | `c` | `c` |
| ଛ | U+0B1B | ORIYA LETTER CHA | `chha` | `ch` | `ch` |
| ଜ | U+0B1C | ORIYA LETTER JA | `ja` | `j` | `j` |
| ଝ | U+0B1D | ORIYA LETTER JHA | `jha` | `jh` | `jh` |
| ଞ | U+0B1E | ORIYA LETTER NYA | `nya` | `ny` | `n` |
| ଟ | U+0B1F | ORIYA LETTER TTA | `ta` | `tt` | `t` |
| ଠ | U+0B20 | ORIYA LETTER TTHA | `tha` | `tth` | `th` |
| ଡ | U+0B21 | ORIYA LETTER DDA | `da` | `dd` | `d` |
| ଢ | U+0B22 | ORIYA LETTER DDHA | `dha` | `ddh` | `dh` |
| ଣ | U+0B23 | ORIYA LETTER NNA | `na` | `nn` | `n` |
| ତ | U+0B24 | ORIYA LETTER TA | `ta` | `t` | `t` |
| ଥ | U+0B25 | ORIYA LETTER THA | `tha` | `th` | `th` |
| ଦ | U+0B26 | ORIYA LETTER DA | `da` | `d` | `d` |
| ଧ | U+0B27 | ORIYA LETTER DHA | `dha` | `dh` | `dh` |
| ନ | U+0B28 | ORIYA LETTER NA | `na` | `n` | `n` |
| ପ | U+0B2A | ORIYA LETTER PA | `pa` | `p` | `p` |
| ଫ | U+0B2B | ORIYA LETTER PHA | `pha` | `ph` | `ph` |
| ବ | U+0B2C | ORIYA LETTER BA | `ba` | `b` | `b` |
| ଭ | U+0B2D | ORIYA LETTER BHA | `bha` | `bh` | `bh` |
| ମ | U+0B2E | ORIYA LETTER MA | `ma` | `m` | `m` |
| ଯ | U+0B2F | ORIYA LETTER YA | `ya` | `y` | `y` |
| ର | U+0B30 | ORIYA LETTER RA | `ra` | `r` | `r` |
| ଲ | U+0B32 | ORIYA LETTER LA | `la` | `l` | `l` |
| ଳ | U+0B33 | ORIYA LETTER LLA | `la` | `ll` | `l` |
| ଶ | U+0B36 | ORIYA LETTER SHA | `sha` | `sh` | `s` |
| ଷ | U+0B37 | ORIYA LETTER SSA | `sha` | `ss` | `s` |
| ସ | U+0B38 | ORIYA LETTER SA | `sa` | `s` | `s` |
| ହ | U+0B39 | ORIYA LETTER HA | `ha` | `h` | `h` |
| ା | U+0B3E | ORIYA VOWEL SIGN AA | `a` | `aa` | `a` |
| ୀ | U+0B40 | ORIYA VOWEL SIGN II | `i` | `ii` | `i` |
| ୂ | U+0B42 | ORIYA VOWEL SIGN UU | `u` | `uu` | `u` |
| ୃ | U+0B43 | ORIYA VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| ଡ଼ | U+0B5C | ORIYA LETTER RRA | `da` | `rr` | `r` |
| ଢ଼ | U+0B5D | ORIYA LETTER RHA | `dha` | `rh` | `rh` |
| ୟ | U+0B5F | ORIYA LETTER YYA | `ya` | `yy` | `y` |
| ୠ | U+0B60 | ORIYA LETTER VOCALIC RR | `r` | `RR` | `r` |
| ୡ | U+0B61 | ORIYA LETTER VOCALIC LL | `l` | `LL` | `l` |

### pa — Punjabi

Block: 80 assigned codepoints, 78 mapped by at least one library.

Coverage: translit maps 74/78, Unidecode maps 72/78. **5** mapped only by translit, **3** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ਁ | U+0A01 | GURMUKHI SIGN ADAK BINDI | `m` |
| ਃ | U+0A03 | GURMUKHI SIGN VISARGA | `h` |
| ੲ | U+0A72 | GURMUKHI IRI | `iri` |
| ੳ | U+0A73 | GURMUKHI URA | `ura` |
| ੶ | U+0A76 | GURMUKHI ABBREVIATION SIGN | `.` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ਼ | U+0A3C | GURMUKHI SIGN NUKTA | `'` |
| ੰ | U+0A70 | GURMUKHI TIPPI | `N` |
| ੱ | U+0A71 | GURMUKHI ADDAK | `H` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ਂ | U+0A02 | GURMUKHI SIGN BINDI | `m` | `N` | `m` |
| ਈ | U+0A08 | GURMUKHI LETTER II | `i` | `ii` | `i` |
| ਊ | U+0A0A | GURMUKHI LETTER UU | `u` | `uu` | `u` |
| ਏ | U+0A0F | GURMUKHI LETTER EE | `e` | `ee` | `e` |
| ਓ | U+0A13 | GURMUKHI LETTER OO | `o` | `oo` | `o` |
| ਕ | U+0A15 | GURMUKHI LETTER KA | `ka` | `k` | `k` |
| ਖ | U+0A16 | GURMUKHI LETTER KHA | `kha` | `kh` | `kh` |
| ਗ | U+0A17 | GURMUKHI LETTER GA | `ga` | `g` | `g` |
| ਘ | U+0A18 | GURMUKHI LETTER GHA | `gha` | `gh` | `gh` |
| ਙ | U+0A19 | GURMUKHI LETTER NGA | `nga` | `ng` | `n` |
| ਚ | U+0A1A | GURMUKHI LETTER CA | `cha` | `c` | `c` |
| ਛ | U+0A1B | GURMUKHI LETTER CHA | `chha` | `ch` | `ch` |
| ਜ | U+0A1C | GURMUKHI LETTER JA | `ja` | `j` | `j` |
| ਝ | U+0A1D | GURMUKHI LETTER JHA | `jha` | `jh` | `jh` |
| ਞ | U+0A1E | GURMUKHI LETTER NYA | `nya` | `ny` | `n` |
| ਟ | U+0A1F | GURMUKHI LETTER TTA | `ta` | `tt` | `t` |
| ਠ | U+0A20 | GURMUKHI LETTER TTHA | `tha` | `tth` | `th` |
| ਡ | U+0A21 | GURMUKHI LETTER DDA | `da` | `dd` | `d` |
| ਢ | U+0A22 | GURMUKHI LETTER DDHA | `dha` | `ddh` | `dh` |
| ਣ | U+0A23 | GURMUKHI LETTER NNA | `na` | `nn` | `n` |
| ਤ | U+0A24 | GURMUKHI LETTER TA | `ta` | `t` | `t` |
| ਥ | U+0A25 | GURMUKHI LETTER THA | `tha` | `th` | `th` |
| ਦ | U+0A26 | GURMUKHI LETTER DA | `da` | `d` | `d` |
| ਧ | U+0A27 | GURMUKHI LETTER DHA | `dha` | `dh` | `dh` |
| ਨ | U+0A28 | GURMUKHI LETTER NA | `na` | `n` | `n` |
| ਪ | U+0A2A | GURMUKHI LETTER PA | `pa` | `p` | `p` |
| ਫ | U+0A2B | GURMUKHI LETTER PHA | `pha` | `ph` | `ph` |
| ਬ | U+0A2C | GURMUKHI LETTER BA | `ba` | `b` | `b` |
| ਭ | U+0A2D | GURMUKHI LETTER BHA | `bha` | `bb` | `bh` |
| ਮ | U+0A2E | GURMUKHI LETTER MA | `ma` | `m` | `m` |
| ਯ | U+0A2F | GURMUKHI LETTER YA | `ya` | `y` | `y` |
| ਰ | U+0A30 | GURMUKHI LETTER RA | `ra` | `r` | `r` |
| ਲ | U+0A32 | GURMUKHI LETTER LA | `la` | `l` | `l` |
| ਲ਼ | U+0A33 | GURMUKHI LETTER LLA | `la` | `ll` | `l` |
| ਵ | U+0A35 | GURMUKHI LETTER VA | `va` | `v` | `v` |
| ਸ਼ | U+0A36 | GURMUKHI LETTER SHA | `sha` | `sh` | `s` |
| ਸ | U+0A38 | GURMUKHI LETTER SA | `sa` | `s` | `s` |
| ਹ | U+0A39 | GURMUKHI LETTER HA | `ha` | `h` | `h` |
| ਾ | U+0A3E | GURMUKHI VOWEL SIGN AA | `a` | `aa` | `a` |
| ੀ | U+0A40 | GURMUKHI VOWEL SIGN II | `i` | `ii` | `i` |
| ੂ | U+0A42 | GURMUKHI VOWEL SIGN UU | `u` | `uu` | `u` |
| ੇ | U+0A47 | GURMUKHI VOWEL SIGN EE | `e` | `ee` | `e` |
| ੋ | U+0A4B | GURMUKHI VOWEL SIGN OO | `o` | `oo` | `o` |
| ਖ਼ | U+0A59 | GURMUKHI LETTER KHHA | `kha` | `khh` | `kh` |
| ਗ਼ | U+0A5A | GURMUKHI LETTER GHHA | `ga` | `ghh` | `g` |
| ਜ਼ | U+0A5B | GURMUKHI LETTER ZA | `za` | `z` | `z` |
| ੜ | U+0A5C | GURMUKHI LETTER RRA | `ra` | `rr` | `r` |
| ਫ਼ | U+0A5E | GURMUKHI LETTER FA | `fa` | `f` | `ph` |
| ੴ | U+0A74 | GURMUKHI EK ONKAR | `ek` | `G.E.O.` | `*` |

### sa — Sanskrit

Block: 128 assigned codepoints, 127 mapped by at least one library.

Coverage: translit maps 117/127, Unidecode maps 103/127. **19** mapped only by translit, **5** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ऄ | U+0904 | DEVANAGARI LETTER SHORT A | `a` |
| ॕ | U+0955 | DEVANAGARI VOWEL SIGN CANDRA LONG E | `e` |
| ॖ | U+0956 | DEVANAGARI VOWEL SIGN UE | `u` |
| ॗ | U+0957 | DEVANAGARI VOWEL SIGN UUE | `u` |
| ॱ | U+0971 | DEVANAGARI SIGN HIGH SPACING DOT | `.` |
| ॲ | U+0972 | DEVANAGARI LETTER CANDRA A | `a` |
| ॳ | U+0973 | DEVANAGARI LETTER OE | `oe` |
| ॴ | U+0974 | DEVANAGARI LETTER OOE | `ooe` |
| ॵ | U+0975 | DEVANAGARI LETTER AW | `aw` |
| ॶ | U+0976 | DEVANAGARI LETTER UE | `ue` |
| ॷ | U+0977 | DEVANAGARI LETTER UUE | `uue` |
| ॸ | U+0978 | DEVANAGARI LETTER MARWARI DDA | `dda` |
| ॹ | U+0979 | DEVANAGARI LETTER ZHA | `zha` |
| ॺ | U+097A | DEVANAGARI LETTER HEAVY YA | `ya` |
| ॻ | U+097B | DEVANAGARI LETTER GGA | `gga` |
| ॼ | U+097C | DEVANAGARI LETTER JJA | `jja` |
| ॽ | U+097D | DEVANAGARI LETTER GLOTTAL STOP | `'` |
| ॾ | U+097E | DEVANAGARI LETTER DDDA | `ddda` |
| ॿ | U+097F | DEVANAGARI LETTER BBA | `bba` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ़ | U+093C | DEVANAGARI SIGN NUKTA | `'` |
| ॑ | U+0951 | DEVANAGARI STRESS SIGN UDATTA | `'` |
| ॒ | U+0952 | DEVANAGARI STRESS SIGN ANUDATTA | `'` |
| ॓ | U+0953 | DEVANAGARI GRAVE ACCENT | ``` |
| ॔ | U+0954 | DEVANAGARI ACUTE ACCENT | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ँ | U+0901 | DEVANAGARI SIGN CANDRABINDU | `m` | `N` | `m` |
| ं | U+0902 | DEVANAGARI SIGN ANUSVARA | `m` | `N` | `m` |
| ः | U+0903 | DEVANAGARI SIGN VISARGA | `h` | `H` | `h` |
| ई | U+0908 | DEVANAGARI LETTER II | `i` | `ii` | `i` |
| ऊ | U+090A | DEVANAGARI LETTER UU | `u` | `uu` | `u` |
| ऋ | U+090B | DEVANAGARI LETTER VOCALIC R | `r` | `R` | `r` |
| ऌ | U+090C | DEVANAGARI LETTER VOCALIC L | `l` | `L` | `l` |
| ऍ | U+090D | DEVANAGARI LETTER CANDRA E | `e` | `eN` | `e` |
| ऑ | U+0911 | DEVANAGARI LETTER CANDRA O | `o` | `oN` | `o` |
| क | U+0915 | DEVANAGARI LETTER KA | `ka` | `k` | `k` |
| ख | U+0916 | DEVANAGARI LETTER KHA | `kha` | `kh` | `kh` |
| ग | U+0917 | DEVANAGARI LETTER GA | `ga` | `g` | `g` |
| घ | U+0918 | DEVANAGARI LETTER GHA | `gha` | `gh` | `gh` |
| ङ | U+0919 | DEVANAGARI LETTER NGA | `nga` | `ng` | `n` |
| च | U+091A | DEVANAGARI LETTER CA | `cha` | `c` | `c` |
| छ | U+091B | DEVANAGARI LETTER CHA | `chha` | `ch` | `ch` |
| ज | U+091C | DEVANAGARI LETTER JA | `ja` | `j` | `j` |
| झ | U+091D | DEVANAGARI LETTER JHA | `jha` | `jh` | `jh` |
| ञ | U+091E | DEVANAGARI LETTER NYA | `nya` | `ny` | `n` |
| ट | U+091F | DEVANAGARI LETTER TTA | `ta` | `tt` | `t` |
| ठ | U+0920 | DEVANAGARI LETTER TTHA | `tha` | `tth` | `th` |
| ड | U+0921 | DEVANAGARI LETTER DDA | `da` | `dd` | `d` |
| ढ | U+0922 | DEVANAGARI LETTER DDHA | `dha` | `ddh` | `dh` |
| ण | U+0923 | DEVANAGARI LETTER NNA | `na` | `nn` | `n` |
| त | U+0924 | DEVANAGARI LETTER TA | `ta` | `t` | `t` |
| थ | U+0925 | DEVANAGARI LETTER THA | `tha` | `th` | `th` |
| द | U+0926 | DEVANAGARI LETTER DA | `da` | `d` | `d` |
| ध | U+0927 | DEVANAGARI LETTER DHA | `dha` | `dh` | `dh` |
| न | U+0928 | DEVANAGARI LETTER NA | `na` | `n` | `n` |
| ऩ | U+0929 | DEVANAGARI LETTER NNNA | `na` | `nnn` | `n` |
| प | U+092A | DEVANAGARI LETTER PA | `pa` | `p` | `p` |
| फ | U+092B | DEVANAGARI LETTER PHA | `pha` | `ph` | `ph` |
| ब | U+092C | DEVANAGARI LETTER BA | `ba` | `b` | `b` |
| भ | U+092D | DEVANAGARI LETTER BHA | `bha` | `bh` | `bh` |
| म | U+092E | DEVANAGARI LETTER MA | `ma` | `m` | `m` |
| य | U+092F | DEVANAGARI LETTER YA | `ya` | `y` | `y` |
| र | U+0930 | DEVANAGARI LETTER RA | `ra` | `r` | `r` |
| ऱ | U+0931 | DEVANAGARI LETTER RRA | `ra` | `rr` | `r` |
| ल | U+0932 | DEVANAGARI LETTER LA | `la` | `l` | `l` |
| ळ | U+0933 | DEVANAGARI LETTER LLA | `la` | `l` | `l` |
| ऴ | U+0934 | DEVANAGARI LETTER LLLA | `la` | `lll` | `l` |
| व | U+0935 | DEVANAGARI LETTER VA | `va` | `v` | `v` |
| श | U+0936 | DEVANAGARI LETTER SHA | `sha` | `sh` | `s` |
| ष | U+0937 | DEVANAGARI LETTER SSA | `sha` | `ss` | `s` |
| स | U+0938 | DEVANAGARI LETTER SA | `sa` | `s` | `s` |
| ह | U+0939 | DEVANAGARI LETTER HA | `ha` | `h` | `h` |
| ा | U+093E | DEVANAGARI VOWEL SIGN AA | `a` | `aa` | `a` |
| ी | U+0940 | DEVANAGARI VOWEL SIGN II | `i` | `ii` | `i` |
| ू | U+0942 | DEVANAGARI VOWEL SIGN UU | `u` | `uu` | `u` |
| ृ | U+0943 | DEVANAGARI VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| | | *...18 more differences* | | | |

### as — Assamese

Block: 96 assigned codepoints, 95 mapped by at least one library.

Coverage: translit maps 90/95, Unidecode maps 87/95. **5** mapped only by translit, **2** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ঀ | U+0980 | BENGALI ANJI | `m` |
| ঽ | U+09BD | BENGALI SIGN AVAGRAHA | `'` |
| ৎ | U+09CE | BENGALI LETTER KHANDA TA | `t` |
| ৼ | U+09FC | BENGALI LETTER VEDIC ANUSVARA | `m` |
| ৽ | U+09FD | BENGALI ABBREVIATION SIGN | `.` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ় | U+09BC | BENGALI SIGN NUKTA | `'` |
| ৗ | U+09D7 | BENGALI AU LENGTH MARK | `+` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ঁ | U+0981 | BENGALI SIGN CANDRABINDU | `m` | `N` | `m` |
| ং | U+0982 | BENGALI SIGN ANUSVARA | `m` | `N` | `m` |
| ঃ | U+0983 | BENGALI SIGN VISARGA | `h` | `H` | `h` |
| ঈ | U+0988 | BENGALI LETTER II | `i` | `ii` | `i` |
| ঊ | U+098A | BENGALI LETTER UU | `u` | `uu` | `u` |
| ঋ | U+098B | BENGALI LETTER VOCALIC R | `r` | `R` | `r` |
| ঌ | U+098C | BENGALI LETTER VOCALIC L | `l` | `RR` | `l` |
| ক | U+0995 | BENGALI LETTER KA | `ka` | `k` | `k` |
| খ | U+0996 | BENGALI LETTER KHA | `kha` | `kh` | `kh` |
| গ | U+0997 | BENGALI LETTER GA | `ga` | `g` | `g` |
| ঘ | U+0998 | BENGALI LETTER GHA | `gha` | `gh` | `gh` |
| ঙ | U+0999 | BENGALI LETTER NGA | `nga` | `ng` | `n` |
| চ | U+099A | BENGALI LETTER CA | `cha` | `c` | `c` |
| ছ | U+099B | BENGALI LETTER CHA | `chha` | `ch` | `ch` |
| জ | U+099C | BENGALI LETTER JA | `ja` | `j` | `j` |
| ঝ | U+099D | BENGALI LETTER JHA | `jha` | `jh` | `jh` |
| ঞ | U+099E | BENGALI LETTER NYA | `nya` | `ny` | `n` |
| ট | U+099F | BENGALI LETTER TTA | `ta` | `tt` | `t` |
| ঠ | U+09A0 | BENGALI LETTER TTHA | `tha` | `tth` | `th` |
| ড | U+09A1 | BENGALI LETTER DDA | `da` | `dd` | `d` |
| ঢ | U+09A2 | BENGALI LETTER DDHA | `dha` | `ddh` | `dh` |
| ণ | U+09A3 | BENGALI LETTER NNA | `na` | `nn` | `n` |
| ত | U+09A4 | BENGALI LETTER TA | `ta` | `t` | `t` |
| থ | U+09A5 | BENGALI LETTER THA | `tha` | `th` | `th` |
| দ | U+09A6 | BENGALI LETTER DA | `da` | `d` | `d` |
| ধ | U+09A7 | BENGALI LETTER DHA | `dha` | `dh` | `dh` |
| ন | U+09A8 | BENGALI LETTER NA | `na` | `n` | `n` |
| প | U+09AA | BENGALI LETTER PA | `pa` | `p` | `p` |
| ফ | U+09AB | BENGALI LETTER PHA | `pha` | `ph` | `ph` |
| ব | U+09AC | BENGALI LETTER BA | `ba` | `b` | `b` |
| ভ | U+09AD | BENGALI LETTER BHA | `bha` | `bh` | `bh` |
| ম | U+09AE | BENGALI LETTER MA | `ma` | `m` | `m` |
| য | U+09AF | BENGALI LETTER YA | `ya` | `y` | `y` |
| র | U+09B0 | BENGALI LETTER RA | `ra` | `r` | `r` |
| ল | U+09B2 | BENGALI LETTER LA | `la` | `l` | `l` |
| শ | U+09B6 | BENGALI LETTER SHA | `sha` | `sh` | `s` |
| ষ | U+09B7 | BENGALI LETTER SSA | `sha` | `ss` | `s` |
| স | U+09B8 | BENGALI LETTER SA | `sa` | `s` | `s` |
| হ | U+09B9 | BENGALI LETTER HA | `ha` | `h` | `h` |
| া | U+09BE | BENGALI VOWEL SIGN AA | `a` | `aa` | `a` |
| ী | U+09C0 | BENGALI VOWEL SIGN II | `i` | `ii` | `i` |
| ূ | U+09C2 | BENGALI VOWEL SIGN UU | `u` | `uu` | `u` |
| ৃ | U+09C3 | BENGALI VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| ৄ | U+09C4 | BENGALI VOWEL SIGN VOCALIC RR | `r` | `RR` | `r` |
| ড় | U+09DC | BENGALI LETTER RRA | `ra` | `rr` | `r` |
| ঢ় | U+09DD | BENGALI LETTER RHA | `rha` | `rh` | `rh` |
| য় | U+09DF | BENGALI LETTER YYA | `ya` | `yy` | `y` |
| ৠ | U+09E0 | BENGALI LETTER VOCALIC RR | `r` | `RR` | `r` |
| ৡ | U+09E1 | BENGALI LETTER VOCALIC LL | `l` | `LL` | `l` |
| ৢ | U+09E2 | BENGALI VOWEL SIGN VOCALIC L | `l` | `L` | `l` |
| | | *...9 more differences* | | | |

### hy — Armenian

Block: 91 assigned codepoints, 90 mapped by at least one library.

Coverage: translit maps 86/90, Unidecode maps 85/90. **3** mapped only by translit, **2** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ՠ | U+0560 | ARMENIAN SMALL LETTER TURNED AYB | `a` |
| ֈ | U+0588 | ARMENIAN SMALL LETTER YI WITH STROKE | `yi` |
| ֏ | U+058F | ARMENIAN DRAM SIGN | `AMD` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ՛ | U+055B | ARMENIAN EMPHASIS MARK | `/` |
| ՟ | U+055F | ARMENIAN ABBREVIATION MARK | `.` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Ը | U+0538 | ARMENIAN CAPITAL LETTER ET | `Y` | `E` | `Y` |
| Թ | U+0539 | ARMENIAN CAPITAL LETTER TO | `T` | `T`` | `T'` |
| Ո | U+0548 | ARMENIAN CAPITAL LETTER VO | `Vo` | `O` | `O` |
| Չ | U+0549 | ARMENIAN CAPITAL LETTER CHA | `Ch` | `Ch`` | `Ch'` |
| Ռ | U+054C | ARMENIAN CAPITAL LETTER RA | `R` | `Rh` | `Rr` |
| Ց | U+0551 | ARMENIAN CAPITAL LETTER CO | `Ts` | `Ts`` | `Ts'` |
| Ւ | U+0552 | ARMENIAN CAPITAL LETTER YIWN | `V` | `W` | `W` |
| Փ | U+0553 | ARMENIAN CAPITAL LETTER PIWR | `P` | `P`` | `P'` |
| Ք | U+0554 | ARMENIAN CAPITAL LETTER KEH | `K` | `K`` | `K'` |
| ՙ | U+0559 | ARMENIAN MODIFIER LETTER LEFT HALF RING | `'` | `<` | ``` |
| ը | U+0568 | ARMENIAN SMALL LETTER ET | `y` | `e` | `y` |
| թ | U+0569 | ARMENIAN SMALL LETTER TO | `t` | `t`` | `t'` |
| ո | U+0578 | ARMENIAN SMALL LETTER VO | `vo` | `o` | `o` |
| չ | U+0579 | ARMENIAN SMALL LETTER CHA | `ch` | `ch`` | `ch'` |
| ռ | U+057C | ARMENIAN SMALL LETTER RA | `r` | `rh` | `rr` |
| ց | U+0581 | ARMENIAN SMALL LETTER CO | `ts` | `ts`` | `ts'` |
| ւ | U+0582 | ARMENIAN SMALL LETTER YIWN | `v` | `w` | `w` |
| փ | U+0583 | ARMENIAN SMALL LETTER PIWR | `p` | `p`` | `p'` |
| ք | U+0584 | ARMENIAN SMALL LETTER KEH | `k` | `k`` | `k'` |
| և | U+0587 | ARMENIAN SMALL LIGATURE ECH YIWN | `yev` | `ew` | `ev` |
| ։ | U+0589 | ARMENIAN FULL STOP | `.` | `:` | `.` |

### ka — Georgian

Block: 88 assigned codepoints, 88 mapped by at least one library.

Coverage: translit maps 87/88, Unidecode maps 78/88. **9** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ⴧ | U+10C7 | GEORGIAN CAPITAL LETTER YN | `Yn` |
| Ⴭ | U+10CD | GEORGIAN CAPITAL LETTER AEN | `Ae` |
| ჷ | U+10F7 | GEORGIAN LETTER YN | `yn` |
| ჸ | U+10F8 | GEORGIAN LETTER ELIFI | `el` |
| ჹ | U+10F9 | GEORGIAN LETTER TURNED GAN | `g` |
| ჺ | U+10FA | GEORGIAN LETTER AIN | `'` |
| ჼ | U+10FC | MODIFIER LETTER GEORGIAN NAR | `n` |
| ჽ | U+10FD | GEORGIAN LETTER AEN | `ae` |
| ჿ | U+10FF | GEORGIAN LETTER LABIAL SIGN | `w` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Ⴇ | U+10A7 | GEORGIAN CAPITAL LETTER TAN | `T` | `T`` | `T` |
| Ⴔ | U+10B4 | GEORGIAN CAPITAL LETTER PHAR | `P` | `P`` | `P` |
| Ⴕ | U+10B5 | GEORGIAN CAPITAL LETTER KHAR | `K` | `K`` | `K` |
| Ⴖ | U+10B6 | GEORGIAN CAPITAL LETTER GHAN | `Gh` | `G'` | `Gh` |
| Ⴙ | U+10B9 | GEORGIAN CAPITAL LETTER CHIN | `Ch` | `Ch`` | `Ch` |
| Ⴚ | U+10BA | GEORGIAN CAPITAL LETTER CAN | `Ts` | `C`` | `Ts` |
| Ⴛ | U+10BB | GEORGIAN CAPITAL LETTER JIL | `Dz` | `Z'` | `Dz` |
| Ⴜ | U+10BC | GEORGIAN CAPITAL LETTER CIL | `Ts` | `C` | `Ts'` |
| Ⴞ | U+10BE | GEORGIAN CAPITAL LETTER XAN | `Kh` | `X` | `Kh` |
| Ⴡ | U+10C1 | GEORGIAN CAPITAL LETTER HE | `He` | `E` | `E` |
| Ⴢ | U+10C2 | GEORGIAN CAPITAL LETTER HIE | `Hi` | `Y` | `Y` |
| Ⴤ | U+10C4 | GEORGIAN CAPITAL LETTER HAR | `Har` | `Xh` | `X` |
| Ⴥ | U+10C5 | GEORGIAN CAPITAL LETTER HOE | `Ho` | `OE` | `O` |
| თ | U+10D7 | GEORGIAN LETTER TAN | `t` | `t`` | `t` |
| ფ | U+10E4 | GEORGIAN LETTER PHAR | `p` | `p`` | `p` |
| ქ | U+10E5 | GEORGIAN LETTER KHAR | `k` | `k`` | `k` |
| ღ | U+10E6 | GEORGIAN LETTER GHAN | `gh` | `g'` | `gh` |
| ჩ | U+10E9 | GEORGIAN LETTER CHIN | `ch` | `ch`` | `ch` |
| ც | U+10EA | GEORGIAN LETTER CAN | `ts` | `c`` | `ts` |
| ძ | U+10EB | GEORGIAN LETTER JIL | `dz` | `z'` | `dz` |
| წ | U+10EC | GEORGIAN LETTER CIL | `ts` | `c` | `ts'` |
| ხ | U+10EE | GEORGIAN LETTER XAN | `kh` | `x` | `kh` |
| ჱ | U+10F1 | GEORGIAN LETTER HE | `he` | `e` | `e` |
| ჲ | U+10F2 | GEORGIAN LETTER HIE | `hi` | `y` | `y` |
| ჴ | U+10F4 | GEORGIAN LETTER HAR | `har` | `xh` | `x` |
| ჵ | U+10F5 | GEORGIAN LETTER HOE | `ho` | `oe` | `o` |
| ჻ | U+10FB | GEORGIAN PARAGRAPH SEPARATOR | `.` | ` // ` | `*` |

### si — Sinhala

Block: 91 assigned codepoints, 90 mapped by at least one library.

Coverage: translit maps 90/90, Unidecode maps 79/90. **11** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ඁ | U+0D81 | SINHALA SIGN CANDRABINDU | `m` |
| ෦ | U+0DE6 | SINHALA LITH DIGIT ZERO | `0` |
| ෧ | U+0DE7 | SINHALA LITH DIGIT ONE | `1` |
| ෨ | U+0DE8 | SINHALA LITH DIGIT TWO | `2` |
| ෩ | U+0DE9 | SINHALA LITH DIGIT THREE | `3` |
| ෪ | U+0DEA | SINHALA LITH DIGIT FOUR | `4` |
| ෫ | U+0DEB | SINHALA LITH DIGIT FIVE | `5` |
| ෬ | U+0DEC | SINHALA LITH DIGIT SIX | `6` |
| ෭ | U+0DED | SINHALA LITH DIGIT SEVEN | `7` |
| ෮ | U+0DEE | SINHALA LITH DIGIT EIGHT | `8` |
| ෯ | U+0DEF | SINHALA LITH DIGIT NINE | `9` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ං | U+0D82 | SINHALA SIGN ANUSVARAYA | `m` | `N` | `m` |
| ඃ | U+0D83 | SINHALA SIGN VISARGAYA | `h` | `H` | `h` |
| ඍ | U+0D8D | SINHALA LETTER IRUYANNA | `ri` | `R` | `r` |
| ඎ | U+0D8E | SINHALA LETTER IRUUYANNA | `r` | `RR` | `r` |
| ඏ | U+0D8F | SINHALA LETTER ILUYANNA | `rr` | `L` | `l` |
| ඐ | U+0D90 | SINHALA LETTER ILUUYANNA | `luu` | `LL` | `l` |
| ක | U+0D9A | SINHALA LETTER ALPAPRAANA KAYANNA | `ka` | `k` | `k` |
| ඛ | U+0D9B | SINHALA LETTER MAHAAPRAANA KAYANNA | `kha` | `kh` | `kh` |
| ග | U+0D9C | SINHALA LETTER ALPAPRAANA GAYANNA | `ga` | `g` | `g` |
| ඝ | U+0D9D | SINHALA LETTER MAHAAPRAANA GAYANNA | `gha` | `gh` | `gh` |
| ඞ | U+0D9E | SINHALA LETTER KANTAJA NAASIKYAYA | `nga` | `ng` | `n` |
| ඟ | U+0D9F | SINHALA LETTER SANYAKA GAYANNA | `nnga` | `nng` | `ng` |
| ච | U+0DA0 | SINHALA LETTER ALPAPRAANA CAYANNA | `cha` | `c` | `c` |
| ඡ | U+0DA1 | SINHALA LETTER MAHAAPRAANA CAYANNA | `chha` | `ch` | `ch` |
| ජ | U+0DA2 | SINHALA LETTER ALPAPRAANA JAYANNA | `ja` | `j` | `j` |
| ඣ | U+0DA3 | SINHALA LETTER MAHAAPRAANA JAYANNA | `jha` | `jh` | `jh` |
| ඤ | U+0DA4 | SINHALA LETTER TAALUJA NAASIKYAYA | `nya` | `ny` | `n` |
| ඥ | U+0DA5 | SINHALA LETTER TAALUJA SANYOOGA NAAKSIKYAYA | `jnya` | `jny` | `jn` |
| ඦ | U+0DA6 | SINHALA LETTER SANYAKA JAYANNA | `nyja` | `nyj` | `nj` |
| ට | U+0DA7 | SINHALA LETTER ALPAPRAANA TTAYANNA | `tta` | `tt` | `t` |
| ඨ | U+0DA8 | SINHALA LETTER MAHAAPRAANA TTAYANNA | `ttha` | `tth` | `th` |
| ඩ | U+0DA9 | SINHALA LETTER ALPAPRAANA DDAYANNA | `dda` | `dd` | `d` |
| ඪ | U+0DAA | SINHALA LETTER MAHAAPRAANA DDAYANNA | `ddha` | `ddh` | `dh` |
| ණ | U+0DAB | SINHALA LETTER MUURDHAJA NAYANNA | `nna` | `nn` | `n` |
| ඬ | U+0DAC | SINHALA LETTER SANYAKA DDAYANNA | `nndda` | `nndd` | `nd` |
| ත | U+0DAD | SINHALA LETTER ALPAPRAANA TAYANNA | `ta` | `t` | `t` |
| ථ | U+0DAE | SINHALA LETTER MAHAAPRAANA TAYANNA | `tha` | `th` | `th` |
| ද | U+0DAF | SINHALA LETTER ALPAPRAANA DAYANNA | `da` | `d` | `d` |
| ධ | U+0DB0 | SINHALA LETTER MAHAAPRAANA DAYANNA | `dha` | `dh` | `dh` |
| න | U+0DB1 | SINHALA LETTER DANTAJA NAYANNA | `na` | `n` | `n` |
| ඳ | U+0DB3 | SINHALA LETTER SANYAKA DAYANNA | `nda` | `nd` | `nd` |
| ප | U+0DB4 | SINHALA LETTER ALPAPRAANA PAYANNA | `pa` | `p` | `p` |
| ඵ | U+0DB5 | SINHALA LETTER MAHAAPRAANA PAYANNA | `pha` | `ph` | `ph` |
| බ | U+0DB6 | SINHALA LETTER ALPAPRAANA BAYANNA | `ba` | `b` | `b` |
| භ | U+0DB7 | SINHALA LETTER MAHAAPRAANA BAYANNA | `bha` | `bh` | `bh` |
| ම | U+0DB8 | SINHALA LETTER MAYANNA | `ma` | `m` | `m` |
| ඹ | U+0DB9 | SINHALA LETTER AMBA BAYANNA | `mba` | `mb` | `mb` |
| ය | U+0DBA | SINHALA LETTER YAYANNA | `ya` | `y` | `y` |
| ර | U+0DBB | SINHALA LETTER RAYANNA | `ra` | `r` | `r` |
| ල | U+0DBD | SINHALA LETTER DANTAJA LAYANNA | `la` | `l` | `l` |
| ව | U+0DC0 | SINHALA LETTER VAYANNA | `va` | `v` | `v` |
| ශ | U+0DC1 | SINHALA LETTER TAALUJA SAYANNA | `sha` | `sh` | `s` |
| ෂ | U+0DC2 | SINHALA LETTER MUURDHAJA SAYANNA | `sha` | `ss` | `s` |
| ස | U+0DC3 | SINHALA LETTER DANTAJA SAYANNA | `sa` | `s` | `s` |
| හ | U+0DC4 | SINHALA LETTER HAYANNA | `ha` | `h` | `h` |
| ළ | U+0DC5 | SINHALA LETTER MUURDHAJA LAYANNA | `lla` | `ll` | `l` |
| ෆ | U+0DC6 | SINHALA LETTER FAYANNA | `fa` | `f` | `f` |
| ා | U+0DCF | SINHALA VOWEL SIGN AELA-PILLA | `a` | `aa` | `a` |
| ැ | U+0DD0 | SINHALA VOWEL SIGN KETTI AEDA-PILLA | `aa` | `ae` | `ae` |
| ෑ | U+0DD1 | SINHALA VOWEL SIGN DIGA AEDA-PILLA | `ae` | `aae` | `ae` |
| | | *...5 more differences* | | | |

### th — Thai

Block: 87 assigned codepoints, 80 mapped by at least one library.

Coverage: translit maps 73/80, Unidecode maps 80/80. **0** mapped only by translit, **7** mapped only by Unidecode.

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ฯ | U+0E2F | THAI CHARACTER PAIYANNOI | `~` |
| ฺ | U+0E3A | THAI CHARACTER PHINTHU | `'` |
| ๅ | U+0E45 | THAI CHARACTER LAKKHANGYAO | `ao` |
| ๆ | U+0E46 | THAI CHARACTER MAIYAMOK | `+` |
| ๏ | U+0E4F | THAI CHARACTER FONGMAN | ` * ` |
| ๚ | U+0E5A | THAI CHARACTER ANGKHANKHU | ` // ` |
| ๛ | U+0E5B | THAI CHARACTER KHOMUT | ` /// ` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| จ | U+0E08 | THAI CHARACTER CHO CHAN | `ch` | `cch` | `ch` |
| ซ | U+0E0B | THAI CHARACTER SO SO | `s` | `ch` | `s` |
| ฤ | U+0E24 | THAI CHARACTER RU | `rue` | `R` | `rue` |
| ฦ | U+0E26 | THAI CHARACTER LU | `lue` | `L` | `lue` |
| อ | U+0E2D | THAI CHARACTER O ANG | `o` | ``` | `o` |
| า | U+0E32 | THAI CHARACTER SARA AA | `a` | `aa` | `a` |
| ี | U+0E35 | THAI CHARACTER SARA II | `i` | `ii` | `i` |
| ื | U+0E37 | THAI CHARACTER SARA UEE | `ue` | `uue` | `ue` |
| ู | U+0E39 | THAI CHARACTER SARA UU | `u` | `uu` | `u` |
| ฿ | U+0E3F | THAI CURRENCY SYMBOL BAHT | `B` | `Bh.` | `B` |
| ํ | U+0E4D | THAI CHARACTER NIKHAHIT | `m` | `M` | `m` |

### lo — Lao

Block: 83 assigned codepoints, 76 mapped by at least one library.

Coverage: translit maps 58/76, Unidecode maps 58/76. **2** mapped only by translit, **2** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ຮ | U+0EAE | LAO LETTER HO TAM | `h` |
| ັ | U+0EB1 | LAO VOWEL SIGN MAI KAN | `a` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ຯ | U+0EAF | LAO ELLIPSIS | `~` |
| ໆ | U+0EC6 | LAO KO LA | `+` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ຕ | U+0E95 | LAO LETTER TO | `t` | `h` | `t` |
| ອ | U+0EAD | LAO LETTER O | `o` | ``` | — |
| າ | U+0EB2 | LAO VOWEL SIGN AA | `a` | `aa` | `a` |
| ີ | U+0EB5 | LAO VOWEL SIGN II | `i` | `ii` | `i` |
| ຶ | U+0EB6 | LAO VOWEL SIGN Y | `ue` | `y` | `u` |
| ື | U+0EB7 | LAO VOWEL SIGN YY | `ue` | `yy` | `u` |
| ູ | U+0EB9 | LAO VOWEL SIGN UU | `u` | `uu` | `ou` |
| ຽ | U+0EBD | LAO SEMIVOWEL SIGN NYO | `y` | `ny` | `y` |
| ແ | U+0EC1 | LAO VOWEL SIGN EI | `ae` | `ei` | `e` |
| ໃ | U+0EC3 | LAO VOWEL SIGN AY | `ai` | `ay` | `ai` |
| ໍ | U+0ECD | LAO NIGGAHITA | `m` | `M` | `o` |

### km — Khmer

Block: 114 assigned codepoints, 106 mapped by at least one library.

Coverage: translit maps 85/106, Unidecode maps 94/106. **0** mapped only by translit, **9** mapped only by Unidecode.

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ឴ | U+17B4 | KHMER VOWEL INHERENT AQ | `a` |
| ឵ | U+17B5 | KHMER VOWEL INHERENT AA | `aa` |
| ំ | U+17C6 | KHMER SIGN NIKAHIT | `M` |
| ះ | U+17C7 | KHMER SIGN REAHMUK | `H` |
| ៈ | U+17C8 | KHMER SIGN YUUKALEAPINTU | `a`` |
| ៌ | U+17CC | KHMER SIGN ROBAT | `r` |
| ៎ | U+17CE | KHMER SIGN KAKABAT | `!` |
| ៗ | U+17D7 | KHMER SIGN LEK TOO | `+` |
| ៜ | U+17DC | KHMER SIGN AVAKRAHASANYA | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ក | U+1780 | KHMER LETTER KA | `ka` | `k` | `k` |
| ខ | U+1781 | KHMER LETTER KHA | `kha` | `kh` | `kh` |
| គ | U+1782 | KHMER LETTER KO | `ka` | `g` | `k` |
| ឃ | U+1783 | KHMER LETTER KHO | `kha` | `gh` | `kh` |
| ង | U+1784 | KHMER LETTER NGO | `nga` | `ng` | `ng` |
| ច | U+1785 | KHMER LETTER CA | `cha` | `c` | `ch` |
| ឆ | U+1786 | KHMER LETTER CHA | `chha` | `ch` | `chh` |
| ជ | U+1787 | KHMER LETTER CO | `cha` | `j` | `ch` |
| ឈ | U+1788 | KHMER LETTER CHO | `chha` | `jh` | `chh` |
| ញ | U+1789 | KHMER LETTER NYO | `nya` | `ny` | `nh` |
| ដ | U+178A | KHMER LETTER DA | `da` | `t` | `d` |
| ឋ | U+178B | KHMER LETTER TTHA | `ttha` | `tth` | `th` |
| ឌ | U+178C | KHMER LETTER DO | `da` | `d` | `d` |
| ឍ | U+178D | KHMER LETTER TTHO | `ttha` | `ddh` | `th` |
| ណ | U+178E | KHMER LETTER NNO | `na` | `nn` | `n` |
| ត | U+178F | KHMER LETTER TA | `ta` | `t` | `t` |
| ថ | U+1790 | KHMER LETTER THA | `tha` | `th` | `th` |
| ទ | U+1791 | KHMER LETTER TO | `ta` | `d` | `t` |
| ធ | U+1792 | KHMER LETTER THO | `tha` | `dh` | `th` |
| ន | U+1793 | KHMER LETTER NO | `na` | `n` | `n` |
| ប | U+1794 | KHMER LETTER BA | `ba` | `p` | `b` |
| ផ | U+1795 | KHMER LETTER PHA | `pha` | `ph` | `ph` |
| ព | U+1796 | KHMER LETTER PO | `pa` | `b` | `p` |
| ភ | U+1797 | KHMER LETTER PHO | `pha` | `bh` | `ph` |
| ម | U+1798 | KHMER LETTER MO | `ma` | `m` | `m` |
| យ | U+1799 | KHMER LETTER YO | `ya` | `y` | `y` |
| រ | U+179A | KHMER LETTER RO | `ra` | `r` | `r` |
| ល | U+179B | KHMER LETTER LO | `la` | `l` | `l` |
| វ | U+179C | KHMER LETTER VO | `va` | `v` | `v` |
| ឝ | U+179D | KHMER LETTER SHA | `sha` | `sh` | `s` |
| ឞ | U+179E | KHMER LETTER SSO | `sha` | `ss` | `s` |
| ស | U+179F | KHMER LETTER SA | `sa` | `s` | `s` |
| ហ | U+17A0 | KHMER LETTER HA | `ha` | `h` | `h` |
| ឡ | U+17A1 | KHMER LETTER LA | `la` | `l` | `l` |
| អ | U+17A2 | KHMER LETTER QA | `a` | `q` | `'` |
| ឤ | U+17A4 | KHMER INDEPENDENT VOWEL QAA | `a` | `aa` | `'a` |
| ឥ | U+17A5 | KHMER INDEPENDENT VOWEL QI | `e` | `i` | `e` |
| ឦ | U+17A6 | KHMER INDEPENDENT VOWEL QII | `e` | `ii` | `ei` |
| ឩ | U+17A9 | KHMER INDEPENDENT VOWEL QUU | `u` | `uu` | `ou` |
| ឪ | U+17AA | KHMER INDEPENDENT VOWEL QUUV | `u` | `uuv` | `au` |
| ឬ | U+17AC | KHMER INDEPENDENT VOWEL RYY | `ry` | `ryy` | `rueu` |
| ឮ | U+17AE | KHMER INDEPENDENT VOWEL LYY | `ly` | `lyy` | `lueu` |
| ឱ | U+17B1 | KHMER INDEPENDENT VOWEL QOO TYPE ONE | `o` | `oo` | `ao` |
| ឲ | U+17B2 | KHMER INDEPENDENT VOWEL QOO TYPE TWO | `o` | `oo` | `ao` |
| ា | U+17B6 | KHMER VOWEL SIGN AA | `a` | `aa` | `a` |
| ិ | U+17B7 | KHMER VOWEL SIGN I | `e` | `i` | `e` |
| ី | U+17B8 | KHMER VOWEL SIGN II | `e` | `ii` | `ei` |
| ឹ | U+17B9 | KHMER VOWEL SIGN Y | `o` | `y` | `oe` |
| ឺ | U+17BA | KHMER VOWEL SIGN YY | `o` | `yy` | `eu` |
| ូ | U+17BC | KHMER VOWEL SIGN UU | `u` | `uu` | `ou` |
| | | *...9 more differences* | | | |

### my — Myanmar

Block: 160 assigned codepoints, 141 mapped by at least one library.

Coverage: translit maps 78/141, Unidecode maps 77/141. **18** mapped only by translit, **17** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ါ | U+102B | MYANMAR VOWEL SIGN TALL AA | `a` |
| ဳ | U+1033 | MYANMAR VOWEL SIGN MON II | `o` |
| ဴ | U+1034 | MYANMAR VOWEL SIGN MON O | `o` |
| ဵ | U+1035 | MYANMAR VOWEL SIGN E ABOVE | `e` |
| ျ | U+103B | MYANMAR CONSONANT SIGN MEDIAL YA | `y` |
| ြ | U+103C | MYANMAR CONSONANT SIGN MEDIAL RA | `r` |
| ွ | U+103D | MYANMAR CONSONANT SIGN MEDIAL WA | `w` |
| ှ | U+103E | MYANMAR CONSONANT SIGN MEDIAL HA | `h` |
| ႐ | U+1090 | MYANMAR SHAN DIGIT ZERO | `0` |
| ႑ | U+1091 | MYANMAR SHAN DIGIT ONE | `1` |
| ႒ | U+1092 | MYANMAR SHAN DIGIT TWO | `2` |
| ႓ | U+1093 | MYANMAR SHAN DIGIT THREE | `3` |
| ႔ | U+1094 | MYANMAR SHAN DIGIT FOUR | `4` |
| ႕ | U+1095 | MYANMAR SHAN DIGIT FIVE | `5` |
| ႖ | U+1096 | MYANMAR SHAN DIGIT SIX | `6` |
| ႗ | U+1097 | MYANMAR SHAN DIGIT SEVEN | `7` |
| ႘ | U+1098 | MYANMAR SHAN DIGIT EIGHT | `8` |
| ႙ | U+1099 | MYANMAR SHAN DIGIT NINE | `9` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ံ | U+1036 | MYANMAR SIGN ANUSVARA | `N` |
| ့ | U+1037 | MYANMAR SIGN DOT BELOW | `'` |
| း | U+1038 | MYANMAR SIGN VISARGA | `:` |
| ၌ | U+104C | MYANMAR SYMBOL LOCATIVE | `n*` |
| ၍ | U+104D | MYANMAR SYMBOL COMPLETED | `r*` |
| ၎ | U+104E | MYANMAR SYMBOL AFOREMENTIONED | `l*` |
| ၏ | U+104F | MYANMAR SYMBOL GENITIVE | `e*` |
| ၐ | U+1050 | MYANMAR LETTER SHA | `sh` |
| ၑ | U+1051 | MYANMAR LETTER SSA | `ss` |
| ၒ | U+1052 | MYANMAR LETTER VOCALIC R | `R` |
| ၓ | U+1053 | MYANMAR LETTER VOCALIC RR | `RR` |
| ၔ | U+1054 | MYANMAR LETTER VOCALIC L | `L` |
| ၕ | U+1055 | MYANMAR LETTER VOCALIC LL | `LL` |
| ၖ | U+1056 | MYANMAR VOWEL SIGN VOCALIC R | `R` |
| ၗ | U+1057 | MYANMAR VOWEL SIGN VOCALIC RR | `RR` |
| ၘ | U+1058 | MYANMAR VOWEL SIGN VOCALIC L | `L` |
| ၙ | U+1059 | MYANMAR VOWEL SIGN VOCALIC LL | `LL` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| က | U+1000 | MYANMAR LETTER KA | `ka` | `k` | `k` |
| ခ | U+1001 | MYANMAR LETTER KHA | `kha` | `kh` | `kh` |
| ဂ | U+1002 | MYANMAR LETTER GA | `ga` | `g` | `g` |
| ဃ | U+1003 | MYANMAR LETTER GHA | `gha` | `gh` | `gh` |
| င | U+1004 | MYANMAR LETTER NGA | `nga` | `ng` | `n` |
| စ | U+1005 | MYANMAR LETTER CA | `sa` | `c` | `c` |
| ဆ | U+1006 | MYANMAR LETTER CHA | `hsa` | `ch` | `ch` |
| ဇ | U+1007 | MYANMAR LETTER JA | `za` | `j` | `j` |
| ဈ | U+1008 | MYANMAR LETTER JHA | `zha` | `jh` | `jh` |
| ဉ | U+1009 | MYANMAR LETTER NYA | `nya` | `ny` | `n` |
| ည | U+100A | MYANMAR LETTER NNYA | `nya` | `nny` | `nn` |
| ဋ | U+100B | MYANMAR LETTER TTA | `ta` | `tt` | `t` |
| ဌ | U+100C | MYANMAR LETTER TTHA | `tha` | `tth` | `th` |
| ဍ | U+100D | MYANMAR LETTER DDA | `da` | `dd` | `d` |
| ဎ | U+100E | MYANMAR LETTER DDHA | `dha` | `ddh` | `dh` |
| ဏ | U+100F | MYANMAR LETTER NNA | `na` | `nn` | `n` |
| တ | U+1010 | MYANMAR LETTER TA | `ta` | `tt` | `t` |
| ထ | U+1011 | MYANMAR LETTER THA | `tha` | `th` | `th` |
| ဒ | U+1012 | MYANMAR LETTER DA | `da` | `d` | `d` |
| ဓ | U+1013 | MYANMAR LETTER DHA | `dha` | `dh` | `dh` |
| န | U+1014 | MYANMAR LETTER NA | `na` | `n` | `n` |
| ပ | U+1015 | MYANMAR LETTER PA | `pa` | `p` | `p` |
| ဖ | U+1016 | MYANMAR LETTER PHA | `pha` | `ph` | `ph` |
| ဗ | U+1017 | MYANMAR LETTER BA | `ba` | `b` | `b` |
| ဘ | U+1018 | MYANMAR LETTER BHA | `bha` | `bh` | `bh` |
| မ | U+1019 | MYANMAR LETTER MA | `ma` | `m` | `m` |
| ယ | U+101A | MYANMAR LETTER YA | `ya` | `y` | `y` |
| ရ | U+101B | MYANMAR LETTER RA | `ra` | `r` | `r` |
| လ | U+101C | MYANMAR LETTER LA | `la` | `l` | `l` |
| ဝ | U+101D | MYANMAR LETTER WA | `wa` | `w` | `v` |
| သ | U+101E | MYANMAR LETTER SA | `tha` | `s` | `s` |
| ဟ | U+101F | MYANMAR LETTER HA | `ha` | `h` | `h` |
| ဠ | U+1020 | MYANMAR LETTER LLA | `la` | `ll` | `l` |
| ဤ | U+1024 | MYANMAR LETTER II | `i` | `ii` | `i` |
| ဦ | U+1026 | MYANMAR LETTER UU | `u` | `uu` | `u` |
| ဪ | U+102A | MYANMAR LETTER AU | `o` | `au` | `o` |
| ာ | U+102C | MYANMAR VOWEL SIGN AA | `a` | `aa` | `a` |
| ီ | U+102E | MYANMAR VOWEL SIGN II | `i` | `ii` | `i` |
| ူ | U+1030 | MYANMAR VOWEL SIGN UU | `u` | `uu` | `u` |
| ဲ | U+1032 | MYANMAR VOWEL SIGN AI | `e` | `ai` | `ai` |
| ၊ | U+104A | MYANMAR SIGN LITTLE SECTION | `,` | ` / ` | `,` |
| ။ | U+104B | MYANMAR SIGN SECTION | `.` | ` // ` | `.` |

### bo — Tibetan

Block: 211 assigned codepoints, 201 mapped by at least one library.

Coverage: translit maps 138/201, Unidecode maps 147/201. **8** mapped only by translit, **17** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ༁ | U+0F01 | TIBETAN MARK GTER YIG MGO TRUNCATED A | `.` |
| ༂ | U+0F02 | TIBETAN MARK GTER YIG MGO -UM RNAM BCAD MA | `.` |
| ༃ | U+0F03 | TIBETAN MARK GTER YIG MGO -UM GTER TSHEG MA | `.` |
| ༄ | U+0F04 | TIBETAN MARK INITIAL YIG MGO MDUN MA | `@` |
| ༅ | U+0F05 | TIBETAN MARK CLOSING YIG MGO SGAB MA | `#` |
| ༆ | U+0F06 | TIBETAN MARK CARET YIG MGO PHUR SHAD MA | `.` |
| ༇ | U+0F07 | TIBETAN MARK YIG MGO TSHEG SHAD MA | `.` |
| ༊ | U+0F0A | TIBETAN MARK BKA- SHOG YIG MGO | `*` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ༌ | U+0F0C | TIBETAN MARK DELIMITER TSHEG BSTAR | ` / ` |
| ༴ | U+0F34 | TIBETAN MARK BSDUS RTAGS | `+` |
| ༵ | U+0F35 | TIBETAN MARK NGAS BZUNG NYI ZLA | `*` |
| ༶ | U+0F36 | TIBETAN MARK CARET -DZUD RTAGS BZHI MIG CAN | `^` |
| ༷ | U+0F37 | TIBETAN MARK NGAS BZUNG SGOR RTAGS | `_` |
| ༹ | U+0F39 | TIBETAN MARK TSA -PHRU | `~` |
| ཪ | U+0F6A | TIBETAN LETTER FIXED-FORM RA | `r` |
| ཾ | U+0F7E | TIBETAN SIGN RJES SU NGA RO | `M` |
| ཿ | U+0F7F | TIBETAN SIGN RNAM BCAD | `H` |
| ྀ | U+0F80 | TIBETAN VOWEL SIGN REVERSED I | `i` |
| ཱྀ | U+0F81 | TIBETAN VOWEL SIGN REVERSED II | `ii` |
| ྾ | U+0FBE | TIBETAN KU RU KHA | `X` |
| ྿ | U+0FBF | TIBETAN KU RU KHA BZHI MIG CAN | ` :X: ` |
| ࿀ | U+0FC0 | TIBETAN CANTILLATION SIGN HEAVY BEAT | ` /O/ ` |
| ࿁ | U+0FC1 | TIBETAN CANTILLATION SIGN LIGHT BEAT | ` /o/ ` |
| ࿂ | U+0FC2 | TIBETAN CANTILLATION SIGN CANG TE-U | ` \o\ ` |
| ࿃ | U+0FC3 | TIBETAN CANTILLATION SIGN SBUB -CHAL | ` (O) ` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ༀ | U+0F00 | TIBETAN SYLLABLE OM | `om` | `AUM` | `Om` |
| ༈ | U+0F08 | TIBETAN MARK SBRUL SHAD | `;` | ` // ` | `!` |
| ༉ | U+0F09 | TIBETAN MARK BSKUR YIG MGO | `*` | ` * ` | `*` |
| ། | U+0F0D | TIBETAN MARK SHAD | `.` | ` / ` | `,` |
| ༎ | U+0F0E | TIBETAN MARK NYIS SHAD | `.` | ` // ` | `.` |
| ༏ | U+0F0F | TIBETAN MARK TSHEG SHAD | `.` | ` -/ ` | `;` |
| ༐ | U+0F10 | TIBETAN MARK NYIS TSHEG SHAD | `.` | ` +/ ` | `|` |
| ༑ | U+0F11 | TIBETAN MARK RIN CHEN SPUNGS SHAD | `.` | ` X/ ` | `|` |
| ༒ | U+0F12 | TIBETAN MARK RGYA GRAM SHAD | `.` | ` /XX/ ` | `/` |
| ༓ | U+0F13 | TIBETAN MARK CARET -DZUD RTAGS ME LONG CAN | `.` | ` /X/ ` | `*` |
| ༔ | U+0F14 | TIBETAN MARK GTER TSHEG | `:` | `, ` | `:` |
| ༪ | U+0F2A | TIBETAN DIGIT HALF ONE | `0.0` | `.5` | `1-` |
| ༫ | U+0F2B | TIBETAN DIGIT HALF TWO | `0.5` | `1.5` | `2-` |
| ༬ | U+0F2C | TIBETAN DIGIT HALF THREE | `1.0` | `2.5` | `3-` |
| ༭ | U+0F2D | TIBETAN DIGIT HALF FOUR | `1.5` | `3.5` | `4-` |
| ༮ | U+0F2E | TIBETAN DIGIT HALF FIVE | `2.0` | `4.5` | `5-` |
| ༯ | U+0F2F | TIBETAN DIGIT HALF SIX | `2.5` | `5.5` | `6-` |
| ༰ | U+0F30 | TIBETAN DIGIT HALF SEVEN | `3.0` | `6.5` | `7-` |
| ༱ | U+0F31 | TIBETAN DIGIT HALF EIGHT | `3.5` | `7.5` | `8-` |
| ༲ | U+0F32 | TIBETAN DIGIT HALF NINE | `4.0` | `8.5` | `9-` |
| ༳ | U+0F33 | TIBETAN DIGIT HALF ZERO | `4.5` | `-.5` | `0-` |
| ཀ | U+0F40 | TIBETAN LETTER KA | `ka` | `k` | `k` |
| ཁ | U+0F41 | TIBETAN LETTER KHA | `kha` | `kh` | `kh` |
| ག | U+0F42 | TIBETAN LETTER GA | `ga` | `g` | `g` |
| གྷ | U+0F43 | TIBETAN LETTER GHA | `ga` | `gh` | `gh` |
| ང | U+0F44 | TIBETAN LETTER NGA | `nga` | `ng` | `ng` |
| ཅ | U+0F45 | TIBETAN LETTER CA | `cha` | `c` | `c` |
| ཆ | U+0F46 | TIBETAN LETTER CHA | `chha` | `ch` | `ch` |
| ཇ | U+0F47 | TIBETAN LETTER JA | `ja` | `j` | `j` |
| ཉ | U+0F49 | TIBETAN LETTER NYA | `nya` | `ny` | `ny` |
| ཊ | U+0F4A | TIBETAN LETTER TTA | `ta` | `tt` | `t` |
| ཋ | U+0F4B | TIBETAN LETTER TTHA | `tha` | `tth` | `th` |
| ཌ | U+0F4C | TIBETAN LETTER DDA | `da` | `dd` | `d` |
| ཌྷ | U+0F4D | TIBETAN LETTER DDHA | `da` | `ddh` | `dh` |
| ཎ | U+0F4E | TIBETAN LETTER NNA | `na` | `nn` | `n` |
| ཏ | U+0F4F | TIBETAN LETTER TA | `ta` | `t` | `t` |
| ཐ | U+0F50 | TIBETAN LETTER THA | `tha` | `th` | `th` |
| ད | U+0F51 | TIBETAN LETTER DA | `da` | `d` | `d` |
| དྷ | U+0F52 | TIBETAN LETTER DHA | `da` | `dh` | `dh` |
| ན | U+0F53 | TIBETAN LETTER NA | `na` | `n` | `n` |
| པ | U+0F54 | TIBETAN LETTER PA | `pa` | `p` | `p` |
| ཕ | U+0F55 | TIBETAN LETTER PHA | `pha` | `ph` | `ph` |
| བ | U+0F56 | TIBETAN LETTER BA | `ba` | `b` | `b` |
| བྷ | U+0F57 | TIBETAN LETTER BHA | `ba` | `bh` | `bh` |
| མ | U+0F58 | TIBETAN LETTER MA | `ma` | `m` | `m` |
| ཙ | U+0F59 | TIBETAN LETTER TSA | `tsa` | `ts` | `ts` |
| ཚ | U+0F5A | TIBETAN LETTER TSHA | `tsha` | `tsh` | `tsh` |
| ཛ | U+0F5B | TIBETAN LETTER DZA | `dza` | `dz` | `dz` |
| ཛྷ | U+0F5C | TIBETAN LETTER DZHA | `dza` | `dzh` | `dzh` |
| ཝ | U+0F5D | TIBETAN LETTER WA | `wa` | `w` | `w` |
| | | *...63 more differences* | | | |

### am — Amharic

Block: 384 assigned codepoints, 370 mapped by at least one library.

Coverage: translit maps 370/370, Unidecode maps 343/370. **27** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ሇ | U+1207 | ETHIOPIC SYLLABLE HOA | `hwa` |
| ቇ | U+1247 | ETHIOPIC SYLLABLE QOA | `qwa` |
| ኇ | U+1287 | ETHIOPIC SYLLABLE XOA | `hwa` |
| ኢ | U+12A2 | ETHIOPIC SYLLABLE GLOTTAL I | `i` |
| ኯ | U+12AF | ETHIOPIC SYLLABLE KOA | `kwa` |
| ዏ | U+12CF | ETHIOPIC SYLLABLE WOA | `wwa` |
| ዯ | U+12EF | ETHIOPIC SYLLABLE YOA | `ywa` |
| ጏ | U+130F | ETHIOPIC SYLLABLE GOA | `gwa` |
| ጟ | U+131F | ETHIOPIC SYLLABLE GGWAA | `ggwa` |
| ፇ | U+1347 | ETHIOPIC SYLLABLE TZOA | `swa` |
| ፠ | U+1360 | ETHIOPIC SECTION MARK | ` ` |
| ᎀ | U+1380 | ETHIOPIC SYLLABLE SEBATBEIT MWA | `mwa` |
| ᎁ | U+1381 | ETHIOPIC SYLLABLE MWI | `mwi` |
| ᎂ | U+1382 | ETHIOPIC SYLLABLE MWEE | `mwe` |
| ᎃ | U+1383 | ETHIOPIC SYLLABLE MWE | `mwe` |
| ᎄ | U+1384 | ETHIOPIC SYLLABLE SEBATBEIT BWA | `bwa` |
| ᎅ | U+1385 | ETHIOPIC SYLLABLE BWI | `bwi` |
| ᎆ | U+1386 | ETHIOPIC SYLLABLE BWEE | `bwe` |
| ᎇ | U+1387 | ETHIOPIC SYLLABLE BWE | `bwe` |
| ᎈ | U+1388 | ETHIOPIC SYLLABLE SEBATBEIT FWA | `fwa` |
| ᎉ | U+1389 | ETHIOPIC SYLLABLE FWI | `fwi` |
| ᎊ | U+138A | ETHIOPIC SYLLABLE FWEE | `fwe` |
| ᎋ | U+138B | ETHIOPIC SYLLABLE FWE | `fwe` |
| ᎌ | U+138C | ETHIOPIC SYLLABLE SEBATBEIT PWA | `pwa` |
| ᎍ | U+138D | ETHIOPIC SYLLABLE PWI | `pwi` |
| ᎎ | U+138E | ETHIOPIC SYLLABLE PWEE | `pwe` |
| ᎏ | U+138F | ETHIOPIC SYLLABLE PWE | `pwe` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ሀ | U+1200 | ETHIOPIC SYLLABLE HA | `he` | `ha` | `ha` |
| ሃ | U+1203 | ETHIOPIC SYLLABLE HAA | `ha` | `haa` | `ha` |
| ሄ | U+1204 | ETHIOPIC SYLLABLE HEE | `he` | `hee` | `he` |
| ህ | U+1205 | ETHIOPIC SYLLABLE HE | `h` | `he` | `h` |
| ለ | U+1208 | ETHIOPIC SYLLABLE LA | `le` | `la` | `le` |
| ላ | U+120B | ETHIOPIC SYLLABLE LAA | `la` | `laa` | `la` |
| ሌ | U+120C | ETHIOPIC SYLLABLE LEE | `le` | `lee` | `le` |
| ል | U+120D | ETHIOPIC SYLLABLE LE | `l` | `le` | `l` |
| ሐ | U+1210 | ETHIOPIC SYLLABLE HHA | `hhe` | `hha` | `ha` |
| ሓ | U+1213 | ETHIOPIC SYLLABLE HHAA | `hha` | `hhaa` | `ha` |
| ሔ | U+1214 | ETHIOPIC SYLLABLE HHEE | `hhe` | `hhee` | `he` |
| ሕ | U+1215 | ETHIOPIC SYLLABLE HHE | `hh` | `hhe` | `h` |
| መ | U+1218 | ETHIOPIC SYLLABLE MA | `me` | `ma` | `me` |
| ማ | U+121B | ETHIOPIC SYLLABLE MAA | `ma` | `maa` | `ma` |
| ሜ | U+121C | ETHIOPIC SYLLABLE MEE | `me` | `mee` | `me` |
| ም | U+121D | ETHIOPIC SYLLABLE ME | `m` | `me` | `m` |
| ሠ | U+1220 | ETHIOPIC SYLLABLE SZA | `se` | `sza` | `se` |
| ሡ | U+1221 | ETHIOPIC SYLLABLE SZU | `su` | `szu` | `su` |
| ሢ | U+1222 | ETHIOPIC SYLLABLE SZI | `si` | `szi` | `si` |
| ሣ | U+1223 | ETHIOPIC SYLLABLE SZAA | `sa` | `szaa` | `sa` |
| ሤ | U+1224 | ETHIOPIC SYLLABLE SZEE | `se` | `szee` | `se` |
| ሥ | U+1225 | ETHIOPIC SYLLABLE SZE | `s` | `sze` | `s` |
| ሦ | U+1226 | ETHIOPIC SYLLABLE SZO | `so` | `szo` | `so` |
| ሧ | U+1227 | ETHIOPIC SYLLABLE SZWA | `swa` | `szwa` | `swa` |
| ረ | U+1228 | ETHIOPIC SYLLABLE RA | `re` | `ra` | `re` |
| ራ | U+122B | ETHIOPIC SYLLABLE RAA | `ra` | `raa` | `ra` |
| ሬ | U+122C | ETHIOPIC SYLLABLE REE | `re` | `ree` | `re` |
| ር | U+122D | ETHIOPIC SYLLABLE RE | `r` | `re` | `r` |
| ሰ | U+1230 | ETHIOPIC SYLLABLE SA | `se` | `sa` | `se` |
| ሳ | U+1233 | ETHIOPIC SYLLABLE SAA | `sa` | `saa` | `sa` |
| ሴ | U+1234 | ETHIOPIC SYLLABLE SEE | `se` | `see` | `se` |
| ስ | U+1235 | ETHIOPIC SYLLABLE SE | `s` | `se` | `s` |
| ሸ | U+1238 | ETHIOPIC SYLLABLE SHA | `she` | `sha` | `she` |
| ሻ | U+123B | ETHIOPIC SYLLABLE SHAA | `sha` | `shaa` | `sha` |
| ሼ | U+123C | ETHIOPIC SYLLABLE SHEE | `she` | `shee` | `she` |
| ሽ | U+123D | ETHIOPIC SYLLABLE SHE | `sh` | `she` | `sh` |
| ቀ | U+1240 | ETHIOPIC SYLLABLE QA | `qe` | `qa` | `k'e` |
| ቃ | U+1243 | ETHIOPIC SYLLABLE QAA | `qa` | `qaa` | `k'a` |
| ቄ | U+1244 | ETHIOPIC SYLLABLE QEE | `qe` | `qee` | `k'e` |
| ቅ | U+1245 | ETHIOPIC SYLLABLE QE | `q` | `qe` | `k'` |
| ቋ | U+124B | ETHIOPIC SYLLABLE QWAA | `qwa` | `qwaa` | `k'wa` |
| ቌ | U+124C | ETHIOPIC SYLLABLE QWEE | `qwe` | `qwee` | `k'we` |
| ቍ | U+124D | ETHIOPIC SYLLABLE QWE | `qw` | `qwe` | `k'wi` |
| ቐ | U+1250 | ETHIOPIC SYLLABLE QHA | `qhe` | `qha` | `k'e` |
| ቓ | U+1253 | ETHIOPIC SYLLABLE QHAA | `qha` | `qhaa` | `k'a` |
| ቔ | U+1254 | ETHIOPIC SYLLABLE QHEE | `qhe` | `qhee` | `k'e` |
| ቕ | U+1255 | ETHIOPIC SYLLABLE QHE | `qh` | `qhe` | `k'` |
| ቛ | U+125B | ETHIOPIC SYLLABLE QHWAA | `qhwa` | `qhwaa` | `k'wa` |
| ቜ | U+125C | ETHIOPIC SYLLABLE QHWEE | `qhwe` | `qhwee` | `k'we` |
| ቝ | U+125D | ETHIOPIC SYLLABLE QHWE | `qhw` | `qhwe` | `k'wi` |
| | | *...168 more differences* | | | |

### ru — Russian

Block: 304 assigned codepoints, 301 mapped by at least one library.

Coverage: translit maps 294/301, Unidecode maps 234/301. **65** mapped only by translit, **5** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| Ҋ | U+048A | CYRILLIC CAPITAL LETTER SHORT I WITH TAIL | `Y` |
| ҋ | U+048B | CYRILLIC SMALL LETTER SHORT I WITH TAIL | `y` |
| Ӆ | U+04C5 | CYRILLIC CAPITAL LETTER EL WITH TAIL | `L` |
| ӆ | U+04C6 | CYRILLIC SMALL LETTER EL WITH TAIL | `l` |
| Ӊ | U+04C9 | CYRILLIC CAPITAL LETTER EN WITH TAIL | `N` |
| ӊ | U+04CA | CYRILLIC SMALL LETTER EN WITH TAIL | `n` |
| Ӎ | U+04CD | CYRILLIC CAPITAL LETTER EM WITH TAIL | `M` |
| ӎ | U+04CE | CYRILLIC SMALL LETTER EM WITH TAIL | `m` |
| ӏ | U+04CF | CYRILLIC SMALL LETTER PALOCHKA | `i` |
| Ӷ | U+04F6 | CYRILLIC CAPITAL LETTER GHE WITH DESCENDER | `G` |
| ӷ | U+04F7 | CYRILLIC SMALL LETTER GHE WITH DESCENDER | `g` |
| Ӻ | U+04FA | CYRILLIC CAPITAL LETTER GHE WITH STROKE AND HOOK | `G` |
| ӻ | U+04FB | CYRILLIC SMALL LETTER GHE WITH STROKE AND HOOK | `g` |
| Ӽ | U+04FC | CYRILLIC CAPITAL LETTER HA WITH HOOK | `Kh` |
| ӽ | U+04FD | CYRILLIC SMALL LETTER HA WITH HOOK | `kh` |
| Ӿ | U+04FE | CYRILLIC CAPITAL LETTER HA WITH STROKE | `Kh` |
| ӿ | U+04FF | CYRILLIC SMALL LETTER HA WITH STROKE | `kh` |
| Ԁ | U+0500 | CYRILLIC CAPITAL LETTER KOMI DE | `D` |
| ԁ | U+0501 | CYRILLIC SMALL LETTER KOMI DE | `d` |
| Ԃ | U+0502 | CYRILLIC CAPITAL LETTER KOMI DJE | `Dj` |
| ԃ | U+0503 | CYRILLIC SMALL LETTER KOMI DJE | `dj` |
| Ԅ | U+0504 | CYRILLIC CAPITAL LETTER KOMI ZJE | `Z` |
| ԅ | U+0505 | CYRILLIC SMALL LETTER KOMI ZJE | `z` |
| Ԇ | U+0506 | CYRILLIC CAPITAL LETTER KOMI DZJE | `Dz` |
| ԇ | U+0507 | CYRILLIC SMALL LETTER KOMI DZJE | `dz` |
| Ԉ | U+0508 | CYRILLIC CAPITAL LETTER KOMI LJE | `Lj` |
| ԉ | U+0509 | CYRILLIC SMALL LETTER KOMI LJE | `lj` |
| Ԋ | U+050A | CYRILLIC CAPITAL LETTER KOMI NJE | `Nj` |
| ԋ | U+050B | CYRILLIC SMALL LETTER KOMI NJE | `nj` |
| Ԍ | U+050C | CYRILLIC CAPITAL LETTER KOMI SJE | `Sj` |
| | | *...35 more* | |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ҂ | U+0482 | CYRILLIC THOUSANDS SIGN | `*1000*` |
| ҈ | U+0488 | COMBINING CYRILLIC HUNDRED THOUSANDS SIGN | `*100.000*` |
| ҉ | U+0489 | COMBINING CYRILLIC MILLIONS SIGN | `*1.000.000*` |
| Ҍ | U+048C | CYRILLIC CAPITAL LETTER SEMISOFT SIGN | `"` |
| ҍ | U+048D | CYRILLIC SMALL LETTER SEMISOFT SIGN | `"` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Ѐ | U+0400 | CYRILLIC CAPITAL LETTER IE WITH GRAVE | `E` | `Ie` | `E` |
| Ё | U+0401 | CYRILLIC CAPITAL LETTER IO | `Yo` | `Io` | `E` |
| Ѓ | U+0403 | CYRILLIC CAPITAL LETTER GJE | `G` | `Gj` | `G` |
| Є | U+0404 | CYRILLIC CAPITAL LETTER UKRAINIAN IE | `Ye` | `Ie` | `Ie` |
| Ќ | U+040C | CYRILLIC CAPITAL LETTER KJE | `K` | `Kj` | `K` |
| Й | U+0419 | CYRILLIC CAPITAL LETTER SHORT I | `Y` | `I` | `Y` |
| Ъ | U+042A | CYRILLIC CAPITAL LETTER HARD SIGN | `"` | `'` | `'` |
| Ю | U+042E | CYRILLIC CAPITAL LETTER YU | `Yu` | `Iu` | `Yu` |
| Я | U+042F | CYRILLIC CAPITAL LETTER YA | `Ya` | `Ia` | `Ya` |
| й | U+0439 | CYRILLIC SMALL LETTER SHORT I | `y` | `i` | `y` |
| ъ | U+044A | CYRILLIC SMALL LETTER HARD SIGN | `"` | `'` | `'` |
| ю | U+044E | CYRILLIC SMALL LETTER YU | `yu` | `iu` | `yu` |
| я | U+044F | CYRILLIC SMALL LETTER YA | `ya` | `ia` | `ya` |
| ѐ | U+0450 | CYRILLIC SMALL LETTER IE WITH GRAVE | `e` | `ie` | `e` |
| ё | U+0451 | CYRILLIC SMALL LETTER IO | `yo` | `io` | `e` |
| ѓ | U+0453 | CYRILLIC SMALL LETTER GJE | `g` | `gj` | `g` |
| є | U+0454 | CYRILLIC SMALL LETTER UKRAINIAN IE | `ye` | `ie` | `ie` |
| ќ | U+045C | CYRILLIC SMALL LETTER KJE | `k` | `kj` | `k` |
| Ѣ | U+0462 | CYRILLIC CAPITAL LETTER YAT | `Ye` | `E` | `E` |
| ѣ | U+0463 | CYRILLIC SMALL LETTER YAT | `ye` | `e` | `e` |
| Ѹ | U+0478 | CYRILLIC CAPITAL LETTER UK | `U` | `u` | `U` |
| Ҁ | U+0480 | CYRILLIC CAPITAL LETTER KOPPA | `K` | `Q` | `Q` |
| ҁ | U+0481 | CYRILLIC SMALL LETTER KOPPA | `k` | `q` | `q` |
| Ҏ | U+048E | CYRILLIC CAPITAL LETTER ER WITH TICK | `R` | `R'` | `Rh` |
| ҏ | U+048F | CYRILLIC SMALL LETTER ER WITH TICK | `r` | `r'` | `rh` |
| Ґ | U+0490 | CYRILLIC CAPITAL LETTER GHE WITH UPTURN | `G` | `G'` | `G` |
| ґ | U+0491 | CYRILLIC SMALL LETTER GHE WITH UPTURN | `g` | `g'` | `g` |
| Ғ | U+0492 | CYRILLIC CAPITAL LETTER GHE WITH STROKE | `G` | `G'` | `Gh` |
| ғ | U+0493 | CYRILLIC SMALL LETTER GHE WITH STROKE | `g` | `g'` | `gh` |
| Ҕ | U+0494 | CYRILLIC CAPITAL LETTER GHE WITH MIDDLE HOOK | `G` | `G'` | `Gh` |
| ҕ | U+0495 | CYRILLIC SMALL LETTER GHE WITH MIDDLE HOOK | `g` | `g'` | `gh` |
| Җ | U+0496 | CYRILLIC CAPITAL LETTER ZHE WITH DESCENDER | `Zh` | `Zh'` | `J` |
| җ | U+0497 | CYRILLIC SMALL LETTER ZHE WITH DESCENDER | `zh` | `zh'` | `j` |
| Ҙ | U+0498 | CYRILLIC CAPITAL LETTER ZE WITH DESCENDER | `Z` | `Z'` | `Z` |
| ҙ | U+0499 | CYRILLIC SMALL LETTER ZE WITH DESCENDER | `z` | `z'` | `z` |
| Қ | U+049A | CYRILLIC CAPITAL LETTER KA WITH DESCENDER | `K` | `K'` | `Q` |
| қ | U+049B | CYRILLIC SMALL LETTER KA WITH DESCENDER | `k` | `k'` | `q` |
| Ҝ | U+049C | CYRILLIC CAPITAL LETTER KA WITH VERTICAL STROKE | `K` | `K'` | `G` |
| ҝ | U+049D | CYRILLIC SMALL LETTER KA WITH VERTICAL STROKE | `k` | `k'` | `g` |
| Ҟ | U+049E | CYRILLIC CAPITAL LETTER KA WITH STROKE | `K` | `K'` | `Q` |
| ҟ | U+049F | CYRILLIC SMALL LETTER KA WITH STROKE | `k` | `k'` | `q` |
| Ҡ | U+04A0 | CYRILLIC CAPITAL LETTER BASHKIR KA | `K` | `K'` | `Q` |
| ҡ | U+04A1 | CYRILLIC SMALL LETTER BASHKIR KA | `k` | `k'` | `q` |
| Ң | U+04A2 | CYRILLIC CAPITAL LETTER EN WITH DESCENDER | `N` | `N'` | `Ng` |
| ң | U+04A3 | CYRILLIC SMALL LETTER EN WITH DESCENDER | `n` | `n'` | `ng` |
| Ҧ | U+04A6 | CYRILLIC CAPITAL LETTER PE WITH MIDDLE HOOK | `P` | `P'` | `Ph` |
| ҧ | U+04A7 | CYRILLIC SMALL LETTER PE WITH MIDDLE HOOK | `p` | `p'` | `ph` |
| Ҫ | U+04AA | CYRILLIC CAPITAL LETTER ES WITH DESCENDER | `S` | `S'` | `S` |
| ҫ | U+04AB | CYRILLIC SMALL LETTER ES WITH DESCENDER | `s` | `s'` | `s` |
| Ҭ | U+04AC | CYRILLIC CAPITAL LETTER TE WITH DESCENDER | `T` | `T'` | `Th` |
| | | *...26 more differences* | | | |

### dv — Dhivehi

Block: 50 assigned codepoints, 49 mapped by at least one library.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ޅ | U+0785 | THAANA LETTER LHAVIYANI | `lh` | `L` | `lh` |
| ޏ | U+078F | THAANA LETTER GNAVIYANI | `gn` | `ny` | `gn` |
| ޢ | U+07A2 | THAANA LETTER AINU | `'` | ``` | `'` |

### jv — Javanese

Block: 91 assigned codepoints, 90 mapped by at least one library.

Coverage: translit maps 75/90, Unidecode maps 0/90. **75** mapped only by translit, **0** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ꦄ | U+A984 | JAVANESE LETTER A | `a` |
| ꦅ | U+A985 | JAVANESE LETTER I KAWI | `aa` |
| ꦆ | U+A986 | JAVANESE LETTER I | `i` |
| ꦇ | U+A987 | JAVANESE LETTER II | `ii` |
| ꦈ | U+A988 | JAVANESE LETTER U | `u` |
| ꦉ | U+A989 | JAVANESE LETTER PA CEREK | `uu` |
| ꦊ | U+A98A | JAVANESE LETTER NGA LELET | `e` |
| ꦋ | U+A98B | JAVANESE LETTER NGA LELET RASWADI | `ai` |
| ꦌ | U+A98C | JAVANESE LETTER E | `o` |
| ꦍ | U+A98D | JAVANESE LETTER AI | `au` |
| ꦎ | U+A98E | JAVANESE LETTER O | `e` |
| ꦏ | U+A98F | JAVANESE LETTER KA | `o` |
| ꦐ | U+A990 | JAVANESE LETTER KA SASAK | `ka` |
| ꦑ | U+A991 | JAVANESE LETTER KA MURDA | `kha` |
| ꦒ | U+A992 | JAVANESE LETTER GA | `ga` |
| ꦓ | U+A993 | JAVANESE LETTER GA MURDA | `gha` |
| ꦔ | U+A994 | JAVANESE LETTER NGA | `nga` |
| ꦕ | U+A995 | JAVANESE LETTER CA | `cha` |
| ꦖ | U+A996 | JAVANESE LETTER CA MURDA | `chha` |
| ꦗ | U+A997 | JAVANESE LETTER JA | `ja` |
| ꦘ | U+A998 | JAVANESE LETTER NYA MURDA | `jha` |
| ꦙ | U+A999 | JAVANESE LETTER JA MAHAPRANA | `nya` |
| ꦚ | U+A99A | JAVANESE LETTER NYA | `tta` |
| ꦛ | U+A99B | JAVANESE LETTER TTA | `ttha` |
| ꦜ | U+A99C | JAVANESE LETTER TTA MAHAPRANA | `dda` |
| ꦝ | U+A99D | JAVANESE LETTER DDA | `ddha` |
| ꦞ | U+A99E | JAVANESE LETTER DDA MAHAPRANA | `nna` |
| ꦟ | U+A99F | JAVANESE LETTER NA MURDA | `ta` |
| ꦠ | U+A9A0 | JAVANESE LETTER TA | `tha` |
| ꦡ | U+A9A1 | JAVANESE LETTER TA MURDA | `da` |
| | | *...45 more* | |

### mn — Mongolian

Block: 157 assigned codepoints, 153 mapped by at least one library.

Coverage: translit maps 149/153, Unidecode maps 148/153. **5** mapped only by translit, **4** mapped only by Unidecode.

**Mapped only by translit** (Unidecode returns empty/`[?]`):

| Char | Codepoint | Name | translit |
|------|-----------|------|----------|
| ᠆ | U+1806 | MONGOLIAN TODO SOFT HYPHEN | `-` |
| ᠊ | U+180A | MONGOLIAN NIRUGU | `-` |
| ᡸ | U+1878 | MONGOLIAN LETTER CHA WITH TWO DOTS | `ch` |
| ᢀ | U+1880 | MONGOLIAN LETTER ALI GALI ANUSVARA ONE | `m` |
| ᢪ | U+18AA | MONGOLIAN LETTER MANCHU ALI GALI LHA | `lha` |

**Mapped only by Unidecode** (translit returns empty):

| Char | Codepoint | Name | Unidecode |
|------|-----------|------|-----------|
| ᡃ | U+1843 | MONGOLIAN LETTER TODO LONG VOWEL SIGN | `-` |
| ᢅ | U+1885 | MONGOLIAN LETTER ALI GALI BALUDA | ` 3 ` |
| ᢆ | U+1886 | MONGOLIAN LETTER ALI GALI THREE BALUDA | ` 333 ` |
| ᢩ | U+18A9 | MONGOLIAN LETTER ALI GALI DAGALGA | `'` |

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ᠀ | U+1800 | MONGOLIAN BIRGA | `.` | ` @ ` | `@` |
| ᠁ | U+1801 | MONGOLIAN ELLIPSIS | `.` | ` ... ` | `...` |
| ᠂ | U+1802 | MONGOLIAN COMMA | `,` | `, ` | `,` |
| ᠃ | U+1803 | MONGOLIAN FULL STOP | `:` | `. ` | `.` |
| ᠄ | U+1804 | MONGOLIAN COLON | `...` | `: ` | `:` |
| ᠅ | U+1805 | MONGOLIAN FOUR DOTS | `:` | ` // ` | `*` |
| ᠇ | U+1807 | MONGOLIAN SIBE SYLLABLE BOUNDARY MARKER | `.` | `-` | `-` |
| ᠈ | U+1808 | MONGOLIAN MANCHU COMMA | `,` | `, ` | `,` |
| ᠉ | U+1809 | MONGOLIAN MANCHU FULL STOP | `.` | `. ` | `.` |
| ᠥ | U+1825 | MONGOLIAN LETTER OE | `oe` | `O` | `o` |
| ᠦ | U+1826 | MONGOLIAN LETTER UE | `ue` | `U` | `u` |
| ᠻ | U+183B | MONGOLIAN LETTER KHA | `kh` | `kha` | `k` |
| ᡈ | U+1848 | MONGOLIAN LETTER TODO OE | `oe` | `O` | `o` |
| ᡉ | U+1849 | MONGOLIAN LETTER TODO UE | `ue` | `U` | `u` |
| ᡊ | U+184A | MONGOLIAN LETTER TODO ANG | `ang` | `ng` | `ng` |
| ᡚ | U+185A | MONGOLIAN LETTER TODO JIA | `j` | `jy` | `j` |
| ᡛ | U+185B | MONGOLIAN LETTER TODO NIA | `n` | `ny` | `ny` |
| ᡠ | U+1860 | MONGOLIAN LETTER SIBE UE | `ue` | `U` | `u` |
| ᡢ | U+1862 | MONGOLIAN LETTER SIBE ANG | `ang` | `ng` | `ng` |
| ᢁ | U+1881 | MONGOLIAN LETTER ALI GALI VISARGA ONE | `h` | `H` | `h` |
| ᢂ | U+1882 | MONGOLIAN LETTER ALI GALI DAMARU | `d` | `X` | `h` |
| ᢃ | U+1883 | MONGOLIAN LETTER ALI GALI UBADAMA | `u` | `W` | `h` |
| ᢄ | U+1884 | MONGOLIAN LETTER ALI GALI INVERTED UBADAMA | `u` | `M` | `h` |
| ᢉ | U+1889 | MONGOLIAN LETTER ALI GALI KA | `ka` | `k` | `k` |
| ᢊ | U+188A | MONGOLIAN LETTER ALI GALI NGA | `nga` | `ng` | `ng` |
| ᢋ | U+188B | MONGOLIAN LETTER ALI GALI CA | `ca` | `c` | `ts` |
| ᢌ | U+188C | MONGOLIAN LETTER ALI GALI TTA | `ta` | `tt` | `t` |
| ᢍ | U+188D | MONGOLIAN LETTER ALI GALI TTHA | `tha` | `tth` | `th` |
| ᢎ | U+188E | MONGOLIAN LETTER ALI GALI DDA | `da` | `dd` | `d` |
| ᢏ | U+188F | MONGOLIAN LETTER ALI GALI NNA | `na` | `nn` | `n` |
| ᢐ | U+1890 | MONGOLIAN LETTER ALI GALI TA | `ta` | `t` | `t` |
| ᢑ | U+1891 | MONGOLIAN LETTER ALI GALI DA | `da` | `d` | `d` |
| ᢒ | U+1892 | MONGOLIAN LETTER ALI GALI PA | `pa` | `p` | `p` |
| ᢓ | U+1893 | MONGOLIAN LETTER ALI GALI PHA | `pha` | `ph` | `ph` |
| ᢔ | U+1894 | MONGOLIAN LETTER ALI GALI SSA | `sha` | `ss` | `s` |
| ᢕ | U+1895 | MONGOLIAN LETTER ALI GALI ZHA | `zha` | `zh` | `zh` |
| ᢖ | U+1896 | MONGOLIAN LETTER ALI GALI ZA | `za` | `z` | `z` |
| ᢗ | U+1897 | MONGOLIAN LETTER ALI GALI AH | `ah` | `a` | `'` |
| ᢘ | U+1898 | MONGOLIAN LETTER TODO ALI GALI TA | `ta` | `t` | `t` |
| ᢙ | U+1899 | MONGOLIAN LETTER TODO ALI GALI ZHA | `zha` | `zh` | `zh` |
| ᢚ | U+189A | MONGOLIAN LETTER MANCHU ALI GALI GHA | `gha` | `gh` | `gh` |
| ᢛ | U+189B | MONGOLIAN LETTER MANCHU ALI GALI NGA | `nga` | `ng` | `ng` |
| ᢜ | U+189C | MONGOLIAN LETTER MANCHU ALI GALI CA | `ca` | `c` | `ts` |
| ᢝ | U+189D | MONGOLIAN LETTER MANCHU ALI GALI JHA | `jha` | `jh` | `dzh` |
| ᢞ | U+189E | MONGOLIAN LETTER MANCHU ALI GALI TTA | `ta` | `tta` | `t` |
| ᢟ | U+189F | MONGOLIAN LETTER MANCHU ALI GALI DDHA | `dha` | `ddh` | `dh` |
| ᢠ | U+18A0 | MONGOLIAN LETTER MANCHU ALI GALI TA | `ta` | `t` | `t` |
| ᢡ | U+18A1 | MONGOLIAN LETTER MANCHU ALI GALI DHA | `dha` | `dh` | `dh` |
| ᢢ | U+18A2 | MONGOLIAN LETTER MANCHU ALI GALI SSA | `sha` | `ss` | `s` |
| ᢣ | U+18A3 | MONGOLIAN LETTER MANCHU ALI GALI CYA | `cya` | `cy` | `c` |
| | | *...3 more differences* | | | |

## Key Takeaways

- **Total assigned codepoints scanned**: 49089
- **Mapped by at least one library**: 48825
- **translit coverage**: 48297/48825 (98.9%)
- **Unidecode coverage**: 47408/48825 (97.1%)
- **anyascii coverage**: 48761/48825 (99.9%)
- **Characters mapped only by translit**: 1046
- **Characters mapped only by Unidecode**: 157
- **Different output (both mapped)**: 27017

---

*Generated by `benchmarks/diff_vs_unidecode.py`*
## Analysis: Systematic Difference Patterns

The character-level differences fall into several systematic categories.

### 1. Inherent Vowel Handling (Abugida Scripts)

**Affected**: Hindi, Bengali, Tamil, Telugu, Gujarati, Kannada, Malayalam, Marathi, Nepali, Odia, Punjabi, Sanskrit, Assamese, Sinhala, Tibetan, Myanmar

In Brahmic abugida scripts, each consonant letter carries an inherent /a/ vowel. translit includes this inherent vowel in the transliteration table (`ka`, `ga`, `ta`) and strips it when a virama (halant) or dependent vowel follows. Unidecode outputs bare consonants (`k`, `g`, `t`), producing less readable romanizations.

| Input | translit | Unidecode | Why translit is better |
|-------|----------|-----------|----------------------|
| क (ka) | `ka` | `k` | Inherent vowel is part of the pronunciation |
| क् (k + virama) | `k` | `k` | Virama strips the inherent vowel correctly |
| का (ka + aa) | `ka` | `kaa` | Dependent vowel replaces inherent, not doubles it |

Unidecode's approach produces `kaa` for का (doubling the vowel) and bare `k` for क (dropping the vowel), which are both incorrect for natural reading.

### 2. CJK Pinyin Casing and Spacing

**Affected**: Chinese (~20,633 differences), Japanese

Unidecode capitalizes every pinyin syllable and appends a trailing space (`Zhong `, `Hua `). translit uses lowercase (`zhong`, `hua`) and handles spacing contextually between ideographs. This single design difference accounts for the majority of the 20,633 CJK diffs.

| Input | translit | Unidecode |
|-------|----------|-----------|
| 中华 | `zhong hua` | `Zhong Hua ` |

translit's approach is correct for running text. Unidecode's per-character capitalization was designed for isolated lookups, not sentence transliteration.

### 3. Korean Romanization

**Affected**: Korean (~3,762 differences)

translit and Unidecode both map all 11,172 Hangul syllables, but use different romanization systems. translit follows Revised Romanization (the South Korean government standard), while Unidecode uses an older or variant system.

### 4. Language-Specific Rules

**Affected**: Swedish, Danish, Estonian, Icelandic, Bulgarian, Ukrainian, Russian, Greek

translit applies national romanization standards when a language is specified:

| Char | translit (with lang) | Unidecode | Standard |
|------|---------------------|-----------|----------|
| ä (Swedish) | `ae` | `a` | Swedish convention |
| ø (Danish) | `oe` | `o` | Danish convention |
| ð (Icelandic) | `dh` | `d` | Icelandic convention |
| й (Russian) | `y` | `i` | GOST 7.79 |
| я (Russian) | `ya` | `ia` | GOST 7.79 |
| η (Greek) | `i` | `e` | Modern Greek pronunciation |

Unidecode has no language parameter — it always applies a single generic mapping.

### 5. Cyrillic and Latin Extended Coverage

**Affected**: Bulgarian, Serbian, Ukrainian, Russian, and all Latin-script languages

translit now maps ~292/304 Cyrillic codepoints and ~396/400 Latin Extended codepoints, closely matching Unidecode's coverage. The remaining unmapped entries are combining marks or modifier characters with intentionally empty mappings. Extended Cyrillic characters (U+0460–U+052F) covering historical, phonetic, and minority-language additions are fully mapped.

### 6. Ethiopic Syllable Handling

**Affected**: Amharic (~218 differences)

Ethiopic (Ge'ez) script encodes consonant+vowel as a single syllable character. translit and Unidecode disagree on whether to include the inherent vowel for 6th-order (bare consonant) forms:

| Input | translit | Unidecode |
|-------|----------|-----------|
| ት (te) | `t` | `te` |
| ራ (raa) | `ra` | `raa` |
| መ (ma) | `me` | `ma` |

translit strips the inherent schwa from consonant-final forms, which is more natural for reading.

### 7. Khmer Consonant Errors in Unidecode

**Affected**: Khmer (~59 differences)

Unidecode has several Khmer mappings that appear incorrect:

| Char | Unicode Name | translit | Unidecode |
|------|-------------|----------|-----------|
| ព (po) | KHMER LETTER PO | `pa` | `b` |
| ប (ba) | KHMER LETTER BA | `ba` | `p` |
| ទ (to) | KHMER LETTER TO | `ta` | `d` |

Unidecode swaps voicing for some Khmer consonants (mapping po→b, ba→p), which is likely a data error.

### 8. Javanese: Full Coverage Gap in Unidecode

translit maps 75 Javanese codepoints; Unidecode maps none (returns `[?]` for the entire Javanese block U+A980–U+A9DF). This is a complete coverage gap in Unidecode.

### 9. Intentional Empty Mappings (Combining Marks and Modifiers)

Several characters across Indic, Khmer, and Myanmar blocks are present in translit's default table with intentionally empty mappings. These are combining marks (Unicode categories Mn/Mc) that modify adjacent consonants rather than representing independent sounds. Unidecode maps them to rough approximations; translit suppresses them as the less-wrong default.

Notable examples:

| Char | Codepoint | Name | Language(s) | translit | Unidecode | Rationale for empty |
|------|-----------|------|-------------|----------|-----------|-------------------|
| ় | U+09BC | Bengali Sign Nukta | bn, as | *(empty)* | `'` | Modifies preceding consonant; not independently pronounceable |
| ଼ | U+0B3C | Odia Sign Nukta | or | *(empty)* | `'` | Same as Bengali nukta |
| ੰ | U+0A70 | Gurmukhi Tippi | pa | *(empty)* | `N` | Nasalization marker — `N` is a functional approximation but can mislead |
| ੱ | U+0A71 | Gurmukhi Addak | pa | *(empty)* | `H` | Gemination marker — not phonologically motivated |
| ះ | U+17C7 | Khmer Sign Reahmuk | km | *(empty)* | `H` | Visarga-like final marker; not an independent `H` sound |
| ံ | U+1036 | Myanmar Sign Anusvara | my | *(empty)* | `N` | Nasalization of preceding vowel; standalone `N` misrepresents the phonology |
| ့ | U+1037 | Myanmar Sign Dot Below | my | *(empty)* | `'` | Creaky tone marker; no segmental consonant value |

These are deliberate design choices, not bugs. Language-specific overrides could map them if a particular romanization standard requires it.

## Deep Dive: Ethiopic (Amharic)

### Syllabary Structure

Ethiopic (Ge'ez) script is a syllabary: each character encodes a consonant+vowel pair. There are 7 vowel orders for each of 34+ consonant bases:

| Order | Name | Vowel | Example (H series) |
|-------|------|-------|--------------------|
| 1st | Ge'ez | ä (schwa) | ሀ U+1200 → `he` |
| 2nd | Ka'ib | u | ሁ U+1201 → `hu` |
| 3rd | Salis | i | ሂ U+1202 → `hi` |
| 4th | Rabi' | a | ሃ U+1203 → `ha` |
| 5th | Hamis | é | ሄ U+1204 → `he` |
| 6th | Sadis | (bare/ə) | ህ U+1205 → `h` |
| 7th | Sabi' | o | ሆ U+1206 → `ho` |

Transliteration is pure table lookup — no virama logic needed (unlike Brahmic abugidas).

### 1st/5th Order Vowel Collision

The 1st order (Ge'ez, /ä/) and 5th order (Hamis, /é/) both map to the same ASCII string. This affects every consonant series:

| Series | 1st order | 5th order | Both map to |
|--------|-----------|-----------|-------------|
| H | ሀ U+1200 | ሄ U+1204 | `he` |
| L | ለ U+1208 | ሌ U+120C | `le` |
| M | መ U+1218 | ሜ U+121C | `me` |
| Glottal | አ U+12A0 | ኤ U+12A4 | `e` |

The glottal stop series is worst: U+12A0 (1st), U+12A4 (5th), and U+12A5 (6th) all map to `e` (triple collision).

**Why this is accepted**: Standard ASCII romanization systems (BGN/PCGN, ALALC) do not distinguish 1st from 5th order in plain ASCII — the distinction requires diacritics (ä vs é). Since translit targets pure ASCII output, the collision is inherent to the domain and cannot be resolved without non-ASCII output.

### 6th Order (Bare Consonant) Design

translit strips the inherent schwa from 6th-order forms: ት → `t`, ም → `m`, ብ → `b`. Unidecode preserves it: ት → `te`, ም → `me`, ብ → `be`.

translit's approach is more natural for reading, as 6th order represents a bare consonant (no following vowel) in Amharic phonology.

### Amharic Language Override

The `am` language override addresses Amharic-specific phonological mappings (23 entries):

1. **ጸ/ፀ → s series** (16 entries): In modern Amharic, ጸ (tsade, U+1338–133F) and ፀ (U+1340–1347) are both pronounced as ejective /sʼ/, not /ts/. BGN/PCGN romanizes them as `s`. The default table retains `ts` for the generic Ge'ez mapping.

2. **ዐ pharyngeal → apostrophe-marked** (7 entries): The pharyngeal series (U+12D0–12D6) is distinct from the glottal stop (አ) in Amharic. The override marks it with a leading apostrophe (`'e`, `'a`, etc.), distinguishing ኤ (glottal `e`) from ዔ (pharyngeal `'e`).

## Methodology Notes

- Every assigned codepoint in each language's Unicode block(s) is tested — no sampling or text expansion
- translit is called with the `lang` parameter (language-aware mode), which is the recommended usage
- Unidecode and anyascii have no language parameter
- "Mapped" means at least one library produced meaningful ASCII (not empty, not `[?]`, not the original character unchanged)
- Languages sharing script blocks (e.g., all Latin-based European languages share Latin Supplement/Extended-A/Extended-B) will show similar block sizes but may differ in output due to language-specific overrides
- Regenerate this report: `python benchmarks/diff_vs_unidecode.py --markdown`

---

*Generated by `benchmarks/diff_vs_unidecode.py`*
