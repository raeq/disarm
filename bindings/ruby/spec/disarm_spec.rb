# frozen_string_literal: true

require "disarm"

RSpec.describe Disarm do
  describe ".transliterate" do
    it "transliterates Cyrillic to ASCII with the default scheme" do
      expect(Disarm.transliterate("Москва")).to eq("Moskva")
    end

    it "accepts an explicit scheme as a symbol" do
      expect(Disarm.transliterate("Москва", scheme: :default)).to eq("Moskva")
    end

    it "accepts a scheme as a string" do
      expect(Disarm.transliterate("Москва", scheme: "default")).to eq("Moskva")
    end

    it "raises Disarm::InvalidArgument on an unknown scheme" do
      expect { Disarm.transliterate("x", scheme: :klingon) }
        .to raise_error(Disarm::InvalidArgument)
    end

    it "applies a language profile via lang:" do
      expect(Disarm.transliterate("Київ", lang: "uk")).to eq("Kyiv")
    end

    it "accepts lang: as a symbol" do
      expect(Disarm.transliterate("Київ", lang: :uk)).to eq("Kyiv")
    end

    it "composes a language profile with a scheme" do
      expect(Disarm.transliterate("Київ", scheme: :default, lang: :uk)).to eq("Kyiv")
    end
  end

  describe ".normalize_confusables" do
    it "folds cross-script confusables to the default (:latin) target" do
      expect(Disarm.normalize_confusables("раypal")).to eq("paypal")
    end

    it "accepts a symbol target" do
      expect(Disarm.normalize_confusables("раypal", target: :latin)).to eq("paypal")
    end

    it "raises Disarm::InvalidArgument on an invalid target script" do
      expect { Disarm.normalize_confusables("x", target: :greek) }
        .to raise_error(Disarm::InvalidArgument)
    end

    it "raises a rescuable Disarm::Error" do
      expect { Disarm.normalize_confusables("x", target: :greek) }
        .to raise_error(Disarm::Error)
    end
  end

  describe ".confusable?" do
    it "detects a confusable against the default target" do
      expect(Disarm.confusable?("pаypal")).to be(true)
    end

    it "accepts a symbol target" do
      expect(Disarm.confusable?("pаypal", target: :latin)).to be(true)
    end
  end

  describe ".slugify" do
    it "produces a URL-safe slug with sensible defaults" do
      expect(Disarm.slugify("Héllo, World!")).to eq("hello-world")
    end

    it "honours the separator keyword" do
      expect(Disarm.slugify("a b c", separator: "_")).to eq("a_b_c")
    end

    it "honours max_length with word boundaries" do
      expect(Disarm.slugify("Very Long Title Here", max_length: 10, word_boundary: true))
        .to eq("very-long")
    end

    it "can preserve case" do
      expect(Disarm.slugify("Hello", lowercase: false)).to eq("Hello")
    end

    it "tolerates stopwords: nil" do
      expect(Disarm.slugify("hello world", stopwords: nil)).to eq("hello-world")
    end
  end

  describe ".demojize" do
    it "names emoji" do
      expect(Disarm.demojize("hi 👍")).to eq("hi thumbs up")
    end
  end

  describe "canonicalization primitives" do
    it "strips accents" do
      expect(Disarm.strip_accents("café")).to eq("cafe")
    end

    it "case-folds" do
      expect(Disarm.fold_case("HELLO")).to eq("hello")
    end
  end

  describe "security" do
    it "flags a homoglyph IDN spoof" do
      expect(Disarm.suspicious_hostname?("pаypal.com")).to be(true)
    end
  end

  describe "error hierarchy" do
    it "maps a non-String argument to Disarm::InvalidArgument" do
      expect { Disarm.strip_accents(42) }.to raise_error(Disarm::InvalidArgument)
    end

    it "lets a single rescue Disarm::Error catch a wrong-type argument" do
      expect { Disarm.fold_case(nil) }.to raise_error(Disarm::Error)
    end
  end
end
