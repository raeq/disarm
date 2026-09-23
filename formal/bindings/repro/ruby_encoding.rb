# frozen_string_literal: true

# R1: the Ruby shim reads a String's raw bytes as UTF-8 whatever its encoding says.
#   ruby -I bindings/ruby/lib formal/bindings/repro/ruby_encoding.rb
require "disarm"

def show(label, s)
  printf("%-44s %-22s %s\n", label, s.encoding, s.dump)
end

latin1 = "caf\u{e9}".encode(Encoding::ISO_8859_1)            # bytes 63 61 66 e9
utf16 = "caf\u{e9}".encode(Encoding::UTF_16LE)               # bytes 63 00 61 00 66 00 e9 00
cp1251 = "\u{41c}\u{43e}\u{441}\u{43a}\u{432}\u{430}".encode(Encoding::Windows_1251)

show("input (ISO-8859-1)", latin1)
show("Disarm.transliterate(latin1)", Disarm.transliterate(latin1))
show("Disarm.transliterate(latin1.encode(UTF-8))", Disarm.transliterate(latin1.encode(Encoding::UTF_8)))
show("Disarm.fold_case(utf16)", Disarm.fold_case(utf16))
show("Disarm.transliterate(cp1251)", Disarm.transliterate(cp1251))
show("Disarm.transliterate(cp1251.encode(UTF-8))", Disarm.transliterate(cp1251.encode(Encoding::UTF_8)))
show("Disarm.edit_distance(latin1, \"caf\\u00e9\")", Disarm.edit_distance(latin1, "caf\u{e9}").to_s)
# The text argument is read as raw bytes (Wtf8Text), but the plain String arguments of
# the same call are transcoded by magnus, so one function reads one encoding two ways:
e_acute = "\u{e9}".encode(Encoding::ISO_8859_1)
show("Disarm.replace_emoji(e_acute, \"\")", Disarm.replace_emoji(e_acute, ""))
show("Disarm.replace_emoji(\"\\u{1f600}\", e_acute)", Disarm.replace_emoji("\u{1f600}", e_acute))
