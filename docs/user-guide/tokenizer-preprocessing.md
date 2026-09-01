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
Every snippet is [executed and asserted in CI](https://github.com/raeq/disarm/blob/main/CONTRIBUTING.md#doc-test-recipes).

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

=== "Python"

    ```python
    from disarm import ml_normalize

    assert ml_normalize("CAFÉ") == "cafe"
    assert ml_normalize("Привет") == "привет"  # stays Cyrillic, normalized
    assert ml_normalize("Café — RÉSUMÉ 🎉") == "cafe — resume party popper"
    ```

    Only the emoji is named. The em dash is punctuation, not an emoji, and stays
    an em dash — see [Emoji, and only emoji](#emoji-and-only-emoji) below.

=== "Rust"

    ```rust
    use disarm::api;

    // ml_normalize(text, lang, emoji_style, fold_case) — lang=None preserves the script
    assert_eq!(api::ml_normalize("CAFÉ", None, "cldr", true).unwrap(), "cafe");
    assert_eq!(api::ml_normalize("Привет", None, "cldr", true).unwrap(), "привет");        // stays Cyrillic, normalized
    assert_eq!(api::ml_normalize("Café — RÉSUMÉ 🎉", None, "cldr", true).unwrap(), "cafe — resume party popper");

    // fold_case=false keeps capitals for a cased model (#559).
    assert_eq!(api::ml_normalize("CAFÉ", None, "cldr", false).unwrap(), "CAFE");
    ```

!!! warning "Case folding is on by default — turn it off for a cased model"

    `ml_normalize` folds case, which suits the uncased tokenizers most pipelines use.
    In front of a **cased** model it is a measurable loss, and one an uncased
    evaluation harness cannot see: the fold happens before the model, so the harness
    scores text that has already lost the signal. Pass `fold_case=False` to drop that
    one step and keep every other stage:

    ```python
    assert ml_normalize("José Martínez") == "jose martinez"
    assert ml_normalize("José Martínez", fold_case=False) == "Jose Martinez"
    ```

    Accents still go — `strip_accents` is a separate step. If diacritics must survive
    too, use `normalize_confusables` instead and skip the bundle; see
    [what each entry point costs you](../security/adversarial-defense.md#what-each-entry-point-costs-you).

**Romanize to ASCII.** `transliterate` (and the `rag_ingest` preset) map
non-Latin scripts to a shared Latin representation, which tends to tokenize into
fewer, pretrained-shared subwords. The `transliterate` lever is available in
every binding; the `rag_ingest` preset is a Python pipeline:

=== "Python"

    ```python
    from disarm import transliterate, get_pipeline

    assert transliterate("नमस्ते") == "namaste"
    assert transliterate("Привет, мир") == "Privet, mir"
    assert get_pipeline("rag_ingest")("Привет, мир!") == "Privet, mir!"
    ```

=== "Rust"

    ```rust
    use disarm::api;

    assert_eq!(api::transliterate("नमस्ते"), "namaste");
    assert_eq!(api::transliterate("Привет, мир"), "Privet, mir");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    Disarm.transliterate("नमस्ते")        # => "namaste"
    Disarm.transliterate("Привет, мир")   # => "Privet, mir"
    ```

=== "Node"

    ```ts
    import { transliterate } from 'disarm'

    transliterate('नमस्ते') // => 'namaste'
    transliterate('Привет, мир') // => 'Privet, mir'
    ```

Pick the lever by path: romanize for an index/matching path; keep the script when
the text goes to a multilingual model that reads it natively (see
[when NOT to use disarm](llm-pipelines.md#which-path-and-when-not-to-use-disarm)).

### "Keeps the script" is not "keeps the writing system" (#754)

The page opens on Hindi and Thai, and `ml_normalize` does keep text in its own script —
it does not romanize. But it strips **every combining mark**, and in an abugida the
vowel signs *are* combining marks. So the script survives and the words do not:

```python
from disarm import ml_normalize

ml_normalize("हिन्दी")  # 'हनद'    — Devanagari, still Devanagari, no longer a word
ml_normalize("मराठी")  # 'मरठ'
ml_normalize("မြန်မာ")  # 'မနမ'    — Myanmar
ml_normalize("বাংলা")  # 'বল'     — Bengali
ml_normalize("ภาษาไทย")  # 'ภาษาไทย' — Thai is unaffected
ml_normalize("Привет")  # 'привет' — Cyrillic is unaffected
```

Measured over assigned code points in each block, the share `ml_normalize` deletes
outright:

| script | deleted | of assigned |
|---|---:|---:|
| Myanmar | 58 | 160 |
| Devanagari | 34 | 128 |
| Sinhala | 21 | 91 |
| Bengali | 20 | 96 |
| Tamil | 14 | 72 |
| Thai | 16 | 87 |

Thai is the exception in practice and worth understanding, because it is half of this
page's opening sentence: Thai vowels are written as separate code points that
`strip_accents` does not classify as marks to remove, so ordinary Thai survives. The
Indic abugidas do not.

**If your corpus is Devanagari, Bengali, Tamil, Sinhala or Myanmar, this is the wrong
lever.** Use `transliterate` — which is the other lever on this page and is designed to
lose the script deliberately rather than to lose the vowels accidentally — or apply NFKC
and case folding yourself without `strip_accents`. `ml_normalize` is the right tool for
Latin, Cyrillic, Greek and CJK corpora.

### Emoji, and only emoji

`ml_normalize` names a character when it carries the Unicode `Emoji` or
`Extended_Pictographic` property. Nothing else. The CLDR annotation data disarm reads
also names 326 code points that are not emoji by either property — the curly
apostrophes and quotes, the dashes, the currency signs, the math operators, the CJK
brackets — and naming those inserts words into ordinary prose:

| input | named as (before 0.15.0) | now |
|---|---|---|
| `’` U+2019 | `right apostrophe` | `’` |
| `—` U+2014 | `em dash` | `—` |
| `€` U+20AC | `euro` | `€` |
| `•` U+2022 | `bullet` | `•` |
| `⁄` U+2044 | `fraction slash` | `⁄` |
| `🎉` U+1F389 | `party popper` | `party popper` |

The measurable difference on body text is the count. A 30-word English sentence
carrying nothing but typographic punctuation came back as 47 words: `film’s` became
`film right apostrophe s`, one token to four with the possessive gone. That is the
spurious-token-insertion mechanism [adversarial defense](../security/adversarial-defense.md)
disqualifies `unidecode` for, and it applied to disarm's own tokenizer front-end
until [#757](https://github.com/raeq/disarm/issues/757).

`demojize` is unchanged: called directly it still names every row, because
`demojize("I ❤ €5")` → `"I red heart euro 5"` is what that function is for. The
change is about which table wins inside a *preset*.

To keep every emoji as-is instead, pass `emoji="none"`.

## Measuring fertility

The metric is tokens-per-word (or per-character) before vs after the transform,
across scripts and tokenizers. disarm has no tokenizer dependency, so a
measurement wires in whichever tokenizer you target:

<!--- skip: next -->
```python
# Sketch (requires the external tokenizer; not run in CI):
import tiktoken
from disarm import transliterate

enc = tiktoken.get_encoding("o200k_base")  # GPT-4o
text = "नमस्ते दुनिया"
before = len(enc.encode(text))
after = len(enc.encode(transliterate(text)))  # romanized → fewer subwords
```

A reproducible token-fertility benchmark across several non-Latin scripts and
multiple tokenizers (with a results table) is tracked as a follow-up to this
positioning work; it is intentionally out of CI because it pulls in large,
license-gated tokenizers and datasets.

## Honest caveats

**Neither lever is safe on source code (#745).** Both end in `collapse_whitespace`, which
folds LF to a space by design — right for a prompt, wrong for a file. If the text you are
about to normalize is code, use the `code_context` profile instead; see
[Code is not prose](llm-pipelines.md#code-is-not-prose-code_context-and-strip-and-report).
This matters for the case that looks least like it: an AI coding assistant's *context* is
source code, and the pages recommending disarm for untrusted context are the pages its
authors read.

Romanization is not a free win, and fertility is not the whole story:

- **Compatibility-tier romanization is lossy.** For CJK it is context-free and
  phonetic, so it does not recover the intended reading — `東京タワー`
  ("Tokyo Tower") romanizes via pinyin, not Japanese:

  === "Python"

      ```python
      from disarm import transliterate

      assert transliterate("東京タワー") == "dong jing tawa-"
      ```

  === "Rust"

      ```rust
      use disarm::api;

      assert_eq!(api::transliterate("東京タワー"), "dong jing tawa-");
      ```

  === "Ruby"

      ```ruby
      require "disarm"

      Disarm.transliterate("東京タワー")   # => "dong jing tawa-"
      ```

  === "Node"

      ```ts
      import { transliterate } from 'disarm'

      transliterate('東京タワー') // => 'dong jing tawa-'
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
