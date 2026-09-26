//! Stacks of one combining mark, at every length a loop bound could hide behind.
//!
//! The confusable fold ran a pass loop capped at eight, on the argument that "each pass
//! removes at least one mark, so it converges in a couple of iterations" (#434). That
//! bounds the passes by the number of marks, which the input chooses. `C` + U+0327
//! composes to `Ç`, which folds back to `C`, so ten cedillas came back still confusable
//! and not idempotent (#1071), and the presets' own loops did the same.
//!
//! Nothing caught it for two and a half months, and not by chance. Every sweep crossed a
//! base with one or two marks, the Lean model checked every string up to length five
//! (the shortest failure has ten characters), and the random generators drew characters
//! independently, so a run of ten of one mark had a probability near 1e-19. Run length
//! is a dimension of its own, and this file tests it on purpose: every base the tables
//! can reach, every mark that composes with it, at run lengths either side of every cap
//! in the code, and one long stack per cycle to hold the cost linear.
//!
//! The cases come from the tables in `src/tables/data/`, not from a list of known
//! cycles, so a table change that adds a cycle is covered the day it lands. It runs on
//! `disarm::api`, the layer every binding calls (the #586 lesson).

use std::collections::{BTreeMap, BTreeSet};
use std::sync::OnceLock;
use std::time::{Duration, Instant};

use disarm::api::{self as d, DigitPolicy, TargetScript};
use unicode_normalization::UnicodeNormalization;

const POLICIES: [DigitPolicy; 3] = [
    DigitPolicy::Numeric,
    DigitPolicy::Tr39,
    DigitPolicy::Preserve,
];

/// Short stacks, and both sides of the eight-pass caps the fold and the presets had,
/// with room above for a cap a little larger.
const LENGTHS: &[usize] = &[1, 2, 3, 4, 7, 8, 9, 10, 11, 12, 33];

/// Marks from above and below the letter, to stack beside the one a fold consumes.
const ABOVE: [char; 5] = ['\u{300}', '\u{301}', '\u{303}', '\u{30C}', '\u{367}'];
const BELOW: [char; 5] = ['\u{323}', '\u{324}', '\u{325}', '\u{326}', '\u{331}'];

fn nfc(s: &str) -> String {
    s.nfc().collect()
}

/// One target's table, read from its TSV: source character to its fold.
fn table(target: TargetScript) -> BTreeMap<char, String> {
    let path = format!(
        "{}/src/tables/data/confusables_to_{}.tsv",
        env!("CARGO_MANIFEST_DIR"),
        target.as_str()
    );
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{path}: {e}"));
    let mut out = BTreeMap::new();
    for line in text
        .lines()
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
    {
        let (key, value) = line.split_once('\t').expect("KEY<TAB>VALUE");
        let key = char::from_u32(u32::from_str_radix(key, 16).expect("hex key")).unwrap();
        out.insert(key, unescape(value));
    }
    assert!(out.len() > 200, "{path}: {} rows", out.len());
    out
}

/// The TSVs write a value's non-ASCII characters as `\u{XXXX}`.
fn unescape(value: &str) -> String {
    let mut out = String::new();
    let mut rest = value;
    while let Some(i) = rest.find("\\u{") {
        out.push_str(&rest[..i]);
        let end = rest[i..].find('}').expect("closing brace") + i;
        let cp = u32::from_str_radix(&rest[i + 3..end], 16).expect("hex escape");
        out.push(char::from_u32(cp).expect("scalar"));
        rest = &rest[end + 1..];
    }
    out.push_str(rest);
    out
}

/// Every character with a canonical decomposition, by that decomposition (canonically
/// ordered, as NFD writes it), and every character after the first in one: what
/// composition can take onto a base. That is the combining marks of every class,
/// class-0 vowel signs such as U+09BE included, and U+16D67, which composes backwards
/// (Hangul jamo aside: they compose by arithmetic, and no table maps them). The
/// composition exclusions are in: canonical NFC never rebuilds them, but the fold's
/// compose-at-lookup does (#481), so their marks feed a fold as well.
struct Compositions {
    by_nfd: BTreeMap<String, char>,
    marks: Vec<char>,
}

fn compositions() -> &'static Compositions {
    static CELL: OnceLock<Compositions> = OnceLock::new();
    CELL.get_or_init(|| {
        let mut by_nfd = BTreeMap::new();
        let mut marks = BTreeSet::new();
        for c in (0u32..=0x10_FFFF).filter_map(char::from_u32) {
            let nfd: String = std::iter::once(c).nfd().collect();
            if nfd.chars().count() < 2 {
                continue;
            }
            marks.extend(
                nfd.chars()
                    .skip(1)
                    .filter(|&m| !('\u{1100}'..='\u{11FF}').contains(&m)),
            );
            // Singletons share a decomposition with their canonical form (U+212B and
            // U+00C5): keep the one NFC gives.
            let canonical = nfc(&nfd);
            let pick = if canonical.chars().count() == 1 {
                canonical.chars().next().unwrap()
            } else {
                c
            };
            by_nfd.entry(nfd).or_insert(pick);
        }
        Compositions {
            by_nfd,
            marks: marks.into_iter().collect(),
        }
    })
}

/// The one character `base` + `mark` composes to, canonically or through a composition
/// exclusion, if any.
fn composed(base: char, mark: char) -> Option<char> {
    let pair = format!("{base}{mark}");
    let canonical = nfc(&pair);
    let mut chars = canonical.chars();
    if let (Some(one), None) = (chars.next(), chars.next()) {
        return Some(one);
    }
    let nfd: String = pair.nfd().collect();
    compositions().by_nfd.get(&nfd).copied()
}

/// A base and a mark that composes with it, for one target.
struct Pair {
    base: char,
    mark: char,
    /// The composition is itself a fold source: the shape of every cycle, and of the
    /// fold that moves a mark (`ģ` to `ġ`, #1072).
    composes_to_source: bool,
}

/// Every base the table reaches (its sources, the characters of its values, and each
/// canonical prefix of a source's decomposition) crossed with every composing mark it
/// takes, kept when the fold can touch the result.
fn pairs(target: TargetScript) -> Vec<Pair> {
    let map = table(target);
    let mut bases: BTreeSet<char> = map.keys().copied().collect();
    for value in map.values() {
        bases.extend(value.chars());
    }
    for key in map.keys() {
        let nfd: Vec<char> = std::iter::once(*key).nfd().collect();
        for end in 1..nfd.len() {
            let prefix = nfc(&nfd[..end].iter().collect::<String>());
            if prefix.chars().count() == 1 {
                bases.extend(prefix.chars());
            }
        }
    }
    let mut out = Vec::new();
    for &base in &bases {
        for &mark in &compositions().marks {
            let Some(one) = composed(base, mark) else {
                continue;
            };
            let composes_to_source = map.contains_key(&one);
            if composes_to_source || map.contains_key(&base) {
                out.push(Pair {
                    base,
                    mark,
                    composes_to_source,
                });
            }
        }
    }
    out
}

fn stack(base: char, mark: char, n: usize) -> String {
    std::iter::once(base)
        .chain(std::iter::repeat_n(mark, n))
        .collect()
}

/// The fold on a stack of every length: a fixed point, and complete under `numeric`
/// and `tr39` (under `preserve` the digit rows stay by design, #648).
#[test]
fn the_fold_settles_a_stack_of_any_length() {
    // The two shapes the derivation must reach: a cycle (#1071) and a fold that moves a
    // mark to another class (#1072).
    let latin = pairs(TargetScript::Latin);
    for (base, mark) in [('C', '\u{327}'), ('g', '\u{327}')] {
        assert!(
            latin
                .iter()
                .any(|p| p.base == base && p.mark == mark && p.composes_to_source),
            "{base:?} + U+{:04X} is missing: has the derivation drifted?",
            mark as u32
        );
    }
    let mut checked = 0;
    let mut failures = Vec::new();
    for target in TargetScript::ALL.iter().copied() {
        for pair in pairs(target) {
            for &n in LENGTHS {
                let input = stack(pair.base, pair.mark, n);
                for policy in POLICIES {
                    let once = d::normalize_confusables_with(&input, target, policy);
                    let twice = d::normalize_confusables_with(&once, target, policy);
                    checked += 1;
                    if once != twice {
                        failures.push(format!("not idempotent: {input:?} {target} {policy}"));
                    } else if policy != DigitPolicy::Preserve && d::is_confusable(&once, target) {
                        failures.push(format!("still confusable: {input:?} {target} {policy}"));
                    }
                }
            }
        }
    }
    assert!(
        checked > 20_000,
        "only {checked} cases: has the derivation drifted?"
    );
    assert!(
        failures.is_empty(),
        "{} of {checked} failed:\n{}",
        failures.len(),
        failures[..failures.len().min(20)].join("\n")
    );
}

/// Every surface that iterates the fold in a loop of its own: the builders under each
/// policy, and every profile. Stacks whose composition is a fold source, where the
/// loops have work to do, each alone and beside marks of other classes (#1072's shape).
#[test]
fn every_preset_settles_a_stack_of_any_length() {
    let profiles = d::list_profiles();
    let pipes: Vec<_> = profiles
        .iter()
        .map(|p| (p.clone(), d::get_pipeline(p).unwrap()))
        .collect();
    let mut inputs = BTreeSet::new();
    for target in TargetScript::ALL.iter().copied() {
        for pair in pairs(target).iter().filter(|p| p.composes_to_source) {
            for &n in LENGTHS {
                inputs.insert(stack(pair.base, pair.mark, n));
            }
            for k in 1..=4 {
                for others in [&ABOVE[..k], &BELOW[..k]] {
                    let mut input = stack(pair.base, pair.mark, 1);
                    input.extend(others.iter());
                    inputs.insert(input);
                }
            }
        }
    }
    assert!(inputs.len() > 500, "only {} inputs", inputs.len());
    let mut failures = Vec::new();
    for input in &inputs {
        for policy in POLICIES {
            let builders: [(&str, &dyn Fn(&str) -> String); 7] = [
                ("canonicalize", &|t| {
                    d::canonicalize_with(t, policy).unwrap().into_owned()
                }),
                ("canonicalize_strict", &|t| {
                    d::canonicalize_strict_with(t, policy).unwrap().into_owned()
                }),
                ("strip_obfuscation", &|t| {
                    d::strip_obfuscation_with(t, policy).unwrap().into_owned()
                }),
                ("catalog_key", &|t| {
                    d::catalog_key_with(t, None, false, policy)
                        .unwrap()
                        .into_owned()
                }),
                ("search_key", &|t| {
                    d::search_key_with(t, None, policy).unwrap().into_owned()
                }),
                ("sort_key", &|t| {
                    d::sort_key_with(t, None, policy).unwrap().into_owned()
                }),
                ("skeleton_key", &|t| {
                    d::skeleton_key(t, policy).unwrap().into_owned()
                }),
            ];
            for (name, f) in builders {
                let once = f(input);
                if f(&once) != once {
                    failures.push(format!("{name} ({policy}) on {input:?}"));
                }
            }
        }
        for (profile, pipe) in &pipes {
            let once = pipe.process(input).unwrap();
            if pipe.process(&once).unwrap() != once {
                failures.push(format!("{profile} on {input:?}"));
            }
        }
    }
    assert!(
        failures.is_empty(),
        "{} not fixed points:\n{}",
        failures.len(),
        failures[..failures.len().min(20)].join("\n")
    );
}

/// The cycles themselves, found from the tables: a mark composes onto a character and
/// the result folds back to that character. For each, a stack of 20,000 settles in the
/// fold, `canonicalize_strict` and `skeleton_key`, well inside a bound a pass per mark
/// could never meet (that is about 10^8 steps of work in each).
#[test]
fn a_cycle_eats_a_long_stack_in_linear_time() {
    let mut cycles = Vec::new();
    for target in TargetScript::ALL.iter().copied() {
        let map = table(target);
        for pair in pairs(target).iter().filter(|p| p.composes_to_source) {
            let one = composed(pair.base, pair.mark).unwrap();
            if map[&one].ends_with(pair.base) {
                cycles.push((target, pair.base, pair.mark));
            }
        }
    }
    // The tables hold three today (`C` and `c` + U+0327, `i` + U+0309); that is the
    // floor, so the test cannot pass by finding none.
    assert!(cycles.len() >= 3, "cycles: {cycles:?}");
    let start = Instant::now();
    for &(target, base, mark) in &cycles {
        let input = stack(base, mark, 20_000);
        // Counts, not strings, in the messages: a failure here is 20,000 characters long.
        let what = format!("{target} {base:?} + 20,000 U+{:04X}", mark as u32);
        let folded = d::normalize_confusables(&input, target).into_owned();
        assert!(
            folded == base.to_string(),
            "{what}: the fold left {} characters",
            folded.chars().count()
        );
        if target == TargetScript::Latin {
            let strict = d::canonicalize_strict(&input).unwrap().into_owned();
            assert!(
                d::canonicalize_strict(&strict).unwrap() == strict,
                "{what}: canonicalize_strict is not a fixed point ({} characters)",
                strict.chars().count()
            );
            let key = d::skeleton_key(&input, DigitPolicy::Numeric)
                .unwrap()
                .into_owned();
            assert!(
                d::skeleton_key(&key, DigitPolicy::Numeric).unwrap() == key,
                "{what}: skeleton_key is not a fixed point ({} characters)",
                key.chars().count()
            );
        }
    }
    let spent = start.elapsed();
    assert!(
        spent < Duration::from_secs(60),
        "{} cycles took {spent:?}: is a stack costing a pass per mark again?",
        cycles.len()
    );
}
