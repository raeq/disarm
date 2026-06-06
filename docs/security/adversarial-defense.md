# Adversarial-Text Defense

Unicode gives attackers a large surface for manipulating text that *looks* unchanged
to a human: **homoglyph substitution** (Latin `a` → Cyrillic `а`), **invisible
character injection** (zero-width spaces), **zalgo** (stacked combining marks), and
**bidirectional control abuse**. These perturbations evade NLP classifiers, bypass
content moderation, and corrupt downstream text processing — with no visible cue.

The standard advice is "sanitize your input." But *which* sanitization? Most pipelines
reach for the text-cleaning libraries they already have — `ftfy`, `unidecode`,
`anyascii` — which were built for encoding repair and ASCII conversion, **not**
adversarial defense. translit is built for the defense.

## The core distinction: visual vs. phonetic mapping

The single architectural choice that determines whether a tool can reverse a homoglyph
attack is **how it maps a confusable character**:

| Approach | Example | Reverses a homoglyph attack? |
|---|---|---|
| **Phonetic transliteration** | Cyrillic `р` (U+0440) → Latin `r` (by *sound*) | ❌ No — produces `r`, not the original `p` |
| **Visual confusable mapping (TR39)** | Cyrillic `р` (U+0440) → Latin `p` (by *appearance*) | ✅ Yes — restores the character the attacker replaced |

An attacker who swaps Latin `p` for the identical-looking Cyrillic `р` is exploiting
*appearance*. Only a tool that maps by appearance — per
[Unicode Technical Report #39](https://www.unicode.org/reports/tr39/) — undoes the
substitution. `unidecode`, `anyascii`, `cyrtranslit`, and `uroman` all map
phonetically, so they cannot.

translit implements TR39 visual confusable mapping. Use
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

- **Phonetic tools plateau; visual mapping is perfect.** On homoglyph attacks,
  phonetic transliterators recover roughly half of inputs (XMR ≈ 0.49), while TR39
  visual mapping (translit-rs) achieves **XMR = 1.000** — and this holds for both
  Latin–Cyrillic and Latin–Greek confusables.
- **`ftfy` is equivalent to doing nothing** (TOST equivalence, δ = 0.05, across all
  six attack types).
- **`unidecode` actively harms.** It maps invisible characters to visible ASCII
  sequences, introducing spurious tokens and *significantly degrading* classifier
  accuracy on invisible-character attacks (McNemar's test, p = 6.9 × 10⁻⁹).
- **Plain Unicode normalization is not a defense.** NFC, NFKC, NFKD, and casefold
  provide zero defense against homoglyphs and negligible defense against the rest.
- **Preserve case.** A case-preserving pipeline fully restores downstream accuracy;
  a case-folding variant costs 3.4 pp on cased models. translit's defense pipelines
  preserve case by design (only `ml_normalize` folds case, deliberately).
- **Direction matters.** Normalize confusables *toward the text's dominant script*.
  For Cyrillic-native text, normalizing toward Latin reduces a Cyrillic-native model to
  near-chance — `normalize_confusables(text, target_script="cyrillic")` exists for this.

The XMR metric is published as a versioned specification on Zenodo:
[10.5281/zenodo.19323513](https://doi.org/10.5281/zenodo.19323513).

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

## What to use

| Goal | Use | Pipeline |
|---|---|---|
| Neutralize homoglyphs in a string | `normalize_confusables(text)` | NFKC-free, single pass |
| Maximum deobfuscation (homoglyph + zalgo + invisible + bidi + emoji) | `strip_obfuscation(text)` | NFKC → strip zalgo → confusables → strip bidi → strip zero-width → demojize → strip accents → collapse |
| Clean untrusted user input | `sanitize_user_input(text)` | NFKC → strip zalgo → confusables → strip bidi → collapse |
| General security cleanup | `security_clean(text)` | NFKC → confusables → strip bidi → collapse |
| Detect (don't transform) | `is_confusable(text)`, `is_mixed_script(text)` | predicate |
| Check a domain for IDN spoofing | `is_safe_hostname(host)` | per-label script + confusable analysis |

```python
from translit import strip_obfuscation, normalize_confusables, is_safe_hostname

strip_obfuscation("рroduсt")        # → "product"   (Cyrillic р→p, с→c via TR39)
normalize_confusables("раypal")      # → "paypal"

safe, details = is_safe_hostname("аpple.com")   # leading Cyrillic а
# safe is False; details.mixed_script and details.has_confusables explain why
```

`strip_obfuscation` deliberately does **not** transliterate (it preserves case and
non-confusable characters). If you also need ASCII romanization, chain
`transliterate()` afterwards.

## See also

- [Confusable Detection](../user-guide/confusables.md) — the user guide for TR39 mapping
- [Security & Hostnames](../architecture/security.md) — implementation internals
- [Migration from Unidecode](../migration/from-unidecode.md) — why `unidecode` is the wrong tool for defense
- [Precompiled Pipelines](../api/pipelines.md) — the full pipeline reference
