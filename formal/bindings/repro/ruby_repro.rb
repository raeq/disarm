# frozen_string_literal: true

# Ruby reproductions (README: B1, B2).  ruby -I bindings/ruby/lib formal/bindings/repro/ruby_repro.rb
require "disarm"

def show(label, &blk)
  r = begin
    blk.call.inspect
  rescue StandardError => e
    "raised #{e.class}: #{e.message[0, 90]}"
  end
  printf("%-52s %s\n", label, r)
end

puts "-- B1: strip_zalgo default cap (core DEFAULT_MAX_MARKS = 3, #788) --"
stack = "a\u{316}\u{317}\u{318}" # three marks below one base: not zalgo
show("Disarm.zalgo?(stack)") { Disarm.zalgo?(stack) }
show("Disarm.strip_zalgo(stack).dump") { Disarm.strip_zalgo(stack).dump }
show("Disarm.strip_zalgo(stack, max_marks: 3).dump") { Disarm.strip_zalgo(stack, max_marks: 3).dump }

puts "-- B2: an unknown `lang` is accepted silently --"
kyiv = "\u{41a}\u{438}\u{457}\u{432}"
show("Disarm.transliterate(kyiv, lang: \"uk\")") { Disarm.transliterate(kyiv, lang: "uk") }
show("Disarm.transliterate(kyiv, lang: \"UK\")") { Disarm.transliterate(kyiv, lang: "UK") }
show("Disarm.slugify(\"M\\u00fcnchen\", lang: \"dee\")") { Disarm.slugify("M\u{fc}nchen", lang: "dee") }
show("Disarm.search_key(\"M\\u00fcnchen\", lang: \"dee\")") { Disarm.search_key("M\u{fc}nchen", lang: "dee") }
