# Ruby API reference

The Ruby surface is the singleton methods on the **`Disarm`** module plus the
[`Disarm::Error`](#errors) hierarchy. Every method is a thin, idiomatic wrapper
over the pure-Rust `disarm` core (no Python): keyword arguments carry the core's
defaults, and scheme/target tokens are symbols (`:latin`, `:default`, …) or
strings. The binding is a deliberate **subset** of the Rust
[`disarm::api`](../RUST_API.md) surface — see
[`bindings/ruby/lib/disarm.rb`](https://github.com/raeq/disarm/blob/main/bindings/ruby/lib/disarm.rb)
for the authoritative definitions; if a topic isn't here, that binding doesn't
expose it yet.

For install and a five-line tour, start with [disarm for Ruby](getting-started.md).
The shared, language-neutral explanation of *what* each operation does lives under
**Concepts** and **Guide** in the sidebar — this page is the Ruby call surface,
not the rationale.

```ruby
require "disarm"
```

Every example below is executed against the built gem in CI (the Ruby doc gate),
so the documented outputs cannot rot.

## Transliteration

### `Disarm.transliterate(text, scheme: :default, lang: nil)`

Romanize Unicode text to ASCII. `scheme:` selects the standard — `:default`
(general-purpose), `:strict_iso9` (ISO 9:1995-style ASCII), or `:gost7034`
(GOST R 7.0.34). `lang:` applies a language profile on top of the scheme (sparse
overrides — e.g. `"de"` maps `ü` → `ue`, `"uk"` sharpens Ukrainian); `nil` means
no profile. Both accept a String or Symbol.

This is **phonetic romanization for legibility, not a security control** — reach
for [`normalize_confusables`](#confusable-folding) to
defend against homoglyphs.

```ruby
Disarm.transliterate("café")                       # => "cafe"
Disarm.transliterate("Москва")                     # => "Moskva"
Disarm.transliterate("Київ", lang: "uk")           # => "Kyiv"
Disarm.transliterate("Юрий", scheme: :strict_iso9) # => "Jurij"
Disarm.transliterate("Москва", scheme: :gost7034)  # => "Moskva"
```

## Confusable folding

### `Disarm.normalize_confusables(text, target: :latin)`

Fold cross-script confusables toward `target:` (`:latin` or `:cyrillic`) using
the TR39 visual mapping. This is the homoglyph defence — it canonicalizes
look-alikes (Cyrillic `а` → Latin `a`) rather than romanizing.

```ruby
Disarm.normalize_confusables("раypal")             # => "paypal"
```

### `Disarm.confusable?(text, target: :latin)`

Whether `text` contains any character confusable with `target:` (`:latin` or
`:cyrillic`). A `true` is a positive finding; a `false` asserts only that none of
the bundled confusables were found, not that the text is safe.

```ruby
Disarm.confusable?("pаypal")                       # => true
Disarm.confusable?("paypal")                       # => false
```

## Slugs

### `Disarm.slugify(text, separator: "-", lowercase: true, max_length: 0, …)`

Generate a URL-safe slug. Mirrors the core's `SlugConfig` defaults; every option
past `text` is keyword-only (`separator:`, `lowercase:`, `max_length:`,
`word_boundary:`, `save_order:`, `stopwords:`, `allow_unicode:`, `lang:`,
`entities:`, `decimal:`, `hexadecimal:`, `safe_chars:`).

```ruby
Disarm.slugify("Héllo Wörld")                      # => "hello-world"
Disarm.slugify("café au lait")                     # => "cafe-au-lait"
```

## Canonicalization primitives

### `Disarm.strip_accents(text)`

Strip diacritics.

```ruby
Disarm.strip_accents("café")                       # => "cafe"
```

### `Disarm.fold_case(text)`

Full Unicode case fold — more aggressive than `String#downcase` (e.g. German `ß`
folds to `ss`).

```ruby
Disarm.fold_case("HELLO")                          # => "hello"
Disarm.fold_case("Straße")                         # => "strasse"
```

### `Disarm.demojize(text, strip_modifiers: false)`

Replace emoji with their plain names. `strip_modifiers:` drops skin-tone /
variation modifiers before naming.

```ruby
Disarm.demojize("👍")                               # => "thumbs up"
Disarm.demojize("Café ☕")                          # => "Café hot beverage"
```

## Deobfuscation & security presets

### `Disarm.strip_obfuscation(text)`

Remove obfuscation — zero-width characters, bidi controls, combining-mark abuse,
and TR39 homoglyphs — while keeping legible content. It does **not** transliterate;
chain [`transliterate`](#transliteration) if you also need ASCII.

```ruby
Disarm.strip_obfuscation("рroduсt")                # => "product"
```

### `Disarm.security_clean(text)`

Aggressive security cleaning: NFKC, confusable folding, bidi stripping, and
whitespace collapse in one preset.

```ruby
Disarm.security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥")                 # => "Real text"
```

## Collation & lookup keys

Stable keys for searching, sorting, and deduplicating text across cases, accents,
and scripts. All three accept a `lang:` profile (a String or Symbol; `nil` means
none) and raise `Disarm::InvalidArgument` on an unknown lang.

### `Disarm.search_key(text, lang: nil)`

Case/accent/script-insensitive search-index key — fold to a single canonical form
so `"Köln"` and `"koln"` collide in a lookup table.

```ruby
Disarm.search_key("Köln")                          # => "koln"
Disarm.search_key("Café")                          # => "cafe"
```

### `Disarm.sort_key(text, lang: nil)`

A collation/sort key that **preserves base accented characters** — unlike
`search_key` it keeps the accent (so accented and unaccented forms stay
distinct), while still folding non-Latin scripts to Latin.

```ruby
Disarm.sort_key("café")                            # => "café"
Disarm.sort_key("Éclair")                          # => "éclair"
```

### `Disarm.catalog_key(text, lang: nil, strict_iso9: false)`

Library-catalog deduplication key — `search_key` plus confusable folding.
`strict_iso9:` selects the ISO 9:1995 Cyrillic scheme for transliteration.

```ruby
Disarm.catalog_key("Толстой")                      # => "tolstoy"
Disarm.catalog_key("Толстой", strict_iso9: true)   # => "tolstoj"
```

## Pipelines

### `Disarm.get_pipeline(profile)`

Build a reusable `Disarm::Pipeline` for a named policy `profile` (e.g.
`"search_index"`). The profile's steps are validated and assembled once at
construction, so the returned handle's `#process(text)` can be called many times
without re-resolving the profile. Raises `Disarm::InvalidArgument` on an unknown
profile name.

```ruby
pipe = Disarm.get_pipeline("search_index")
pipe.process("Café")                               # => "cafe"
pipe.process("Köln")                               # => "koln"
```

## Hostname / IDN analysis

### `Disarm.suspicious_hostname?(host)`

Whether the hostname looks like a mixed-script / confusable IDN spoof. As with
`confusable?`, a `false` asserts nothing was *found* — it is not a safety
guarantee. See the [Threat Model](../THREAT_MODEL.md) for what is and isn't in
scope.

```ruby
Disarm.suspicious_hostname?("pаypal.com")          # => true
Disarm.suspicious_hostname?("example.com")         # => false
```

## Normalization

### `Disarm.normalize(text, form: :nfc)`

Apply a Unicode normalization form — `:nfc` (default), `:nfd`, `:nfkc`, or
`:nfkd` (a Symbol or String, case-insensitive).

```ruby
Disarm.normalize("ﬁ", form: :nfkc)                 # => "fi"
Disarm.normalize("2²", form: :nfkc)                # => "22"
```

### `Disarm.normalized?(text, form: :nfc)`

Whether `text` is already in normalization `form:` (default `:nfc`).

```ruby
Disarm.normalized?("café", form: :nfc)             # => true
Disarm.normalized?("ﬁ", form: :nfkc)               # => false
```

## Text cleaning

### `Disarm.collapse_whitespace(text, strip_control: true, strip_zero_width: true)`

Collapse every run of Unicode whitespace to a single ASCII space, and trim
leading/trailing whitespace. By default it also strips control and zero-width
characters; pass `strip_control: false` / `strip_zero_width: false` to keep them.

```ruby
Disarm.collapse_whitespace("  a   b ")             # => "a b"
```

### `Disarm.strip_control_chars(text)` · `Disarm.strip_zero_width_chars(text)` · `Disarm.strip_bidi(text)`

Remove, respectively, C0/C1 control characters (except tab/newline), zero-width
characters (ZWSP/ZWNJ/ZWJ/word-joiner), and Unicode bidirectional controls — the
invisible characters used to obfuscate or spoof text.

```ruby
Disarm.strip_control_chars("a\u0007b")              # => "ab"
Disarm.strip_zero_width_chars("a\u200Bb")           # => "ab"
Disarm.strip_bidi("a\u202Eb")                       # => "ab"
```

### `Disarm.strip_tags(text)` · `Disarm.strip_variation_selectors(text)` · `Disarm.strip_noncharacters(text)` · `Disarm.strip_pua(text)`

Strip the invisible / non-interchange code-point classes weaponized for "ASCII
smuggling" into LLMs and adjacent hygiene (#413): the Unicode **Tags** block
(preserving valid emoji flag sequences), every **variation selector**, every
**noncharacter**, and the **Private Use Area**. These are the composable
primitives behind the security presets, which strip them automatically.

```ruby
Disarm.strip_tags("a\u{E0001}b")                    # => "ab"
Disarm.strip_variation_selectors("g\u{FE01}data")   # => "gdata"
Disarm.strip_noncharacters("a\u{FFFE}b")            # => "ab"
Disarm.strip_pua("a\u{E000}b")                      # => "ab"
```

### `Disarm.strip_zalgo(text, max_marks: 2)` · `Disarm.zalgo?(text, threshold: 3)`

`zalgo?` flags "zalgo" — combining marks stacked past `threshold:` on a base
character; `strip_zalgo` caps each base character at `max_marks:` combining marks.

```ruby
Disarm.zalgo?("Z\u0301\u0301\u0301\u0301")                       # => true
Disarm.zalgo?(Disarm.strip_zalgo("Z\u0301\u0301\u0301\u0301"))  # => false
```

## Grapheme clusters

Operate on **user-perceived characters** (grapheme clusters) rather than code
points — an emoji, a flag, or a base-plus-combining-mark counts as one.

### `Disarm.grapheme_len(text)`

Number of grapheme clusters (contrast `String#length`, which counts code points).

```ruby
Disarm.grapheme_len("a👍b")                        # => 3
Disarm.grapheme_len("🇬🇧")                          # => 1
```

### `Disarm.grapheme_split(text)`

Split into an array of grapheme-cluster strings.

```ruby
Disarm.grapheme_split("a👍")                       # => ["a", "👍"]
```

### `Disarm.grapheme_truncate(text, max_graphemes)`

Truncate to at most `max_graphemes` clusters, never cutting through one.

```ruby
Disarm.grapheme_truncate("héllo", 3)               # => "hél"
Disarm.grapheme_truncate("a👍b👎", 2)               # => "a👍"
```

### `Disarm.grapheme_width(cluster, ambiguous_wide: false)` · `Disarm.terminal_width(text, ambiguous_wide: false)`

Display width in terminal columns by East Asian Width — `grapheme_width` for a
single cluster, `terminal_width` for a whole string. Pass `ambiguous_wide: true`
to count ambiguous-width characters as two columns.

```ruby
Disarm.grapheme_width("👍")                         # => 2
Disarm.terminal_width("a👍")                        # => 3
```

## Filenames

### `Disarm.sanitize_filename(text, separator: "_", max_length: 255, platform: :universal, lang: nil, preserve_extension: true)`

Turn arbitrary text into a filesystem-safe filename. `platform:` is `:universal`
(default), `:windows`, or `:posix`; `preserve_extension:` keeps the final
extension when truncating to `max_length:`. Raises `Disarm::InvalidArgument` on an
unknown platform.

```ruby
Disarm.sanitize_filename("My: report*.txt")         # => "My_report.txt"
Disarm.sanitize_filename("CON", platform: :windows) # => "_CON"
```

## Reverse transliteration & untranslatable scan

### `Disarm.reverse_transliterate(text, lang:)`

Reverse-transliterate Latin back to a native script. `lang:` is `:el` (Greek),
`:ru` (Russian), or `:uk` (Ukrainian).

```ruby
Disarm.reverse_transliterate("Moskva", lang: :ru)  # => "Москва"
Disarm.reverse_transliterate("Athina", lang: :el)  # => "Αθηνα"
```

### `Disarm.find_untranslatable(text, scheme: :default, lang: nil)`

Every character with no romanization — the ones `transliterate` would replace —
as `{ char:, offset: }` hashes (byte offset), in order. `scheme:`/`lang:` mirror
`transliterate`.

```ruby
Disarm.find_untranslatable("a🜊")                   # => [{ char: "🜊", offset: 1 }]
Disarm.find_untranslatable("café")                 # => []
```

## Script analysis

### `Disarm.detect_scripts(text)` · `Disarm.mixed_script?(text)` · `Disarm.bidi_conflict?(text)`

The Unicode scripts present (first-appearance order, Common/Inherited excluded),
whether more than one script is present, and whether the text mixes strong
left-to-right and strong right-to-left characters — the "BiDi Swap"
display-reorder precondition (fires on real letters, no `U+202x` override).

```ruby
Disarm.detect_scripts("aМ")                        # => ["Latin", "Cyrillic"]
Disarm.mixed_script?("aМ")                         # => true
Disarm.bidi_conflict?("helloא")                    # => true  (Latin + Hebrew)
Disarm.bidi_conflict?("helloМ")                    # => false (both LTR)
```

### `Disarm.inspect_auto_lang(text)`

Explain how `lang: "auto"` detection resolves `text` — a hash with `:script` and
`:chosen_lang` (both `nil` if undetected), the `:reason`, and any
`:discriminators_hit`.

```ruby
Disarm.inspect_auto_lang("Москва") # => { script: "Cyrillic", chosen_lang: "ru", reason: "script_default", discriminators_hit: [] }
```

### `Disarm.lang_info(code)` · `Disarm.script_info(name)`

Curated metadata for one language `code` (e.g. `"de"`) or one script `name` (e.g.
`"Coptic"`), each a hash with symbol keys. `lang_info` returns `{ name:, script:,
region:, context: }` (where `:context` is `"none"`/`"partial"`/`"full"`);
`script_info` returns `{ name:, default_lang:, example:, context_aware: }`
(`:default_lang` is `nil` when none). Each raises `Disarm::InvalidArgument` on an
unknown code/name.

```ruby
Disarm.lang_info("de")[:name]                      # => "German"
Disarm.lang_info("de")[:script]                    # => "Latin"
Disarm.script_info("Coptic")[:default_lang]        # => "cop"
Disarm.script_info("Coptic")[:context_aware]       # => false
```

### `Disarm.list_scripts` · `Disarm.list_context_langs`

Enumerate what disarm knows: `list_scripts` is every Unicode script as a stable
UCD identifier (includes `"Common"`/`"Inherited"`), sorted by name;
`list_context_langs` is the language codes with context-aware transliteration
support, sorted by code. Both return an `Array<String>`.

```ruby
Disarm.list_scripts.include?("Latin")              # => true
Disarm.list_context_langs                          # => ["ar", "fa", "he"]
```

## Anomaly detection

### `Disarm.has_anomalies?(text, lexicon)` · `Disarm.inspect_anomalies(text, lexicon)`

Flag text carrying out-of-place characters that disguise a real word — a
cross-script homoglyph, leet, segmentation, a zero-width / bidi control, or zalgo.
Reports a technical fact, not intent. `lexicon` is a common-word Array or Set
(used only by the leet and segmentation branches). `inspect_anomalies` returns a
hash with `:anomalous`, `:kinds`, `:findings` (each `{ kind:, token:, start:,
end:, detail:, reason: }`), and `:reason`. See
[Anomaly Detection](../user-guide/anomaly-detection.md) for the detected classes.

```ruby
Disarm.has_anomalies?("get fr33 now", ["free"])        # => true
Disarm.inspect_anomalies("paypаl", ["paypal"])[:kinds] # => ["mixed_script"]
```

## Errors

Everything disarm raises descends from `Disarm::Error < StandardError`, so a
single `rescue Disarm::Error` catches the whole surface. Bad input — an unknown
scheme/target token, a non-String argument, a negative `max_length` — raises the
more specific `Disarm::InvalidArgument` (itself a `Disarm::Error`), with the
original native backtrace preserved.

| Class | Raised for |
| --- | --- |
| `Disarm::Error` | Base class — `rescue` this to catch everything. |
| `Disarm::InvalidArgument` | An invalid argument (bad scheme/target, wrong type, out-of-range option). |

```ruby
begin
  Disarm.transliterate("x", scheme: :klingon)
rescue Disarm::InvalidArgument => e   # also rescuable as Disarm::Error
  warn e.message
end
```

## Stability

The Ruby gem version tracks the Rust crate and Python package numerically. The
binding inherits the core's behavioural guarantees and limits verbatim — read the
[Threat Model](../THREAT_MODEL.md) before relying on it in a security context, and
note that transliteration **output** is data-driven (Unicode tables, romanization
standards) and can change across releases without being treated as a breaking
change. Pin a version if you need byte-stable output.
