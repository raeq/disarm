# Adversarial-text robustness evaluation harness (#49)

A reusable benchmark that measures how disarm's defense transform
(`strip_obfuscation`) behaves on **real-world** spam/phishing corpora — turning
scattered datasets into one principled, repeatable evaluation.

This is a **benchmark, not CI.** It pulls large external datasets over the
network, so it lives outside the test gate — run it on demand.

> **Guardrail (from #39/#40).** These corpora are **measuring instruments, never
> optimization targets.** Do not add confusable mappings to improve a benchmark
> number. Coverage grows only from authoritative sources (UTS#39 + transitive
> closure; real attacker confusables verified and upstreamed per #40). Report
> results as observations; route principled misses to #40, not to silent table edits.

## Usage

```bash
pip install -e ".[test]" datasets        # datasets only needed for BitAbuse
python -m benchmarks.adversarial_eval --list
python -m benchmarks.adversarial_eval --corpus youtube-spam --report reports/youtube-spam.md
python -m benchmarks.adversarial_eval --corpus bitabuse --limit 20000 --report reports/bitabuse.md
```

Downloads are cached under `/tmp/adversarial_eval_cache` (override with
`ADVERSARIAL_EVAL_CACHE`).

## Corpora (pluggable adapters)

| corpus | source | credentials | ground truth |
|---|---|---|---|
| `youtube-spam` | UCI 380 (Alberto et al.) | none | unlabeled |
| `bitabuse` | HuggingFace `AutoML/bitabuse` | none | perturbed→clean pairs |
| `trec-2007` | Kaggle `imdeepmind/preprocessed-trec-2007-public-corpus-dataset` | Kaggle API | unlabeled |
| `meajor` | arXiv:2507.17978 corpus | manual download (`ADVERSARIAL_EVAL_MEAJOR`) | unlabeled |

`youtube-spam` and `bitabuse` run with no credentials; committed reports for both
are in [`reports/`](reports/). `trec-2007` (Kaggle creds, as in
`scripts/bootstrap_dicts.sh`) and `meajor` (manual data placement) are
maintainer-run.

**Adding a corpus** is a one-class adapter in `corpora.py`: set `name` /
`labeled` / `requires_credentials` and implement `load()` to yield `Record`s.

## Metrics

- **Recovery** (labeled corpora, e.g. BitAbuse):
  - **XMR / exact-match recovery** — `strip_obfuscation(perturbed) == strip_obfuscation(clean)`.
  - **line-exact recovery** — `strip_obfuscation(perturbed) == clean`.
  - **word-level recovery** — multiset word overlap with the *canonicalized*
    clean text (`strip_obfuscation(clean)`), consistent with how XMR compares
    both sides.
- **Canonicalization stats** (all corpora): % of perturbation-bearing rows and
  % of non-ASCII codepoints folded by `strip_obfuscation`.
- **Miss-mining**: the non-ASCII codepoints that *survive* the defense, split
  into **principled** (present in UTS#39 `data/confusables.txt` — addressable,
  candidates for #40) vs **novel** (not in UTS#39 — out of scope). The split uses
  the full UTS#39 source set, not disarm's bundled subset, so a char that is in
  the standard but not yet mapped counts as an addressable miss, not novel.

## Baseline (BitAbuse, established prior to this harness)

- `strip_obfuscation` word-level recovery ≈ 68% (vs SimChar DB ≈ 35% in the
  literature); line-exact ≈ 6%.
- ~76% of non-ASCII perturbation-char occurrences folded; of the misses, ~106
  distinct are in UTS#39 (addressable) and ~363 distinct are novel/Viper-synthetic
  (out of scope).

Findings feed [#40](https://github.com/raeq/disarm/issues/40) (real-attacker
confusables to verify and upstream) — not silent table edits.
