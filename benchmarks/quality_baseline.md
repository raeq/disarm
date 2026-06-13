# disarm transliteration-quality baseline (Phase 0)

Recorded CER/WER baseline for issue [#173](https://github.com/raeq/disarm/issues/173) (epic [#326](https://github.com/raeq/disarm/issues/326), 0.10 milestone).

- **disarm version:** `0.9.1` (pre-split baseline)
- **fixture pairs:** 29
- **harness:** `benchmarks/quality_cer_wer.py` — pure-Python, offline, deterministic
- **fixtures:** `benchmarks/quality_fixtures/cer_wer_pairs.tsv`

Regenerate / verify with:

```bash
python benchmarks/quality_cer_wer.py                  # view
python benchmarks/quality_cer_wer.py --update-baseline # rewrite this file
```

## Why this exists

This is the **Phase-0** slice of #173: a pre-split behavioural baseline, not the full benchmark. Re-running it after the #38 module split must reproduce these numbers, proving the refactor caused no transliteration-quality drift. The fuller CER/WER work (Dakshina / uroman / ICU baselines) and the abjad CCPD indicators (Selection Rate, Partial-/Reader-DER) remain scoped to #173.

`disarm-default` rows score the engine against **its own** documented default output, so their error is expected to be ~0 — they are the drift sentinel. `english-common` rows score against established English exonyms (e.g. *Tchaikovsky*) that the phonetic default legitimately differs from, recording an **honest** non-zero gap.

## Overall (micro-averaged)

| metric | value |
|--------|-------|
| pairs | 29 |
| CER | 3.53% |
| WER | 11.11% |

## By romanization standard

| standard | pairs | CER | WER |
|----------|------:|----:|----:|
| disarm-default | 25 | 0.00% | 0.00% |
| english-common | 4 | 19.57% | 80.00% |

## By script

| script | pairs | CER | WER |
|--------|------:|----:|----:|
| cyrillic | 11 | 5.65% | 18.75% |
| greek | 7 | 3.28% | 14.29% |
| latin | 11 | 0.00% | 0.00% |

## Non-exact pairs

| standard | source | hypothesis | reference | CER |
|----------|--------|------------|-----------|----:|
| english-common | `Чайковский` | `Chaykovskiy` | `Tchaikovsky` | 36.36% |
| english-common | `Хрущёв` | `Khrushchyov` | `Khrushchev` | 20.00% |
| english-common | `Фёдор Достоевский` | `Fyodor Dostoevskiy` | `Fyodor Dostoevsky` | 5.88% |
| english-common | `Σωκράτης` | `Sokratis` | `Socrates` | 25.00% |
