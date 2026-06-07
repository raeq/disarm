# Known Limitations

This document covers the known limitations of translit's transliteration, encoding detection, normalization, confusable handling, and text segmentation. Understanding these boundaries helps you choose the right tool and set expectations for edge cases.

Where possible, each section references the academic and technical literature that establishes or quantifies the limitation.

## Encoding Detection

### Detection is inherently probabilistic

Automatic encoding detection cannot be deterministic. A given byte sequence may be valid under multiple encodings simultaneously, and no algorithm can recover the original encoding without external metadata. translit's `detect_encoding` wraps [chardetng](https://hsivonen.fi/chardetng/), Firefox's production encoding detector.

Sivonen's analysis of chardetng shows document-length accuracy exceeds 98% for most language/encoding pairs, but title-length detection (roughly 5-20 bytes of non-ASCII content) is substantially weaker. Lithuanian drops to 48% and Latvian to 61% on short inputs due to overlapping character repertoires in windows-1257 and ISO-8859-4. GBK short-input accuracy is deliberately traded for binary size (88% vs Google's ced at 95%).

The confidence score returned by `detect_encoding` should not be treated as reliable for inputs under ~20 bytes of non-ASCII content. chardetng converges to document-level accuracy with approximately 10 non-ASCII bytes for CJK and 20 for Latin-script encodings.

**Notable limitation**: chardetng's accuracy was evaluated on the same Wikipedia dataset used for training, unlike ced's testing against independent corpora. Real-world accuracy on domain-specific content (e.g., machine-generated logs, mixed-encoding streams) may differ.

### Encoding coverage is web-focused

chardetng targets encodings historically deployed as browser defaults per the [WHATWG Encoding Standard](https://encoding.spec.whatwg.org/). It does not detect macintosh encoding, ISO-8859-3, or the font-hack encodings used in South Asian web content. Content from .in and .lk domains may be misidentified.

## Transliteration

For a detailed character-level comparison of translit's transliteration against Unidecode and anyascii across all 83 supported languages, including analysis of systematic difference patterns and intentional design choices, see the [Transliteration Comparison](architecture/transliteration-comparison.md).

### Context-free mapping: a fundamental tradeoff

All of translit's transliteration is strictly character-by-character with no context awareness. The survey by [Jaf et al. (2025)](https://www.researchgate.net/publication/392346405_Advances_in_machine_transliteration_methods_limitations_challenges_applications_and_future_directions) identifies the core problem: there is no one-to-one phoneme-to-grapheme correspondence between scripts. Sounds present in one language may not exist in another, and a single source grapheme may map to 0, 1, or multiple target characters.

This is the same approach taken by Python's Unidecode, text-unidecode, anyascii, and similar libraries. The benefit is O(1) per-character lookup with no runtime dependencies. The cost is that disambiguation requiring sentence-level context is impossible.

### Missing diacritics and short vowels

Arabic, Hebrew, and Urdu romanization is heavily context-dependent without vowel pointing. [Jaf et al. (2021)](https://onlinelibrary.wiley.com/doi/10.1155/2021/7152935) demonstrate this specifically for Ottoman Turkish script, where character-level mapping produces poor results for scripts with suppressed vowels. translit's Arabic transliteration is best-effort and does not recover unwritten short vowels.

### Hebrew matres lectionis and contextual vowels

Hebrew uses *matres lectionis* — consonant letters (yod, vav, he) that function as vowel markers in certain positions. For example, vav with a dagesh (שׁוּרֶק *shureq*) represents /u/, and ḥolam followed by vav (חוֹלָם מָלֵא) represents /o/. These multi-character sequences require lookahead to distinguish from their consonantal uses.

translit's character-by-character engine maps each codepoint independently, so it cannot detect these contextual patterns. Pointed Hebrew text (with nikkud vowel marks) will produce the correct vowel from the nikkud itself, but the accompanying mater lectionis consonant will also appear in the output (e.g., an extra "y" or "v"). Unpointed Hebrew produces a consonant skeleton only.

For scholarly-grade Hebrew transliteration with full contextual rules (hiriq-yod, shureq, qamats-he, dagesh forte doubling), use a dedicated Hebrew transliterator such as [hebrew-transliteration](https://github.com/charlesLoder/hebrew-transliteration).

### Competing standards

Even within a single language, multiple romanization standards exist. Russian alone has BGN/PCGN, GOST, ISO 9 (scholarly), passport transliteration, and several informal systems. translit's `lang` parameter selects one standard per language; `strict_iso9=True` provides a scholarly ASCII Cyrillic transliteration (ISO 9-style digraphs such as ж→zh, ч→ch; **not** the diacritic ISO 9:1995 standard — translit tables are ASCII-only). Users needing a specific standard not offered by the default or `lang` can use `register_lang()` to override.

The [IndoNLP 2025 shared task](https://arxiv.org/html/2501.05816) on reverse transliteration for romanized Indo-Aryan languages highlights an additional dimension: informal romanization (e.g., Hindi in Latin script on social media) follows no standard. Round-tripping from such text is a fundamentally different problem from transliteration.

### Low-resource script coverage

The [South Asian languages survey (2025)](https://arxiv.org/html/2509.11570v1) confirms that corpus coverage and script fidelity remain binding constraints for transliteration of languages with limited digital presence.

As of v0.3.0, translit added 2,553 codepoints: 11 new Unicode form/extension blocks (fullwidth, IPA, Greek Extended, Kangxi Radicals, CJK Compatibility Ideographs, etc.), gap-filled 7 partially-covered scripts, and added 14 new scripts — 10 abugida (Sundanese, Tai Tham, Cham, Batak, Buginese, Tagalog, Hanunoo, Buhid, Tagbanwa, Meetei Mayek) and 4 alphabetic/syllabic (Tifinagh, Lisu, Ol Chiki, Bamum). Scripts that still have no transliteration mapping (characters produce `[?]`):

- Most CJK Extension blocks (B through I)

The `register_lang()` API allows users to add custom mappings for these scripts at runtime.

### Lossy by design

Transliteration to ASCII is inherently lossy. Multiple source characters map to the same ASCII output:

- German ä, Swedish ä, Finnish ä all → `a` (unless `lang` is specified)
- Greek η and ι both → `i` with `lang="el"`
- Multiple Chinese characters share the same pinyin (e.g., 是/事/式/试 all → `shi`)

Round-tripping (ASCII → original script) is not possible.

### Reverse transliteration is approximate

The `target` parameter enables Latin → native script conversion, but this is inherently lossy due to the many-to-one nature of forward transliteration.

**Many-to-one forward mappings are not invertible.** Multiple source characters map to the same Latin output:

- Russian: both Й and Ы → `Y` forward; reverse always produces Ы
- Russian: both Э and Е → `E` forward; reverse always produces Е
- Greek: η and ι both → `i`; reverse cannot distinguish between them

**Empty-string mappings are permanently lost.** Characters that map to empty string in forward transliteration cannot be recovered:

- Russian soft sign Ь and hard sign Ъ → `""` forward
- Example: `тьма` → `tma` → `тма` (soft sign lost)

**Digraph ambiguity.** Forward `сх` → `skh` but reverse `kh` → `х`; greedy scanning may not match the original segmentation.

**Round-trip example:**

```python
from translit import transliterate

text = "Тьма"
fwd = transliterate(text, lang="ru")        # "Tma"
rev = transliterate(fwd, target="ru")       # "Тма" (soft sign lost)
fwd2 = transliterate(rev, lang="ru")        # "Tma" (looks same but Ь is gone)
```

**Guidance:** Reverse transliteration is useful for recovering romanized text written in a standard transliteration scheme, not for lossless round-tripping. Note that `strict_iso9=True` is an ASCII (digraph) scheme, **not** a reversible diacritic standard — digraphs like ж→zh are not uniquely invertible. For recovering native script from romanized Latin, use reverse transliteration (`target=`, ru/uk/el).

## CJK Transliteration

### Chinese (Hanzi → Pinyin)

**Context-free, single-reading mapping.** Each Chinese character is assigned exactly one pinyin reading from the Unicode Unihan `kMandarin` field. Chinese is inherently polyphonic — the same character can have different readings depending on context:

| Character | Our output | Possible readings |
|-----------|-----------|-------------------|
| 行        | xing      | xíng (walk), háng (row/profession) |
| 了        | le        | le (aspect particle), liǎo (to finish) |
| 长        | chang     | cháng (long), zhǎng (to grow) |
| 还        | hai       | hái (still), huán (to return) |
| 得        | de        | de (particle), dé (obtain), děi (must) |

Disambiguation requires word segmentation and sentence-level context, which is outside translit's scope. For applications that need contextual pinyin (e.g., text-to-speech, language learning tools), use a dedicated library such as `pypinyin` (Python) or the `pinyin` crate (Rust).

**Tone marks.** By default, pinyin output is tone-stripped ASCII: `北京` becomes `bei jing`, not `běi jīng`. This is intentional for the primary use cases (URLs, filenames, slugs) where diacritics are unwanted. Pass `tones=True` for diacritical pinyin (`transliterate("北京", tones=True)` → `"běi jīng"`). Toned pinyin coverage includes the ~2,000 most common characters; others fall through to toneless pinyin.

**Coverage is the CJK Unified Ideographs main block only** (U+4E00–U+9FFF, ~20,924 characters). Characters in Extension A (U+3400–U+4DBF), Extension B (U+20000–U+2A6DF), and later extensions are not mapped and will produce `[?]` in replace mode. These extensions contain rare, archaic, or variant characters that appear infrequently in modern text.

**Word boundaries are character-level.** Each character gets a space-separated pinyin syllable: `北京烤鸭` → `bei jing kao ya`. Chinese does not use spaces between words, and translit does not perform word segmentation. The slugifier handles this well (`bei-jing-kao-ya`), but the raw transliteration output may look unusual to native speakers who would expect `Beijing kǎoyā`.

### Korean (Hangul → Revised Romanization)

**No inter-syllable phonological rules.** Korean pronunciation changes based on adjacent syllables (연음법칙 liaison, 경음화 tensification, 비음화 nasalization, etc.). translit performs syllable-by-syllable decomposition without these rules:

| Word   | Our output   | Correct pronunciation |
|--------|-------------|----------------------|
| 독립   | dog lib      | dongnip (nasalization) |
| 같이   | gat i        | gachi (palatalization) |
| 학교   | hag gyo      | hakgyo (no change — this one is correct) |

For URL slugs and filenames, the character-level output is adequate. For linguistic or phonetic applications, use a Korean morphological analyzer.

**Revised Romanization only.** translit implements the South Korean government's Revised Romanization (RR, 2000). McCune-Reischauer, Yale, and other romanization systems are not available. RR is the most widely used system internationally and is the ISO/TR 11941 recommendation.

### Japanese (Kanji)

**Kanji falls back to Chinese pinyin readings.** Japanese kanji share Unicode codepoints with Chinese Han characters. Since translit's Hanzi table is Chinese-based:

| Character | Our output | Japanese reading |
|-----------|-----------|-----------------|
| 東京      | dong jing  | toukyou (Tokyo) |
| 漢字      | han zi     | kanji |
| 山        | shan       | yama / san |

Hiragana and katakana transliteration (Modified Hepburn) is correct and complete. Only kanji readings are affected by this limitation.

For correct Japanese kanji readings, a morphological dictionary (e.g., MeCab, kuromoji) is required. This is fundamentally different from character-by-character mapping and is outside translit's design.

## Unicode Normalization

### Normalization is not losslessly invertible

[UAX #15](https://unicode.org/reports/tr15/) defines the four normalization forms. The critical distinction: NFC↔NFD round-tripping is stable, but NFKC/NFKD permanently destroy information. NFKC replaces compatibility characters with canonical equivalents: ﬁ→fi, ½→1/2, ℃→°C. This is desirable for NLP and search indexing but destructive when visual fidelity matters.

The [WG21 paper P2729R0](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2729r0.html) documents a real-world case where OS X normalized Unicode filenames via NFD while file-sharing software did not recognize the altered filenames as equivalent to the originals, leading to data loss. Resolving such mismatches is non-trivial precisely because normalization is one-way for compatibility variants.

**translit implication**: `ml_normalize` uses NFKC deliberately — compatibility decomposition is desired for NLP pipelines. Users should understand that NFKC is destructive and not appropriate when typographic distinctions must be preserved.

### Normalization is language-sensitive

Whether accents are semantically significant varies across languages. In French, é and e are distinct phonemes. In Turkish, the İ→i vs I→ı distinction is critical and interacts with case folding. Unicode case folding (which `fold_case()` implements via all 1,557 CaseFolding.txt mappings) handles Turkish İ correctly per the Unicode standard, but applying `strip_accents()` indiscriminately to multilingual datasets can destroy meaningful distinctions.

Multilingual datasets may require per-language normalization strategies. Language-agnostic normalization is always a compromise.

### Unicode version dependency

Normalization depends on the version of the `unicode-normalization` Rust crate compiled into the library. Different Unicode versions may normalize certain characters differently, particularly for recently added scripts.

## Case Folding

### Default (non-Turkic) folding only

`fold_case()` implements the default (non-Turkic) Unicode case folding rules from CaseFolding.txt status C and F entries. The Turkic-specific mappings (status T: I→ı and İ→i without combining dot above) are not applied. The İ→i̇ mapping in the default table is correct for most languages but differs from the Turkic convention. Applications processing Turkish or Azerbaijani text that require Turkic-specific behavior should apply their own İ/I handling.

### Cherokee folding direction

Cherokee case folding is unusual: CaseFolding.txt maps the *small* letter forms (U+AB70–U+ABBF, added in Unicode 8.0) to the original uppercase forms (U+13A0–U+13EF), not the other way around. The uppercase forms have no folding entry and map to themselves. This matches the Unicode specification and `str.casefold()` behavior but may be surprising for scripts where uppercase→lowercase is the expected direction.

### Not locale-aware

Case folding is a locale-independent operation by design. Unlike `str.lower()` with locale settings, `fold_case()` always applies the same mappings regardless of the user's locale. This is the correct behavior for case-insensitive matching per the Unicode standard but may not match user expectations in specific locale contexts.

### PHF table is static

The case folding table is generated at compile time from Unicode 16.0 CaseFolding.txt. New case folding mappings added in future Unicode versions will not be available until the data file and library are rebuilt.

## Confusable/Homoglyph Detection

### The confusable space is combinatorially large

The foundational problem is established in the [Unicode Technical Report #39](https://www.unicode.org/reports/tr39/) and analyzed by [Haase et al.](https://www.researchgate.net/publication/221194427_Finding_Homoglyphs_-_A_Step_towards_Detecting_Unicode-Based_Visual_Spoofing_Attacks), who demonstrated systematic methods for identifying visually similar characters across scripts. Cyrillic is the most exploited alphabet — 11 lowercase glyphs are identical or near-identical to Latin (а, с, е, о, р, etc.). Xudong Zheng's 2017 demonstration showed that `аррӏе.com` (entirely Cyrillic) displayed identically to `apple.com` in Chrome's address bar while resolving to a different server.

The [MDPI homoglyph detection paper (2022)](https://www.mdpi.com/2224-2708/11/3/54) proposes ML-based detection using hash functions but notes the fundamental difficulty: the confusable space grows combinatorially with string length.

**translit implication**: `normalize_confusables()`, `is_confusable()`, and `is_safe_hostname()` use the TR39 confusables table, which is the standard mitigation. However, confusable detection is necessarily conservative. Legitimate multilingual text (e.g., a Russian name in an otherwise English sentence) will trigger warnings. False positives are an inherent tradeoff of any confusable detection system.

### Mixed-script detection is heuristic

`is_mixed_script()` reports whether multiple scripts are present in a string. It does not assess whether the mixing is benign (e.g., Latin punctuation in Arabic text, which is universal) or malicious (Cyrillic spoofing Latin). The `is_safe_hostname()` function applies stricter heuristics but its safe/unsafe classification is still a best-effort judgment, not a cryptographic guarantee.

## Bidirectional Text Security

### Bidi overrides are a real attack vector

[Boucher & Anderson (USENIX Security 2023)](https://www.usenix.org/conference/usenixsecurity23/presentation/boucher) demonstrated that Unicode bidi override characters (U+202A–U+202E, U+2066–U+2069) injected into source code, filenames, and chat messages can make text appear to have different content than it actually contains. Their "Trojan Source" attack produced working exploits in C, C++, C#, JavaScript, Java, Rust, Go, Python, SQL, Bash, Assembly, and Solidity. CVE-2021-42574 was assigned; Rust rejected bidi overrides in source by default from version 1.56.1.

Beyond source code, bidi overrides can disguise malicious filenames. The sequence `invoice[RLO]fdp.exe` renders visually as `invoiceexe.pdf` in many text renderers.

**translit implication**: `strip_bidi()` and the `security_clean()` pipeline strip these characters. This is the correct mitigation for user-submitted content destined for display. Soft hyphens (U+00AD), which can enable text-reordering attacks in some renderers, are also stripped.

### Stripping is destructive for legitimate bidi text

Arabic, Hebrew, and other right-to-left scripts legitimately use bidi formatting characters for correct display of mixed-direction text. `strip_bidi()` is designed for security contexts (usernames, filenames, URL display) where bidi overrides are dangerous. It should not be applied to body text in languages that require bidi formatting.

## Grapheme Cluster Segmentation

### User-perceived character ≠ codepoint

[UAX #29](https://www.unicode.org/reports/tr29/) defines extended grapheme cluster boundaries, but [Lindenberg (2023)](https://www.unicode.org/L2/L2023/23140-graphemes-expectations.pdf) documents the persistent gap between user expectations and technical reality. Key problem areas: Indic consonant clusters, emoji ZWJ sequences (👨‍👩‍👧‍👦 is 7 codepoints but 1 grapheme), and the fact that precomposed vs decomposed sequences may or may not form different cluster boundaries depending on normalization state.

[Hashimoto's terminal emulator analysis](https://mitchellh.com/writing/grapheme-clusters-in-terminals) demonstrates that virtually all terminal emulators get this wrong for complex emoji, rendering ZWJ family sequences as multiple characters rather than one.

**translit implication**: `grapheme_len()`, `grapheme_split()`, and `grapheme_truncate()` use the `unicode-segmentation` crate implementing UAX #29 extended grapheme clusters. This is the correct implementation for the specification, but "user-perceived character" is ultimately a rendering question and not all systems agree on cluster boundaries — particularly for newer emoji sequences.

### Emoji tables require version updates

New ZWJ emoji sequences are added with each Unicode version. The `unicode-segmentation` crate's tables must be updated to correctly segment newly standardized sequences. Between crate updates, a brand-new emoji ZWJ sequence may be split across multiple grapheme clusters.

## Filename Sanitization

### Platform-specific behavior

`sanitize_filename()` produces filenames safe for Windows, macOS, and Linux simultaneously. This means it applies the most restrictive rules from all platforms:

- Windows reserved names (CON, PRN, NUL, COM1–COM9, LPT1–LPT9) are prefixed with `_` on all platforms, even POSIX systems where they are valid
- The maximum filename length defaults to 255 bytes, which is the common limit across ext4, NTFS, and APFS
- NFC normalization is always applied, even on Linux where the filesystem is encoding-agnostic

### Truncation is byte-aware but not grapheme-aware

When `max_length` forces truncation, the stem is shortened to fit. Truncation respects UTF-8 byte boundaries (never splits a multi-byte character) but does not consider grapheme clusters. A truncation point could split a base character from its combining mark.

### No round-trip guarantee

`sanitize_filename()` is a one-way function. Given only the output, you cannot reconstruct the original input. Multiple distinct inputs can produce the same sanitized filename.

## Slugification

### Separator collapsing

Consecutive non-alphanumeric characters are collapsed into a single separator. This means distinct punctuation sequences in the original text become indistinguishable:

- `"hello...world"` and `"hello—world"` both → `"hello-world"`

### Maximum length truncation

When `max_length` is set, slugs are truncated to that byte length. With `word_boundary=True`, truncation will look for the last separator within the allowed length to avoid cutting mid-word. Without `word_boundary`, a word may be cut mid-syllable.

### Regex pattern limitations

The `regex_pattern` parameter uses Rust's `regex` crate syntax, which differs from Python's `re` module in some edge cases (notably: no lookbehind assertions of variable length, different Unicode property syntax).

## CLDR Emoji Annotations

Emoji demojization uses CLDR short names. These are English-language descriptions only. Localized emoji names are not supported. The `set_emoji_provider()` API allows users to supply custom name mappings for localization.

## Performance Characteristics

### Memory usage

The Hanzi→Pinyin PHF table adds approximately 200KB to the compiled binary. The Hangul romanization is algorithmic and adds negligible memory overhead.

### Hangul caching

The Hangul romanization module caches computed romanizations in a `RwLock<HashMap>`. Each unique Hangul syllable is computed once and stored as a leaked `&'static str`. The cache is bounded by the 11,172 possible Hangul syllables × ~8 bytes average, giving an upper bound of ~100KB.

### Compile time

PHF tables are generated at build time by `build.rs` using `phf_codegen`. The build script reads TSV data files from `src/tables/data/`, computes perfect hash functions, and writes the generated maps to `$OUT_DIR`. Source files pull them in via `include!()`.

Because `build.rs` output is cached by Cargo, incremental rebuilds that only touch Rust source (not data files) skip PHF generation entirely. When a data file changes, `build.rs` re-runs and regenerates the affected maps before the main crate compilation.

Adding new PHF tables requires adding a TSV file to `src/tables/data/` and a corresponding `generate_*` call in `build.rs`. This does not increase incremental compile times for source-only changes.

## What translit Is Not

translit is a fast, context-free Unicode text processing toolkit. It is not:

- **A transliteration standard implementation**: it approximates multiple standards pragmatically rather than implementing any single standard perfectly
- **A natural language processing library**: it has no word segmentation, morphological analysis, or language detection
- **A phonetic transcription system**: output represents conventional romanization, not IPA or phonetic notation
- **A reversible encoding**: all operations are one-way lossy transformations
- **An encoding oracle**: encoding detection is probabilistic and can be wrong, especially on short inputs
- **A rendering engine**: grapheme cluster boundaries are defined by Unicode specification, not by what any particular font or terminal actually displays

## Language detection limitations

The `lang="auto"` feature uses a two-tier strategy:

1. **Script detection** — identifies the Unicode script (Cyrillic, Arabic, etc.)
2. **Character discrimination** — for ambiguous scripts, scans for characters exclusive to one language

This works well for languages with distinctive alphabets (Ukrainian, Serbian, Persian, Vietnamese, Turkish, German) but cannot distinguish languages that share identical character sets:

- **Russian vs. Bulgarian** — both use standard Cyrillic without exclusive characters
- **Hindi vs. Marathi vs. Nepali** — all use Devanagari with the same character inventory
- **French vs. Spanish vs. Portuguese vs. Italian** — all use Latin with overlapping accented characters

For these cases, pass an explicit language code (`lang="bg"`, `lang="mr"`, `lang="fr"`, etc.).

Character discrimination is also unable to detect a language if the input text happens not to contain any exclusive characters. For example, a short Ukrainian phrase that avoids ґ, ї, є, і will be detected as Russian. Again, use an explicit language code when precision matters.

## References

1. Sivonen, H. (2020). [chardetng: A Character Encoding Detector for the Encoding Standard](https://hsivonen.fi/chardetng/).
2. Jaf, S. et al. (2025). [Advances in machine transliteration methods, limitations, challenges, applications and future directions](https://www.researchgate.net/publication/392346405_Advances_in_machine_transliteration_methods_limitations_challenges_applications_and_future_directions). *Engineering Applications of Artificial Intelligence*.
3. Jaf, S. et al. (2021). [Machine-Based Transliterate of Ottoman to Latin-Based Script](https://onlinelibrary.wiley.com/doi/10.1155/2021/7152935). *Scientific Programming*.
4. IndoNLP. (2025). [Reverse Transliteration for Romanized Indo-Aryan Languages: Shared Task](https://arxiv.org/html/2501.05816).
5. Singh, A. et al. (2025). [South Asian Low-Resource Languages: Script and Corpus Challenges](https://arxiv.org/html/2509.11570v1).
6. The Unicode Consortium. [UAX #15: Unicode Normalization Forms](https://unicode.org/reports/tr15/).
7. Zabel, B. (2023). [P2729R0: Unicode in the Library, Part 2: Normalization](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2729r0.html). *ISO/IEC JTC1/SC22/WG21*.
8. Haase, M. et al. (2010). [Finding Homoglyphs: A Step Towards Detecting Unicode-Based Visual Spoofing Attacks](https://www.researchgate.net/publication/221194427_Finding_Homoglyphs_-_A_Step_towards_Detecting_Unicode-Based_Visual_Spoofing_Attacks).
9. Moussa, M. et al. (2022). [Homoglyph Attack Detection Using Machine Learning and Hash Functions](https://www.mdpi.com/2224-2708/11/3/54). *J. Sens. Actuator Netw.* 11(3), 54.
10. Boucher, N. & Anderson, R. (2023). [Trojan Source: Invisible Vulnerabilities](https://www.usenix.org/conference/usenixsecurity23/presentation/boucher). *USENIX Security Symposium*.
11. The Unicode Consortium. [UAX #29: Unicode Text Segmentation](https://www.unicode.org/reports/tr29/).
12. Lindenberg, N. (2023). [Setting Expectations for Grapheme Clusters](https://www.unicode.org/L2/L2023/23140-graphemes-expectations.pdf). *Unicode L2/23-140*.
13. Hashimoto, M. (2023). [Grapheme Clusters and Terminal Emulators](https://mitchellh.com/writing/grapheme-clusters-in-terminals).
14. The Unicode Consortium. [UTS #39: Unicode Security Mechanisms](https://www.unicode.org/reports/tr39/).
