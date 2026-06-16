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

    # Apply a Unicode normalization form. `form:` is :nfc (default), :nfd,
    # :nfkc, or :nfkd (a Symbol or String; case-insensitive).
    def normalize(text, form: :nfc)
      translate_errors { _normalize(text, form.to_s.upcase) }
    end

    # Whether `text` is already in normalization `form:` (default :nfc).
    def normalized?(text, form: :nfc)
      translate_errors { _normalized?(text, form.to_s.upcase) }
    end

    # Collapse every run of Unicode whitespace to a single ASCII space and trim
    # leading/trailing whitespace. By default also strips control characters
    # (`strip_control:`) and zero-width characters (`strip_zero_width:`).
    def collapse_whitespace(text, strip_control: true, strip_zero_width: true)
      translate_errors { _collapse_whitespace(text, strip_control, strip_zero_width) }
    end

    # Remove C0/C1 control characters (except tab and newline).
    def strip_control_chars(text)
      translate_errors { _strip_control_chars(text) }
    end

    # Remove zero-width characters (ZWSP, ZWNJ, ZWJ, word joiner).
    def strip_zero_width_chars(text)
      translate_errors { _strip_zero_width_chars(text) }
    end

    # Remove Unicode bidirectional control characters (a homoglyph/spoof vector).
    def strip_bidi(text)
      translate_errors { _strip_bidi(text) }
    end

    # Strip "zalgo" combining-mark stacking, keeping at most `max_marks:` (2)
    # combining marks per base character.
    def strip_zalgo(text, max_marks: 2)
      translate_errors { _strip_zalgo(text, max_marks) }
    end

    # Whether `text` looks like zalgo: any base character carries more than
    # `threshold:` (3) combining marks.
    def zalgo?(text, threshold: 3)
      translate_errors { _zalgo?(text, threshold) }
    end

    # Number of grapheme clusters (user-perceived characters). Counts an emoji
    # or flag as one, unlike `String#length` (code points).
    def grapheme_len(text)
      translate_errors { _grapheme_len(text) }
    end

    # Split `text` into an array of grapheme-cluster strings.
    def grapheme_split(text)
      translate_errors { _grapheme_split(text) }
    end

    # Truncate `text` to at most `max_graphemes` grapheme clusters, never cutting
    # through the middle of a cluster.
    def grapheme_truncate(text, max_graphemes)
      translate_errors { _grapheme_truncate(text, max_graphemes) }
    end

    # Display width (terminal columns) of a single grapheme `cluster` by East
    # Asian Width. Pass `ambiguous_wide: true` to treat ambiguous-width
    # characters as 2 columns.
    def grapheme_width(cluster, ambiguous_wide: false)
      translate_errors { _grapheme_width(cluster, ambiguous_wide) }
    end

    # Total display width (terminal columns) of `text`.
    def terminal_width(text, ambiguous_wide: false)
      translate_errors { _terminal_width(text, ambiguous_wide) }
    end

    # Turn arbitrary text into a safe filename. `platform:` is :universal
    # (default), :windows, or :posix; `preserve_extension:` keeps the final
    # extension when truncating to `max_length:`. Raises Disarm::InvalidArgument
    # on an unknown platform.
    def sanitize_filename(text, separator: "_", max_length: 255, platform: :universal,
                          lang: nil, preserve_extension: true)
      translate_errors do
        _sanitize_filename(text, separator.to_s, max_length, platform.to_s,
                           lang&.to_s, preserve_extension)
      end
    end

    # Reverse-transliterate Latin back to a native script. `lang:` is :el (Greek),
    # :ru (Russian), or :uk (Ukrainian) — a Symbol or String.
    def reverse_transliterate(text, lang:)
      translate_errors { _reverse_transliterate(text, lang.to_s) }
    end

    # Every character in `text` with no romanization, as an array of
    # `{ char:, offset: }` hashes (byte offset), in order of appearance.
    # `scheme:`/`lang:` mirror #transliterate.
    def find_untranslatable(text, scheme: :default, lang: nil)
      translate_errors do
        _find_untranslatable(text, scheme.to_s, lang&.to_s)
          .map { |ch, offset| { char: ch, offset: offset } }
      end
    end

    # The Unicode scripts present in `text`, in first-appearance order
    # (Common/Inherited excluded), as stable UCD identifiers (e.g. "Latin").
    def detect_scripts(text)
      translate_errors { _detect_scripts(text) }
    end

    # Whether `text` mixes characters from more than one script.
    def mixed_script?(text)
      translate_errors { _is_mixed_script?(text) }
    end

    # Explain how `lang: "auto"` detection resolves `text`: a hash with
    # `:script`, `:chosen_lang` (both nil if undetected), `:reason`, and
    # `:discriminators_hit`.
    def inspect_auto_lang(text)
      script, chosen_lang, reason, discriminators = translate_errors { _inspect_auto_lang(text) }
      { script: script, chosen_lang: chosen_lang, reason: reason,
        discriminators_hit: discriminators }
    end

    # Whether any whitespace token carries out-of-place characters that disguise a
    # real word — a cross-script homoglyph, leet, segmentation, a zero-width / bidi
    # control, or zalgo. Reports a technical fact and leaves the malicious-or-not
    # judgement to the caller. `lexicon` is a common-word collection (Array or Set)
    # used only by the leet and segmentation branches; it defaults to an empty list
    # when those branches are not needed. A bare String is rejected — pass an Array
    # or any object responding to `:each`.
    def has_anomalies?(text, lexicon = [])
      translate_errors { _has_anomalies?(text, coerce_lexicon(lexicon)) }
    end

    # Full anomaly analysis: a hash with `:anomalous`, `:kinds` (in first-appearance
    # order), `:findings` (each `{ kind:, token:, start:, end:, detail:, reason: }`,
    # with byte offsets), and `:reason` (the first finding's reason, or nil).
    # `lexicon` defaults to an empty list; a bare String is rejected.
    def inspect_anomalies(text, lexicon = [])
      anomalous, kinds, findings, reason =
        translate_errors { _inspect_anomalies(text, coerce_lexicon(lexicon)) }
      {
        anomalous: anomalous,
        kinds: kinds,
        findings: findings.map do |kind, token, start, finish, detail, fr|
          { kind: kind, token: token, start: start, end: finish, detail: detail, reason: fr }
        end,
        reason: reason,
      }
    end

    private

    # Coerce a lexicon argument to an Array of Strings for the native layer.
    # Fast-path: an Array already containing only Strings is passed through as-is.
    # Any other Enumerable (Set, etc.) is mapped to String. A bare String is rejected
    # with ArgumentError — callers must wrap it in an Array: ["word"].
    def coerce_lexicon(lexicon)
      # An explicit nil is treated as an empty lexicon (parity with the `= []`
      # default and the other bindings' null handling), not an error.
      return [] if lexicon.nil?

      raise ::ArgumentError, "lexicon must be an Array or Enumerable, not a String" \
        if lexicon.is_a?(::String)

      return lexicon if lexicon.is_a?(::Array) && lexicon.all?(::String)

      lexicon.map(&:to_s)
    end

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
