# Adversarial-Text Defense

Unicode gives attackers a large surface for manipulating text that *looks* unchanged
to a human: **homoglyph substitution** (Latin `a` → Cyrillic `а`), **invisible
character injection** (zero-width spaces), **zalgo** (stacked combining marks), and
**bidirectional control abuse**. These perturbations evade NLP classifiers, bypass
content moderation, and corrupt downstream text processing — with no visible cue.

The standard advice is "sanitize your input." But *which* sanitization? Most pipelines
reach for the text-cleaning libraries they already have — `ftfy`, `unidecode`,
`anyascii` — which were built for encoding repair and ASCII conversion. disarm provides
the *visual* mapping they miss — as a **defense-in-depth layer, not a complete control.**

> **Scope.** disarm canonicalizes the confusables it bundles (TR39) and strips the
> format characters it enumerates. It does **not** promise to stop any attack class, and
> the confusable space is far larger than any table. See the
> [Threat Model](https://github.com/raeq/disarm/blob/main/THREAT_MODEL.md) and *[Coverage and limits](#coverage-and-limits)* below.

## The core distinction: visual vs. phonetic mapping

The single architectural choice that determines whether a tool can reverse a homoglyph
attack is **how it maps a confusable character**:

| Approach | Example | Reverses a *TR39* homoglyph? |
|---|---|---|
| **Phonetic transliteration** | Cyrillic `р` (U+0440) → Latin `r` (by *sound*) | ❌ No — produces `r`, not the original `p` |
| **Visual confusable mapping (TR39)** | Cyrillic `р` (U+0440) → Latin `p` (by *appearance*) | ✅ For confusables in the TR39 table — restores the prototype the attacker replaced |

An attacker who swaps Latin `p` for the identical-looking Cyrillic `р` is exploiting
*appearance*. Only a tool that maps by appearance — per
[Unicode Technical Report #39](https://www.unicode.org/reports/tr39/) — undoes the
substitution. `unidecode`, `anyascii`, `cyrtranslit`, and `uroman` all map
phonetically, so they cannot.

disarm implements TR39 visual confusable mapping. Use
[`normalize_confusables`](../user-guide/confusables.md) and `strip_obfuscation` for
defense; use [`transliterate`](../user-guide/transliteration.md) only when you want
phonetic romanization (e.g. building a readable slug), never as a security control.

## Evidence

This distinction was evaluated empirically in *"Fire Extinguishers Full of Gasoline:
Evaluating Unicode Text Normalization as a Defence Against Adversarial Attacks"* — a
benchmark of eight preprocessing tools, two independent TR39 implementations, and seven
Unicode normalization baselines across six attack types, three downstream tasks
(SST-2, toxicity, AG News), and two model architectures (DistilBERT, RoBERTa-base):
**435,864 experimental observations**. Headline results:

- **Phonetic tools plateau; visual mapping leads, but is bounded by table coverage.**
  The XMR confusable-recovery metric was re-measured (v2) over a broad sample of the
  TR39 space — the 1,314 single-codepoint sources whose skeleton is a single Latin letter
  (of 6,565). disarm's visual TR39 mapping reaches **XMR = 0.634** (`strip_obfuscation`;
  95% CI 0.603–0.664) and **0.682** (full pipeline; CI 0.652–0.710), versus **≤ 0.187**
  for phonetic transliterators and **0.103** for NFKC. The TR39 skeleton transform scores
  **1.000 by construction** — it shares its table with the attack, so it is the *oracle
  ceiling*, not a competitor. **Per-source coverage is distinct from instance XMR:** disarm
  neutralizes **~95% of sources** (0.949 / 0.954); because one unrecovered substitution
  fails a whole instance and each snippet carries several, that ~5% gap compounds into the
  instance scores above. On the original v1 curated cut (18 hand-curated Cyrillic look-alike
  pairs) disarm reproduces **XMR = 1.000** exactly — a labeled sanity check, not the headline
  (see *[Coverage and limits](#coverage-and-limits)*).
- **`ftfy` is equivalent to doing nothing** (TOST equivalence, δ = 0.05, across all
  six attack types).
- **`unidecode` actively harms.** It maps invisible characters to visible ASCII
  sequences, introducing spurious tokens and *significantly degrading* classifier
  accuracy on invisible-character attacks (McNemar's test, p = 6.9 × 10⁻⁹).
- **Plain Unicode normalization is not a defense.** NFC, NFKC, NFKD, and casefold
  provide zero defense against homoglyphs and negligible defense against the rest.
- **Preserve case.** A case-preserving pipeline fully restores downstream accuracy;
  a case-folding variant costs 3.4 pp on cased models. disarm's defense pipelines
  preserve case by design (only `ml_normalize` folds case, deliberately).
- **Direction matters.** Normalize confusables *toward the text's dominant script*.
  For Cyrillic-native text, normalizing toward Latin reduces a Cyrillic-native model to
  near-chance — `normalize_confusables(text, target_script="cyrillic")` exists for this.

The XMR metric and this broad-sample re-measurement are published as a versioned note on
Zenodo: [10.5281/zenodo.20618323](https://doi.org/10.5281/zenodo.20618323) (v2; supersedes
the v1 note's curated-set headline).

### Exact Match Recovery (XMR)

XMR measures whether a preprocessing function `P` exactly reverses an adversarial
corruption `C` on a corpus `T`:

```
XMR(P, C, T) = (1/|T|) · Σ  1[ P(C(t)) == P(t) ]   for t in T
```

It compares the preprocessed-corrupted text against the preprocessed-*clean* text (not
the raw original), so it is fair to tools that alter clean text as a side effect. It is
inference-free (O(n) string comparison), decomposable per attack type, and a
conservative upper bound on failure rate.

## Coverage and limits

The XMR results above measure a broad sample of the TR39 confusable space (1,314
single-codepoint sources). Real-world coverage is bounded further by the bundled data
and by what normalization can do at all:

- **Single-letter Latin confusables: complete.** disarm folds 100% of UTS#39
  single-codepoint confusables whose prototype is a basic Latin letter (gated by
  `tests/test_confusable_coverage.py`). This is the dominant real-world case — registered
  homograph domains are overwhelmingly single-character Latin substitutions
  ([Holgers et al., USENIX 2006](https://www.gribble.org/papers/usenix06_homograph.pdf)).
- **The confusable space is unbounded.** [Deng et al. (2020)](https://arxiv.org/abs/2010.04382)
  found 8,000+ homoglyphs with deep learning; measured against disarm's bundled data,
  ~89% of their *letter* homoglyphs are **not in TR39 at all**. A TR39-derived tool cannot
  canonicalize what TR39 does not list.
- **Normalization alone is a partial defense on real text.** On real phishing,
  table-driven confusable lookup restores only ~35% of perturbed words, vs ~96% for a
  context-aware model ([Lee et al., *BitAbuse*, 2025](https://arxiv.org/abs/2502.05225)).
  Use disarm as the fast, deterministic first layer — not the whole pipeline.

Out of scope by design (not bugs): confusables outside the bundled table, whole-script
spoofs, multi-character confusables (`rn`→`m`), and Unicode-version skew. See the full
**[Threat Model](https://github.com/raeq/disarm/blob/main/THREAT_MODEL.md)**.

## What to use

Function names below are language-neutral; see each binding's tab/reference for
its exact signature (e.g. Rust's `normalize_confusables` takes an explicit
`TargetScript`).

| Goal | Use | Pipeline |
|---|---|---|
| Fold confusables in a string (TR39) | `normalize_confusables` | NFKC-free, single pass |
| Maximum deobfuscation (homoglyph + zalgo + invisible + bidi + emoji) | `strip_obfuscation` | NFKC → strip zalgo → strip bidi → strip zero-width → demojize → confusables → strip accents → collapse |
| Clean untrusted user input | `canonicalize_strict` | NFKC → strip bidi → strip zero-width → strip control → strip invisibles → strip zalgo → confusables → collapse → NFC |
| General security cleanup | `canonicalize` | NFKC → strip bidi → strip invisibles → strip control/zero-width → collapse → cap marks → NFC → confusables → NFC |
| Detect (don't transform) | `is_confusable`, `is_mixed_script` | predicate |
| Check a domain for IDN spoofing | `is_suspicious_hostname` | per-label script + confusable analysis |

=== "Python"

    ```python
    from disarm import strip_obfuscation, normalize_confusables, is_suspicious_hostname

    assert strip_obfuscation("рroduсt") == 'product'
    assert normalize_confusables("раypal") == 'paypal'

    # leading Cyrillic 'а' is flagged
    suspicious, analysis = is_suspicious_hostname("аpple.com")
    assert suspicious is True
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, TargetScript};

    assert_eq!(api::strip_obfuscation("рroduсt").unwrap(), "product");
    assert_eq!(api::normalize_confusables("раypal", TargetScript::Latin), "paypal");

    // leading Cyrillic 'а' is flagged
    let analysis = api::is_suspicious_hostname("аpple.com");
    assert!(analysis.suspicious);
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    Disarm.strip_obfuscation("рroduсt")       # => "product"
    Disarm.normalize_confusables("раypal")    # => "paypal"
    # leading Cyrillic 'а' is flagged
    Disarm.suspicious_hostname?("аpple.com")  # => true
    ```

`strip_obfuscation` deliberately does **not** transliterate (it preserves case and
non-confusable characters). If you also need ASCII romanization, chain
`transliterate()` afterwards.

## See also

- [Confusable Detection](../user-guide/confusables.md) — the user guide for TR39 mapping
- [Security & Hostnames](../architecture/security.md) — implementation internals
- [Migration from Unidecode](../migration/from-unidecode.md) — why `unidecode` is the wrong tool for defense
- [Precompiled Pipelines](../api/pipelines.md) — the full pipeline reference
