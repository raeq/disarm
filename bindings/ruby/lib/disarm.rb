# frozen_string_literal: true

require_relative "disarm/version"

# Load the native extension. Precompiled platform gems ship a per-minor-version
# subdir (e.g. lib/disarm/3.3/disarm.so); a source gem compiles to
# lib/disarm/disarm.so. Try the versioned path first, then fall back.
begin
  ruby_minor = RUBY_VERSION[/\d+\.\d+/]
  require_relative "disarm/#{ruby_minor}/disarm"
rescue LoadError => e
  # Only fall back to the unversioned (source-gem) path when the versioned file
  # is genuinely absent. A real load failure of an *existing* ext (e.g. a missing
  # dependent shared library or an undefined symbol) must propagate, not be masked
  # by the fallback.
  raise unless e.message.include?("cannot load such file")

  require_relative "disarm/disarm"
end

# The native extension (ext/disarm) defines the raw `_`-prefixed shims and the
# already-idiomatic no-option methods (strip_accents, fold_case,
# suspicious_hostname?). This file adds the idiomatic Ruby surface on top (#357):
# keyword arguments with the core's defaults, symbol tokens (:latin, :default, …),
# a single transliterate(text, scheme:) entrypoint, and a Disarm::Error hierarchy.
# Each method is still a thin wrapper over the pure-Rust `disarm` core.
module Disarm
  # Base class for every error disarm raises, so consumers can `rescue
  # Disarm::Error`. The native shim raises Ruby's built-in ArgumentError /
  # RuntimeError; the wrappers below translate those into this hierarchy.
  class Error < StandardError; end

  # Raised for an invalid argument — an unknown scheme/target token, a
  # malformed option, etc. (the core's `ErrorKind::InvalidArgument`).
  class InvalidArgument < Error; end

  class << self
    # Transliterate Unicode text to ASCII. `scheme:` selects the standard:
    # :default (the general-purpose scheme), :strict_iso9, or :gost7034. Accepts
    # a String or Symbol.
    def transliterate(text, scheme: :default)
      scheme = scheme.to_s
      translate_errors do
        # The bare default keeps the core's borrow-on-no-op fast path.
        scheme == "default" ? _transliterate(text) : _transliterate_scheme(text, scheme)
      end
    end

    # Fold cross-script confusables toward `target:` (:latin or :cyrillic).
    def normalize_confusables(text, target: :latin)
      translate_errors { _normalize_confusables(text, target.to_s) }
    end

    # Whether `text` contains a character confusable with `target:` (:latin or
    # :cyrillic).
    def confusable?(text, target: :latin)
      translate_errors { _confusable?(text, target.to_s) }
    end

    # Generate a URL-safe slug. Mirrors the core's `SlugConfig` defaults; every
    # option past `text` is keyword-only. (`regex_pattern`/`replacements` are not
    # surfaced yet — see ext/disarm/src/lib.rs.)
    def slugify(
      text,
      separator: "-",
      lowercase: true,
      max_length: 0,
      word_boundary: false,
      save_order: false,
      stopwords: [],
      allow_unicode: false,
      lang: nil,
      entities: true,
      decimal: true,
      hexadecimal: true,
      safe_chars: ""
    )
      translate_errors do
        # `Array(stopwords)` tolerates the common `stopwords: nil` (and a bare
        # String) instead of raising NoMethodError on `.map`.
        _slugify(
          text, separator.to_s, lowercase, max_length, word_boundary, save_order,
          Array(stopwords).map(&:to_s), allow_unicode, lang&.to_s, entities, decimal,
          hexadecimal, safe_chars.to_s
        )
      end
    end

    # Replace emoji with their plain names (e.g. "👍" → "thumbs up").
    # `strip_modifiers:` drops skin-tone / variation modifiers before naming.
    def demojize(text, strip_modifiers: false)
      translate_errors { _demojize(text, strip_modifiers) }
    end

    # Remove obfuscation (zero-width, bidi, combining-mark abuse) while keeping
    # legible content.
    def strip_obfuscation(text)
      translate_errors { _strip_obfuscation(text) }
    end

    # Aggressive security cleaning: strip obfuscation, control characters, and
    # other spoofing vectors.
    def security_clean(text)
      translate_errors { _security_clean(text) }
    end

    # Strip diacritics ("café" → "cafe").
    def strip_accents(text)
      translate_errors { _strip_accents(text) }
    end

    # Unicode case-fold ("HELLO" → "hello").
    def fold_case(text)
      translate_errors { _fold_case(text) }
    end

    # Whether the hostname looks like a mixed-script / confusable IDN spoof. A
    # false result asserts nothing was *found*, not that the host is safe.
    def suspicious_hostname?(host)
      translate_errors { _suspicious_hostname?(host) }
    end

    private

    # Run a native call, re-raising its built-in exception as the matching
    # Disarm::Error subclass so callers can `rescue Disarm::Error` across the
    # whole surface. The original backtrace is preserved (passed as the third
    # `raise` argument) so the failing native call site stays visible. A bad
    # argument from the native layer can arrive as ArgumentError (an invalid
    # scheme/target), TypeError (a non-String argument), or RangeError (e.g. a
    # negative max_length) — all map to Disarm::InvalidArgument.
    def translate_errors
      yield
    rescue Error
      raise # already in our hierarchy — don't re-wrap
    rescue ::ArgumentError, ::TypeError, ::RangeError => e
      raise InvalidArgument, e.message, e.backtrace
    rescue ::RuntimeError => e
      raise Error, e.message, e.backtrace
    end
  end
end
