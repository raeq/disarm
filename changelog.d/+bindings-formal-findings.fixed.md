- **A lone surrogate from Java became three U+FFFD and broke every emoji beside it
  (`formal/bindings` J1; #PR).** The JNI shim read each `String` with jni's modified-UTF-8
  conversion, which falls back to a lossy decode of the whole buffer when any part of it
  fails: `transliterate("a\ud800b")` gave `"a[?][?][?]b"`, and a well-formed emoji in the
  same string became six U+FFFD, so `replaceEmoji("x\u{1F600}y\ud800", "")` removed nothing.
  Arguments are now decoded back to their UTF-16 code units, a surrogate pair is its
  astral character and each lone surrogate is one U+FFFD, the contract the other
  bindings keep (#469).
- **Ruby read a String's bytes as UTF-8 whatever its encoding said (R1; #PR).** An
  ISO-8859-1 `"caf\xE9"` transliterated to `"caf[?]"` and a Windows-1251 word to a row of
  `[?]`. A text argument is now read by its declared encoding: UTF-8 and US-ASCII as they
  are (a US-ASCII byte above `0x7F` is one U+FFFD), ASCII-8BIT as UTF-8, the way the C
  ABI reads bytes, and anything else transcoded with `String#encode`, each invalid or
  unmappable sequence becoming one U+FFFD. An encoding Ruby cannot convert from raises
  `Disarm::InvalidArgument`. `docs/ruby/api.md` has the table.
- **`strip_zalgo` defaulted to a cap of 2 in Node and Ruby (B1; #PR).** #788 raised the
  core's to 3, `is_zalgo`'s threshold, so the transform never removes a mark from text
  the predicate declines to flag; Python followed and the two bindings kept a literal 2.
  Every binding now reads its default from the core: the new
  `api::DEFAULT_ZALGO_MAX_MARKS` and `api::DEFAULT_ZALGO_THRESHOLD`, `Disarm::DEFAULT_*`
  in Ruby, and the Python signature defaults.
- **An unknown `lang` was silently ignored outside Python (B2; #PR).** `transliterate`,
  `find_untranslatable` and `slugify` in Node, Ruby, Java and the C ABI fell back to the
  default tables for a code such as `"UK"`, giving `"Kiyiv"` for `"Kyiv"`, while Python
  and every binding's `search_key` rejected it (#68). The rule now lives in the core:
  `api::validate_lang`, the fallible `Transliterate::try_run` and
  `Transliterate::try_find_untranslatable`, and `api::try_slugify`, which every binding
  calls. An unknown code is the binding's invalid-argument error; in the C ABI it is the
  `error` half of `disarm_transliterate_opts`'s result, with no signature change. The
  infallible `run`, `find_untranslatable` and `slugify` stay lenient and say so.
- **`strip_accents` of a singleton decomposition depended on the rest of the string
  (S1; #PR).** Its borrowing fast path returned the input whenever the NFD form carried no
  combining mark, so `U+037E` stayed `U+037E` alone and became `;` beside any accent, and
  the Rust API, Node, Ruby, Java and C disagreed with Python on 1,401 inputs. The fast
  path now also requires the text to be NFC.
- **`api::register_replacements` had no effect on the Rust API (E1; #PR).** It was
  documented as "applied before the tables" and only the PyO3 glue applied it.
  `Transliterate::try_run` and `try_find_untranslatable` apply it now, and Python's
  `transliterate` and `find_untranslatable` call the same core body rather than a copy of
  it.
- **Node coerced size options (N1; #PR).** `NaN`, fractions and `2 ** 64` reached napi,
  which made integers of them, so `stripZalgo('café', { maxMarks: NaN })` stripped the
  accent. `maxMarks`, `threshold`, `maxGraphemes`, `maxLength` and `maxDistance` must now
  be non-negative safe integers, or the call throws `DisarmInvalidArgument`.
- **Not everything Node and Ruby threw was a disarm error (N2; #PR).** The Node docs say
  everything disarm throws is a `DisarmError`; the infallible functions, the `Lexicon`
  constructor and the `Pipeline` methods threw a plain `Error` on an argument of the wrong
  type. Every entry point now throws a `DisarmError`, `DisarmInvalidArgument` for a wrong
  type. In Ruby, `bidi_control?`, `strip_format` and `nearest_match` raised bare
  `TypeError` or `NoMethodError`; they raise `Disarm::InvalidArgument` now, as every other
  method does.
- **Java, Kotlin and Node's types could not name the `arabic` and `hebrew` confusable
  targets (J2; #PR).** The core and every other binding accept them (#792).
  `TargetScript` gains `ARABIC` and `HEBREW`, and Node's `TargetScript` type the two
  members its runtime already accepted.
