# Normalize-First Canonicalization

Put Unicode normalization at the **front** of every text pipeline, run the
remaining steps in a fixed, grapheme-correct order, and decide up front whether
your output needs to be **reversible** or **script-pure**. disarm turns these
from tribal knowledge into guarantees: pipeline step order is single-source and
invariant-checked, and normalization provably never splits a grapheme cluster.

This page is a set of recipes built from existing functions — it introduces no
new API.

## Why normalize first

The same visible text can be encoded many ways (see
[Normalization](normalization.md)). Preprocessing that runs *before*
normalization — stripping, folding, transliterating, matching — sees those
inconsistent encodings and produces inconsistent results. Worse, naive
preprocessing can split an Indic conjunct or a combining-mark sequence, or mix
scripts, corrupting both security checks and downstream models.

Normalizing first collapses the representations to one canonical form, so every
later step operates on stable input.

## Guarantee 1 — the step order can't drift

[`TextPipeline`](pipeline.md) always runs its steps in a fixed, optimal order
**regardless of the order you pass the arguments** — normalization first, the
final whitespace cleanup last:

```python
from disarm import TextPipeline

pipe = TextPipeline(
    fold_case=True,           # passed first…
    normalize="NFKC",         # …but normalize always runs first
    confusables=True,
    collapse_whitespace=True,
)

assert [name for name, _param in pipe.steps] == ['normalize', 'confusables', 'fold_case', 'strip_control', 'strip_zero_width', 'collapse_whitespace']
```

The order a pipeline **reports** (`pipe.steps`) is, by construction, the order it
**executes** — both read from one shared list inside the engine. A step cannot be
reported at one position and run at another (the class of bug that #141 was). If
you are introspecting a pipeline to audit it, what you see is what runs.

## Guarantee 2 — normalization is grapheme-correct

Normalization **respects grapheme-cluster boundaries**. For every form
(NFC/NFD/NFKC/NFKD):

```python
import disarm

normalize_whole = lambda s, f: disarm.normalize(s, form=f)
normalize_parts = lambda s, f: "".join(
    disarm.normalize(g, form=f) for g in disarm.grapheme_split(s)
)

s = "क्ष"  # Devanagari conjunct: KA + virama + SSA
assert normalize_whole(s, "NFC") == normalize_parts(s, "NFC")
```

In plain terms: normalization never orphans a combining mark, never splits an
Indic conjunct, and never merges across cluster boundaries. This is verified
exhaustively over every Hangul syllable, every Devanagari conjunct, the full
combining-diacriticals block, and the whole BMP.

One intended exception to watch for: **NFKC/NFKD change the grapheme *count*** by
expanding compatibility characters (the ligature `ﬁ` becomes `fi`, two
clusters). That is normalization working as designed, not a boundary violation —
but it is one more reason to choose your form deliberately (below).

If you need to shorten text without cutting a cluster in half, use
[`grapheme_truncate`](../api/graphemes.md), which only cuts on boundaries.

## Recipe — script purity (one script in, one script out)

Mixed-script text is a classic spoofing vector (`pаypаl` with Cyrillic `а`).
Detect it with `is_mixed_script`, and fold it to a single script with
`normalize_confusables`:

```python
import disarm

raw = "pаypаl"                     # contains Cyrillic а (U+0430)

# Normalize first — NFKC folds compatibility variants (fullwidth, ligatures)
# so the script check sees canonical input, never a disguised bypass.
s = disarm.normalize(raw, form="NFKC")

assert disarm.is_mixed_script(s) == True

pure = disarm.normalize_confusables(s, target_script="latin")
assert pure == 'paypal'
assert disarm.is_mixed_script(pure) == False
```

- **Flag** with `is_mixed_script` when you only need to *reject* suspicious input
  (e.g. before storing a username). For hostnames, `is_suspicious_hostname` returns
  per-label mixed-script and confusable details.
- **Fold** with `normalize_confusables(target_script=...)` when you want to
  *coerce* input to a canonical script for comparison.

Normalize first, then check or fold — confusable detection is most reliable on
canonical input.

## Recipe — reversibility-preserving canonicalization (use NFC, not NFKC)

If you may need to convert text **back** to its native script later — disarm
supports reverse transliteration for Greek, Russian, and Ukrainian via
`transliterate(text, target=lang)` — canonicalize with **NFC**, never NFKC.

NFKC's compatibility folding is **lossy** and destroys the information a reversal
would need:

```python
import disarm

assert disarm.normalize("⁵", form="NFC") == '⁵'    # superscript five — preserved
assert disarm.normalize("⁵", form="NFKC") == '5'   # folded to ASCII — unrecoverable
```

An NFC-first canonicalization keeps the door open to a clean round-trip:

```python
native = "Москва"
canonical = disarm.normalize(native, form="NFC")        # canonical, lossless
romanized = disarm.transliterate(canonical, lang="ru")
assert romanized == 'Moskva'
back = disarm.transliterate(romanized, target="ru")
assert back == 'Москва'                                   # round-trips
```

For the reversible direction, also avoid the steps that erase recoverable
information — `strip_accents`, `fold_case`, and transliteration to ASCII — unless
you keep the original alongside the canonical key.

This is the deliberate counterpart to the **security/search** canonicalization
recipes (`security_clean`, `catalog_key`, `search_key`), which use **NFKC** on
purpose: they *want* the lossy folding so that `⁵`, `ﬁ`, and fullwidth variants
all collapse to one comparison key. Reversibility and aggressive folding are
opposite goals — choose per use case.

## Choosing a normalization form

| Goal | Form | Why |
|------|------|-----|
| Storage, comparison, **reversible** canonicalization | **NFC** | Canonical and lossless; preserves the round-trip to native script. |
| Security keys, search keys, dedup | **NFKC** | Folds compatibility variants (`⁵→5`, `ﬁ→fi`, fullwidth→ASCII) into one key — lossy by design. |
| Accent stripping (as an intermediate) | **NFD** / **NFKD** | Decomposes so combining marks can be removed; see [`strip_accents`](../api/transforms.md). |

When unsure, normalize with **NFC** first; reach for NFKC only when you
explicitly want compatibility folding and do not need the original back.

## See also

- [Normalization](normalization.md) — the forms in depth
- [Text Pipeline](pipeline.md) — composing the steps
- [Precompiled Pipelines](../api/pipelines.md) — `security_clean`, `catalog_key`, `search_key`, and the policy profiles
- [Confusable Detection](confusables.md) — script and homoglyph analysis
