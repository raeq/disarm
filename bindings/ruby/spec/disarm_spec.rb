# frozen_string_literal: true

require "disarm"

RSpec.describe Disarm do
  it "transliterates Cyrillic to ASCII" do
    expect(Disarm.transliterate("Москва")).to eq("Moskva")
  end

  it "folds cross-script confusables to the target script" do
    expect(Disarm.normalize_confusables("раypal", "latin")).to eq("paypal")
  end

  it "detects a confusable" do
    expect(Disarm.confusable?("pаypal", "latin")).to be(true)
  end

  it "strips accents" do
    expect(Disarm.strip_accents("café")).to eq("cafe")
  end

  it "case-folds" do
    expect(Disarm.fold_case("HELLO")).to eq("hello")
  end

  it "flags a homoglyph IDN spoof" do
    expect(Disarm.suspicious_hostname?("pаypal.com")).to be(true)
  end

  it "raises ArgumentError on an invalid target script" do
    expect { Disarm.normalize_confusables("x", "greek") }.to raise_error(ArgumentError)
  end
end
