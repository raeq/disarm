//! Core-API reproductions (README: B2, E1, E2). Each block prints what the public
//! `disarm::api` does, for comparison with what the Python binding does for the same
//! call (`../repro/python_core_repro.py`).
//!
//! B2 is the lenient `Transliterate::run`, deprecated since 0.17 in favour of `try_run`
//! (removed in 1.0); reproducing the finding means calling it, hence the `allow`.
#![allow(deprecated)]

use disarm::api;
use std::collections::HashMap;

fn main() {
    // S1: api::strip_accents borrows when NFD holds no combining mark, assuming the
    // NFD -> strip -> NFC round trip is then the identity. A singleton decomposition
    // breaks that: the Python binding (which calls the owning form) disagrees.
    println!("-- S1: api::strip_accents on singleton decompositions --");
    for c in ['\u{37e}', '\u{374}', '\u{f900}', '\u{2126}', '\u{1fef}'] {
        let s = c.to_string();
        let a = api::strip_accents(&s);
        let n = api::normalize(&a, "NFC".parse().unwrap());
        println!("  strip_accents(U+{:04X}) = U+{:04X}; NFC of that = U+{:04X}", c as u32,
                 a.chars().next().unwrap() as u32, n.chars().next().unwrap() as u32);
    }
    println!("  strip_accents(\"a\\u{{37e}}\\u{{301}}\") = {:?} (the owning path, taken when a mark is present)",
             api::strip_accents("a\u{37e}\u{301}"));

    // B2: the public builder never validates `lang`; the PyO3 glue does (#68).
    let kyiv = "\u{41a}\u{438}\u{457}\u{432}";
    println!("-- B2: api::Transliterate::lang is unvalidated --");
    for lang in ["uk", "UK", "ukrainian"] {
        let out = api::Transliterate::new().lang(lang).run(kyiv);
        println!("  Transliterate::new().lang({lang:?}).run(kyiv) = {out:?}");
    }
    println!("  search_key(kyiv, Some(\"UK\")) = {:?}", api::search_key(kyiv, Some("UK")).map_err(|e| e.to_string()));

    // E1: registered replacements are applied by the Python binding's transliterate,
    // but not by the public api::transliterate / Transliterate::run.
    println!("-- E1: api::register_replacements has no effect on api::transliterate --");
    let mut m = HashMap::new();
    m.insert("foo".to_owned(), "bar".to_owned());
    api::register_replacements(m).expect("register");
    println!("  after register_replacements({{\"foo\": \"bar\"}}):");
    println!("  api::transliterate(\"foo\")                 = {:?}", api::transliterate("foo"));
    println!("  Transliterate::new().lang(\"de\").run(\"foo\") = {:?}", api::Transliterate::new().lang("de").run("foo"));
    println!("  api::slugify(\"foo\", default)              = {:?}", api::slugify("foo", &api::SlugConfig::default()));
    println!("  api::search_key(\"foo\", None)              = {:?}", api::search_key("foo", None).map_err(|e| e.to_string()));

    // E2: the documented kind of a sealed-registration error.
    println!("-- E2: kind of the error a sealed registration returns --");
    api::seal_registrations();
    let e = api::register_replacements(HashMap::new()).expect_err("sealed");
    println!("  register_replacements after seal: kind = {:?}, message = {:?}", e.kind(), e.to_string());
    let e = api::register_lang("xx", HashMap::new()).expect_err("sealed");
    println!("  register_lang after seal:         kind = {:?}", e.kind());
    let e = api::clear_replacements().expect_err("sealed");
    println!("  clear_replacements after seal:    kind = {:?}", e.kind());
    println!("  (src/api/transliterate.rs documents ErrorKind::Unsupported for all three)");
}
