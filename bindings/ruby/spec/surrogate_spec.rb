# frozen_string_literal: true

require "disarm"

# #469: the malformed-Unicode contract for the Ruby binding.
#
# Ruby has no "lone surrogate" type; the equivalent malformed input is a String
# tagged UTF-8 whose bytes are not valid UTF-8. A lone surrogate U+D83D is the
# (forbidden) 3-byte sequence ED A0 BD; a surrogate *pair* for U+1F600 is the two
# halves ED A0 BD ED B8 80. Such bytes cannot become a Rust &str at the magnus
# boundary, so today every entrypoint raises EncodingError.
#
# Contract (uniform with Python/Node — WTF-8 -> UTF-8, NOT Ruby's per-byte
# String#scrub, which would emit three U+FFFD for one surrogate): a well-formed
# high+low pair recombines into its astral scalar, and each genuinely lone
# surrogate code unit becomes exactly ONE U+FFFD. The reference outputs below are
# spelled explicitly so the granularity is pinned and matches the other bindings.
RSpec.describe "Disarm surrogate / invalid-UTF-8 contract (#469)",
               skip: "blocked on the Ruby WTF-8->UTF-8 boundary decode (#472); spec is the target" do
  utf8 = ->(bytes) { bytes.dup.force_encoding("UTF-8") }

  lone_hi = utf8.call("\xED\xA0\xBD")          # U+D83D, lone
  lone_lo = utf8.call("\xED\xB2\xA0")          # U+DCA0, lone
  pair = utf8.call("\xED\xA0\xBD\xED\xB8\x80") # U+D83D U+DE00 -> recombines to U+1F600

  # (description, raw invalid-UTF-8 input, expected WTF-8->UTF-8 reference form).
  cases = [
    ["lone high", lone_hi, "\u{FFFD}"],
    ["lone low", lone_lo, "\u{FFFD}"],
    ["adjacent to text", utf8.call("abc" + lone_hi), "abc\u{FFFD}"],
    ["two lone around text", utf8.call("a" + lone_hi + "b" + lone_lo + "c"), "a\u{FFFD}b\u{FFFD}c"],
    ["embedded in actionable", utf8.call("PаyPal" + lone_hi + "  ‮ rld"), "PаyPal\u{FFFD}  ‮ rld"],
    ["well-formed pair", pair, "\u{1F600}"],                 # recombine, NOT "??"
    ["pair embedded", utf8.call("x" + pair + "y"), "x\u{1F600}y"],
    ["lone then pair", utf8.call(lone_hi + pair), "\u{FFFD}\u{1F600}"]
  ]

  entrypoints = {
    "canonicalize" => ->(s) { Disarm.canonicalize(s) },
    "strip_obfuscation" => ->(s) { Disarm.strip_obfuscation(s) },
    "transliterate" => ->(s) { Disarm.transliterate(s) },
    "strip_accents" => ->(s) { Disarm.strip_accents(s) },
    "fold_case" => ->(s) { Disarm.fold_case(s) },
    "search_key" => ->(s) { Disarm.search_key(s) },
    "sort_key" => ->(s) { Disarm.sort_key(s) },
    "catalog_key" => ->(s) { Disarm.catalog_key(s) }
  }

  entrypoints.each do |name, fn|
    cases.each do |desc, raw, clean|
      it "#{name}: #{desc} behaves as its WTF-8->UTF-8 form" do
        expect { fn.call(raw) }.not_to raise_error
        expect(fn.call(raw)).to eq(fn.call(clean))
      end
    end

    it "#{name}: valid astral is unaffected" do
      expect(fn.call("\u{1F600} grin \u{103FF}")).to eq(fn.call("\u{1F600} grin \u{103FF}"))
    end
  end
end
