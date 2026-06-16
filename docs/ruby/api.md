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

Aggressive security cleaning: NFKC, confusable folding, bidi stripping,
whitespace collapse, and path-safety in one preset.

```ruby
Disarm.security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥")                 # => "Real text"
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
