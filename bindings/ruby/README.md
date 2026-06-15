# disarm (Ruby)

Ruby bindings for [**disarm**](https://github.com/raeq/disarm) — Unicode
confusable / text-security building blocks (homoglyph & bidi & zalgo handling,
plus standards-based transliteration), powered by Rust.

The native extension wraps the **pure-Rust `disarm` core** (no Python), via
[magnus](https://github.com/matsadler/magnus) + [rb-sys](https://github.com/oxidize-rb/rb-sys).
Precompiled platform gems install without a local Rust toolchain.

## Install

```ruby
# Gemfile
gem "disarm"
```

```sh
gem install disarm
```

Requires Ruby >= 3.1. `gem install disarm` pulls a precompiled platform gem
(Linux x86_64/aarch64, macOS x86_64/arm64, Windows) when one is available, and
falls back to compiling from source (needs a Rust toolchain) otherwise.

## Usage

```ruby
require "disarm"

# Standards-based transliteration to ASCII. `scheme:` is a symbol (or string):
# :default (general-purpose), :strict_iso9 (ISO 9:1995), :gost7034.
Disarm.transliterate("Москва")                       # => "Moskva"
Disarm.transliterate("Москва", scheme: :strict_iso9)

# TR39 confusable folding (homoglyph defense). `target:` defaults to :latin.
Disarm.normalize_confusables("раypal")               # => "paypal"
Disarm.confusable?("pаypal")                          # => true
Disarm.normalize_confusables("paypal", target: :cyrillic)

# Canonicalization primitives
Disarm.strip_accents("café")                         # => "cafe"
Disarm.fold_case("HELLO")                            # => "hello"
Disarm.slugify("Héllo Wörld")                        # => "hello-world"
Disarm.slugify("Hello World", separator: "_", max_length: 5, word_boundary: true)
Disarm.demojize("I ❤️ Ruby")                          # => "I :red_heart: Ruby"
Disarm.demojize("👍🏽", strip_modifiers: true)

# Security presets
Disarm.strip_obfuscation("Ѕ𝗲𝗰𝗿𝗲𝘁  ​data")            # deobfuscated
Disarm.security_clean("…")                           # homoglyph/bidi/zero-width clean

# IDN / hostname spoof check (a false result is not a safety guarantee)
Disarm.suspicious_hostname?("pаypal.com")            # => true (Cyrillic 'а')
```

Every option past the text is a keyword argument with the core's default, and
scheme/target tokens accept symbols or strings. `slugify` exposes the core's
`SlugConfig` surface (`separator:`, `lowercase:`, `max_length:`,
`word_boundary:`, `save_order:`, `stopwords:`, `allow_unicode:`, `lang:`,
`entities:`, `decimal:`, `hexadecimal:`, `safe_chars:`).

### Errors

Everything disarm raises descends from `Disarm::Error < StandardError`, so a
single `rescue Disarm::Error` catches all of them; an invalid scheme/target or
other bad argument raises the more specific `Disarm::InvalidArgument`.

```ruby
begin
  Disarm.transliterate("x", scheme: :klingon)
rescue Disarm::InvalidArgument => e   # also rescuable as Disarm::Error
  warn e.message
end
```

## Security posture

This binding inherits the core's guarantees and limitations verbatim — it adds
no logic of its own. disarm is an **input-normalization** layer, not an output
sanitizer; read the [Threat Model](https://github.com/raeq/disarm/blob/main/THREAT_MODEL.md)
before relying on it in a security context.

## Development

```sh
cd bindings/ruby
bundle install
bundle exec rake compile   # builds the native ext for the host platform
bundle exec rake spec      # runs the RSpec suite against it
```

`bundle exec rake compile` requires a Rust toolchain (the core is a path
dependency until disarm 0.10 is published to crates.io). Cross-platform release
gems are built in CI with `rb-sys-dock`.

## License

MIT — same as the disarm core.
