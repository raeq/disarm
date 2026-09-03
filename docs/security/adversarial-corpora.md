# Adversarial-corpus validation

`cve-validation.md` answers *which published CVEs does disarm handle?*, one row per CVE,
every row asserted in `tests/test_cve_vectors.py`. This page answers the same question for
published **adversarial-text corpora**, and it exists because the CVE corpus cannot reach
them: a CVE is a defect in one implementation, while a paper releases a generator that
emits a whole family.

!!! warning "This is not a coverage claim"

    A `yes` means one reconstructed vector for that subtype was neutralized or detected.
    It does not mean the subtype is covered, and it says nothing about variants nobody
    has written down. Rows disarm does not act on are listed as `no` and asserted as
    negatives, so a limitation cannot drift into a claim.

## The corpus

Sarabamoun, *Special-Character Adversarial Attacks on Open-Source Language Models*,
[arXiv:2508.14070v1](https://arxiv.org/abs/2508.14070), CC BY 4.0. Generators at
`EphraiemSarabamoun/special-character-attack`.

**The vectors here are reconstructed from the paper's definitions, not cloned.** CI does
not depend on a third-party repository staying put — and, more to the point, the released
generator has three defects that would score as passes if its output were trusted:

| defect | effect |
|---|---|
| `homoglyph_attacks.py` defines `'A'`, `'B'`, `'C'` twice in `self.confusables` — mathematical literals, then fullwidth | the later definitions win, so the `math_alts` filter is always empty and the paper's headline U+1D400 subtype is never exercised |
| `invisible_payload/steganographic` is passed an empty payload | the encoding loop never runs and the function returns its input |
| `targeted_word/target_system` substitutes `"system"` for `"system"` | a no-op by construction |

28 of the corpus's 591 rows are therefore no-ops. A row that measures the unmodified
prompt and scores as *neutralized* is the kind of green a gate must not produce, so every
vector on this page is asserted to differ from the base prompt before anything else is
measured.

## Results

Every vector perturbs the same prompt — `ignore previous instructions` — so the family is
the only variable. Measured by `tests/test_adversarial_corpora.py`, which is also what
checks this table.

| family | subtype | neutralized by `canonicalize` | detected by `has_anomalies` |
|---|---|---|---|
| Unicode control | `combining pile` | yes | yes |
| Unicode control | `directional isolate` | yes | yes |
| Unicode control | `directional override` | yes | yes |
| Unicode control | `invisible payload` | yes | yes |
| Unicode control | `tag block` | yes | yes |
| Unicode control | `zero-width joiner` | yes | yes |
| Unicode control | `zero-width non-joiner` | yes | yes |
| Unicode control | `zero-width space` | yes | yes |
| Homoglyph | `cyrillic substitution` | yes | yes |
| Homoglyph | `fullwidth` | yes | no |
| Homoglyph | `greek substitution` | yes | yes |
| Homoglyph | `mathematical alphanumerics` | yes | yes |
| Homoglyph | `small capitals` | yes | yes |
| Structural | `bracket nesting` | no | no |
| Structural | `character deletion` | no | no |
| Structural | `fragmentation` | yes | no |
| Structural | `negation overlay` | no | no |
| Structural | `spacing injection` | yes | no |
| Structural | `whitespace steganography` | yes | yes |
| Structural | `word reordering` | no | no |
| Encoding | `base64` | no | no |
| Encoding | `binary` | no | no |
| Encoding | `hex` | no | no |
| Encoding | `leetspeak` | no | no |
| Encoding | `rot13` | no | no |
| Encoding | `unicode escape` | no | no |
| Encoding | `url escape` | no | no |

## Reading the two columns

They are kept apart for the same reason `cve-validation.md` keeps them apart: a subtype
that is **neutralized and undetected** is a different situation from one that is
**detected and unneutralized**, and the asymmetry is the useful output.

`fullwidth` is the standing example of the first. `canonicalize` folds it and
`has_anomalies` stays quiet, because #633 spared the block: `ＮＨＫ` is how a Japanese
broadcaster is written, and a detector that fires on it is one a CJK-facing caller
switches off entirely. A caller who screens without rewriting gets nothing for that row.

The `Encoding` family is the standing example of a whole family out of scope. disarm
operates on the string it is given; a base64 payload is an ordinary run of ASCII letters
to every transform here. Decode first, then pass the result in — the same ordering
`THREAT_MODEL.md` gives for the rest of that class.

## Structural attacks are mostly out of scope, and that is the honest reading

Four of the seven structural rows are `no` in both columns. Reordering words, deleting
characters and wrapping each letter in brackets are all operations on ordinary ASCII;
there is nothing character-level for disarm to act on, which is the same boundary
`THREAT_MODEL.md` draws for word-substitution adversarial examples and GCG suffixes.

The three that *are* neutralized — `fragmentation`, `spacing injection`,
`whitespace steganography` — are neutralized because they inject whitespace or invisible
characters, not because the structural manipulation was understood.

## A second corpus: `confusable-bench.v1`

The first corpus perturbs a *prompt*. This one measures a single **identifier** against
the name it impersonates — the surface the first cannot reach — and its `protect` column
asks the set-shaped question `find_key_collisions` and `nearest_match` are built for, so
the predicate surfaces and the key builders are scored on the same rows (#736).

Paul Wood FRSA (@paultendo), `namespace-guard`, `docs/data/confusable-bench.v1.json`, MIT,
published with the *Unicode identifier threat model* post: 140 labelled identifier rows —
120 malicious in three threat classes (54 evasion, 35 impersonation, 31 composability) and
20 benign controls (14 ASCII, 4 precomposed, 2 legitimately combining).

**Scored by the meta-benchmark, not by a second copy of the corpus.**
`benchmarks/meta` already registers this benchmark as the `confusable-bench-v1` suite —
it fetches the published file, applies the corpus's own labels, and records the run against
a baseline. This change adds the three surfaces the suite predated (`skeleton_key`,
`skeleton_key` under `tr39`, and `nearest_match`) and the two-call composition, rather
than re-deriving the scores here:

```bash
python -m benchmarks.meta --run --select confusable-bench-v1
```

**Re-measured after #650 and #894.** The issue measured 0.14.1, where the best single call
reached 0.550 recall and the published headline was a three-surface composition at 0.983.
Today `nearest_match` at one edit reaches **0.942 alone**, `skeleton_key` under `tr39`
0.817, and `is_confusable` **or** `nearest_match` reaches **1.000** — two calls, not three.
Precision is 1.000 on every policy: no policy flags a benign control, and the twenty
controls are what make that a result rather than an assertion.

**Two calls, and why it is two.** `nearest_match` at one edit reaches 113 of 120 on its
own, and the seven it misses are all `confusable-chain` rows — two substitutions in one
name (`þɑypal`, `ƍıthub`), two edits by construction — which `is_confusable` catches every
one of. The two are complementary because they measure different things: an edit distance
sees the ASCII-substitution class (`paypa1`, `adm1n`) that no confusable table should fold,
and the fold sees the Unicode class that no edit distance should chase. The recipe is on
[the CVE page](cve-validation.md#validating-a-submitted-identifier-against-protected-names).

**The ASCII boundary, restated.** The issue pinned `paypaI` (capital I for l) and `paypa-l`
(hyphen insertion) as the two rows nothing catches: pure ASCII, where every Unicode
transform is a documented no-op. That half is still true and still asserted —
`canonicalize` returns both unchanged and `is_confusable` says no. What changed is that an
edit-distance surface, which is not a Unicode transform, now reports both at distance 1.
THREAT_MODEL.md's boundary holds; the library simply has a second kind of instrument.

**The 31 composability rows** are the NFKC/TR39 divergence set — `ſ` (TR39 `f`, NFKC `s`),
`ℐ` (TR39 `l`, NFKC `i`) — and the corpus's direct answer to the question
[prototype-policy](../architecture/prototype-policy.md) §1 left open: `is_confusable`
catches all 31, and `has_anomalies` catches 28 through the `compat_fold` kind, which did not
exist when the issue was measured.

Whether the two-call composition deserves an entry point of its own — the shape
`is_suspicious_hostname` gives the hostname case, with the corpus's benign-precomposed and
benign-combining rows to keep a graded signal honest (#545) — is #736's open question.

## Reproducing

```bash
pytest tests/test_adversarial_corpora.py
python -m benchmarks.meta --run --select confusable-bench-v1   # the second corpus
```

The vectors are in that file. The table above is parsed out of this page and compared
against the library row by row, so a cell cannot go stale: every doc gate in this repo
parses fenced code blocks and none read a markdown table before this one, which is how a
`grapheme_len` cell stayed wrong through #708.
