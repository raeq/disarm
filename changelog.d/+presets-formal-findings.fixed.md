- **Five defects found by a Lean model of the presets, key builders and profiles
  (`formal/lean/Presets`; #PR).** The model transcribes every preset step list, the
  fast-path guard and the eight profiles, agrees with the library on 22,682,192
  differential comparisons, and each counterexample was reproduced on the library before
  anything changed. Finding 1, `skeleton_key`, was fixed in #1024.

  - **`search_key` and `sort_key` were not fixed points under `digit_policy="tr39"` or
    `"preserve"`.** Their only confusable fold under those policies is the pre-fold on
    the raw text, and their case fold, NFKC and transliteration then make sources it
    never saw: U+A760 keyed as U+A761, whose key is `w`; U+01C1 transliterates to `||`,
    whose key is `ll`; `qty-` U+00BD keyed as `qty-1` U+2044 `2`, whose key has `/`. The
    library search found 62 and 171 single code points and 682 and 1,879 two-character
    strings. Under a non-default policy the two builders now run to a fixed point; the
    default runs once, as before, and no default key moves.
  - **`llm_guardrail` and `ml_corpus_normalize` kept a negation overlay, then orphaned
    it.** #749 keeps U+0338 or U+20D2 on a base that is not alphanumeric, and the mark
    strip runs before the confusable fold and before `strip_pua`: U+00A2 U+0338 came back
    as `c` U+0338 and then `c`, and a PUA code point with an overlay as a bare overlay
    and then nothing. The named profiles now run to a fixed point. A `TextPipeline`
    built from the same flags still runs its steps once, because a caller composing one
    can give `demojize` a replacement that is itself two emoji, which a fixed point
    would double eight times; the two agree wherever one pass is already a fixed point,
    which includes every single code point.
  - **A character removed after the last normalization kept two characters that compose
    apart.** `strip_obfuscation` stripped controls, and `ml_normalize` controls and
    zero-width characters, after their last composing step, so conjoining jamo U+1100 NUL
    U+1161 came back as the two jamo, whose key is U+AC00. Both now end with an NFC
    pass. The profiles had the same defect three ways (`normalize_web_input` returned
    `c` U+0327 for `c` NUL U+0327, and `c` the next time), and the fixed point above
    closes it for them.
  - **`PRESETS` was not what the presets run.** It lacked `resolve_deletions`,
    `strip_invisibles` in the three key builders, `drop_repeated_marks`, `sort_key`'s
    cap, `catalog_key`'s fixed point and the whole of `skeleton_key`; it still listed the
    `demojize` step #910 removed from `strip_obfuscation`, and put
    `canonicalize_strict`'s cap before the fold. Executing its lists with the public
    functions disagreed with the presets on 15 of the model's 48 probes. It is now one
    tuple per Rust step, `test_preset_steps_exact` reads the expected lists from
    `src/presets.rs` instead of from a second hand-written copy, and a new test executes
    every list and compares it with its preset. `is_canonical` accepts `skeleton_key`,
    since its `preset` is documented as any `PRESETS` name.
  - **The preset output ceiling was neither a bound on output nor neutral to input
    size.** It was an absolute size tested after NFKC alone, so `ml_normalize` turned
    10.4 MB of U+1FAF0 into 106.6 MB with no error, while 11 MiB of `a` after one `"`
    was refused as having "expanded" and the same 11 MiB without the quote was
    accepted. The limit is now on growth: after every step, a preset refuses to leave
    the text more than 10 MiB longer than its input, whichever step does the growing.
    An input of any size that no step grows is accepted. The error code is unchanged,
    and its message now names the input size as well as the output.

  Stored keys move only where a key was not a fixed point, so no stable value moves:
  `strip_obfuscation` and `ml_normalize` on a composing pair split by a removed
  character, `search_key` and `sort_key` under a non-default `digit_policy`, and the
  three profiles above. `KEY_SCHEMA_VERSION` stays at the unreleased 10, with the moves
  recorded under it, and three rows for the separated-composition class were added to
  the key-stability corpus, which had none.
