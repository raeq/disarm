# frozen_string_literal: true

# Harness runner for the Ruby binding: the public idiomatic layer (lib/disarm.rb).
# Protocol: see ../rust_oracle/src/main.rs and ../README.md ("The harness").
require "zlib"
require "disarm"

NSCALAR = 0x110000 - 0x800
BLOCK = 4096

Rec = Struct.new(:fields)
def rec(*fields) = Rec.new(fields)

def enc(v, out)
  case v
  when true then out << "b1"
  when false then out << "b0"
  when Integer then out << "i#{v};"
  when nil then out << "n"
  when String
    b = v.b
    out << "s#{b.bytesize}:" << b
  when Symbol then enc(v.to_s, out)
  when Rec
    out << "r#{v.fields.size}:"
    v.fields.each { |f| enc(f, out) }
  when Array
    out << "l#{v.size}:"
    v.each { |x| enc(x, out) }
  else raise "cannot encode #{v.class}"
  end
end

def encode_call(fn, t)
  out = +"".b
  begin
    v = fn.call(t)
  rescue Disarm::InvalidArgument => e
    out << "einv:"
    enc(e.message, out)
    return out
  rescue Disarm::Error => e
    out << "eerr:"
    enc(e.message, out)
    return out
  rescue StandardError => e
    out << "erb:#{e.class}:"
    enc(e.message, out)
    return out
  end
  enc(v, out)
  out
end

def host(a)
  rec(*%i[suspicious scripts mixed_script has_confusables bidi_conflict bidi_control
          has_invisible compat_fold cross_label_script label_scripts
          whole_script_confusable label_whole_script_confusable canonical].map { |k| a.fetch(k) })
end

def anomalies(r)
  rec(r[:anomalous], r[:kinds],
      r[:findings].map { |f| rec(f[:kind], f[:token], f[:start], f[:end], f[:detail], f[:reason]) },
      r[:reason])
end

D = Disarm
CASES = {
  "tr" => ->(t) { D.transliterate(t) },
  "tr_iso9" => ->(t) { D.transliterate(t, scheme: :strict_iso9) },
  "tr_gost" => ->(t) { D.transliterate(t, scheme: :gost7034) },
  "tr_de" => ->(t) { D.transliterate(t, lang: "de") },
  "tr_auto" => ->(t) { D.transliterate(t, lang: "auto") },
  "tr_uk" => ->(t) { D.transliterate(t, lang: "uk") },
  "tr_ja" => ->(t) { D.transliterate(t, lang: "ja") },
  "tr_bad" => ->(t) { D.transliterate(t, lang: "xx") },
  "nc_lat" => ->(t) { D.normalize_confusables(t, target: :latin) },
  "nc_lat_tr39" => ->(t) { D.normalize_confusables(t, target: :latin, digit_policy: :tr39) },
  "nc_lat_pres" => ->(t) { D.normalize_confusables(t, target: :latin, digit_policy: :preserve) },
  "nc_cyr" => ->(t) { D.normalize_confusables(t, target: :cyrillic) },
  "nc_ara" => ->(t) { D.normalize_confusables(t, target: :arabic) },
  "nc_heb" => ->(t) { D.normalize_confusables(t, target: :hebrew) },
  "sa" => ->(t) { D.strip_accents(t) },
  "fc" => ->(t) { D.fold_case(t) },
  "cfs" => ->(t) { D.case_fold_stable?(t) },
  "dj" => ->(t) { D.demojize(t) },
  "dj_sm" => ->(t) { D.demojize(t, strip_modifiers: true) },
  "re_empty" => ->(t) { D.replace_emoji(t, "") },
  "re_sp" => ->(t) { D.replace_emoji(t, " ") },
  "cw" => ->(t) { D.collapse_whitespace(t) },
  "scc" => ->(t) { D.strip_control_chars(t) },
  "szw" => ->(t) { D.strip_zero_width_chars(t) },
  "sbd" => ->(t) { D.strip_bidi(t) },
  "stg" => ->(t) { D.strip_tags(t) },
  "svs" => ->(t) { D.strip_variation_selectors(t) },
  "snc" => ->(t) { D.strip_noncharacters(t) },
  "spua" => ->(t) { D.strip_pua(t) },
  "can" => ->(t) { D.canonicalize(t) },
  "can_tr39" => ->(t) { D.canonicalize(t, digit_policy: :tr39) },
  "can_pres" => ->(t) { D.canonicalize(t, digit_policy: :preserve) },
  "cans" => ->(t) { D.canonicalize_strict(t) },
  "sfmt" => ->(t) { D.strip_format(t) },
  "sobf" => ->(t) { D.strip_obfuscation(t) },
  "sobf_tr39" => ->(t) { D.strip_obfuscation(t, digit_policy: :tr39) },
  "sk" => ->(t) { D.search_key(t) },
  "sk_de" => ->(t) { D.search_key(t, lang: "de") },
  "sok" => ->(t) { D.sort_key(t) },
  "ck" => ->(t) { D.catalog_key(t) },
  "ck_iso" => ->(t) { D.catalog_key(t, strict_iso9: true) },
  "skel" => ->(t) { D.skeleton_key(t) },
  "skel_tr39" => ->(t) { D.skeleton_key(t, digit_policy: :tr39) },
  "nfc" => ->(t) { D.normalize(t, form: :nfc) },
  "nfd" => ->(t) { D.normalize(t, form: :nfd) },
  "nfkc" => ->(t) { D.normalize(t, form: :nfkc) },
  "nfkd" => ->(t) { D.normalize(t, form: :nfkd) },
  "isn_nfc" => ->(t) { D.normalized?(t, form: :nfc) },
  "mix" => ->(t) { D.mixed_script?(t) },
  "bconf" => ->(t) { D.bidi_conflict?(t) },
  "bctl" => ->(t) { D.bidi_control?(t) },
  "susp" => ->(t) { D.suspicious_hostname?(t) },
  "ah" => ->(t) { host(D.analyze_hostname(t)) },
  "ah_c" => ->(t) { host(D.analyze_hostname(t, contractions: true)) },
  "glen" => ->(t) { D.grapheme_len(t) },
  "gsplit" => ->(t) { D.grapheme_split(t) },
  "gtrunc1" => ->(t) { D.grapheme_truncate(t, 1) },
  "tw" => ->(t) { D.terminal_width(t) },
  "tw_amb" => ->(t) { D.terminal_width(t, ambiguous_wide: true) },
  "ial" => lambda { |t|
    a = D.inspect_auto_lang(t)
    rec(a[:script], a[:chosen_lang], a[:reason], a[:discriminators_hit])
  },
  "ds" => ->(t) { D.detect_scripts(t) },
  "iscan" => ->(t) { D.canonical?(t) },
  "mln" => ->(t) { D.ml_normalize(t) },
  "mln_nofold" => ->(t) { D.ml_normalize(t, fold_case: false) },
  "sfn" => ->(t) { D.sanitize_filename(t) },
  "ia" => ->(t) { anomalies(D.inspect_anomalies(t)) },
  "ha" => ->(t) { D.has_anomalies?(t) },
  "ed" => ->(t) { D.edit_distance(t, "paypal") },
  "fu" => ->(t) { D.find_untranslatable(t).map { |u| rec(u[:char], u[:offset]) } },
  "fuc" => ->(t) { D.find_unmapped_confusables(t).map { |u| rec(u[:char], u[:offset]) } },
  "rv_ru" => ->(t) { D.reverse_transliterate(t, lang: :ru) },
  "rv_el" => ->(t) { D.reverse_transliterate(t, lang: :el) },
  "rv_uk" => ->(t) { D.reverse_transliterate(t, lang: :uk) },
  "slug" => ->(t) { D.slugify(t) },
  "zs" => ->(t) { D.strip_zalgo(t, max_marks: 3) },
  "zi" => ->(t) { D.zalgo?(t, threshold: 3) },
  "isconf" => ->(t) { D.confusable?(t) },
}.freeze

# `surr N SEED`: the malformed-Unicode contract (THREAT_MODEL.md, #469) relationally.
# Ruby has no lone surrogate; the equivalent input is a UTF-8-tagged String holding
# WTF-8 (a surrogate encoded as its own 3-byte sequence). f(wtf8) must equal f(scrubbed),
# where scrubbed recombines a high+low pair and turns each lone surrogate into U+FFFD.
def surrogate_check(n, seed)
  rng = Random.new(seed)
  units = [
    -> { 0xD800 + rng.rand(0x400) }, -> { 0xDC00 + rng.rand(0x400) },
    -> { 0x61 + rng.rand(26) }, -> { 0x20 },
    -> { [0xE9, 0x430, 0x5D0, 0x301, 0x200B, 0x202E].sample(random: rng) },
    -> { 0x1F600 + rng.rand(0x50) },
  ]
  enc3 = ->(cp) { [0xE0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3F), 0x80 | (cp & 0x3F)].pack("C*") }
  pairs = []
  n.times do
    cps = Array.new(1 + rng.rand(12)) { units.sample(random: rng).call }
    # Split some astral characters into two surrogate code units, written separately.
    cps = cps.flat_map { |c| c > 0xFFFF && rng.rand < 0.5 ? [0xD800 + ((c - 0x10000) >> 10), 0xDC00 + ((c - 0x10000) & 0x3FF)] : [c] }
    wtf8 = cps.map { |c| (0xD800..0xDFFF).cover?(c) ? enc3.(c) : [c].pack("U").b }.join.force_encoding(Encoding::UTF_8)
    out = []
    i = 0
    while i < cps.size
      c = cps[i]
      if (0xD800..0xDBFF).cover?(c) && cps[i + 1] && (0xDC00..0xDFFF).cover?(cps[i + 1])
        out << (0x10000 + ((c - 0xD800) << 10) + (cps[i + 1] - 0xDC00))
        i += 2
      else
        out << ((0xD800..0xDFFF).cover?(c) ? 0xFFFD : c)
        i += 1
      end
    end
    pairs << [wtf8, out.pack("U*")]
  end
  CASES.each do |c, fn|
    bad = pairs.reject { |w, s| encode_call(fn, w) == encode_call(fn, s) }
    puts "#{c}\t#{pairs.size}\t#{bad.size}\t#{bad.empty? ? '' : bad[0][0].b.inspect}"
  end
end

mode, corpus_path, arg3, lo, hi = ARGV
if mode == "list"
  puts CASES.keys.join(",")
  exit
end
if mode == "surr"
  surrogate_check(corpus_path.to_i, arg3.to_i)
  exit
end
corpus = File.readlines(corpus_path, chomp: true).map { |l| [l].pack("H*").force_encoding(Encoding::UTF_8) }
total = NSCALAR + corpus.size
inp = ->(i) { i < NSCALAR ? [i < 0xD800 ? i : i + 0x800].pack("U") : corpus[i - NSCALAR] }
out = $stdout
out.binmode
case mode
when "crc"
  arg3.split(",").each do |c|
    fn = CASES[c] or next
    (0...((total + BLOCK - 1) / BLOCK)).each do |b|
      l = b * BLOCK
      h = [l + BLOCK, total].min
      crc = 0
      (l...h).each { |i| crc = Zlib.crc32(encode_call(fn, inp.(i)), crc) }
      out.write(format("%s\t%d\t%08x\t%d\n", c, b, crc, h - l))
    end
  end
when "dump"
  fn = CASES.fetch(arg3)
  (lo.to_i...[hi.to_i, total].min).each { |i| out.write("#{i}\t#{encode_call(fn, inp.(i)).unpack1('H*')}\n") }
else
  raise "unknown mode #{mode}"
end
