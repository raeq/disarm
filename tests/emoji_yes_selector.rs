//! `U+FE0F` opens an emoji presentation sequence only on an `Emoji=Yes` base (#992).
//!
//! UTS #51 defines the emoji presentation sequence for `Emoji=Yes` bases alone. The VS16
//! arm of the scanner, and the VS16 rule of the width model, asked the wider
//! `Emoji` OR `Extended_Pictographic` table, which reserves whole blocks: a black star
//! followed by a selector was deleted by `replace_emoji` and measured two columns wide,
//! and so were 1,022 unassigned code points.

use disarm::api::{replace_emoji, terminal_width};

/// `Extended_Pictographic`, not `Emoji`: a selector after one is stray.
const PICTOGRAPHIC_ONLY: [char; 3] = ['\u{2605}', '\u{2388}', '\u{1FC00}'];

/// `Emoji=Yes`, text by default: a selector after one asks for emoji presentation.
const EMOJI_TEXT_DEFAULT: [char; 3] = ['\u{263A}', '\u{00A9}', '\u{2665}'];

#[test]
fn replace_emoji_keeps_a_pictograph_and_its_stray_selector() {
    for base in PICTOGRAPHIC_ONLY {
        let text = format!("a{base}\u{FE0F}b");
        assert_eq!(replace_emoji(&text, ""), text, "U+{:04X}", u32::from(base));
    }
}

#[test]
fn replace_emoji_still_removes_an_emoji_base_with_its_selector() {
    for base in EMOJI_TEXT_DEFAULT {
        let text = format!("a{base}\u{FE0F}b");
        assert_eq!(replace_emoji(&text, ""), "ab", "U+{:04X}", u32::from(base));
    }
}

#[test]
fn a_stray_selector_does_not_widen_a_pictograph() {
    for base in ['\u{2605}', '\u{2388}'] {
        let alone = terminal_width(&base.to_string(), false);
        let with_selector = terminal_width(&format!("{base}\u{FE0F}"), false);
        assert_eq!(with_selector, alone, "U+{:04X}", u32::from(base));
    }
    for base in EMOJI_TEXT_DEFAULT {
        assert_eq!(terminal_width(&format!("{base}\u{FE0F}"), false), 2);
    }
}

fn ranges(tsv: &str) -> Vec<char> {
    tsv.lines()
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
        .flat_map(|l| {
            let mut it = l
                .split('\t')
                .map(|h| u32::from_str_radix(h, 16).expect("hex"));
            let (lo, hi) = (it.next().expect("start"), it.next().expect("end"));
            (lo..=hi).filter_map(char::from_u32)
        })
        .collect()
}

/// Every code point in one table and not the other, both ways round. Two `Emoji=Yes`
/// classes are left out of the second half: the keycap bases open nothing without a
/// keycap after them, and a regional indicator takes no selector at all (it is replaced
/// alone and the stray `U+FE0F` stays, as `tables::selector_may_follow` has it).
#[test]
fn the_selector_opens_exactly_the_emoji_yes_bases() {
    let yes = ranges(include_str!("../src/tables/data/emoji_yes.tsv"));
    let pictographic = ranges(include_str!("../src/tables/data/emoji_property.tsv"));
    let only_pictographic: Vec<char> = pictographic
        .iter()
        .copied()
        .filter(|c| !yes.contains(c))
        .collect();
    assert_eq!(
        only_pictographic.len(),
        2_156,
        "Extended_Pictographic minus Emoji at UCD 15.1.0"
    );

    let opened: Vec<String> = only_pictographic
        .iter()
        .filter(|&&base| {
            let text = format!("a{base}\u{FE0F}b");
            replace_emoji(&text, "") != text
        })
        .map(|&c| format!("U+{:04X}", u32::from(c)))
        .collect();
    assert!(
        opened.is_empty(),
        "a selector opened {} non-emoji bases: {opened:?}",
        opened.len()
    );

    let missed: Vec<String> = yes
        .iter()
        .filter(|c| !matches!(c, '0'..='9' | '#' | '*' | '\u{1F1E6}'..='\u{1F1FF}'))
        .filter(|&&base| replace_emoji(&format!("a{base}\u{FE0F}b"), "") != "ab")
        .map(|&c| format!("U+{:04X}", u32::from(c)))
        .collect();
    assert!(
        missed.is_empty(),
        "a selector failed to open {} emoji bases: {missed:?}",
        missed.len()
    );
}
