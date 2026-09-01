# Key-stability fixture (#644)

The golden fixture behind `tests/test_key_stability.py`, which holds the contract
in [RUST_API.md](../../../docs/RUST_API.md) — *a patch release never changes
key-builder output; a minor release may.*

| file | what it is |
|---|---|
| `corpus.txt` | 22,977 rows: 22,478 natural word forms + 499 hand-built adversarial rows |
| `golden_keys.tsv.gz` | the corpus crossed with eight key-producing functions, generated on a pinned build |

Regenerate with `python scripts/gen_key_fixture.py`, and read
[that script's docstring](../../../scripts/gen_key_fixture.py) before you do —
running it to make a red test go green is the one use it does not have.

## Why the corpus is what it is

An earlier Latin-only corpus measured a `tr39` numeral tax of 0.00%, because it
contained no non-ASCII digit at all. That is the failure this one is built
against: a corpus that cannot express a class of input reports that class as
free.

```
LATIN 8850   ARABIC 1706   CYRILLIC 1695   DEVANAGARI 1482   BENGALI 860
ETHIOPIC 820  HEBREW 806   TAMIL 790   SINHALA 751   CJK 736
ARMENIAN 699  HANGUL 688   GEORGIAN 676   MYANMAR 647   THAI 493
```

153 rows carry a non-ASCII digit. The 400 hand-built rows cover Indic, Arabic,
Thai and Khmer numerals; every character observed to move a key between `v0.13.0`
and `0.14.0` (soft sign, hard sign, kra, micro sign, Greek mu); the filler block
from #643; bidi controls and embeddings; Tags, PUA and variation selectors; the
case-folding minefield (Turkish dotted I, Greek final sigma, Cherokee, ß/ẞ); brand
homoglyph spoofs; and NFKC amplification edges (`U+FDFA`, `U+1CCD6`, `U+A7F1`).

**The classes added in #806.** Three of the categories above were named here and barely
present — one tag character, one variation selector, two PUA code points — and
**noncharacters and soft hyphens did not appear at all**. Those are the classes most likely
to move a key, so a corpus without them reports them as free. #805 was a live key evasion
using a noncharacter, and against the old corpus its fixture diff would have been **0 rows
of 22,878**. 85 rows now carry noncharacters at each edge and inside a word, soft hyphens
in four words, and thicker coverage of PUA, tags, variation selectors, ZWSP, word joiner
and the BOM — each beside a clean control, so a diff shows two keys converging rather than
one key appearing.

**An invisible between two combining marks (#850).** 8 rows place a zero-width, ZWNJ,
ZWJ, soft hyphen or BOM *inside* a mark run rather than beside one. The corpus expressed
every character involved and never that arrangement, so a mark-capping step placed before
the invisible strip counted two short runs where there was one long one, and #843's
fixture diff was **0 rows of 22,963**. With the rows present that change moves 4.

**A cross-script mark between two mark runs (#862).** 6 rows place a mark whose own
script differs from its base *inside* a run of ordinary ones. It is a different class from
the #850 rows above: the #615 cross-script strip removes it in strict mode only, so it
splits the run for the count and is then deleted. The corpus expressed every character
involved and never that arrangement, so #862's fixture diff would have been **0 rows**.

**Burmese is load-bearing (#842).** The 669 Myanmar rows carry the deepest combining
sequences in the corpus: a syllable takes a base, a medial, two vowel signs and a tone.
They are what showed that a flat mark count cannot separate orthography from stacking —
`is_zalgo` called 142 of them zalgo and `strip_zalgo` deleted a tone mark from each. Keep
them.

`tests/test_key_stability.py` asserts a floor per class and the row count in the table
above, rather than this paragraph, so adding rows stays free and losing a class fails.

`tests/test_key_stability.py` asserts the breadth rather than trusting this
paragraph: a corpus that lost the soft sign, or its non-ASCII digits, or its
script spread, fails there rather than passing forever and meaning nothing.

## It catches the change it was built for

The fixture is generated on `0.14.0`. Checked against the published `0.13.0`
wheel, the gate reports:

```
sort_key               3026 of 22878 changed (13.23%)
canonicalize_strict     604                   (2.64%)
search_key              267                   (1.17%)
catalog_key             267                   (1.17%)
canonicalize            249                   (1.09%)
normalize_confusables   249                   (1.09%)
strip_obfuscation       164                   (0.72%)
```

Every one is a correctness fix — `'banĸ.example'` → `'bank.example'`,
`'podъezd'` → `'podezd'`, the eclipsing mark in `'exaّmple.com'`, the Hangul
fillers in `'adᅟmin'`. That is the point: all of them were invisible at review
time, and all of them invalidate stored keys.

`sort_key` moving 13% is the number worth looking at twice, and it is the
function that appears in no stability clause anywhere before #644.

## Two things to know before trusting it

Neither is a defect to fix. Both are trades, recorded so the next person inherits
the reasoning rather than the conclusion.

### It is not reproducible

The natural rows are tokenised from random Wikipedia article titles fetched
through the MediaWiki `list=random` endpoint. Re-running that fetch returns a
different sample, so no script regenerates `corpus.txt` identically. The
committed file *is* the fixture.

`scripts/gen_key_fixture.py` regenerates `golden_keys.tsv.gz` deterministically
*from* that corpus — that half is reproducible, and byte-identical across runs.
It is the corpus itself that cannot be rebuilt.

This is a deliberate trade rather than an oversight. A corpus generated from the
bundled tables would be reproducible and would test the tables against
themselves; real word forms in fifteen scripts do not, which is why this one
found things a derived corpus would not have.

### Its licence is not the repository's

| what | terms |
|---|---|
| Source | Wikipedia, 41 language editions. Article titles retrieved through the MediaWiki API and tokenised into individual word forms. |
| `corpus.txt` | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), per the Wikipedia [terms of use](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use) |
| Everything else here and in the repository | MIT, see [LICENSE](../../../LICENSE) |

The rows are individual short factual strings rather than prose, and those are
unlikely to attract copyright on their own. The attribution is here regardless:
the compiled set came from somewhere, and saying so costs nothing.

`golden_keys.tsv.gz` is a mechanical transformation of `corpus.txt` and inherits
its terms.

If the licence ever becomes inconvenient, the corpus can be replaced without
touching the gate: `tests/test_key_stability.py` reads whatever `corpus.txt`
contains, and the breadth assertions state what a replacement has to keep.
