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

# The native extension defines the `Disarm` module and its singleton methods
# (transliterate, normalize_confusables, strip_accents, fold_case, slugify,
# strip_obfuscation, security_clean, suspicious_hostname?, confusable?, demojize).
# Each is a thin wrapper over the pure-Rust `disarm` core — see the README.
module Disarm
end
