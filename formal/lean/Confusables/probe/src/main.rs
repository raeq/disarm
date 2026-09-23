//! Property sweeps of the confusable surface, run against the in-repo core.
//!
//! This is the "large-scale search directly against the library" half of the
//! Confusables model (see ../README.md). It calls only the public `disarm::api`
//! surface every binding reaches, so a failure here is a failure a caller sees.
//!
//! Subcommands (all print `property count [first examples]`):
//!
//! * `starters`  composites whose canonical decomposition ends in a character that is
//!               NOT a combining mark and not a conjoining jamo: the compositions
//!               `compose::composed` cannot see (F3).
//! * `pairs`     every table source, value character and decomposition head, crossed
//!               with every combining mark, for all four targets and all three digit
//!               policies: idempotence, completeness, NFC/NFD invariance of the fold
//!               and of `is_confusable`, and `is_confusable == !find_confusables`.
//! * `triples`   the same, Latin target, source x composing mark x composing mark.
//! * `skeleton`  `skeleton_key` idempotence, NFC/NFD invariance and "not flagged by
//!               is_confusable": every scalar value, and every scalar crossed with
//!               every composing mark (directly, and with U+0001 between them).
//! * `cow`       the borrow contract of `api::normalize_confusables` (F10).
//! * `emit`      reads hex inputs on stdin, prints the fold and skeleton_key under each
//!               policy (for scripts/difftest_fix.py against a patched build).
//!
//! Run from this directory:
//!   CARGO_TARGET_DIR=target cargo run --release -- <subcommand>

use std::collections::{BTreeMap, BTreeSet};
use std::sync::Mutex;

use disarm::api::{self, DigitPolicy, NormalizationForm, TargetScript};
use unicode_normalization::char::{canonical_combining_class, is_combining_mark};
use unicode_normalization::UnicodeNormalization;

const TARGETS: [TargetScript; 4] = [
    TargetScript::Latin,
    TargetScript::Cyrillic,
    TargetScript::Arabic,
    TargetScript::Hebrew,
];
const POLICIES: [DigitPolicy; 3] = [DigitPolicy::Numeric, DigitPolicy::Tr39, DigitPolicy::Preserve];

fn data_dir() -> std::path::PathBuf {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../../src/tables/data")
}

/// Parse a `confusables_to_*.tsv` value: literal ASCII plus `\u{XXXX}` escapes.
fn parse_value(v: &str) -> String {
    let mut out = String::new();
    let mut rest = v;
    while !rest.is_empty() {
        if let Some(r) = rest.strip_prefix("\\u{") {
            let end = r.find('}').expect("closed escape");
            let cp = u32::from_str_radix(&r[..end], 16).expect("hex");
            out.push(char::from_u32(cp).expect("scalar"));
            rest = &r[end + 1..];
        } else {
            let c = rest.chars().next().unwrap();
            out.push(c);
            rest = &rest[c.len_utf8()..];
        }
    }
    out
}

fn table(t: TargetScript) -> BTreeMap<char, String> {
    let path = data_dir().join(format!("confusables_to_{}.tsv", t.as_str()));
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{path:?}: {e}"));
    text.lines()
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
        .map(|l| {
            let mut it = l.split('\t');
            let k = u32::from_str_radix(it.next().unwrap(), 16).unwrap();
            (char::from_u32(k).unwrap(), parse_value(it.next().unwrap()))
        })
        .collect()
}

fn all_scalars() -> impl Iterator<Item = char> {
    (0u32..=0x10FFFF).filter_map(char::from_u32)
}

fn marks() -> Vec<char> {
    all_scalars().filter(|&c| is_combining_mark(c)).collect()
}

/// Marks that occur (after the first position) in some canonical decomposition: the
/// only marks that can take part in a composition.
fn composing_marks() -> Vec<char> {
    let mut set = BTreeSet::new();
    for c in all_scalars() {
        let d: Vec<char> = std::iter::once(c).nfd().collect();
        for &m in d.iter().skip(1) {
            if is_combining_mark(m) {
                set.insert(m);
            }
        }
        if d.len() >= 1 && is_combining_mark(d[0]) && d.len() > 1 {
            set.insert(d[0]);
        }
    }
    set.into_iter().collect()
}

fn esc(s: &str) -> String {
    s.chars()
        .map(|c| {
            if c.is_ascii_graphic() || c == ' ' {
                c.to_string()
            } else {
                format!("\\u{{{:04X}}}", c as u32)
            }
        })
        .collect()
}

#[derive(Default)]
struct Report {
    counts: BTreeMap<String, usize>,
    examples: BTreeMap<String, Vec<String>>,
}

impl Report {
    fn hit(&mut self, prop: &str, example: String) {
        *self.counts.entry(prop.to_owned()).or_default() += 1;
        let ex = self.examples.entry(prop.to_owned()).or_default();
        if ex.len() < 6 {
            ex.push(example);
        }
    }
    fn tally(&mut self, prop: &str) {
        self.counts.entry(prop.to_owned()).or_default();
    }
    fn merge(&mut self, other: Report) {
        for (k, v) in other.counts {
            *self.counts.entry(k).or_default() += v;
        }
        for (k, v) in other.examples {
            let ex = self.examples.entry(k).or_default();
            for e in v {
                if ex.len() < 6 {
                    ex.push(e);
                }
            }
        }
    }
    fn print(&self, checked: usize) {
        println!("checked {checked} (input, target, policy) cases");
        for (k, v) in &self.counts {
            println!("{k}\t{v}\t{}", self.examples.get(k).map(|e| e.join(" ; ")).unwrap_or_default());
        }
    }
}

fn nfc(s: &str) -> String {
    api::normalize(s, NormalizationForm::Nfc)
}
fn nfd(s: &str) -> String {
    api::normalize(s, NormalizationForm::Nfd)
}

/// Every fold property on one input, one target, one policy.
fn check_fold(r: &mut Report, s: &str, t: TargetScript, p: DigitPolicy) {
    let tag = format!("{}/{}", t.as_str(), p.as_str());
    let once = api::normalize_confusables_with(s, t, p).into_owned();
    let twice = api::normalize_confusables_with(&once, t, p).into_owned();
    r.tally(&format!("idempotent/{tag}"));
    if once != twice {
        r.hit(&format!("idempotent/{tag}"), format!("{} -> {} -> {}", esc(s), esc(&once), esc(&twice)));
    }
    r.tally(&format!("complete/{tag}"));
    if api::is_confusable(&once, t) {
        r.hit(&format!("complete/{tag}"), format!("{} -> {}", esc(s), esc(&once)));
    }
    let (c, d) = (nfc(s), nfd(s));
    let fc = api::normalize_confusables_with(&c, t, p).into_owned();
    let fd = api::normalize_confusables_with(&d, t, p).into_owned();
    r.tally(&format!("nfc_nfd_fold/{tag}"));
    if fc != fd {
        r.hit(&format!("nfc_nfd_fold/{tag}"), format!("{}: NFC->{} NFD->{}", esc(s), esc(&fc), esc(&fd)));
    }
    if p == DigitPolicy::Numeric {
        r.tally(&format!("nfc_nfd_detect/{}", t.as_str()));
        if api::is_confusable(&c, t) != api::is_confusable(&d, t) {
            r.hit(&format!("nfc_nfd_detect/{}", t.as_str()), esc(s));
        }
        r.tally(&format!("detect_eq_find/{}", t.as_str()));
        if api::is_confusable(s, t) == api::find_confusables(s, t).is_empty() {
            r.hit(&format!("detect_eq_find/{}", t.as_str()), esc(s));
        }
    }
}

fn check_skeleton(r: &mut Report, s: &str) {
    for p in POLICIES {
        let tag = p.as_str();
        let Ok(k) = api::skeleton_key(s, p) else { continue };
        let k = k.into_owned();
        let k2 = api::skeleton_key(&k, p).unwrap().into_owned();
        r.tally(&format!("sk_idempotent/{tag}"));
        if k != k2 {
            r.hit(&format!("sk_idempotent/{tag}"), format!("{} -> {} -> {}", esc(s), esc(&k), esc(&k2)));
        }
        if p == DigitPolicy::Numeric {
            // The skeleton is not flagged by the library's own detector.
            r.tally("sk_not_confusable/numeric");
            if api::is_confusable(&k, TargetScript::Latin) {
                r.hit("sk_not_confusable/numeric", format!("{} -> {}", esc(s), esc(&k)));
            }
        }
        r.tally(&format!("sk_nfc_nfd/{tag}"));
        let kc = api::skeleton_key(&nfc(s), p).unwrap().into_owned();
        let kd = api::skeleton_key(&nfd(s), p).unwrap().into_owned();
        if kc != kd {
            r.hit(&format!("sk_nfc_nfd/{tag}"), format!("{}: NFC->{} NFD->{}", esc(s), esc(&kc), esc(&kd)));
        }
    }
}

fn parallel<T: Sync>(items: &[T], f: impl Fn(&mut Report, &T) + Sync) -> Report {
    let total = Mutex::new(Report::default());
    let n = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4);
    let chunk = items.len().div_ceil(n).max(1);
    std::thread::scope(|sc| {
        for part in items.chunks(chunk) {
            let f = &f;
            let total = &total;
            sc.spawn(move || {
                let mut r = Report::default();
                for it in part {
                    f(&mut r, it);
                }
                total.lock().unwrap().merge(r);
            });
        }
    });
    total.into_inner().unwrap()
}

fn main() {
    let cmd = std::env::args().nth(1).unwrap_or_default();
    match cmd.as_str() {
        "starters" => {
            for c in all_scalars() {
                let d: Vec<char> = std::iter::once(c).nfd().collect();
                if d.len() < 2 {
                    continue;
                }
                let last = *d.last().unwrap();
                let recomposes = std::iter::once(c).nfd().nfc().eq(std::iter::once(c));
                let jamo = (0x1100..=0x11FF).contains(&(last as u32));
                if recomposes && !is_combining_mark(last) && !jamo {
                    println!(
                        "U+{:04X} = {} (last: ccc {}, mark {})",
                        c as u32,
                        esc(&d.iter().collect::<String>()),
                        canonical_combining_class(last),
                        is_combining_mark(last)
                    );
                }
            }
            // And the non-mark characters with a non-zero combining class, which the
            // cluster gate would also split from their base.
            for c in all_scalars() {
                if canonical_combining_class(c) != 0 && !is_combining_mark(c) {
                    println!("ccc!=0 but not a mark: U+{:04X}", c as u32);
                }
            }
        }
        "pairs" => {
            let ms = marks();
            eprintln!("{} combining marks", ms.len());
            let mut cases: Vec<(TargetScript, char)> = Vec::new();
            for t in TARGETS {
                let tab = table(t);
                let mut bases: BTreeSet<char> = tab.keys().copied().collect();
                for (k, v) in &tab {
                    bases.extend(v.chars());
                    bases.extend(std::iter::once(*k).nfd().take(1));
                }
                cases.extend(bases.into_iter().map(|b| (t, b)));
            }
            eprintln!("{} (target, base) cases x {} marks", cases.len(), ms.len());
            let r = parallel(&cases, |r, &(t, b)| {
                for &m in &ms {
                    let s: String = [b, m].iter().collect();
                    for p in POLICIES {
                        check_fold(r, &s, t, p);
                    }
                }
            });
            r.print(cases.len() * ms.len() * 3);
        }
        "triples" => {
            let cm = composing_marks();
            eprintln!("{} composing marks", cm.len());
            let tab = table(TargetScript::Latin);
            let mut bases: BTreeSet<char> = tab.keys().copied().collect();
            for (k, v) in &tab {
                bases.extend(v.chars());
                bases.extend(std::iter::once(*k).nfd().take(1));
            }
            let bases: Vec<char> = bases.into_iter().collect();
            let r = parallel(&bases, |r, &b| {
                for &m1 in &cm {
                    for &m2 in &cm {
                        let s: String = [b, m1, m2].iter().collect();
                        check_fold(r, &s, TargetScript::Latin, DigitPolicy::Numeric);
                    }
                }
            });
            r.print(bases.len() * cm.len() * cm.len());
        }
        "skeleton" => {
            let cm = composing_marks();
            let singles: Vec<char> = all_scalars().collect();
            eprintln!("{} scalars, {} composing marks", singles.len(), cm.len());
            let r = parallel(&singles, |r, &c| {
                check_skeleton(r, &c.to_string());
            });
            r.print(singles.len());
            // Pairs: every scalar that case-folds, NFKC-changes, or is a fold source,
            // crossed with every composing mark. (A scalar none of the steps touches
            // behaves like any other letter.)
            let lat = table(TargetScript::Latin);
            let bases: Vec<char> = all_scalars()
                .filter(|&c| {
                    lat.contains_key(&c)
                        || api::fold_case(&c.to_string()) != c.to_string()
                        || nfc(&c.to_string()) != c.to_string()
                        || std::iter::once(c).nfkd().count() > 1
                        || c.is_ascii_alphanumeric()
                })
                .collect();
            eprintln!("{} pair bases", bases.len());
            let r = parallel(&bases, |r, &c| {
                for &m in &cm {
                    check_skeleton(r, &[c, m].iter().collect::<String>());
                    // The same pair with a control between them: StripControl runs last.
                    check_skeleton(r, &[c, '\u{0001}', m].iter().collect::<String>());
                }
            });
            r.print(bases.len() * cm.len() * 2);
        }
        "emit" => {
            // One input per stdin line (hex code points, space separated); prints the
            // fold under each policy and skeleton_key under each policy, `|`-separated,
            // in the order of the model's modes 0-2 and 6-8. scripts/difftest_fix.py
            // feeds it and the model's `fixed` mode the same inputs, to check that the
            // model of the fix is the fix (run it on a build of the patched crate).
            use std::io::BufRead;
            let hex = |s: &str| {
                s.chars().map(|c| format!("{:X}", c as u32)).collect::<Vec<_>>().join(" ")
            };
            for line in std::io::stdin().lock().lines() {
                let line = line.unwrap();
                let s: String = line
                    .split_whitespace()
                    .map(|w| char::from_u32(u32::from_str_radix(w, 16).unwrap()).unwrap())
                    .collect();
                let mut out = Vec::new();
                for p in POLICIES {
                    out.push(hex(&api::normalize_confusables_with(&s, TargetScript::Latin, p)));
                }
                for p in POLICIES {
                    out.push(hex(&api::skeleton_key(&s, p).unwrap()));
                }
                println!("{}", out.join("|"));
            }
        }
        "cow" => {
            // api/safety.rs:115-117: "Returns `Cow::Borrowed` when the input is already NFC
            // and nothing folds (zero allocation), `Cow::Owned` otherwise."
            use std::borrow::Cow;
            for (s, why) in [
                ("x\u{0301}", "NFC, nothing folds"),
                ("\u{2126}", "not NFC (OHM SIGN), nothing folds"),
                ("abc", "NFC, nothing folds"),
            ] {
                let r = api::normalize_confusables(s, TargetScript::Latin);
                let kind = if matches!(r, Cow::Borrowed(_)) { "Borrowed" } else { "Owned" };
                println!(
                    "{}: is_nfc={} -> {} {}",
                    esc(s),
                    api::normalize(s, NormalizationForm::Nfc) == s,
                    kind,
                    why
                );
            }
        }
        _ => eprintln!("usage: confusables-probe starters|pairs|triples|skeleton|emit|cow"),
    }
}
