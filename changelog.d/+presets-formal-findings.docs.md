- **Documented properties of the presets that did not hold, found by the Lean model in
  `formal/lean/Presets` (#PR).**

  - The empty-key census said every string built from the characters that key to `""`
    keys to `""` too. That is false for `ml_normalize`: each regional indicator keys to
    `""` alone, and a pair names a flag (259 such pairs). The docstring and
    `docs/limitations.md` now say so; the claim holds for the other seven builders.
  - `catalog_key`, `search_key` and `sort_key` said private-use characters survive into
    the key. All three have stripped them since #805.
  - `docs/api/pipelines.md` listed `ml_corpus_normalize`'s output as ASCII. It has no
    transliteration step, so a script without accents keeps its letters.
    `docs/policy-templates.md` said the same.
  - `digit_policy` was described as folding digit variants. On `catalog_key`,
    `search_key` and `sort_key`, `"tr39"` and `"preserve"` run the whole confusable
    table on the raw text, so a Cyrillic spelling of `paypal` keys as `paypal` rather
    than `raural`, and `search_key` and `sort_key` rewrite `|`, `"` and the backtick,
    which `docs/limitations.md` said they never do.
  - The step lists in the preset docstrings, the Rust doc comments, the binding docs for
    `ml_normalize` and `canonicalize`, and `docs/api/pipelines.md` predated
    `resolve_deletions`, `drop_repeated_marks`, the fixed points and #910's removal of
    `demojize` from `strip_obfuscation`, and a comment gave the zalgo cap as 2 where it
    is 3. The profile table in `docs/api/pipelines.md` now lists what each profile's
    `steps` reports, `list_profiles()` includes `code_context`, and `TextPipeline`'s
    execution order in `docs/api/classes.md` is the one it runs.
