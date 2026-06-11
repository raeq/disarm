# disarm as a tokenizer preprocessing front-end

English-centric subword tokenizers over-fragment non-Latin scripts: the same
sentence costs far more tokens in Hindi or Thai than in English, which raises
inference cost and latency and produces uneven quality across languages. A fast,
deterministic, dependency-free normalizer in front of the tokenizer is a cheap
lever on that problem — and that is exactly the class of transform disarm
already ships (`ml_normalize`, `transliterate`, normalization).

This page positions disarm for that **tokenizer-efficiency** use case and is
honest about where it helps and where it does not. For the guardrail-matching and
RAG-ingestion recipes, see [Using disarm in LLM pipelines](llm-pipelines.md);
this page is the deterministic-preprocessing / token-fertility companion to it
(both build on the [LLM pre-processing survey](https://github.com/raeq/disarm/issues/133)).
Every snippet is [executed and asserted in CI](../CONTRIBUTING.md#doc-test-recipes).

## Why token fertility matters

"Fertility" is the average number of subword tokens per word (or per character).
Recent work shows it is driven by **design choices** — script, normalization,
romanization — not intrinsic difficulty, and that those choices materially affect
cost, fairness, and cross-lingual transfer:

- Jung et al. 2025, *"Happiness is Sharing a Vocabulary"* ([arXiv:2510.10827](https://arxiv.org/abs/2510.10827)) — romanization beats other input representations in 7 of 8 NER/NLI settings; longer subword tokens shared with pretrained languages drive the gains.
- Limisiewicz et al. 2024, *MYTE* ([arXiv:2403.10691](https://arxiv.org/abs/2403.10691)) — encoding choices yield shorter, fairer sequences across 99 languages.
- Shani et al. 2026, *"The Roots of Performance Disparity in Multilingual LMs"* ([arXiv:2601.07220](https://arxiv.org/abs/2601.07220)) — multilingual gaps stem largely from tokenization/normalization design, and shrink when those are normalized.

## Two deterministic levers

disarm offers two complementary front-end transforms. Both are O(1) PHF
lookups with ASCII-or-script-stable output and no runtime dependencies.

**Normalize, keep the script.** `ml_normalize` applies NFKC, folds emoji to
words, strips accents and case, and collapses whitespace — without romanizing, so
the script is preserved:

```python
from disarm import ml_normalize

assert ml_normalize("CAFÉ") == "cafe"
assert ml_normalize("Привет") == "привет"        # stays Cyrillic, normalized
assert ml_normalize("Café — RÉSUMÉ 🎉") == "cafe em dash resume party popper"
```

**Romanize to ASCII.** `transliterate` (and the `rag_ingest` preset) map
non-Latin scripts to a shared Latin representation, which tends to tokenize into
fewer, pretrained-shared subwords:

```python
from disarm import transliterate, get_pipeline

assert transliterate("नमस्ते") == "namaste"
assert transliterate("Привет, мир") == "Privet, mir"
assert get_pipeline("rag_ingest")("Привет, мир!") == "Privet, mir!"
```

Pick the lever by path: romanize for an index/matching path; keep the script when
the text goes to a multilingual model that reads it natively (see
[when NOT to use disarm](llm-pipelines.md#which-path-and-when-not-to-use-disarm)).

## Measuring fertility

The metric is tokens-per-word (or per-character) before vs after the transform,
across scripts and tokenizers. disarm has no tokenizer dependency, so a
measurement wires in whichever tokenizer you target:

<!--- skip: next -->
```python
# Sketch (requires the external tokenizer; not run in CI):
import tiktoken
from disarm import transliterate

enc = tiktoken.get_encoding("o200k_base")          # GPT-4o
text = "नमस्ते दुनिया"
before = len(enc.encode(text))
after = len(enc.encode(transliterate(text)))        # romanized → fewer subwords
```

A reproducible token-fertility benchmark across several non-Latin scripts and
multiple tokenizers (with a results table) is tracked as a follow-up to this
positioning work; it is intentionally out of CI because it pulls in large,
license-gated tokenizers and datasets.

## Honest caveats

Romanization is not a free win, and fertility is not the whole story:

- **Compatibility-tier romanization is lossy.** For CJK it is context-free and
  phonetic, so it does not recover the intended reading — `東京タワー`
  ("Tokyo Tower") romanizes via pinyin, not Japanese:

  ```python
  from disarm import transliterate

  assert transliterate("東京タワー") == "dong jing tawa-"
  ```

  Use romanization for matching/indexing where this is acceptable, not where the
  reading must be preserved. See [Limitations](../limitations.md).
- **Fertility alone is a poor quality proxy** — Asgari et al. 2025, *MorphBPE*
  ([arXiv:2502.00894](https://arxiv.org/abs/2502.00894)). Fewer tokens is not
  automatically better; pair it with a downstream-quality check.
- **Romanization must be high quality** or it strips query nuance — Chari et al.
  2025, *"Lost in Transliteration"* ([arXiv:2505.08411](https://arxiv.org/abs/2505.08411)).
- **Byte-level / tokenizer-free models** (MYTE-style) reduce the need for this
  front-end entirely; it is a lever for subword tokenizers, not a universal one.

Downstream-quality numbers (CER/WER and abjad indicators) are tracked by the
quality-benchmark capstone, [#173](https://github.com/raeq/disarm/issues/173).

## See also

- [Using disarm in LLM pipelines](llm-pipelines.md) — guardrail and RAG recipes, and which path to choose.
- [Research: Transliteration for LLM Pre-Processing](https://github.com/raeq/disarm/issues/133) and [#172](https://github.com/raeq/disarm/issues/172) — the survey and positioning issue.
- [Precompiled Pipelines](../api/pipelines.md), [Limitations](../limitations.md).
