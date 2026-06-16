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

  describe "normalization" do
    it "defaults to NFC and accepts an explicit form" do
      # The default form is :nfc, which leaves the ﬁ ligature intact;
      # :nfkc is the compatibility form that decomposes it.
      expect(Disarm.normalize("ﬁ")).to eq("ﬁ")
      expect(Disarm.normalize("ﬁ", form: :nfkc)).to eq("fi")
    end

    it "accepts the form as a case-insensitive string" do
      expect(Disarm.normalize("2²", form: "NFKC")).to eq("22")
    end

    it "reports whether text is already in a form" do
      expect(Disarm.normalized?("café", form: :nfc)).to be(true)
      expect(Disarm.normalized?("ﬁ", form: :nfkc)).to be(false)
    end

    it "raises Disarm::InvalidArgument on an unknown form" do
      expect { Disarm.normalize("x", form: :nfz) }
        .to raise_error(Disarm::InvalidArgument)
    end
  end

  describe "text cleaning" do
    it "collapses whitespace runs to single spaces" do
      expect(Disarm.collapse_whitespace("  a   b ")).to eq("a b")
    end

    it "strips control characters" do
      expect(Disarm.strip_control_chars("a\u0007b")).to eq("ab")
    end

    it "can leave control characters in place" do
      expect(Disarm.collapse_whitespace("a\u0007b", strip_control: false))
        .to eq("a\u0007b")
    end

    it "strips zero-width characters" do
      expect(Disarm.strip_zero_width_chars("a\u200Bb")).to eq("ab")
    end

    it "strips bidi controls" do
      expect(Disarm.strip_bidi("a\u202Eb")).to eq("ab")
    end

    it "detects zalgo and strips it back under the threshold" do
      zalgo = "Z" + ("\u0301" * 8)
      expect(Disarm.zalgo?(zalgo)).to be(true)
      expect(Disarm.zalgo?(Disarm.strip_zalgo(zalgo))).to be(false)
    end
  end

  describe "grapheme clusters" do
    it "counts user-perceived characters, not code points" do
      expect(Disarm.grapheme_len("a👍b")).to eq(3)
      expect(Disarm.grapheme_len("🇬🇧")).to eq(1)
    end

    it "splits into grapheme-cluster strings" do
      expect(Disarm.grapheme_split("a👍")).to eq(["a", "👍"])
    end

    it "truncates by graphemes without cutting a cluster" do
      expect(Disarm.grapheme_truncate("héllo", 3)).to eq("hél")
      expect(Disarm.grapheme_truncate("a👍b👎", 2)).to eq("a👍")
    end

    it "measures display width by East Asian Width" do
      expect(Disarm.grapheme_width("👍")).to eq(2)
      expect(Disarm.grapheme_width("a")).to eq(1)
    end

    it "measures total terminal width" do
      expect(Disarm.terminal_width("a👍")).to eq(3)
      expect(Disarm.terminal_width("hello")).to eq(5)
    end
  end

  describe "filenames" do
    it "turns text into a safe filename" do
      expect(Disarm.sanitize_filename("My: report*.txt")).to eq("My_report.txt")
    end

    it "applies platform rules" do
      expect(Disarm.sanitize_filename("CON", platform: :windows)).to eq("_CON")
    end

    it "raises Disarm::InvalidArgument on an unknown platform" do
      expect { Disarm.sanitize_filename("x", platform: :amiga) }
        .to raise_error(Disarm::InvalidArgument)
    end
  end

  describe "reverse transliteration" do
    it "maps Latin back to a native script" do
      expect(Disarm.reverse_transliterate("Moskva", lang: :ru)).to eq("Москва")
      expect(Disarm.reverse_transliterate("Athina", lang: :el)).to eq("Αθηνα")
    end

    it "raises Disarm::InvalidArgument on an unsupported lang" do
      expect { Disarm.reverse_transliterate("x", lang: :fr) }
        .to raise_error(Disarm::InvalidArgument)
    end
  end

  describe "untranslatable scan" do
    it "lists characters with no romanization as { char:, offset: }" do
      expect(Disarm.find_untranslatable("a🜊")).to eq([{ char: "🜊", offset: 1 }])
    end

    it "is empty when everything romanizes" do
      expect(Disarm.find_untranslatable("café")).to eq([])
    end
  end

  describe "script analysis" do
    it "detects the scripts present, in order" do
      expect(Disarm.detect_scripts("aМ")).to eq(%w[Latin Cyrillic])
    end

    it "flags mixed-script text" do
      expect(Disarm.mixed_script?("aМ")).to be(true)
      expect(Disarm.mixed_script?("abc")).to be(false)
    end

    it "explains auto-language detection" do
      info = Disarm.inspect_auto_lang("Москва")
      expect(info[:script]).to eq("Cyrillic")
      expect(info[:chosen_lang]).to eq("ru")
      expect(info[:reason]).to eq("script_default")
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
