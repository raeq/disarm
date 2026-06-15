#!/usr/bin/env ruby
# frozen_string_literal: true

# Verify the ```ruby doc examples against the built binding (#50 phase 5).
#
# The Ruby tabs document outputs with `# =>` comments, e.g.
#   Disarm.transliterate("Київ", lang: :uk)   # => "Kyiv"
# This script loads the compiled gem and, for every such line, evaluates the
# Disarm.* call and checks it against the documented value — the Ruby analogue of
# the Sybil (Python) and cargo (Rust) doc gates. It is lenient about trailing
# prose in the comment (`# => true (Cyrillic 'а')`): when the expected side does
# not parse as a literal, the call is still run (so a raise is caught) and only
# the value comparison is skipped. Lines without a `# =>` (setup, intentional
# error demos) are ignored — those are covered by RSpec.
#
# Usage:  ruby scripts/check_doc_ruby_examples.rb
# Requires the gem to be built (rake compile) and on the load path.

root = File.expand_path("..", __dir__)
$LOAD_PATH.unshift(File.join(root, "bindings", "ruby", "lib"))
require "disarm"

checked = 0
failures = []

Dir.glob(File.join(root, "docs", "**", "*.md")).sort.each do |md|
  File.read(md).scan(/^[ \t]*```ruby\n(.*?)\n[ \t]*```/m) do |(block)|
    block.each_line do |raw|
      line = raw.strip
      # Only lines that call Disarm.* AND document an expected value.
      next unless line.include?("Disarm.") && line =~ /\A(.+?)\s*#\s*=>\s*(.+?)\s*\z/

      expr = Regexp.last_match(1).strip
      expected_src = Regexp.last_match(2).strip
      next if expr.empty?

      checked += 1
      begin
        got = eval(expr) # rubocop:disable Security/Eval — trusted, our own docs
      rescue StandardError, SyntaxError => e
        failures << "#{File.basename(md)}: `#{expr}` raised #{e.class}: #{e.message}"
        next
      end

      begin
        want = eval(expected_src) # the `# =>` literal
      rescue StandardError, SyntaxError
        next # trailing prose after the literal — call ran, skip value check
      end
      next if got == want

      failures << "#{File.basename(md)}: `#{expr}` => #{got.inspect}, documented #{want.inspect}"
    end
  end
end

puts "checked #{checked} ruby doc expressions"
if failures.empty?
  puts "all ruby doc examples ok"
else
  failures.each { |f| warn "FAIL #{f}" }
  exit 1
end
