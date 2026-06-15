# Using disarm in LLM pipelines

The LLM ecosystem rebuilds disarm's functionality ad hoc — LiteLLM ships a
hand-written normaliser, Haystack has `ascii_only`, every tokenizer wrapper has
its own accent-stripping. The
[survey behind this page](https://github.com/raeq/disarm/issues/133) found the
functionality gap is small; the **documentation** gap is the whole problem.
`normalize_confusables()` is usually presented as a transliteration utility, when
for this audience it is a **guardrail primitive**.

This page frames disarm's existing transforms for two LLM jobs — **guardrail
matching** (filtering untrusted input) and **ingestion** (normalising content for
ASCII indexes) — and is explicit about which path each recipe belongs to. Every
snippet is [executed and asserted in CI](https://github.com/raeq/disarm/blob/main/CONTRIBUTING.md#doc-test-recipes).

!!! warning "Two paths, do not cross them"
    The guardrail path *folds confusables* to defeat homoglyph spoofing. Run it
    on legitimate non-Latin text and it **corrupts** that text (see
    [Which path?](#which-path-and-when-not-to-use-disarm)). The ingestion path
    *romanises* and must not be used to rewrite a prompt the model already
    handles. Pick the path on purpose.

## The NFKC-first convention

Matching frameworks normalise before they compare, because an attacker controls
the *encoding* of a string, not just its letters. disarm's defense functions
follow the same convention — NFKC is their first step — so they are safe to call
on raw, untrusted input:

=== "Python"

    ```python
    from disarm import strip_obfuscation

    # Fullwidth letters (NFKC-folded) and zero-width joiners (stripped):
    assert strip_obfuscation("Ｈｅｌｌｏ") == "Hello"
    assert strip_obfuscation("h​i") == "hi"
    ```

=== "Rust"

    ```rust
    use disarm::api;

    // Fullwidth letters (NFKC-folded) and zero-width joiners (stripped):
    assert_eq!(api::strip_obfuscation("Ｈｅｌｌｏ").unwrap(), "Hello");
    assert_eq!(api::strip_obfuscation("h​i").unwrap(), "hi");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    # Fullwidth letters (NFKC-folded) and zero-width joiners (stripped):
    Disarm.strip_obfuscation("Ｈｅｌｌｏ")   # => "Hello"
    Disarm.strip_obfuscation("h​i")       # => "hi"
    ```

You do not need to pre-normalise before handing text to `strip_obfuscation()` or
`normalize_confusables()`; they start from NFKC themselves.

## Guardrail primitives

For filtering untrusted input — denylist checks, prompt-injection screening,
policy matching — the primitives are `strip_obfuscation()` (full deobfuscation)
and `normalize_confusables()` (TR39 visual fold only).

The key difference from a LiteLLM-style hand-rolled normaliser is what disarm
**refuses** to do: it does not apply leet/digit remapping. Digit remapping
corrupts the numeric text that pervades an LLM stack — model names, versions,
quantities — so `4`, `0`, `1` are left alone:

=== "Python"

    ```python
    from disarm import normalize_confusables

    # Identifiers and version numbers survive untouched:
    assert normalize_confusables("gpt-4o") == "gpt-4o"
    assert normalize_confusables("Llama-3.1-70B") == "Llama-3.1-70B"

    # But cross-script homoglyph spoofs are folded to their Latin skeleton:
    assert normalize_confusables("pаypаl") == "paypal"   # Cyrillic а → a
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, TargetScript};

    // Identifiers and version numbers survive untouched:
    assert_eq!(api::normalize_confusables("gpt-4o", TargetScript::Latin), "gpt-4o");
    assert_eq!(api::normalize_confusables("Llama-3.1-70B", TargetScript::Latin), "Llama-3.1-70B");

    // But cross-script homoglyph spoofs are folded to their Latin skeleton:
    assert_eq!(api::normalize_confusables("pаypаl", TargetScript::Latin), "paypal"); // Cyrillic а → a
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    # Identifiers and version numbers survive untouched:
    Disarm.normalize_confusables("gpt-4o")        # => "gpt-4o"
    Disarm.normalize_confusables("Llama-3.1-70B") # => "Llama-3.1-70B"

    # But cross-script homoglyph spoofs are folded to their Latin skeleton:
    Disarm.normalize_confusables("pаypаl")        # => "paypal"  (Cyrillic а → a)
    ```

What TR39 covers instead of leet tables is *visual* confusability: a Cyrillic
`а` that renders identically to Latin `a` folds to `a`. See
[Confusable Detection](confusables.md) for the table and its limits.

**Recipe — guardrail matching key:**

```python
from disarm import get_pipeline

guardrail = get_pipeline("llm_guardrail")
# NFKC → strip zalgo/bidi → demojize → strip accents → confusables →
# fold case → strip control/zero-width → collapse whitespace
assert guardrail("Ѕ𝗲𝗰𝗿𝗲𝘁  ​data") == "secret data"
```

Compare the matched key, not the raw string, against your policy.

## Convert, don't delete

The other common pattern is `NFKD` + `encode("ascii", "ignore")` (Haystack's
`ascii_only`, Whisper's text cleaner). On non-Latin content this **deletes** the
text — an ASCII index built that way simply loses the document:

=== "Python"

    ```python
    from disarm import transliterate

    passage = "Привет мир"
    # ascii-ignore throws the whole passage away:
    assert passage.encode("ascii", "ignore") == b" "
    # transliterate keeps it, searchable, as readable romanisation:
    assert transliterate(passage) == "Privet mir"
    ```

=== "Rust"

    ```rust
    use disarm::api;

    // transliterate keeps non-Latin content, searchable, as readable romanisation:
    assert_eq!(api::transliterate("Привет мир"), "Privet mir");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    # transliterate keeps non-Latin content, searchable, as readable romanisation:
    Disarm.transliterate("Привет мир")   # => "Privet mir"
    ```

This is the wedge for index/retrieval: non-Latin content stays findable in an
ASCII-normalised index without losing its semantics.

**Recipe — ingestion / RAG index normalisation:**

```python
from disarm import get_pipeline

ingest = get_pipeline("rag_ingest")
# NFKC → strip bidi → strip accents → transliterate →
# strip control/zero-width → collapse whitespace
assert ingest("Café déjà vu") == "Cafe deja vu"
assert ingest("Привет, мир!") == "Privet, mir!"
```

## A composed entry point

If you want one function, compose the two paths and keep transliteration
**optional** — it belongs to the index/matching paths, never to a prompt you are
about to send to a model that reads the original script fine:

```python
from disarm import get_pipeline

def prepare_for_llm(text, *, romanize=False):
    """Normalize untrusted text for an LLM index / matching path.

    romanize=False → guardrail fold (homoglyph + obfuscation defense).
    romanize=True  → ingestion romanisation for an ASCII index.
    Either way this is for indexing/matching, not for rewriting prompts.
    """
    profile = "rag_ingest" if romanize else "llm_guardrail"
    return get_pipeline(profile)(text)

assert prepare_for_llm("pаypаl") == "paypal"            # guardrail
assert prepare_for_llm("Москва", romanize=True) == "Moskva"      # ingestion
```

## Which path, and when NOT to use disarm

Being explicit about the path is what earns credibility with this audience —
the wrong path actively destroys signal:

```python
from disarm import get_pipeline

# WRONG: the guardrail fold mangles legitimate Cyrillic — its confusable step
# rewrites real letters to Latin look-alikes, here producing the plausible-but-
# wrong all-Latin "mockba" instead of the romanisation "moskva":
assert get_pipeline("llm_guardrail")("Москва") == "mockba"

# RIGHT: the ingestion path romanises the same input cleanly:
assert get_pipeline("rag_ingest")("Москва") == "Moskva"
```

Do **not** reach for disarm when:

- **The text goes straight to a multilingual model.** Modern tokenizers already
  NFC/NFKC-normalise, and the model handles native script better than any
  romanisation. Transliterating the prompt throws away signal.
- **You only need encoding repair.** That is `ftfy`'s job, not disarm's.
- **You need lossless round-tripping.** Compatibility-tier romanisation (CJK,
  Indic) is lossy; see [Limitations](../limitations.md).

Use disarm on the **guardrail** path (match untrusted input against policy)
and the **ingestion** path (build an ASCII-normalised index) — not on the
generation path.

## See also

- [Research: Transliteration for LLM Pre-Processing](https://github.com/raeq/disarm/issues/133) — the underlying survey.
- [Precompiled Pipelines](../api/pipelines.md) — every named profile and its steps.
- [Confusable Detection](confusables.md), [Adversarial-Text Defense](../security/adversarial-defense.md).
