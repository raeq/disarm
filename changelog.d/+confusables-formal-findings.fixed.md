- **A `skeleton_key` defect found by a Lean model of the confusable fold
  (`formal/lean/Confusables`).** The model mirrors the fold, compose-at-lookup and
  `skeleton_key` step by step, agrees with the library on 404,205 differential inputs,
  and each of its counterexamples was reproduced on the library before anything changed.

  - **`skeleton_key` was not a fixed point, so two spellings of one identity could key
    apart.** Full case folding leaves `\u0390` as three code points and nothing
    recomposed them, so its key was `i\u0308\u0301` and the key of that key was
    `\u1e2f`. The confusable fold leaves a base beside a mark it composes with:
    `\u00a5\u0300` keyed as `y\u0300`, which `is_confusable` flags, and the #522 pair
    `\u04aa\u0327` keyed as `c\u0327` while `\u00e7` keyed as `c`. Controls and
    zero-width characters were removed only after the last fold, so `a\x01\u0300` keyed
    as `a\u0300`. Over every scalar value and every BMP base carrying a composing mark,
    8 code points and 9,526 of 5,396,480 pairs failed, and 40,229 with a control
    between. NFKC now runs inside the fixed point, and every strip step runs before NFKC
    rather than after it. The second half also stops a removed character from moving the
    key: an invisible between a base and its mark kept them from composing, so
    `I\u200b\u0301` keyed as `l\u0301` where `I\u0301` keys as `\u00ed`, and 3,066 of
    129,200 Latin, Greek and Cyrillic base-mark pairs moved that way for each invisible
    tried. `tests/exhaustive_confusables.rs` now sweeps `skeleton_key` over every scalar
    and the BMP crossed with every composing mark (tier 3).

  `skeleton_key` output moves for these inputs; `KEY_SCHEMA_VERSION` 10 is unreleased
  and records it.
