- **The `allow_unicode` mark cap, word-boundary truncation and stopwords are described
  as they behave (`formal/lean/Sanitizers`; #PR).** The docs said combining marks are
  "capped at two per base character"; the cap counts the base's own marks over its
  decomposition, so a precomposed character that already carries three, such as
  polytonic Greek U+1F82, is kept whole. The Rust, Python and user-guide descriptions now
  say so. `docs/migration/from-python-slugify.md` records two places disarm differs from
  python-slugify: stopwords match case-insensitively with `lowercase=False` too, and
  `word_boundary` stops at the first word that does not fit rather than packing in later,
  shorter ones.
