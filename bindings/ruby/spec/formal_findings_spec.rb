# frozen_string_literal: true

require "disarm"

# Regression specs for the bindings harness findings (formal/bindings/README.md).
RSpec.describe Disarm do
  describe "R1: a String is read by the encoding it declares" do
    let(:latin1) { "caf\xE9".b.force_encoding(Encoding::ISO_8859_1) }
    let(:cp1251) { "\xCC\xEE\xF1\xEA\xE2\xE0".b.force_encoding(Encoding::Windows_1251) }
    let(:e_acute) { "caf\u00e9" }

    it "transcodes ISO-8859-1" do
      expect(Disarm.transliterate(latin1)).to eq("cafe")
      expect(Disarm.fold_case(latin1)).to eq(e_acute)
      expect(Disarm.edit_distance(latin1, e_acute)).to eq(0)
    end

    it "transcodes Windows-1251" do
      expect(Disarm.transliterate(cp1251)).to eq("Moskva")
    end

    it "transcodes UTF-16LE" do
      expect(Disarm.fold_case("CAF\u00c9".encode(Encoding::UTF_16LE))).to eq(e_acute)
    end

    it "reads one argument two ways no longer" do
      latin1_e = "\xE9".b.force_encoding(Encoding::ISO_8859_1)
      expect(Disarm.replace_emoji(latin1_e, "")).to eq("\u00e9")
      expect(Disarm.replace_emoji("\u{1F600}", latin1_e)).to eq("\u00e9")
    end

    it "maps a byte the declared encoding does not define to one U+FFFD" do
      undefined = "a\x98b".b.force_encoding(Encoding::Windows_1251)
      expect(Disarm.strip_accents(undefined)).to eq("a\uFFFDb")
    end

    it "reads ASCII-8BIT as UTF-8, as the C ABI reads its bytes" do
      expect(Disarm.transliterate("caf\xC3\xA9".b)).to eq("cafe")
      expect(Disarm.strip_accents("caf\xE9".b)).to eq("caf\uFFFD")
    end

    it "maps a US-ASCII String's high byte to one U+FFFD" do
      expect(Disarm.strip_accents("caf\xC3\xA9".b.force_encoding(Encoding::US_ASCII)))
        .to eq("caf\uFFFD\uFFFD")
      expect(Disarm.transliterate("plain".encode(Encoding::US_ASCII))).to eq("plain")
    end

    it "keeps the surrogate contract for UTF-8 Strings" do
      lone = "a\xED\xA0\x80b".b.force_encoding(Encoding::UTF_8)
      expect(Disarm.strip_accents(lone)).to eq("a\uFFFDb")
    end

    it "raises Disarm::InvalidArgument for an encoding Ruby cannot convert" do
      expect { Disarm.transliterate("a".b.force_encoding(Encoding::UTF_7)) }
        .to raise_error(Disarm::InvalidArgument)
    end
  end

  describe "B1: the zalgo defaults are the core defaults" do
    let(:three) { "a\u0316\u0317\u0318" }

    it "exposes the core's constants" do
      expect(Disarm::DEFAULT_ZALGO_MAX_MARKS).to eq(3)
      expect(Disarm::DEFAULT_ZALGO_THRESHOLD).to eq(3)
    end

    it "never strips what zalgo? declines to flag (#788)" do
      expect(Disarm.zalgo?(three)).to be(false)
      expect(Disarm.strip_zalgo(three)).to eq(three)
      expect(Disarm.strip_zalgo("#{three}\u0319")).to eq(three)
    end
  end

  describe "B2: an unknown lang is rejected, as search_key always did" do
    let(:kyiv) { "\u041a\u0438\u0457\u0432" }

    it "raises from transliterate, find_untranslatable and slugify" do
      expect { Disarm.transliterate(kyiv, lang: "UK") }
        .to raise_error(Disarm::InvalidArgument, /unknown language code/)
      expect { Disarm.find_untranslatable(kyiv, lang: "UK") }
        .to raise_error(Disarm::InvalidArgument, /unknown language code/)
      expect { Disarm.slugify("M\u00fcnchen", lang: "dee") }
        .to raise_error(Disarm::InvalidArgument, /unknown language code/)
    end

    it "still accepts a known lang" do
      expect(Disarm.transliterate(kyiv, lang: "uk")).to eq("Kyiv")
      expect(Disarm.slugify("M\u00fcnchen", lang: "de")).to eq("muenchen")
    end
  end

  describe "S1: strip_accents is per character" do
    it "folds a singleton decomposition alone and beside a mark" do
      expect(Disarm.strip_accents("\u037e")).to eq(";")
      expect(Disarm.strip_accents("\u037ee\u0301")).to eq(";e")
    end
  end

  describe "D1: an emoji CLDR cannot name is the [?] sentinel" do
    it "writes [?] for a lone regional indicator" do
      expect(Disarm.demojize("\u{1F1E6}")).to eq("[?]")
      expect(Disarm.demojize("x\u{1F1E6}!")).to eq("x[?]!")
    end
  end

  describe "N2: every wrapper raises in the Disarm hierarchy" do
    it "wraps bidi_control? and strip_format" do
      expect { Disarm.bidi_control?(nil) }.to raise_error(Disarm::InvalidArgument)
      expect { Disarm.strip_format(nil) }.to raise_error(Disarm::InvalidArgument)
    end

    it "gives no public method a bare exception for a wrong-typed argument" do
      public_methods = Disarm.singleton_methods.reject { |m| m.to_s.start_with?("_") }
      expect(public_methods.size).to be > 50
      public_methods.each do |name|
        method = Disarm.method(name)
        required = method.parameters.count { |kind, _| kind == :req }
        keywords = method.parameters.filter_map { |kind, key| key if kind == :keyreq }
        next if required.zero? && keywords.empty?

        [nil, 42, Object.new].each do |bad|
          Disarm.public_send(name, *Array.new(required, bad), **keywords.to_h { |k| [k, bad] })
        rescue Disarm::Error
          nil
        rescue StandardError => e
          raise "#{name}(#{bad.inspect}) raised #{e.class}: #{e.message}"
        end
      end
    end
  end

  describe "J2: the arabic and hebrew targets (#792)" do
    it "accepts them" do
      expect(Disarm.normalize_confusables("x", target: :arabic)).to be_a(String)
      expect(Disarm.confusable?("x", target: :hebrew)).to be(false)
    end
  end
end
