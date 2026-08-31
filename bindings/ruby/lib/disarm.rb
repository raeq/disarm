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
    # :default (the general-purpose scheme), :strict_iso9, or :gost7034. `lang:`
    # applies a language profile on top of the scheme (e.g. "uk" → Київ → "Kyiv",
    # "de" → ü → "ue"); nil means no profile. Both accept a String or Symbol.
    def transliterate(text, scheme: :default, lang: nil)
      scheme = scheme.to_s
      lang = lang&.to_s
      translate_errors do
        # The bare default with no profile keeps the core's borrow-on-no-op fast
        # path; any scheme or lang takes the option-carrying builder path.
        if lang.nil? && scheme == "default"
          _transliterate(text)
        else
          _transliterate_opts(text, scheme, lang)
        end
      end
    end

    # Fold cross-script confusables toward `target:` (:latin or :cyrillic).
    #
    # `digit_policy:` selects how non-Latin DIGITS fold (#561).
    #
    # `:numeric` (default) sends them to the ASCII digit — `०` becomes `0` — which is
    # right for prose, where a Devanagari zero really is a zero.
    #
    # `:tr39` uses upstream's targets, which send most of them to a Latin letter
    # (`०` → `o`; three of the 45 rows fold to `.` or to the two characters `rn`
    # instead). That is what an identifier *skeleton* wants, since its only job is to
    # make two confusable identifiers collide. The two differ on 45 rows and agree
    # everywhere else. Scoped to `target: :latin` — the override rows are generated from
    # the Latin table and carry TR39's Latin-script targets, so with `target: :cyrillic`
    # it is a no-op.
    #
    # `:preserve` leaves the digit alone (#648). The other two both yield a mixed-script
    # numeral — `२०२४` becomes `२0२४` or `२o२४` — so neither keeps the script. Unlike
    # `:tr39` it applies under every target script.
    def normalize_confusables(text, target: :latin, digit_policy: :numeric)
      translate_errors { _normalize_confusables(text, target.to_s, digit_policy.to_s) }
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

    # Canonicalize, but raise rather than silently normalize a structural difference
    # away — the half of the pair that lets a caller reject input instead of comparing
    # a value the sender never wrote.
    def canonicalize_strict(text)
      translate_errors { _canonicalize_strict(text) }
    end

    # Strip the non-interchange and invisible classes while KEEPING the script.
    #
    # Unlike `canonicalize` it folds no confusables, so non-Latin text survives as
    # itself. It cannot be rebuilt from the seven universal `strip_*` methods, and the
    # difference runs both ways: this preserves the Private Use Area (icon fonts) and
    # keeps the VS15/VS16 presentation selectors after a base, which the naive chain
    # deletes, and it collapses TAB/LF to a space, which the primitives leave alone.
