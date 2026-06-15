# disarm for Ruby

Ruby bindings wrap the **pure-Rust `disarm` core** (no Python) via
[magnus](https://github.com/matsadler/magnus) +
[rb-sys](https://github.com/oxidize-rb/rb-sys). Precompiled platform gems
install without a local Rust toolchain.

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
falls back to compiling from source otherwise.

## Quick start

Options are keyword arguments; scheme/target tokens are symbols (or strings).
The two operations people most often confuse are *visual* confusable folding
(homoglyph defence) and *phonetic* transliteration (romanization) — see
[Which function do I want?](../concepts/which-function.md).

```ruby
require "disarm"

# Visual (TR39) confusable folding — homoglyph defence
Disarm.normalize_confusables("раypal")        # => "paypal"
Disarm.confusable?("pаypal")                  # => true

# Phonetic romanization — readable ASCII, NOT a security control.
# A language profile sharpens the output: the uk profile gives Київ → Kyiv.
Disarm.transliterate("Київ", lang: "uk")      # => "Kyiv"
Disarm.transliterate("Київ", scheme: :strict_iso9)
Disarm.slugify("Héllo Wörld")                 # => "hello-world"

# Hostname / IDN spoof check (a false result is not a safety guarantee)
Disarm.suspicious_hostname?("pаypal.com")     # => true (Cyrillic 'а')
```

## Errors

Everything disarm raises descends from `Disarm::Error < StandardError`, so a
single `rescue Disarm::Error` catches all of them. Bad input (an invalid
scheme/target, a non-String argument) raises the more specific
`Disarm::InvalidArgument`, with the original backtrace preserved.

```ruby
begin
  Disarm.transliterate("x", scheme: :klingon)
rescue Disarm::InvalidArgument => e   # also rescuable as Disarm::Error
  warn e.message
end
```

## Where next

- **[Ruby API reference](api.md)** — the full `Disarm` call surface, every method
  with a runnable example.
- **Concepts** (shared across every language) — start with
  [Which function do I want?](../concepts/which-function.md), then the topic
  guides under *Guide* in the sidebar.
- The binding inherits the core's guarantees and limits verbatim — read the
  [Threat Model](../THREAT_MODEL.md) before relying on it in a security context.
