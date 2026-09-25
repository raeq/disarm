- **`Transliterate::run`, `Transliterate::find_untranslatable`, `api::slugify` and
  `DisarmStr::slugify` are deprecated in favour of their `try_` forms, and removed in
  1.0.** The infallible forms let a typo through: an unknown `lang` (`"UK"` for `"uk"`)
  fell back to the default tables and gave quietly wrong output, and `run` skipped the
  replacements registered with `register_replacements`. `try_run`,
  `try_find_untranslatable` and `try_slugify` reject the code with
  `ErrorKind::InvalidArgument`, and are what every binding already calls
  (`formal/bindings`, B2). `DisarmStr` gains `try_slugify`. The deprecated forms behave
  exactly as before until they go, which a test pins. `api::transliterate(text)` is not
  deprecated: it takes no `lang` to get wrong. Rust only: the Python, Node, Ruby, Java
  and C bindings already validate `lang`.
