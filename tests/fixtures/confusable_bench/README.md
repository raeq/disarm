# confusable-bench.v1 (#736)

| file | what |
|---|---|
| `confusable-bench.v1.json` | 140 labelled identifier rows: 120 malicious, 20 benign controls — verbatim |

**Source.** Paul Wood FRSA (@paultendo), `namespace-guard`,
`docs/data/confusable-bench.v1.json`, MIT; published with
<https://paultendo.github.io/posts/unicode-identifier-threat-model/>. Revision of
2026-02-25, sha256 `edfc98673b86c78c9df04c99608733e1bfc3171ff31cd483e851b8e81c5ed937`. Checked in verbatim rather than fetched at test time, per
#732 §2: CI does not depend on a third-party repository staying put.

Every row carries an `identifier`, the `target` it impersonates, a `protect` list, a
`category` and a `threatClass`. The `protect` column is what makes it useful here: it asks
the set-shaped question `find_key_collisions` and `nearest_match` are built for, so the
predicate surfaces and the key builders can be scored on the same rows.

| threat class | rows |
|---|---|
| evasion | 54 |
| impersonation | 35 |
| composability | 31 |
| control | 20 |

| category | rows |
|---|---|
| `nfkc-tr39-divergence` | 31 |
| `mixed-script-confusable` | 28 |
| `invisible-default-ignorable` | 14 |
| `invisible-bidi-control` | 14 |
| `combining-mark-evasion` | 14 |
| `benign-ascii` | 14 |
| `ascii-lookalike` | 12 |
| `confusable-chain` | 7 |
| `benign-unicode-precomposed` | 4 |
| `benign-combining-legit` | 2 |

Scored by `tests/test_confusable_bench.py`, which is also what checks the table on
`docs/security/adversarial-corpora.md`.
