- **`src/presets.rs` is a module directory now.** The 5,101-line file is split by concern
  into `src/presets/`: the `Step` vocabulary and its dispatch (`steps.rs`), the fast-path
  guard (`guard.rs`), the runners and output ceiling (`runner.rs`), `strip_bidi`
  (`bidi.rs`), the text presets (`text.rs`), the key builders (`keys.rs`), `is_canonical`
  (`verify.rs`), and the two test modules. Every item moved verbatim apart from its
  visibility, and every `crate::presets::` path the rest of the crate uses is re-exported
  from `mod.rs`, so no caller changed and no output did either. The tests and
  `tests/conftest.py`, which read the step lists from the source, read the new files.
