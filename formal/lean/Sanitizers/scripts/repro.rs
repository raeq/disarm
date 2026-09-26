// Reproduces the findings of README.md on the Rust core (Layer 2 API), independent of
// any built wheel. Not built by lake. To run: make a scratch crate whose Cargo.toml has
// `disarm = { path = "<repository root>" }` and an empty `[workspace]`, copy this file to
// its `src/main.rs`, and `cargo run`. Labels match `repro.py`.

use disarm::api::{self, Platform, SlugConfig};

fn sf(t: &str, sep: &str, ml: usize, pe: bool) -> String {
    api::sanitize_filename(t, sep, ml, Platform::Universal, None, pe).unwrap()
}

fn main() {
    // Finding 1
    for t in ["_.con", "*.con", "/.nul", "../.con", "?.aux", "\u{200b}.com1"] {
        let o = sf(t, "_", 255, true);
        println!("F1 {:?} -> {:?} -> {:?}", t, o, sf(&o, "_", 255, true));
    }
    let o = api::sanitize_filename("*.NUL", "_", 255, Platform::Windows, None, true).unwrap();
    println!("F1 windows {:?}", o);
    // Finding 2
    println!("F2 {:?}", sf("con _", " ", 4, false));
    println!("F2 {:?}", sf("AUX .txt", " ", 255, false));
    println!("F2 {:?}", sf("../etc/passwd", "/", 255, true));
    println!("F2 {:?}", sf("a b", "\0", 255, true));
    // Finding 3
    for (t, ml, pe) in [("_.x.*", 255, true), ("ab_cd", 3, false), ("a.bcd.txt", 6, true), ("a. .b", 255, false)] {
        let sep = if t == "a. .b" { "" } else { "_" };
        let o = sf(t, sep, ml, pe);
        println!("F3 {:?} -> {:?} -> {:?}", t, o, sf(&o, sep, ml, pe));
    }
    // Slug findings
    let c = SlugConfig::new().with_separator("-_").with_max_length(2);
    println!("F5 {:?}", api::try_slugify("a b", &c).unwrap());
    let c = SlugConfig::new().with_max_length(9).with_word_boundary(true);
    println!("F6 {:?}", api::try_slugify("very long title here", &c).unwrap());
    let c = SlugConfig::new().with_stopwords(["The"]);
    println!("F7 {:?}", api::try_slugify("The Fox", &c).unwrap());
    let c = SlugConfig::new().with_separator("").with_stopwords(["b"]);
    println!("F8 {:?}", api::try_slugify("abc", &c).unwrap());
    let c = SlugConfig::new().with_allow_unicode(true);
    println!("F4 {:?}", api::try_slugify("\u{24b6}dmin", &c).unwrap());
    println!("F10 {:?} {:?}", api::try_slugify("T\u{308}", &c).unwrap(), api::try_slugify("\u{1e97}", &c).unwrap());
    println!("F11 {:?}", api::try_slugify("\u{1f82}", &c).unwrap());
    let c = SlugConfig::new().with_allow_unicode(true).with_max_length(4);
    println!("F13 {:?}", api::try_slugify("a\u{200d}b", &c).unwrap());
    let d = api::decode_to_utf8(&[0xFE, 0xFF, 0, b'A'], Some("utf-8"), 0.0, true).unwrap();
    println!("F14 {:?} {}", d.text, d.had_errors);
    println!("F15 {:?}", sf("%\u{ff05}\u{ff12}\u{ff25}\u{ff05}\u{ff12}\u{ff25}\u{ff05}\u{ff12}\u{ff26}etc.txt", "_", 255, true));
    // Hostname
    for h in ["e\u{ad}vil.com", "e\u{115f}vil.com", "e\u{34f}vil.com", "e\u{180b}vil.com"] {
        let a = api::is_suspicious_hostname(h);
        println!("F12 {:?} suspicious={} invisible={} canonical={:?}", h, a.suspicious, a.has_invisible, a.canonical);
    }
}
