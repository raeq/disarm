//! Differential-testing oracle: the Rust core's answer for every harness case.
//!
//! Every runner (this one, and one per binding under `../runners/`) implements the
//! same protocol, described in `../README.md` ("The harness"):
//!
//! * inputs: index `i < NSCALAR` is the `i`-th Unicode scalar value (surrogates
//!   skipped); index `NSCALAR + k` is line `k` of the corpus file (hex of UTF-8).
//! * each result is encoded with `V` (below) and CRC-32'd per block of `BLOCK` inputs.
//! * `crc <corpus> <case,case,...>` prints `case\tblock\tcrc\tcount` per block.
//! * `dump <corpus> <case> <from> <to>` prints `idx\thex(V(result))` per input.
//!
//! Only `disarm::api` is called: this is the public core surface every binding wraps.

use disarm::api;
use std::fmt::Write as _;
use std::io::{BufWriter, Write};

const NSCALAR: usize = 0x11_0000 - 0x800;
const BLOCK: usize = 4096;

// -- value encoding V -------------------------------------------------------------

enum Val {
    S(String),
    B(bool),
    I(i128),
    N,
    L(Vec<Val>),
    R(Vec<Val>),
}

fn enc(v: &Val, out: &mut Vec<u8>) {
    match v {
        Val::S(s) => {
            out.extend_from_slice(format!("s{}:", s.len()).as_bytes());
            out.extend_from_slice(s.as_bytes());
        }
        Val::B(b) => out.extend_from_slice(if *b { b"b1" } else { b"b0" }),
        Val::I(i) => out.extend_from_slice(format!("i{i};").as_bytes()),
        Val::N => out.push(b'n'),
        Val::L(xs) | Val::R(xs) => {
            let tag = if matches!(v, Val::L(_)) { 'l' } else { 'r' };
            out.extend_from_slice(format!("{tag}{}:", xs.len()).as_bytes());
            for x in xs {
                enc(x, out);
            }
        }
    }
}

fn enc_err(e: &disarm::Error, out: &mut Vec<u8>) {
    let kind = match e.kind() {
        disarm::ErrorKind::InvalidArgument => "inv",
        _ => "err",
    };
    out.extend_from_slice(format!("e{kind}:").as_bytes());
    enc(&Val::S(e.to_string()), out);
}

fn s(x: impl Into<String>) -> Val {
    Val::S(x.into())
}
fn strs<I: IntoIterator<Item = T>, T: Into<String>>(xs: I) -> Val {
    Val::L(xs.into_iter().map(|x| Val::S(x.into())).collect())
}
fn opt(x: Option<String>) -> Val {
    x.map_or(Val::N, Val::S)
}

// -- crc32 (IEEE, reflected; identical to zlib.crc32) -----------------------------

fn crc_table() -> [u32; 256] {
    let mut t = [0u32; 256];
    for (n, slot) in t.iter_mut().enumerate() {
        let mut c = n as u32;
        for _ in 0..8 {
            c = if c & 1 != 0 { 0xEDB8_8320 ^ (c >> 1) } else { c >> 1 };
        }
        *slot = c;
    }
    t
}

fn crc_update(t: &[u32; 256], crc: u32, bytes: &[u8]) -> u32 {
    let mut c = !crc;
    for &b in bytes {
        c = t[((c ^ u32::from(b)) & 0xFF) as usize] ^ (c >> 8);
    }
    !c
}

// -- cases ------------------------------------------------------------------------

type R = Result<Val, disarm::Error>;

fn tr(text: &str, scheme: Option<api::Scheme>, lang: Option<&str>) -> R {
    let mut b = api::Transliterate::new();
    if let Some(sc) = scheme {
        b = b.scheme(sc);
    }
    if let Some(l) = lang {
        b = b.lang(l);
    }
    // `try_run`, not `run`: it is what every binding calls, so an unknown `lang` is an
    // InvalidArgument here as there (B2), and registered replacements apply (E1).
    Ok(s(b.try_run(text)?))
}

fn nc(text: &str, target: &str, policy: &str) -> R {
    let t: api::TargetScript = target.parse()?;
    let p: api::DigitPolicy = policy.parse()?;
    Ok(s(api::normalize_confusables_with(text, t, p)))
}

fn host(a: &api::HostnameAnalysis) -> Val {
    Val::R(vec![
        Val::B(a.suspicious),
        strs(a.scripts.iter().cloned()),
        Val::B(a.mixed_script),
        Val::B(a.has_confusables),
        Val::B(a.bidi_conflict),
        Val::B(a.bidi_control),
        Val::B(a.has_invisible),
        Val::B(a.compat_fold),
        Val::B(a.cross_label_script),
        Val::L(a.label_scripts.iter().map(|l| strs(l.iter().cloned())).collect()),
        Val::B(a.whole_script_confusable),
        Val::L(a.label_whole_script_confusable.iter().map(|b| Val::B(*b)).collect()),
        s(a.canonical.clone()),
    ])
}

fn anomalies(r: &api::AnomalyReport) -> Val {
    Val::R(vec![
        Val::B(r.anomalous),
        strs(r.kinds.iter().map(|k| k.as_str())),
        Val::L(
            r.findings
                .iter()
                .map(|f| {
                    Val::R(vec![
                        s(f.kind.as_str()),
                        s(f.token.clone()),
                        Val::I(f.start as i128),
                        Val::I(f.end as i128),
                        s(f.detail.clone()),
                        s(f.reason()),
                    ])
                })
                .collect(),
        ),
        opt(r.reason.clone()),
    ])
}

fn run_case(case: &str, t: &str) -> Option<R> {
    use api::DigitPolicy as D;
    let pol = |p: &str| -> D { p.parse().unwrap() };
    Some(match case {
        "tr" => Ok(s(api::transliterate(t))),
        "tr_iso9" => tr(t, Some(api::Scheme::StrictIso9), None),
        "tr_gost" => tr(t, Some(api::Scheme::GostR7034), None),
        "tr_de" => tr(t, None, Some("de")),
        "tr_auto" => tr(t, None, Some("auto")),
        "tr_uk" => tr(t, None, Some("uk")),
        "tr_ja" => tr(t, None, Some("ja")),
        "tr_bad" => tr(t, None, Some("xx")),
        "nc_lat" => nc(t, "latin", "numeric"),
        "nc_lat_tr39" => nc(t, "latin", "tr39"),
        "nc_lat_pres" => nc(t, "latin", "preserve"),
        "nc_cyr" => nc(t, "cyrillic", "numeric"),
        "nc_ara" => nc(t, "arabic", "numeric"),
        "nc_heb" => nc(t, "hebrew", "numeric"),
        "sa" => Ok(s(api::strip_accents(t))),
        "fc" => Ok(s(api::fold_case(t))),
        "cfs" => Ok(Val::B(api::is_case_fold_stable(t))),
        "dj" => Ok(s(api::demojize(t, false))),
        "dj_sm" => Ok(s(api::demojize(t, true))),
        "re_empty" => Ok(s(api::replace_emoji(t, ""))),
        "re_sp" => Ok(s(api::replace_emoji(t, " "))),
        "cw" => Ok(s(api::collapse_whitespace(t))),
        "scc" => Ok(s(api::strip_control_chars(t))),
        "szw" => Ok(s(api::strip_zero_width_chars(t))),
        "sbd" => Ok(s(api::strip_bidi(t))),
        "stg" => Ok(s(api::strip_tags(t))),
        "svs" => Ok(s(api::strip_variation_selectors(t))),
        "snc" => Ok(s(api::strip_noncharacters(t))),
        "spua" => Ok(s(api::strip_pua(t))),
        "can" => api::canonicalize_with(t, D::Numeric).map(s),
        "can_tr39" => api::canonicalize_with(t, pol("tr39")).map(s),
        "can_pres" => api::canonicalize_with(t, pol("preserve")).map(s),
        "cans" => api::canonicalize_strict_with(t, D::Numeric).map(s),
        "sfmt" => Ok(s(api::strip_format(t))),
        "sobf" => api::strip_obfuscation_with(t, D::Numeric).map(s),
        "sobf_tr39" => api::strip_obfuscation_with(t, pol("tr39")).map(s),
        "sk" => api::search_key_with(t, None, D::Numeric).map(s),
        "sk_de" => api::search_key_with(t, Some("de"), D::Numeric).map(s),
        "sok" => api::sort_key_with(t, None, D::Numeric).map(s),
        "ck" => api::catalog_key_with(t, None, false, D::Numeric).map(s),
        "ck_iso" => api::catalog_key_with(t, None, true, D::Numeric).map(s),
        "skel" => api::skeleton_key(t, D::Numeric).map(s),
        "skel_tr39" => api::skeleton_key(t, pol("tr39")).map(s),
        "nfc" | "nfd" | "nfkc" | "nfkd" => {
            let f: api::NormalizationForm = case.to_uppercase().parse().unwrap();
            Ok(s(api::normalize(t, f)))
        }
        "isn_nfc" => Ok(Val::B(api::is_normalized(t, "NFC".parse().unwrap()))),
        "mix" => Ok(Val::B(api::is_mixed_script(t))),
        "bconf" => Ok(Val::B(api::has_bidi_conflict(t))),
        "bctl" => Ok(Val::B(api::has_bidi_control(t))),
        "susp" => Ok(Val::B(api::is_suspicious_hostname(t).suspicious)),
        "ah" => Ok(host(&api::analyze_hostname_with(t, false))),
        "ah_c" => Ok(host(&api::analyze_hostname_with(t, true))),
        "glen" => Ok(Val::I(api::grapheme_len(t) as i128)),
        "gsplit" => Ok(strs(api::grapheme_split(t))),
        "gtrunc1" => Ok(s(api::grapheme_truncate(t, 1))),
        "tw" => Ok(Val::I(api::terminal_width(t, false) as i128)),
        "tw_amb" => Ok(Val::I(api::terminal_width(t, true) as i128)),
        "ial" => {
            let a = api::inspect_auto_lang(t);
            Ok(Val::R(vec![
                opt(a.script.clone()),
                opt(a.chosen_lang.clone()),
                s(a.reason.clone()),
                strs(a.discriminators_hit.iter().cloned()),
            ]))
        }
        "ds" => Ok(strs(api::detect_scripts(t))),
        "iscan" => api::is_canonical(t, "canonicalize").map(Val::B),
        "mln" => api::ml_normalize(t, None, "cldr", true).map(s),
        "mln_nofold" => api::ml_normalize(t, None, "cldr", false).map(s),
        "sfn" => api::sanitize_filename(t, "_", 255, api::Platform::Universal, None, true).map(s),
        "ia" => Ok(anomalies(&api::inspect_anomalies(t, &api::lexicon(Vec::<String>::new())))),
        "ha" => Ok(Val::B(api::has_anomalies(t, &api::lexicon(Vec::<String>::new())))),
        "ed" => Ok(Val::I(api::edit_distance(t, "paypal") as i128)),
        "fu" => api::Transliterate::new()
            .try_find_untranslatable(t)
            .map(|found| {
                Val::L(
                    found
                        .into_iter()
                        .map(|u| Val::R(vec![s(u.ch.to_string()), Val::I(u.offset as i128)]))
                        .collect(),
                )
            }),
        "fuc" => Ok(Val::L(
            api::find_unmapped_confusables(t, api::TargetScript::Latin)
                .into_iter()
                .map(|u| Val::R(vec![s(u.ch.to_string()), Val::I(u.offset as i128)]))
                .collect(),
        )),
        "rv_ru" | "rv_el" | "rv_uk" => {
            let l: api::ReverseLang = case[3..].parse().unwrap();
            Ok(s(api::reverse_transliterate(t, l)))
        }
        "slug" => api::try_slugify(t, &api::SlugConfig::default()).map(s),
        "zs" => Ok(s(api::strip_zalgo(t, 3))),
        "zi" => Ok(Val::B(api::is_zalgo(t, 3))),
        // B1: each binding's own default, against the core's.
        "zs_def" => Ok(s(api::strip_zalgo(t, api::DEFAULT_ZALGO_MAX_MARKS))),
        "zi_def" => Ok(Val::B(api::is_zalgo(t, api::DEFAULT_ZALGO_THRESHOLD))),
        "isconf" => Ok(Val::B(api::is_confusable(t, api::TargetScript::Latin))),
        _ => return None,
    })
}

fn load_corpus(path: &str) -> Vec<String> {
    let data = std::fs::read_to_string(path).expect("corpus");
    data.lines()
        .map(|l| {
            let bytes: Vec<u8> = (0..l.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&l[i..i + 2], 16).unwrap())
                .collect();
            String::from_utf8(bytes).expect("corpus line is UTF-8")
        })
        .collect()
}

fn input(i: usize, corpus: &[String]) -> String {
    if i < NSCALAR {
        let cp = if i < 0xD800 { i } else { i + 0x800 } as u32;
        char::from_u32(cp).unwrap().to_string()
    } else {
        corpus[i - NSCALAR].clone()
    }
}

fn encode(case: &str, t: &str, buf: &mut Vec<u8>) {
    match run_case(case, t).unwrap_or_else(|| panic!("unknown case {case}")) {
        Ok(v) => enc(&v, buf),
        Err(e) => enc_err(&e, buf),
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let corpus = load_corpus(&args[2]);
    let total = NSCALAR + corpus.len();
    let out = std::io::stdout();
    let mut out = BufWriter::new(out.lock());
    match args[1].as_str() {
        "crc" => {
            let table = crc_table();
            for case in args[3].split(',') {
                let mut buf = Vec::new();
                for block in 0..total.div_ceil(BLOCK) {
                    let (lo, hi) = (block * BLOCK, ((block + 1) * BLOCK).min(total));
                    let mut crc = 0u32;
                    for i in lo..hi {
                        buf.clear();
                        encode(case, &input(i, &corpus), &mut buf);
                        crc = crc_update(&table, crc, &buf);
                    }
                    writeln!(out, "{case}\t{block}\t{crc:08x}\t{}", hi - lo).unwrap();
                }
            }
        }
        "dump" => {
            let case = &args[3];
            let lo: usize = args[4].parse().unwrap();
            let hi: usize = args[5].parse::<usize>().unwrap().min(total);
            let mut buf = Vec::new();
            for i in lo..hi {
                buf.clear();
                encode(case, &input(i, &corpus), &mut buf);
                let mut hex = String::with_capacity(buf.len() * 2);
                for b in &buf {
                    write!(hex, "{b:02x}").unwrap();
                }
                writeln!(out, "{i}\t{hex}").unwrap();
            }
        }
        "cases" => {
            for c in args[3].split(',') {
                writeln!(out, "{c}\t{}", run_case(c, "a").is_some()).unwrap();
            }
        }
        m => panic!("unknown mode {m}"),
    }
}
