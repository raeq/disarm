- **The build script's helpers live in `codegen/` now.** `build.rs` kept its 694-line
  `main()`, which says what is generated and asserts what the data must satisfy, and its
  1,718 lines drop to 751. The readers and emitters it calls moved verbatim into five
  modules it includes by path: the TSV readers (`codegen/readers.rs`), the
  confusable-table checks (`codegen/confusables.rs`), the PHF emitters
  (`codegen/phf_tables.rs`), the dense arrays and tries (`codegen/arrays.rs`) and the
  sorted range tables (`codegen/ranges.rs`). Every file the script writes to `OUT_DIR` is
  byte-identical. The crate's `include` list ships the new files, and the CI path
  filters that named `build.rs` name `codegen/` too.
