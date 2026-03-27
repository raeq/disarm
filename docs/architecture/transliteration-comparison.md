# Transliteration Comparison: translit vs Unidecode vs anyascii

Character-level correctness comparison across all 65 supported languages.
Each language tested with ~4,000 characters of real-world text.

## Methodology

For each language:
1. Canonical sample text is expanded to ~4k characters
2. Unique non-ASCII characters are extracted
3. Each character is transliterated by all three libraries
4. "Mapped" means the library produced meaningful ASCII output
   (not empty, not `[?]`, not the original character)

## Summary

| Lang | Description | Unique chars | translit | Unidecode | anyascii | translit-only | Unidecode-only | Output diffs |
|------|-------------|-------------|----------|-----------|----------|---------------|----------------|-------------|
| bg | Bulgarian | 24 | 24 | 24 | 24 | 0 | 0 | 3 |
| ca | Catalan | 2 | 2 | 2 | 2 | 0 | 0 | 0 |
| cs | Czech | 5 | 5 | 5 | 5 | 0 | 0 | 0 |
| cy | Welsh | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| da | Danish | 1 | 1 | 1 | 1 | 0 | 0 | 1 |
| de | German | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| el | Greek | 21 | 21 | 21 | 21 | 0 | 0 | 5 |
| es | Spanish | 2 | 2 | 2 | 2 | 0 | 0 | 0 |
| et | Estonian | 2 | 2 | 2 | 2 | 0 | 0 | 1 |
| fi | Finnish | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| fr | French | 3 | 3 | 3 | 3 | 0 | 0 | 0 |
| ga | Irish | 3 | 3 | 3 | 3 | 0 | 0 | 0 |
| hr | Croatian | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| hu | Hungarian | 4 | 4 | 4 | 4 | 0 | 0 | 0 |
| is | Icelandic | 4 | 4 | 4 | 4 | 0 | 0 | 1 |
| it | Italian | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| lt | Lithuanian | 2 | 2 | 2 | 2 | 0 | 0 | 0 |
| lv | Latvian | 2 | 2 | 2 | 2 | 0 | 0 | 0 |
| mt | Maltese | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| nl | Dutch | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| no | Norwegian | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| pl | Polish | 2 | 2 | 2 | 2 | 0 | 0 | 0 |
| pt | Portuguese | 3 | 3 | 3 | 3 | 0 | 0 | 0 |
| ro | Romanian | 2 | 2 | 2 | 2 | 0 | 0 | 0 |
| sk | Slovak | 3 | 3 | 3 | 3 | 0 | 0 | 0 |
| sl | Slovenian | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| sq | Albanian | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| sr | Serbian | 23 | 23 | 23 | 23 | 0 | 0 | 0 |
| sv | Swedish | 3 | 3 | 3 | 3 | 0 | 0 | 2 |
| tr | Turkish | 2 | 2 | 2 | 2 | 0 | 0 | 0 |
| uk | Ukrainian | 24 | 23 | 24 | 24 | 0 | 1 | 5 |
| vi | Vietnamese | 8 | 8 | 8 | 8 | 0 | 0 | 0 |
| ja | Japanese | 15 | 15 | 15 | 15 | 0 | 0 | 8 |
| ja-kunrei | Japanese Kunrei | 5 | 5 | 5 | 5 | 0 | 0 | 3 |
| ko | Korean | 15 | 15 | 15 | 15 | 0 | 0 | 0 |
| zh | Chinese | 18 | 18 | 18 | 18 | 0 | 0 | 18 |
| ar | Arabic | 19 | 19 | 18 | 18 | 1 | 0 | 2 |
| fa | Persian | 15 | 15 | 14 | 14 | 1 | 0 | 2 |
| he | Hebrew | 16 | 15 | 16 | 16 | 0 | 1 | 4 |
| hi | Hindi | 22 | 21 | 21 | 21 | 0 | 0 | 17 |
| bn | Bengali | 23 | 21 | 22 | 22 | 0 | 1 | 18 |
| ta | Tamil | 21 | 20 | 20 | 20 | 0 | 0 | 14 |
| te | Telugu | 20 | 19 | 19 | 19 | 0 | 0 | 16 |
| gu | Gujarati | 20 | 19 | 19 | 19 | 0 | 0 | 14 |
| kn | Kannada | 17 | 16 | 16 | 16 | 0 | 0 | 13 |
| ml | Malayalam | 20 | 19 | 19 | 19 | 0 | 0 | 14 |
| mr | Marathi | 17 | 16 | 16 | 16 | 0 | 0 | 13 |
| ne | Nepali | 18 | 17 | 17 | 17 | 0 | 0 | 13 |
| or | Odia | 20 | 18 | 19 | 19 | 0 | 1 | 13 |
| pa | Punjabi | 14 | 12 | 14 | 14 | 0 | 2 | 10 |
| sa | Sanskrit | 19 | 18 | 18 | 18 | 0 | 0 | 17 |
| as | Assamese | 20 | 18 | 19 | 19 | 0 | 1 | 15 |
| hy | Armenian | 6 | 6 | 6 | 6 | 0 | 0 | 0 |
| ka | Georgian | 17 | 17 | 17 | 17 | 0 | 0 | 6 |
| si | Sinhala | 19 | 17 | 17 | 17 | 0 | 0 | 15 |
| th | Thai | 26 | 23 | 23 | 23 | 0 | 0 | 4 |
| lo | Lao | 15 | 15 | 14 | 15 | 1 | 0 | 2 |
| km | Khmer | 17 | 15 | 16 | 16 | 0 | 1 | 12 |
| my | Myanmar | 18 | 15 | 14 | 16 | 3 | 2 | 8 |
| bo | Tibetan | 17 | 16 | 17 | 17 | 0 | 1 | 14 |
| am | Amharic | 34 | 34 | 33 | 34 | 1 | 0 | 21 |
| ru | Russian | 23 | 23 | 23 | 23 | 0 | 0 | 2 |
| dv | Dhivehi | 10 | 9 | 9 | 8 | 0 | 0 | 0 |
| jv | Javanese | 5 | 5 | 0 | 5 | 5 | 0 | 0 |
| mn | Mongolian | 5 | 5 | 5 | 5 | 0 | 0 | 0 |
| **TOTAL** | | **716** | **685** | **684** | **692** | **12** | **11** | **326** |

## Notable Differences

### bg — Bulgarian

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ъ | U+044A | CYRILLIC SMALL LETTER HARD SIGN | `a` | `'` | `'` |
| я | U+044F | CYRILLIC SMALL LETTER YA | `ya` | `ia` | `ya` |
| Ю | U+042E | CYRILLIC CAPITAL LETTER YU | `Yu` | `Iu` | `Yu` |

### da — Danish

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ø | U+00F8 | LATIN SMALL LETTER O WITH STROKE | `oe` | `o` | `o` |

### el — Greek

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| Η | U+0397 | GREEK CAPITAL LETTER ETA | `I` | `E` | `I` |
| η | U+03B7 | GREEK SMALL LETTER ETA | `i` | `e` | `i` |
| ή | U+03AE | GREEK SMALL LETTER ETA WITH TONOS | `i` | `e` | `i` |
| χ | U+03C7 | GREEK SMALL LETTER CHI | `ch` | `kh` | `ch` |
| υ | U+03C5 | GREEK SMALL LETTER UPSILON | `y` | `u` | `y` |

### et — Estonian

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ä | U+00E4 | LATIN SMALL LETTER A WITH DIAERESIS | `ae` | `a` | `a` |

### is — Icelandic

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ð | U+00F0 | LATIN SMALL LETTER ETH | `dh` | `d` | `d` |

### sv — Swedish

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ä | U+00E4 | LATIN SMALL LETTER A WITH DIAERESIS | `ae` | `a` | `a` |
| ö | U+00F6 | LATIN SMALL LETTER O WITH DIAERESIS | `oe` | `o` | `o` |

### uk — Ukrainian

Coverage: translit maps 23/24 chars, Unidecode maps 24/24. **0** mapped only by translit, **1** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ї | U+0457 | CYRILLIC SMALL LETTER YI | `i` | `yi` | `i` |
| є | U+0454 | CYRILLIC SMALL LETTER UKRAINIAN IE | `ye` | `ie` | `ie` |
| ю | U+044E | CYRILLIC SMALL LETTER YU | `yu` | `iu` | `yu` |
| й | U+0439 | CYRILLIC SMALL LETTER SHORT I | `y` | `i` | `y` |
| Є | U+0404 | CYRILLIC CAPITAL LETTER UKRAINIAN IE | `Ye` | `Ie` | `Ie` |

### ja — Japanese

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| 日 | U+65E5 | CJK UNIFIED IDEOGRAPH-65E5 | `ri` | `Ri ` | `Ri` |
| 本 | U+672C | CJK UNIFIED IDEOGRAPH-672C | `ben` | `Ben ` | `Ben` |
| 国 | U+56FD | CJK UNIFIED IDEOGRAPH-56FD | `guo` | `Guo ` | `Guo` |
| 東 | U+6771 | CJK UNIFIED IDEOGRAPH-6771 | `dong` | `Dong ` | `Dong` |
| ジ | U+30B8 | KATAKANA LETTER ZI | `ji` | `zi` | `ji` |
| 位 | U+4F4D | CJK UNIFIED IDEOGRAPH-4F4D | `wei` | `Wei ` | `Wei` |
| 置 | U+7F6E | CJK UNIFIED IDEOGRAPH-7F6E | `zhi` | `Zhi ` | `Zhi` |
| 島 | U+5CF6 | CJK UNIFIED IDEOGRAPH-5CF6 | `dao` | `Dao ` | `Dao` |

### ja-kunrei — Japanese Kunrei

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| し | U+3057 | HIRAGANA LETTER SI | `si` | `shi` | `shi` |
| ち | U+3061 | HIRAGANA LETTER TI | `ti` | `chi` | `chi` |
| つ | U+3064 | HIRAGANA LETTER TU | `tu` | `tsu` | `tsu` |

### zh — Chinese

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| 中 | U+4E2D | CJK UNIFIED IDEOGRAPH-4E2D | `zhong` | `Zhong ` | `Zhong` |
| 华 | U+534E | CJK UNIFIED IDEOGRAPH-534E | `hua` | `Hua ` | `Hua` |
| 人 | U+4EBA | CJK UNIFIED IDEOGRAPH-4EBA | `ren` | `Ren ` | `Ren` |
| 民 | U+6C11 | CJK UNIFIED IDEOGRAPH-6C11 | `min` | `Min ` | `Min` |
| 共 | U+5171 | CJK UNIFIED IDEOGRAPH-5171 | `gong` | `Gong ` | `Gong` |
| 和 | U+548C | CJK UNIFIED IDEOGRAPH-548C | `he` | `He ` | `He` |
| 国 | U+56FD | CJK UNIFIED IDEOGRAPH-56FD | `guo` | `Guo ` | `Guo` |
| 是 | U+662F | CJK UNIFIED IDEOGRAPH-662F | `shi` | `Shi ` | `Shi` |
| 位 | U+4F4D | CJK UNIFIED IDEOGRAPH-4F4D | `wei` | `Wei ` | `Wei` |
| 于 | U+4E8E | CJK UNIFIED IDEOGRAPH-4E8E | `yu` | `Yu ` | `Yu` |
| 东 | U+4E1C | CJK UNIFIED IDEOGRAPH-4E1C | `dong` | `Dong ` | `Dong` |
| 亚 | U+4E9A | CJK UNIFIED IDEOGRAPH-4E9A | `ya` | `Ya ` | `Ya` |
| 的 | U+7684 | CJK UNIFIED IDEOGRAPH-7684 | `de` | `De ` | `De` |
| 社 | U+793E | CJK UNIFIED IDEOGRAPH-793E | `she` | `She ` | `She` |
| 会 | U+4F1A | CJK UNIFIED IDEOGRAPH-4F1A | `hui` | `Hui ` | `Hui` |
| 主 | U+4E3B | CJK UNIFIED IDEOGRAPH-4E3B | `zhu` | `Zhu ` | `Zhu` |
| 义 | U+4E49 | CJK UNIFIED IDEOGRAPH-4E49 | `yi` | `Yi ` | `Yi` |
| 家 | U+5BB6 | CJK UNIFIED IDEOGRAPH-5BB6 | `jia` | `Jia ` | `Jia` |

### ar — Arabic

Coverage: translit maps 19/19 chars, Unidecode maps 18/19. **1** mapped only by translit, **0** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ة | U+0629 | ARABIC LETTER TEH MARBUTA | `h` | `@` | `h` |
| ع | U+0639 | ARABIC LETTER AIN | `'` | ``` | ``` |

### fa — Persian

Coverage: translit maps 15/15 chars, Unidecode maps 14/15. **1** mapped only by translit, **0** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| و | U+0648 | ARABIC LETTER WAW | `v` | `w` | `w` |
| ک | U+06A9 | ARABIC LETTER KEHEH | `k` | `kh` | `k` |

### he — Hebrew

Coverage: translit maps 15/16 chars, Unidecode maps 16/16. **0** mapped only by translit, **1** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ש | U+05E9 | HEBREW LETTER SHIN | `sh` | `SH` | `s` |
| ב | U+05D1 | HEBREW LETTER BET | `v` | `b` | `v` |
| ח | U+05D7 | HEBREW LETTER HET | `ch` | `H` | `h` |
| כ | U+05DB | HEBREW LETTER KAF | `kh` | `KH` | `kh` |

### hi — Hindi

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| भ | U+092D | DEVANAGARI LETTER BHA | `bha` | `bh` | `bh` |
| ा | U+093E | DEVANAGARI VOWEL SIGN AA | `a` | `aa` | `a` |
| र | U+0930 | DEVANAGARI LETTER RA | `ra` | `r` | `r` |
| त | U+0924 | DEVANAGARI LETTER TA | `ta` | `t` | `t` |
| ग | U+0917 | DEVANAGARI LETTER GA | `ga` | `g` | `g` |
| ण | U+0923 | DEVANAGARI LETTER NNA | `na` | `nn` | `n` |
| ज | U+091C | DEVANAGARI LETTER JA | `ja` | `j` | `j` |
| य | U+092F | DEVANAGARI LETTER YA | `ya` | `y` | `y` |
| द | U+0926 | DEVANAGARI LETTER DA | `da` | `d` | `d` |
| क | U+0915 | DEVANAGARI LETTER KA | `ka` | `k` | `k` |
| ष | U+0937 | DEVANAGARI LETTER SSA | `sha` | `ss` | `s` |
| श | U+0936 | DEVANAGARI LETTER SHA | `sha` | `sh` | `s` |
| म | U+092E | DEVANAGARI LETTER MA | `ma` | `m` | `m` |
| ं | U+0902 | DEVANAGARI SIGN ANUSVARA | `m` | `N` | `m` |
| स | U+0938 | DEVANAGARI LETTER SA | `sa` | `s` | `s` |
| थ | U+0925 | DEVANAGARI LETTER THA | `tha` | `th` | `th` |
| ह | U+0939 | DEVANAGARI LETTER HA | `ha` | `h` | `h` |

### bn — Bengali

Coverage: translit maps 21/23 chars, Unidecode maps 22/23. **0** mapped only by translit, **1** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| গ | U+0997 | BENGALI LETTER GA | `ga` | `g` | `g` |
| ণ | U+09A3 | BENGALI LETTER NNA | `na` | `nn` | `n` |
| প | U+09AA | BENGALI LETTER PA | `pa` | `p` | `p` |
| র | U+09B0 | BENGALI LETTER RA | `ra` | `r` | `r` |
| জ | U+099C | BENGALI LETTER JA | `ja` | `j` | `j` |
| া | U+09BE | BENGALI VOWEL SIGN AA | `a` | `aa` | `a` |
| ত | U+09A4 | BENGALI LETTER TA | `ta` | `t` | `t` |
| ন | U+09A8 | BENGALI LETTER NA | `na` | `n` | `n` |
| ী | U+09C0 | BENGALI VOWEL SIGN II | `i` | `ii` | `i` |
| ব | U+09AC | BENGALI LETTER BA | `ba` | `b` | `b` |
| ং | U+0982 | BENGALI SIGN ANUSVARA | `m` | `N` | `m` |
| ল | U+09B2 | BENGALI LETTER LA | `la` | `l` | `l` |
| দ | U+09A6 | BENGALI LETTER DA | `da` | `d` | `d` |
| শ | U+09B6 | BENGALI LETTER SHA | `sha` | `sh` | `s` |
| ক | U+0995 | BENGALI LETTER KA | `ka` | `k` | `k` |
| ষ | U+09B7 | BENGALI LETTER SSA | `sha` | `ss` | `s` |
| য | U+09AF | BENGALI LETTER YA | `ya` | `y` | `y` |
| ট | U+099F | BENGALI LETTER TTA | `ta` | `tt` | `t` |

### ta — Tamil

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| த | U+0BA4 | TAMIL LETTER TA | `ta` | `t` | `t` |
| ம | U+0BAE | TAMIL LETTER MA | `ma` | `m` | `m` |
| ழ | U+0BB4 | TAMIL LETTER LLLA | `zha` | `lll` | `l` |
| ந | U+0BA8 | TAMIL LETTER NA | `na` | `n` | `n` |
| ா | U+0BBE | TAMIL VOWEL SIGN AA | `a` | `aa` | `a` |
| ட | U+0B9F | TAMIL LETTER TTA | `ta` | `tt` | `t` |
| ய | U+0BAF | TAMIL LETTER YA | `ya` | `y` | `y` |
| வ | U+0BB5 | TAMIL LETTER VA | `va` | `v` | `v` |
| ன | U+0BA9 | TAMIL LETTER NNNA | `na` | `nnn` | `n` |
| ற | U+0BB1 | TAMIL LETTER RRA | `ra` | `rr` | `r` |
| க | U+0B95 | TAMIL LETTER KA | `ka` | `k` | `k` |
| ே | U+0BC7 | TAMIL VOWEL SIGN EE | `e` | `ee` | `e` |
| ள | U+0BB3 | TAMIL LETTER LLA | `la` | `ll` | `l` |
| ல | U+0BB2 | TAMIL LETTER LA | `la` | `l` | `l` |

### te — Telugu

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| త | U+0C24 | TELUGU LETTER TA | `ta` | `t` | `t` |
| ల | U+0C32 | TELUGU LETTER LA | `la` | `l` | `l` |
| గ | U+0C17 | TELUGU LETTER GA | `ga` | `g` | `g` |
| భ | U+0C2D | TELUGU LETTER BHA | `bha` | `bh` | `bh` |
| ా | U+0C3E | TELUGU VOWEL SIGN AA | `a` | `aa` | `a` |
| ష | U+0C37 | TELUGU LETTER SSA | `sha` | `ss` | `s` |
| ద | U+0C26 | TELUGU LETTER DA | `da` | `d` | `d` |
| ర | U+0C30 | TELUGU LETTER RA | `ra` | `r` | `r` |
| వ | U+0C35 | TELUGU LETTER VA | `va` | `v` | `v` |
| డ | U+0C21 | TELUGU LETTER DDA | `da` | `dd` | `d` |
| క | U+0C15 | TELUGU LETTER KA | `ka` | `k` | `k` |
| ట | U+0C1F | TELUGU LETTER TTA | `ta` | `tt` | `t` |
| ం | U+0C02 | TELUGU SIGN ANUSVARA | `m` | `N` | `m` |
| బ | U+0C2C | TELUGU LETTER BA | `ba` | `b` | `b` |
| న | U+0C28 | TELUGU LETTER NA | `na` | `n` | `n` |
| చ | U+0C1A | TELUGU LETTER CA | `cha` | `c` | `c` |

### gu — Gujarati

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ગ | U+0A97 | GUJARATI LETTER GA | `ga` | `g` | `g` |
| જ | U+0A9C | GUJARATI LETTER JA | `ja` | `j` | `j` |
| ર | U+0AB0 | GUJARATI LETTER RA | `ra` | `r` | `r` |
| ા | U+0ABE | GUJARATI VOWEL SIGN AA | `a` | `aa` | `a` |
| ત | U+0AA4 | GUJARATI LETTER TA | `ta` | `t` | `t` |
| ભ | U+0AAD | GUJARATI LETTER BHA | `bha` | `bh` | `bh` |
| ન | U+0AA8 | GUJARATI LETTER NA | `na` | `n` | `n` |
| ં | U+0A82 | GUJARATI SIGN ANUSVARA | `m` | `N` | `m` |
| ક | U+0A95 | GUJARATI LETTER KA | `ka` | `k` | `k` |
| છ | U+0A9B | GUJARATI LETTER CHA | `chha` | `ch` | `ch` |
| પ | U+0AAA | GUJARATI LETTER PA | `pa` | `p` | `p` |
| શ | U+0AB6 | GUJARATI LETTER SHA | `sha` | `sh` | `s` |
| ચ | U+0A9A | GUJARATI LETTER CA | `cha` | `c` | `c` |
| મ | U+0AAE | GUJARATI LETTER MA | `ma` | `m` | `m` |

### kn — Kannada

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ಕ | U+0C95 | KANNADA LETTER KA | `ka` | `k` | `k` |
| ರ | U+0CB0 | KANNADA LETTER RA | `ra` | `r` | `r` |
| ನ | U+0CA8 | KANNADA LETTER NA | `na` | `n` | `n` |
| ಾ | U+0CBE | KANNADA VOWEL SIGN AA | `a` | `aa` | `a` |
| ಟ | U+0C9F | KANNADA LETTER TTA | `ta` | `tt` | `t` |
| ದ | U+0CA6 | KANNADA LETTER DA | `da` | `d` | `d` |
| ಷ | U+0CB7 | KANNADA LETTER SSA | `sha` | `ss` | `s` |
| ಣ | U+0CA3 | KANNADA LETTER NNA | `na` | `nn` | `n` |
| ಭ | U+0CAD | KANNADA LETTER BHA | `bha` | `bh` | `bh` |
| ತ | U+0CA4 | KANNADA LETTER TA | `ta` | `t` | `t` |
| ಂ | U+0C82 | KANNADA SIGN ANUSVARA | `m` | `N` | `m` |
| ಜ | U+0C9C | KANNADA LETTER JA | `ja` | `j` | `j` |
| ಯ | U+0CAF | KANNADA LETTER YA | `ya` | `y` | `y` |

### ml — Malayalam

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ക | U+0D15 | MALAYALAM LETTER KA | `ka` | `k` | `k` |
| േ | U+0D47 | MALAYALAM VOWEL SIGN EE | `e` | `ee` | `e` |
| ര | U+0D30 | MALAYALAM LETTER RA | `ra` | `r` | `r` |
| ള | U+0D33 | MALAYALAM LETTER LLA | `la` | `ll` | `l` |
| ം | U+0D02 | MALAYALAM SIGN ANUSVARA | `m` | `N` | `m` |
| ന | U+0D28 | MALAYALAM LETTER NA | `na` | `n` | `n` |
| ത | U+0D24 | MALAYALAM LETTER TA | `ta` | `t` | `t` |
| യ | U+0D2F | MALAYALAM LETTER YA | `ya` | `y` | `y` |
| ല | U+0D32 | MALAYALAM LETTER LA | `la` | `l` | `l` |
| സ | U+0D38 | MALAYALAM LETTER SA | `sa` | `s` | `s` |
| ഥ | U+0D25 | MALAYALAM LETTER THA | `tha` | `th` | `th` |
| ാ | U+0D3E | MALAYALAM VOWEL SIGN AA | `a` | `aa` | `a` |
| മ | U+0D2E | MALAYALAM LETTER MA | `ma` | `m` | `m` |
| ണ | U+0D23 | MALAYALAM LETTER NNA | `na` | `nn` | `n` |

### mr — Marathi

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| म | U+092E | DEVANAGARI LETTER MA | `ma` | `m` | `m` |
| ह | U+0939 | DEVANAGARI LETTER HA | `ha` | `h` | `h` |
| ा | U+093E | DEVANAGARI VOWEL SIGN AA | `a` | `aa` | `a` |
| र | U+0930 | DEVANAGARI LETTER RA | `ra` | `r` | `r` |
| ष | U+0937 | DEVANAGARI LETTER SSA | `sha` | `ss` | `s` |
| ट | U+091F | DEVANAGARI LETTER TTA | `ta` | `tt` | `t` |
| भ | U+092D | DEVANAGARI LETTER BHA | `bha` | `bh` | `bh` |
| त | U+0924 | DEVANAGARI LETTER TA | `ta` | `t` | `t` |
| ी | U+0940 | DEVANAGARI VOWEL SIGN II | `i` | `ii` | `i` |
| ल | U+0932 | DEVANAGARI LETTER LA | `la` | `l` | `l` |
| क | U+0915 | DEVANAGARI LETTER KA | `ka` | `k` | `k` |
| ज | U+091C | DEVANAGARI LETTER JA | `ja` | `j` | `j` |
| य | U+092F | DEVANAGARI LETTER YA | `ya` | `y` | `y` |

### ne — Nepali

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| न | U+0928 | DEVANAGARI LETTER NA | `na` | `n` | `n` |
| प | U+092A | DEVANAGARI LETTER PA | `pa` | `p` | `p` |
| ा | U+093E | DEVANAGARI VOWEL SIGN AA | `a` | `aa` | `a` |
| ल | U+0932 | DEVANAGARI LETTER LA | `la` | `l` | `l` |
| श | U+0936 | DEVANAGARI LETTER SHA | `sha` | `sh` | `s` |
| य | U+092F | DEVANAGARI LETTER YA | `ya` | `y` | `y` |
| क | U+0915 | DEVANAGARI LETTER KA | `ka` | `k` | `k` |
| स | U+0938 | DEVANAGARI LETTER SA | `sa` | `s` | `s` |
| व | U+0935 | DEVANAGARI LETTER VA | `va` | `v` | `v` |
| त | U+0924 | DEVANAGARI LETTER TA | `ta` | `t` | `t` |
| र | U+0930 | DEVANAGARI LETTER RA | `ra` | `r` | `r` |
| द | U+0926 | DEVANAGARI LETTER DA | `da` | `d` | `d` |
| ह | U+0939 | DEVANAGARI LETTER HA | `ha` | `h` | `h` |

### or — Odia

Coverage: translit maps 18/20 chars, Unidecode maps 19/20. **0** mapped only by translit, **1** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ଡ | U+0B21 | ORIYA LETTER DDA | `da` | `dd` | `d` |
| ଶ | U+0B36 | ORIYA LETTER SHA | `sha` | `sh` | `s` |
| ା | U+0B3E | ORIYA VOWEL SIGN AA | `a` | `aa` | `a` |
| ଭ | U+0B2D | ORIYA LETTER BHA | `bha` | `bh` | `bh` |
| ର | U+0B30 | ORIYA LETTER RA | `ra` | `r` | `r` |
| ତ | U+0B24 | ORIYA LETTER TA | `ta` | `t` | `t` |
| ପ | U+0B2A | ORIYA LETTER PA | `pa` | `p` | `p` |
| ୂ | U+0B42 | ORIYA VOWEL SIGN UU | `u` | `uu` | `u` |
| ବ | U+0B2C | ORIYA LETTER BA | `ba` | `b` | `b` |
| କ | U+0B15 | ORIYA LETTER KA | `ka` | `k` | `k` |
| ଳ | U+0B33 | ORIYA LETTER LLA | `la` | `ll` | `l` |
| ସ | U+0B38 | ORIYA LETTER SA | `sa` | `s` | `s` |
| ଥ | U+0B25 | ORIYA LETTER THA | `tha` | `th` | `th` |

### pa — Punjabi

Coverage: translit maps 12/14 chars, Unidecode maps 14/14. **0** mapped only by translit, **2** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ਪ | U+0A2A | GURMUKHI LETTER PA | `pa` | `p` | `p` |
| ਜ | U+0A1C | GURMUKHI LETTER JA | `ja` | `j` | `j` |
| ਾ | U+0A3E | GURMUKHI VOWEL SIGN AA | `a` | `aa` | `a` |
| ਬ | U+0A2C | GURMUKHI LETTER BA | `ba` | `b` | `b` |
| ਭ | U+0A2D | GURMUKHI LETTER BHA | `bha` | `bb` | `bh` |
| ਰ | U+0A30 | GURMUKHI LETTER RA | `ra` | `r` | `r` |
| ਤ | U+0A24 | GURMUKHI LETTER TA | `ta` | `t` | `t` |
| ਦ | U+0A26 | GURMUKHI LETTER DA | `da` | `d` | `d` |
| ਕ | U+0A15 | GURMUKHI LETTER KA | `ka` | `k` | `k` |
| ਹ | U+0A39 | GURMUKHI LETTER HA | `ha` | `h` | `h` |

### sa — Sanskrit

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| स | U+0938 | DEVANAGARI LETTER SA | `sa` | `s` | `s` |
| ं | U+0902 | DEVANAGARI SIGN ANUSVARA | `m` | `N` | `m` |
| क | U+0915 | DEVANAGARI LETTER KA | `ka` | `k` | `k` |
| ृ | U+0943 | DEVANAGARI VOWEL SIGN VOCALIC R | `r` | `R` | `r` |
| त | U+0924 | DEVANAGARI LETTER TA | `ta` | `t` | `t` |
| म | U+092E | DEVANAGARI LETTER MA | `ma` | `m` | `m` |
| ज | U+091C | DEVANAGARI LETTER JA | `ja` | `j` | `j` |
| ग | U+0917 | DEVANAGARI LETTER GA | `ga` | `g` | `g` |
| ः | U+0903 | DEVANAGARI SIGN VISARGA | `h` | `H` | `h` |
| ा | U+093E | DEVANAGARI VOWEL SIGN AA | `a` | `aa` | `a` |
| प | U+092A | DEVANAGARI LETTER PA | `pa` | `p` | `p` |
| र | U+0930 | DEVANAGARI LETTER RA | `ra` | `r` | `r` |
| च | U+091A | DEVANAGARI LETTER CA | `cha` | `c` | `c` |
| ी | U+0940 | DEVANAGARI VOWEL SIGN II | `i` | `ii` | `i` |
| न | U+0928 | DEVANAGARI LETTER NA | `na` | `n` | `n` |
| भ | U+092D | DEVANAGARI LETTER BHA | `bha` | `bh` | `bh` |
| ष | U+0937 | DEVANAGARI LETTER SSA | `sha` | `ss` | `s` |

### as — Assamese

Coverage: translit maps 18/20 chars, Unidecode maps 19/20. **0** mapped only by translit, **1** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| স | U+09B8 | BENGALI LETTER SA | `sa` | `s` | `s` |
| ম | U+09AE | BENGALI LETTER MA | `ma` | `m` | `m` |
| ভ | U+09AD | BENGALI LETTER BHA | `bha` | `bh` | `bh` |
| া | U+09BE | BENGALI VOWEL SIGN AA | `a` | `aa` | `a` |
| ত | U+09A4 | BENGALI LETTER TA | `ta` | `t` | `t` |
| প | U+09AA | BENGALI LETTER PA | `pa` | `p` | `p` |
| ূ | U+09C2 | BENGALI VOWEL SIGN UU | `u` | `uu` | `u` |
| ব | U+09AC | BENGALI LETTER BA | `ba` | `b` | `b` |
| ঞ | U+099E | BENGALI LETTER NYA | `nya` | `ny` | `n` |
| চ | U+099A | BENGALI LETTER CA | `cha` | `c` | `c` |
| ল | U+09B2 | BENGALI LETTER LA | `la` | `l` | `l` |
| খ | U+0996 | BENGALI LETTER KHA | `kha` | `kh` | `kh` |
| ন | U+09A8 | BENGALI LETTER NA | `na` | `n` | `n` |
| জ | U+099C | BENGALI LETTER JA | `ja` | `j` | `j` |
| য | U+09AF | BENGALI LETTER YA | `ya` | `y` | `y` |

### ka — Georgian

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ქ | U+10E5 | GEORGIAN LETTER KHAR | `k` | `k`` | `k` |
| თ | U+10D7 | GEORGIAN LETTER TAN | `t` | `t`` | `t` |
| ხ | U+10EE | GEORGIAN LETTER XAN | `kh` | `x` | `kh` |
| წ | U+10EC | GEORGIAN LETTER CIL | `ts` | `c` | `ts'` |
| ფ | U+10E4 | GEORGIAN LETTER PHAR | `p` | `p`` | `p` |
| ღ | U+10E6 | GEORGIAN LETTER GHAN | `gh` | `g'` | `gh` |

### si — Sinhala

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ශ | U+0DC1 | SINHALA LETTER TAALUJA SAYANNA | `sha` | `sh` | `s` |
| ර | U+0DBB | SINHALA LETTER RAYANNA | `ra` | `r` | `r` |
| ල | U+0DBD | SINHALA LETTER DANTAJA LAYANNA | `la` | `l` | `l` |
| ං | U+0D82 | SINHALA SIGN ANUSVARAYA | `m` | `N` | `m` |
| ක | U+0D9A | SINHALA LETTER ALPAPRAANA KAYANNA | `ka` | `k` | `k` |
| ා | U+0DCF | SINHALA VOWEL SIGN AELA-PILLA | `a` | `aa` | `a` |
| ප | U+0DB4 | SINHALA LETTER ALPAPRAANA PAYANNA | `pa` | `p` | `p` |
| ජ | U+0DA2 | SINHALA LETTER ALPAPRAANA JAYANNA | `ja` | `j` | `j` |
| ත | U+0DAD | SINHALA LETTER ALPAPRAANA TAYANNA | `ta` | `t` | `t` |
| න | U+0DB1 | SINHALA LETTER DANTAJA NAYANNA | `na` | `n` | `n` |
| ස | U+0DC3 | SINHALA LETTER DANTAJA SAYANNA | `sa` | `s` | `s` |
| ම | U+0DB8 | SINHALA LETTER MAYANNA | `ma` | `m` | `m` |
| ව | U+0DC0 | SINHALA LETTER VAYANNA | `va` | `v` | `v` |
| ද | U+0DAF | SINHALA LETTER ALPAPRAANA DAYANNA | `da` | `d` | `d` |
| ය | U+0DBA | SINHALA LETTER YAYANNA | `ya` | `y` | `y` |

### th — Thai

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| า | U+0E32 | THAI CHARACTER SARA AA | `a` | `aa` | `a` |
| อ | U+0E2D | THAI CHARACTER O ANG | `o` | ``` | `o` |
| ู | U+0E39 | THAI CHARACTER SARA UU | `u` | `uu` | `u` |
| ี | U+0E35 | THAI CHARACTER SARA II | `i` | `ii` | `i` |

### lo — Lao

Coverage: translit maps 15/15 chars, Unidecode maps 14/15. **1** mapped only by translit, **0** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| າ | U+0EB2 | LAO VOWEL SIGN AA | `a` | `aa` | `a` |
| ຕ | U+0E95 | LAO LETTER TO | `t` | `h` | `t` |

### km — Khmer

Coverage: translit maps 15/17 chars, Unidecode maps 16/17. **0** mapped only by translit, **1** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| ព | U+1796 | KHMER LETTER PO | `pa` | `b` | `p` |
| រ | U+179A | KHMER LETTER RO | `ra` | `r` | `r` |
| ា | U+17B6 | KHMER VOWEL SIGN AA | `a` | `aa` | `a` |
| ជ | U+1787 | KHMER LETTER CO | `cha` | `j` | `ch` |
| ណ | U+178E | KHMER LETTER NNO | `na` | `nn` | `n` |
| ច | U+1785 | KHMER LETTER CA | `cha` | `c` | `ch` |
| ក | U+1780 | KHMER LETTER KA | `ka` | `k` | `k` |
| ម | U+1798 | KHMER LETTER MO | `ma` | `m` | `m` |
| ប | U+1794 | KHMER LETTER BA | `ba` | `p` | `b` |
| ទ | U+1791 | KHMER LETTER TO | `ta` | `d` | `t` |
| ស | U+179F | KHMER LETTER SA | `sa` | `s` | `s` |
| យ | U+1799 | KHMER LETTER YO | `ya` | `y` | `y` |

### my — Myanmar

Coverage: translit maps 15/18 chars, Unidecode maps 14/18. **3** mapped only by translit, **2** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| မ | U+1019 | MYANMAR LETTER MA | `ma` | `m` | `m` |
| န | U+1014 | MYANMAR LETTER NA | `na` | `n` | `n` |
| ာ | U+102C | MYANMAR VOWEL SIGN AA | `a` | `aa` | `a` |
| င | U+1004 | MYANMAR LETTER NGA | `nga` | `ng` | `n` |
| သ | U+101E | MYANMAR LETTER SA | `tha` | `s` | `s` |
| ည | U+100A | MYANMAR LETTER NNYA | `nya` | `nny` | `nn` |
| ရ | U+101B | MYANMAR LETTER RA | `ra` | `r` | `r` |
| တ | U+1010 | MYANMAR LETTER TA | `ta` | `tt` | `t` |

### bo — Tibetan

Coverage: translit maps 16/17 chars, Unidecode maps 17/17. **0** mapped only by translit, **1** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| བ | U+0F56 | TIBETAN LETTER BA | `ba` | `b` | `b` |
| ད | U+0F51 | TIBETAN LETTER DA | `da` | `d` | `d` |
| ར | U+0F62 | TIBETAN LETTER RA | `ra` | `r` | `r` |
| ང | U+0F44 | TIBETAN LETTER NGA | `nga` | `ng` | `ng` |
| ས | U+0F66 | TIBETAN LETTER SA | `sa` | `s` | `s` |
| ྐ | U+0F90 | TIBETAN SUBJOINED LETTER KA | `ka` | `k` | `k` |
| ྱ | U+0FB1 | TIBETAN SUBJOINED LETTER YA | `ya` | `y` | `y` |
| ལ | U+0F63 | TIBETAN LETTER LA | `la` | `l` | `l` |
| ྗ | U+0F97 | TIBETAN SUBJOINED LETTER JA | `ja` | `j` | `j` |
| ན | U+0F53 | TIBETAN LETTER NA | `na` | `n` | `n` |
| ྒ | U+0F92 | TIBETAN SUBJOINED LETTER GA | `ga` | `g` | `g` |
| ག | U+0F42 | TIBETAN LETTER GA | `ga` | `g` | `g` |
| ཁ | U+0F41 | TIBETAN LETTER KHA | `kha` | `kh` | `kh` |
| ཏ | U+0F4F | TIBETAN LETTER TA | `ta` | `t` | `t` |

### am — Amharic

Coverage: translit maps 34/34 chars, Unidecode maps 33/34. **1** mapped only by translit, **0** mapped only by Unidecode.

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| የ | U+12E8 | ETHIOPIC SYLLABLE YA | `ye` | `ya` | `ye` |
| ት | U+1275 | ETHIOPIC SYLLABLE TE | `t` | `te` | `t` |
| ጵ | U+1335 | ETHIOPIC SYLLABLE PHE | `p` | `phe` | `p'` |
| ያ | U+12EB | ETHIOPIC SYLLABLE YAA | `ya` | `yaa` | `ya` |
| ፌ | U+134C | ETHIOPIC SYLLABLE FEE | `fe` | `fee` | `fe` |
| ዴ | U+12F4 | ETHIOPIC SYLLABLE DEE | `de` | `dee` | `de` |
| ራ | U+122B | ETHIOPIC SYLLABLE RAA | `ra` | `raa` | `ra` |
| ላ | U+120B | ETHIOPIC SYLLABLE LAA | `la` | `laa` | `la` |
| ክ | U+12AD | ETHIOPIC SYLLABLE KE | `k` | `ke` | `k` |
| ፐ | U+1350 | ETHIOPIC SYLLABLE PA | `pe` | `pa` | `pe` |
| ብ | U+1265 | ETHIOPIC SYLLABLE BE | `b` | `be` | `b` |
| መ | U+1218 | ETHIOPIC SYLLABLE MA | `me` | `ma` | `me` |
| ን | U+1295 | ETHIOPIC SYLLABLE NE | `n` | `ne` | `n` |
| ግ | U+130D | ETHIOPIC SYLLABLE GE | `g` | `ge` | `g` |
| ሥ | U+1225 | ETHIOPIC SYLLABLE SZE | `s` | `sze` | `s` |
| ስ | U+1235 | ETHIOPIC SYLLABLE SE | `s` | `se` | `s` |
| ለ | U+1208 | ETHIOPIC SYLLABLE LA | `le` | `la` | `le` |
| ም | U+121D | ETHIOPIC SYLLABLE ME | `m` | `me` | `m` |
| ር | U+122D | ETHIOPIC SYLLABLE RE | `r` | `re` | `r` |
| ቤ | U+1264 | ETHIOPIC SYLLABLE BEE | `be` | `bee` | `be` |
| ች | U+127D | ETHIOPIC SYLLABLE CE | `ch` | `ce` | `ch` |

### ru — Russian

| Char | Codepoint | Name | translit | Unidecode | anyascii |
|------|-----------|------|----------|-----------|----------|
| й | U+0439 | CYRILLIC SMALL LETTER SHORT I | `y` | `i` | `y` |
| я | U+044F | CYRILLIC SMALL LETTER YA | `ya` | `ia` | `ya` |

### jv — Javanese

Coverage: translit maps 5/5 chars, Unidecode maps 0/5. **5** mapped only by translit, **0** mapped only by Unidecode.

## Key Takeaways

- **Total unique non-ASCII characters tested**: 716
- **translit coverage**: 685/716 (95.7%)
- **Unidecode coverage**: 684/716 (95.5%)
- **anyascii coverage**: 692/716 (96.6%)
- **Characters mapped only by translit**: 12
- **Characters mapped only by Unidecode**: 11
- **Different output (both mapped)**: 326

## Analysis: Systematic Difference Patterns

The 326 character-level differences fall into five systematic categories.

### 1. Inherent Vowel Handling (Abugida Scripts)

**Affected**: Hindi, Bengali, Tamil, Telugu, Gujarati, Kannada, Malayalam, Marathi, Nepali, Odia, Punjabi, Sanskrit, Assamese, Sinhala, Tibetan, Myanmar (~200 differences)

In Brahmic abugida scripts, each consonant letter carries an inherent /a/ vowel. translit includes this inherent vowel in the transliteration table (`ka`, `ga`, `ta`) and strips it when a virama (halant) or dependent vowel follows. Unidecode outputs bare consonants (`k`, `g`, `t`), producing less readable romanizations.

| Input | translit | Unidecode | Why translit is better |
|-------|----------|-----------|----------------------|
| क (ka) | `ka` | `k` | Inherent vowel is part of the pronunciation |
| क् (k + virama) | `k` | `k` | Virama strips the inherent vowel correctly |
| का (ka + aa) | `ka` | `kaa` | Dependent vowel replaces inherent, not doubles it |

Unidecode's approach produces `kaa` for का (doubling the vowel) and bare `k` for क (dropping the vowel), which are both incorrect for natural reading.

### 2. CJK Pinyin Casing and Spacing

**Affected**: Chinese, Japanese (~26 differences)

Unidecode capitalizes every pinyin syllable and appends a trailing space (`Zhong `, `Hua `). translit uses lowercase (`zhong`, `hua`) and handles spacing contextually between ideographs.

| Input | translit | Unidecode |
|-------|----------|-----------|
| 中华 | `zhong hua` | `Zhong Hua ` |

translit's approach is correct for running text. Unidecode's per-character capitalization was designed for isolated lookups, not sentence transliteration.

### 3. Language-Specific Rules

**Affected**: Swedish, Danish, Estonian, Icelandic, Bulgarian, Ukrainian, Russian, Greek (~25 differences)

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

### 4. Ethiopic Syllable Handling

**Affected**: Amharic (~21 differences)

Ethiopic (Ge'ez) script encodes consonant+vowel as a single syllable character. translit and Unidecode disagree on whether to include the inherent vowel:

| Input | translit | Unidecode |
|-------|----------|-----------|
| ት (te) | `t` | `te` |
| ራ (raa) | `ra` | `raa` |
| መ (ma) | `me` | `ma` |

Both approaches are defensible. translit strips the inherent 6th-order vowel from consonant-final forms.

### 5. Khmer Consonant Errors in Unidecode

**Affected**: Khmer (~12 differences)

Unidecode has several Khmer mappings that appear incorrect:

| Char | Unicode Name | translit | Unidecode |
|------|-------------|----------|-----------|
| ព (po) | KHMER LETTER PO | `pa` | `b` |
| ប (ba) | KHMER LETTER BA | `ba` | `p` |
| ទ (to) | KHMER LETTER TO | `ta` | `d` |

Unidecode swaps voicing for some Khmer consonants (mapping po→b, ba→p), which is likely a data error.

### 6. Javanese: Full Coverage Gap

translit maps all 5 Javanese consonants tested; Unidecode maps none (returns `[?]` for the entire Javanese block). This is a complete coverage gap in Unidecode.

## Methodology Notes

- All tests use the `lang` parameter for translit (language-aware mode), which is the recommended usage
- Unidecode and anyascii have no language parameter
- "Mapped" means the library produced meaningful ASCII (not empty, not `[?]`, not the original character unchanged)
- Character-level comparison tests individual characters, not word/sentence-level context. translit's virama handling (stripping inherent vowels before halant) is exercised at the word level in the full test suite
- Regenerate this report: `python benchmarks/diff_vs_unidecode.py --markdown`

---

*Generated by `benchmarks/diff_vs_unidecode.py`*
