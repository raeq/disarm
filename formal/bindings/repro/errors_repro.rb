# frozen_string_literal: true

# R2: "Everything disarm raises descends from Disarm::Error" (docs/ruby/api.md, Errors).
#   ruby -I bindings/ruby/lib formal/bindings/repro/errors_repro.rb
require "disarm"

[
  ["Disarm.transliterate(nil)", -> { Disarm.transliterate(nil) }],
  ["Disarm.strip_accents(nil)", -> { Disarm.strip_accents(nil) }],
  ["Disarm.fold_case(1)", -> { Disarm.fold_case(1) }],
  ["Disarm.suspicious_hostname?(nil)", -> { Disarm.suspicious_hostname?(nil) }],
  ["Disarm.bidi_control?(nil)", -> { Disarm.bidi_control?(nil) }],
  ["Disarm.strip_zalgo(\"x\", max_marks: 1.5)", -> { Disarm.strip_zalgo("x", max_marks: 1.5) }],
  ["Disarm.strip_zalgo(\"x\", max_marks: -1)", -> { Disarm.strip_zalgo("x", max_marks: -1) }],
].each do |label, f|
  r = f.call
  printf("%-44s returned %p\n", label, r)
rescue Exception => e # rubocop:disable Lint/RescueException
  printf("%-44s raised %s; is_a?(Disarm::Error) = %s\n", label, e.class, e.is_a?(Disarm::Error))
end
