# frozen_string_literal: true

# Emit disarm's LIVE Ruby public surface as a JSON array of method names.
#
# Reality, not source-scraping: require the built gem and read the Disarm module's
# own public methods (predicates keep their ? / ! suffix, matching the manifest).
# The parity checker (scripts/parity_check.py) diffs this against the manifest.
# Run after `rake compile`, on a magnus-compatible Ruby (3.1-3.3):
#
#   ruby tools/introspect/ruby_surface.rb > surfaces/ruby.json
require "json"
require_relative "../../bindings/ruby/lib/disarm"

# Public op surface only: the `_`-prefixed methods are the raw magnus shims that
# lib/disarm.rb wraps — implementation detail, not part of the public API.
names = Disarm.methods(false).map(&:to_s).reject { |m| m.start_with?("_") }.sort
puts JSON.generate(names)
