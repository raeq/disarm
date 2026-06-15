# frozen_string_literal: true

require_relative "lib/disarm/version"

Gem::Specification.new do |spec|
  spec.name = "disarm"
  spec.version = Disarm::VERSION
  spec.authors = ["Richard Quinn"]
  spec.email = ["quinn.richard@gmail.com"]

  spec.summary = "Unicode confusable/text-security building blocks, powered by Rust"
  spec.description = <<~DESC
    Ruby bindings for the disarm Rust core: TR39 confusable folding, bidi/zalgo/
    zero-width neutralization, Unicode normalization, standards-based
    transliteration, slugification, and IDN/hostname spoof detection. The native
    extension wraps the pure-Rust core (no Python), so precompiled platform gems
    run without a local Rust toolchain.
  DESC
  spec.homepage = "https://github.com/raeq/disarm"
  spec.license = "MIT"
  # 3.1 is the oldest non-EOL Ruby and matches the CI test matrix + cross-gem
  # targets; magnus 0.7 supports it. RubyGems >= 3.3.22 is required for rb-sys
  # precompiled platform-gem resolution (older RubyGems can't match the platform
  # gems) — Ruby 3.1 ships a new-enough RubyGems.
  spec.required_ruby_version = ">= 3.1.0"
  spec.required_rubygems_version = ">= 3.3.22"

  spec.files = Dir[
    "lib/**/*.rb",
    "ext/**/*.{rs,toml,rb}",
    "README.md",
    "LICENSE"
  ]
  spec.require_paths = ["lib"]
  spec.extensions = ["ext/disarm/extconf.rb"]

  spec.metadata["homepage_uri"] = spec.homepage
  spec.metadata["source_code_uri"] = "https://github.com/raeq/disarm"
  spec.metadata["documentation_uri"] = "https://docs.disarm.dev"
  spec.metadata["rubygems_mfa_required"] = "true"

  # rb_sys provides the build-time bridge between cargo and rake-compiler.
  spec.add_dependency "rb_sys", "~> 0.9"

  spec.add_development_dependency "rake", "~> 13.0"
  spec.add_development_dependency "rake-compiler", "~> 1.2"
  spec.add_development_dependency "rspec", "~> 3.0"
end
