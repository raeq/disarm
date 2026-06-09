# Abjad Script Transliteration

translit provides two transliteration modes for abjad scripts — Arabic, Persian (Farsi), and Hebrew — where standard writing omits most vowels.

## The problem with abjad scripts

Arabic, Persian, and Hebrew are written in **abjad** scripts: the alphabet primarily represents consonants. Short vowels are either omitted entirely or indicated by optional diacritical marks (Arabic *tashkeel*, Hebrew *niqqud*) that most published text does not include.

This means a single written word can represent multiple spoken words:

| Arabic | Consonant skeleton | Possible readings |
|---|---|---|
| كتب | k-t-b | **kataba** (he wrote), **kutub** (books), **kutiba** (was written), **kuttāb** (writers) |
| درس | d-r-s | **dars** (lesson), **darrasa** (he taught), **durūs** (lessons) |
| علم | ʿ-l-m | **ʿilm** (knowledge), **ʿalam** (flag), **ʿallama** (he taught) |

Standard character-by-character transliteration — the approach used by Unidecode, anyascii, and translit's default mode — can only produce the consonant skeleton: `ktb`, `drs`, `'lm`. This is unreadable to anyone who doesn't already know the word.

## Two modes

### Context-free (default)

```python
from translit import transliterate
assert transliterate("كتب العربية") == "ktb al'rbyh"
assert transliterate("שלום", lang="he") == "shlvm"
assert transliterate("کتاب فارسی", lang="fa") == "ktab farsy"
```

This is the same approach as every other transliteration library. Each character maps to a fixed ASCII equivalent via a lookup table. No context, no dictionary, no ambiguity resolution. Fast (O(1) per character), deterministic, and produces the same output as Unidecode for these scripts.

**When to use:** Machine processing where human readability is not required (search indexing, deduplication, database keys).

### Context-aware (`context=True`)

<!--- skip: next -->
```python
# Requires context dictionaries (see bootstrap_dicts.sh and TRANSLIT_DICT_DIR)
transliterate("كتب العربية", context=True)              # "kataba al'arabiyahi"
transliterate("שלום", lang="he", context=True)           # "shalvom"
transliterate("کتاب فارسی", lang="fa", context=True)     # "ketab farsy"
```

This mode uses a **dictionary-based vowel restoration** system to recover the missing vowels before transliterating. The result is readable romanized text rather than a consonant skeleton.

**When to use:** Any application where a human will read the output — display, NLP preprocessing, content moderation, transliteration for non-native readers.

**Requires the prebuilt context dictionaries**, which are **not** shipped in the
PyPI wheel (they are ~37 MB). Context mode is therefore not available from a plain
`pip install`; build the dictionaries from a source checkout and point
`TRANSLIT_DICT_DIR` at them:

```bash
git clone https://github.com/raeq/translit && cd translit
bash scripts/bootstrap_dicts.sh           # builds data/{arabic,persian,hebrew}_dict.bin
export TRANSLIT_DICT_DIR="$PWD/data"      # transliterate(context=True) now finds them
```

The dictionaries are loaded only from `TRANSLIT_DICT_DIR` (or, in a source build,
the crate's own `data/` directory) — never from a current-working-directory
relative path, so an attacker who controls the working directory cannot inject a
substitute dictionary. For a self-contained build, compile the extension with the
`embed-dicts` Cargo feature.

> Packaging the dictionaries for `pip install` is tracked in
> [issues #56/#60](https://github.com/raeq/translit/issues/56).

## How context-aware transliteration works

### Architecture

The system uses a three-tier fallback for each word:

1. **Bigram lookup**: check if the combination of the *previous word* and the *current word* (both as consonant skeletons) has a known best reading. This resolves ambiguity using context — for example, after the Arabic article ال, the word كتب is more likely to be *kutub* (books) than *kataba* (he wrote).

2. **Unigram lookup**: if no bigram match, look up the current word's skeleton in a frequency-ranked dictionary. The most common reading is selected.

3. **Context-free fallback**: if the word is not in the dictionary at all, the existing character-by-character transliteration is used. The output is never worse than the default mode.

### Dictionary sources

| Language | Source corpus | Size | License |
|---|---|---|---|
| Arabic | [Tashkeela](https://www.kaggle.com/datasets/linuxscout/tashkeela) — 65.7M diacritized words from 97 books | 182K unigrams, 200K bigrams | CC-BY |
| Hebrew | [Project Ben Yehuda](https://github.com/projectbenyehuda/public_domain_dump) — 11.4M niqqud-pointed words from 26K literary texts | 227K unigrams, 200K bigrams | Public domain |
| Persian | Curated vocabulary — 266 common words with diacritics applied per BGN/PCGN 1958 | 257 unigrams | Hand-curated |

Dictionaries are built reproducibly from source corpora via `scripts/bootstrap_dicts.sh`. All parameters and expected checksums are pinned. See [Building dictionaries](#building-dictionaries) below.

---

## Arabic

### Standard used

**BGN/PCGN Arabic romanization (1956)** for consonant mappings. This is the system used by the US Board on Geographic Names and the UK Permanent Committee on Geographical Names. It uses digraphs for emphatic and pharyngeal consonants: ث→th, خ→kh, ذ→dh, ش→sh, غ→gh.

### How it differs from other systems

| Feature | translit (context-free) | translit (context-aware) | Buckwalter | ALA-LC / Library of Congress |
|---|---|---|---|---|
| Vowels | Omitted (consonant skeleton) | Restored from dictionary | Omitted | Required in source |
| Emphatics | Merged with plain (ص→s, ط→t) | Same | Distinct single chars (S, T) | Underdots (ṣ, ṭ) |
| Shadda (gemination) | Dropped | Preserved via diacritized form | `~` | Doubled consonant |
| Output charset | ASCII | ASCII | ASCII | Requires diacritics |
| Context needed | No | Yes (dictionary) | No | Yes (human judgment) |

### Context-aware accuracy

The Arabic dictionary covers 99%+ of newspaper vocabulary. The bigram table resolves the most common ambiguities:

```python
# Without context
assert transliterate("السلام عليكم") == "alslam 'lykm"
```

<!--- skip: next -->
```python
# With context — vowels restored, readable (requires context dictionaries)
transliterate("السلام عليكم", context=True)  # "alsalaamu 'alaykum"
```

### What it cannot do

- **Recover vowels not in the dictionary**: Rare proper nouns, neologisms, and code-mixed text will fall back to consonant skeletons.
- **Sentence-level disambiguation**: The bigram model captures adjacent-word context but not full sentence meaning. For كتب after a subject pronoun (he wrote) vs after an article (the books), bigrams usually resolve correctly, but complex sentences may not.
- **Dialect variation**: The dictionary is built from Modern Standard Arabic (MSA) sources. Dialectal Arabic (Egyptian, Gulf, Levantine) uses different vowel patterns that are not covered.

---

## Persian (Farsi)

### Standard used

**BGN/PCGN Persian romanization (1958, updated 2019)**. Persian shares the Arabic script but differs in four key ways:

1. **Four extra letters**: پ (p), چ (ch), ژ (zh), گ (g) — sounds that don't exist in Arabic.
2. **Different vowel system**: Persian has 6 vowels — three short (/æ, e, o/) and three long (/ɒː, iː, uː/). The critical difference from Arabic: Persian kasra = **e** (not i), Persian damma = **o** (not u).
3. **Waw is v, not w**: و is pronounced /v/ in Persian (consonant position), not /w/ as in Arabic.
4. **The ezafe**: A connecting vowel (-e after consonants, -ye after vowels) links nouns to their modifiers. Written as a kasra or with ه‌ی but often unmarked.

### How translit handles Persian

The `lang="fa"` profile overrides 51 character mappings from the Arabic default:

| Character | Arabic default | Persian override | Reason |
|---|---|---|---|
| ث (thā) | th | **s** | Persian pronunciation |
| ذ (dhāl) | dh | **z** | Persian pronunciation |
| ض (ḍād) | d | **z** | Persian pronunciation |
| و (wāw) | w | **v** | Persian pronunciation |
| kasra (ِ) | i | **e** | Persian 6-vowel system |
| damma (ُ) | u | **o** | Persian 6-vowel system |
| tāʾ marbūṭa | h | **e** | Persian feminine ending |

### Context-aware Persian

Unlike Arabic and Hebrew, no large diacritized Persian corpus exists. Persian rarely uses diacritics even in formal text. translit addresses this with a **curated vocabulary** of 266 common words with diacritics applied following BGN/PCGN pronunciation rules:

```python
# Without context
assert transliterate("کتاب فارسی", lang="fa") == "ktab farsy"
```

<!--- skip: next -->
```python
# With context — vowels from curated dictionary (requires context dictionaries)
transliterate("کتاب فارسی", lang="fa", context=True) # "ketab farsy"
```

For words not in the curated vocabulary, the system falls back to the Arabic context dictionary. Since approximately 40% of Persian vocabulary is Arabic-origin, many loanwords benefit from the Arabic dictionary automatically.

### Limitations specific to Persian

- **Smaller dictionary**: 266 curated entries vs Arabic's 182K corpus-derived entries. Common words are covered; rare words fall back to context-free.
- **No ezafe prediction**: The ezafe construction (-e/-ye connecting nouns to adjectives/possessors) is not predicted. It would require syntactic analysis beyond dictionary lookup.
- **Waw ambiguity**: و serves as both consonant (/v/) and vowel (/o, u/). The `lang="fa"` override maps it to v; the context dictionary provides the correct vowel form for known words.

---

## Hebrew

### Standard used

The default Hebrew mappings follow **common Israeli romanization** conventions. Hebrew has the same fundamental abjad challenge as Arabic: the consonantal alphabet with optional niqqud (vowel points) that most text omits.

### How context-aware Hebrew works

The Hebrew dictionary is built from [Project Ben Yehuda](https://github.com/projectbenyehuda/public_domain_dump), a public domain collection of 26,000+ Hebrew literary works with niqqud. The dictionary maps unpointed consonant skeletons to their most common niqqud-pointed forms:

```python
# Without context
assert transliterate("שלום", lang="he") == "shlvm"
```

<!--- skip: next -->
```python
# With context — niqqud restored from dictionary (requires context dictionaries)
transliterate("שלום", lang="he", context=True) # "shalvom"
```

### Differences from Arabic

| Feature | Arabic | Hebrew |
|---|---|---|
| Vowel marks | Tashkeel (fatha, kasra, damma, etc.) | Niqqud (patach, segol, hiriq, etc.) |
| Gemination | Shadda (ّ) | Dagesh (ּ) |
| Dictionary size | 182K unigrams (65.7M-word corpus) | 227K unigrams (11.4M-word corpus) |
| Ambiguity level | High (many homographs) | Moderate (fewer morphological patterns) |

### Limitations specific to Hebrew

- **Literary bias**: The Ben Yehuda corpus is predominantly literary (19th-20th century). Modern Hebrew slang, technical terms, and recent loanwords may not be covered.
- **No morphological analysis**: Hebrew verbs follow predictable root+pattern templates (*binyanim*) that could theoretically be used to predict vowels for unknown words. The current system does not exploit this — it relies purely on dictionary lookup.

---

## Building dictionaries

All dictionaries are built reproducibly from source corpora:

```bash
# Build all dictionaries from scratch (downloads corpora, builds, verifies checksums)
bash scripts/bootstrap_dicts.sh all

# Build individually
bash scripts/bootstrap_dicts.sh arabic    # Tashkeela corpus → arabic_dict.bin
bash scripts/bootstrap_dicts.sh persian   # Curated vocab → persian_dict.bin
bash scripts/bootstrap_dicts.sh hebrew    # Ben Yehuda → hebrew_dict.bin

# Verify existing dictionaries match expected checksums
bash scripts/bootstrap_dicts.sh verify
```

The bootstrap script pins all parameters (corpus source, min-frequency threshold, max bigram count) and expected output checksums. Changing any parameter requires updating the checksum — making all dictionary changes visible and auditable.

## How translit differs from other approaches

| Approach | Used by | Strengths | Weaknesses |
|---|---|---|---|
| **Character-by-character** | Unidecode, anyascii, translit (default) | Fast, deterministic, no data dependency | Consonant skeletons for abjad scripts |
| **Dictionary + bigram** | **translit (context=True)** | Readable output, no ML dependency, fast | Dictionary size, no sentence-level context |
| **Neural diacritization** | libtashkeel, Rababa, Mishkal | Handles unknown words, sentence context | Requires ONNX runtime (~15MB+), slower, non-deterministic |
| **Rule-based morphology** | Buckwalter Analyzer, MADAMIRA | Linguistically precise | Complex, language-specific, slow |
| **Human transcription** | ALA-LC, scholarly publications | Perfect accuracy | Not automatable |

translit's dictionary+bigram approach occupies the middle ground: substantially better than character-by-character for human-readable output, without the weight and complexity of neural or morphological systems. The three-tier fallback ensures graceful degradation — the output is never worse than the default mode.
