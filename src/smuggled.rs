//! Layer 1 (pure-Rust core): decode what a smuggled run *spells* (#701).
//!
//! disarm strips the three ASCII-smuggling carriers and, since #700, reports that
//! invisible characters are present. Neither answer tells the caller that the run reads
//! `tracked-by:acct-99213`.
//!
//! Presence and decode are different strengths of evidence. An invisible character can
//! arrive by accident — a copy-paste artefact, a BOM, an editor quirk. A run that decodes
//! to readable text cannot: random damage does not spell words. A successful decode is
//! the one signal in this area that needs no threshold and no policy to interpret.
//!
//! Pure arithmetic on code point values. No table, which matters under #695: this adds
//! nothing to the data section that dominates a wasm build.
//!
//! The three schemes, and the printable-only rule, follow `juriku/untrace`'s
//! `internal/decode`.

/// Which carrier a [`Payload`] was hidden in.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PayloadScheme {
    /// `U+E0020`–`U+E007E`: subtract `0xE0000`, one byte per character.
    TagAscii,
    /// `U+FE00`–`U+FE0F` and `U+E0100`–`U+E01EF`: an index 0–255, one byte per character.
    VariationBytes,
    /// `U+200B` = 0, `U+200C` = 1, MSB first. `U+200D`, `U+2060` and `U+FEFF` separate.
    ZeroWidthBinary,
}

impl PayloadScheme {
    /// The wire name of the scheme, as the bindings and `Finding.detail` report it.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::TagAscii => "tag_ascii",
            Self::VariationBytes => "variation_bytes",
            Self::ZeroWidthBinary => "zero_width_binary",
        }
    }
}

/// One decoded run.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Payload {
    /// Which carrier the run was hidden in.
    pub scheme: PayloadScheme,
    /// Byte offset of the first carrier character, into the string that was passed in.
    pub start: usize,
    /// Byte offset one past the last carrier character.
    pub end: usize,
    /// Carrier characters consumed — not bytes decoded, which differ for every scheme.
    pub units: usize,
    /// The decoded bytes, whether or not they form printable text.
    pub bytes: Vec<u8>,
    /// The decoded string, and **only** when the bytes are valid UTF-8 and wholly
    /// printable.
    ///
    /// Left `None` otherwise, deliberately. A run of arbitrary selectors is reported as a
    /// payload of *n* bytes with no decoded string rather than as a bogus one: reporting
    /// a garbage decode would undo the reason a decode is trustworthy in the first place.
    pub text: Option<String>,
}

/// A variation-selector run shorter than this is not reported.
///
/// One selector is the overwhelmingly common legitimate use — `VS16` asking for emoji
/// presentation — and one byte cannot spell anything. Without the floor every
/// `☂\u{FE0F}` in ordinary text is a "payload".
const MIN_VARIATION_RUN: usize = 2;

/// Decode every smuggled run in `text`, in order of appearance.
///
/// A well-formed emoji subdivision flag is not a payload: `U+1F3F4` + tag letters +
/// `U+E007F` spelling one of the three RGI values is the Scotland flag, not a channel.
/// The allowlist is the stripper's own, borrowed rather than
/// restated — #700 is about exactly that kind of drift.
pub fn decode_smuggled(text: &str) -> Vec<Payload> {
    let chars: Vec<(usize, char)> = text.char_indices().collect();
    let just_chars: Vec<char> = chars.iter().map(|&(_, c)| c).collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        let (offset, ch) = chars[i];
        // A valid subdivision flag is skipped whole, so its tag letters never reach the
        // tag-ascii scan below.
        if let Some(len) = crate::invisibles::subdivision_flag_len(&just_chars[i..]) {
            i += len;
            continue;
        }
        if let Some(p) = scan_tag_ascii(&chars, i, offset) {
            i += p.units;
            out.push(p);
            continue;
        }
        if let Some(p) = scan_variation(&chars, i, offset) {
            i += p.units;
            out.push(p);
            continue;
        }
        if let Some((p, consumed)) = scan_zero_width(&chars, i, offset) {
            i += consumed;
            if let Some(p) = p {
                out.push(p);
            }
            continue;
        }
        let _ = ch;
        i += 1;
    }
    out
}

fn finish(
    scheme: PayloadScheme,
    start: usize,
    end: usize,
    units: usize,
    bytes: Vec<u8>,
) -> Payload {
    let text = printable(&bytes);
    Payload {
        scheme,
        start,
        end,
        units,
        bytes,
        text,
    }
}

/// `Some` only for bytes that are valid UTF-8 **and** wholly printable.
///
/// "Printable" excludes every control character, which is what makes a decode evidence
/// rather than a guess: a run of selectors that happens to be valid UTF-8 is usually
/// control characters, and reporting that as recovered text would be the bogus decode the
/// `None` case exists to avoid.
fn printable(bytes: &[u8]) -> Option<String> {
    if bytes.is_empty() {
        return None;
    }
    let s = std::str::from_utf8(bytes).ok()?;
    s.chars().all(|c| !c.is_control()).then(|| s.to_owned())
}

fn is_tag_byte(ch: char) -> bool {
    matches!(ch, '\u{E0020}'..='\u{E007E}')
}

fn scan_tag_ascii(chars: &[(usize, char)], i: usize, offset: usize) -> Option<Payload> {
    if !is_tag_byte(chars[i].1) {
        return None;
    }
    let mut bytes = Vec::new();
    let mut j = i;
    while j < chars.len() && is_tag_byte(chars[j].1) {
        // Every value in the range is ASCII by construction, so the cast cannot truncate.
        bytes.push((chars[j].1 as u32 - 0xE0000) as u8);
        j += 1;
    }
    // A trailing CANCEL TAG belongs to the run; it terminates the channel as well as a flag.
    let end = chars
        .get(j)
        .map_or_else(|| offset + tail_len(chars, i, j), |&(o, _)| o);
    Some(finish(PayloadScheme::TagAscii, offset, end, j - i, bytes))
}

/// Byte length of `chars[i..j]`, for the case where the run reaches the end of the string.
fn tail_len(chars: &[(usize, char)], i: usize, j: usize) -> usize {
    chars[i..j].iter().map(|&(_, c)| c.len_utf8()).sum()
}

fn variation_byte(ch: char) -> Option<u8> {
    let cp = ch as u32;
    match cp {
        0xFE00..=0xFE0F => u8::try_from(cp - 0xFE00).ok(),
        0xE0100..=0xE01EF => u8::try_from(cp - 0xE0100 + 16).ok(),
        _ => None,
    }
}

fn scan_variation(chars: &[(usize, char)], i: usize, offset: usize) -> Option<Payload> {
    variation_byte(chars[i].1)?;
    let mut bytes = Vec::new();
    let mut j = i;
    while j < chars.len() {
        match variation_byte(chars[j].1) {
            Some(b) => bytes.push(b),
            None => break,
        }
        j += 1;
    }
    if j - i < MIN_VARIATION_RUN {
        return None;
    }
    let end = chars
        .get(j)
        .map_or_else(|| offset + tail_len(chars, i, j), |&(o, _)| o);
    Some(finish(
        PayloadScheme::VariationBytes,
        offset,
        end,
        j - i,
        bytes,
    ))
}

fn is_zw_separator(ch: char) -> bool {
    matches!(ch, '\u{200D}' | '\u{2060}' | '\u{FEFF}')
}

/// Returns the payload (if the run yielded at least one whole byte) and how many
/// characters to advance past — the run is consumed either way, so a bit-short run is not
/// rescanned character by character.
fn scan_zero_width(
    chars: &[(usize, char)],
    i: usize,
    offset: usize,
) -> Option<(Option<Payload>, usize)> {
    if !matches!(chars[i].1, '\u{200B}' | '\u{200C}') {
        return None;
    }
    let mut bits: Vec<u8> = Vec::new();
    let mut j = i;
    while j < chars.len() {
        match chars[j].1 {
            '\u{200B}' => bits.push(0),
            '\u{200C}' => bits.push(1),
            c if is_zw_separator(c) => {}
            _ => break,
        }
        j += 1;
    }
    let units = j - i;
    // Only whole bytes are decoded. A trailing partial byte is dropped rather than
    // zero-padded: padding invents bits the carrier did not contain.
    let bytes: Vec<u8> = bits
        .as_chunks::<8>()
        .0
        .iter()
        .map(|c| c.iter().fold(0u8, |acc, &b| (acc << 1) | b))
        .collect();
    if bytes.is_empty() {
        return Some((None, units));
    }
    let end = chars
        .get(j)
        .map_or_else(|| offset + tail_len(chars, i, j), |&(o, _)| o);
    Some((
        Some(finish(
            PayloadScheme::ZeroWidthBinary,
            offset,
            end,
            units,
            bytes,
        )),
        units,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Encode `s` as tag characters, the way the channel is actually used.
    fn tags(s: &str) -> String {
        s.chars()
            .map(|c| char::from_u32(c as u32 + 0xE0000).unwrap())
            .collect()
    }

    /// Encode `s` as MSB-first zero-width binary.
    fn zw(s: &str) -> String {
        s.bytes()
            .flat_map(|b| {
                (0..8).map(move |i| {
                    if (b >> (7 - i)) & 1 == 1 {
                        '\u{200C}'
                    } else {
                        '\u{200B}'
                    }
                })
            })
            .collect()
    }

    #[test]
    fn a_tag_run_decodes_to_what_it_spells() {
        let found = decode_smuggled(&format!("hello{}", tags("tracked-by:acct-99213")));
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].scheme, PayloadScheme::TagAscii);
        assert_eq!(found[0].text.as_deref(), Some("tracked-by:acct-99213"));
        assert_eq!(found[0].start, 5, "byte offset of the first carrier");
        assert_eq!(found[0].units, 21);
    }

    #[test]
    fn a_zero_width_run_decodes_to_what_it_spells() {
        let found = decode_smuggled(&format!("hi{}", zw("hi")));
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].scheme, PayloadScheme::ZeroWidthBinary);
        assert_eq!(found[0].text.as_deref(), Some("hi"));
        assert_eq!(found[0].units, 16, "two bytes, eight carriers each");
    }

    #[test]
    fn a_variation_run_decodes_to_what_it_spells() {
        // 'h' = 0x68 = 104 -> U+E0100 + (104 - 16); 'i' = 0x69 = 105.
        let carriers: String = "hi"
            .bytes()
            .map(|b| char::from_u32(0xE0100 + u32::from(b) - 16).unwrap())
            .collect();
        let found = decode_smuggled(&carriers);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].scheme, PayloadScheme::VariationBytes);
        assert_eq!(found[0].text.as_deref(), Some("hi"));
    }

    /// The rule that makes a decode trustworthy: no bogus text, ever.
    #[test]
    fn undecodable_bytes_are_reported_without_a_string() {
        // Two selectors whose bytes are not printable UTF-8.
        let found = decode_smuggled("\u{FE00}\u{FE01}");
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].bytes, vec![0, 1]);
        assert_eq!(found[0].text, None, "a garbage decode must not be reported");
    }

    /// A valid subdivision flag is an emoji, not a channel (#700's allowlist, reused).
    #[test]
    fn a_subdivision_flag_is_not_a_payload() {
        for flag in ["gbeng", "gbsct", "gbwls"] {
            let s = format!("\u{1F3F4}{}\u{E007F}", tags(flag));
            assert!(
                decode_smuggled(&s).is_empty(),
                "{flag} reported as a payload"
            );
        }
    }

    /// ...but the same base with any other tail is the channel wearing a flag.
    #[test]
    fn a_flag_base_with_another_tail_is_still_decoded() {
        let s = format!("\u{1F3F4}{}\u{E007F}", tags("ushi"));
        let found = decode_smuggled(&s);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].text.as_deref(), Some("ushi"));
    }

    /// One variation selector is emoji presentation, not a payload.
    #[test]
    fn a_lone_variation_selector_is_not_a_payload() {
        assert!(decode_smuggled("\u{2602}\u{FE0F}").is_empty());
        assert!(decode_smuggled("text\u{FE0E}").is_empty());
    }

    /// A run too short to fill a byte yields no payload, and is not rescanned.
    #[test]
    fn a_bit_short_zero_width_run_yields_nothing() {
        assert!(decode_smuggled("a\u{200B}\u{200C}\u{200B}b").is_empty());
    }

    /// Partial trailing bits are dropped, never zero-padded into a byte that was not sent.
    #[test]
    fn trailing_bits_are_dropped_not_padded() {
        let found = decode_smuggled(&format!("{}\u{200C}\u{200C}", zw("A")));
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].bytes, b"A".to_vec());
        assert_eq!(found[0].units, 10, "the stray bits are still consumed");
    }

    #[test]
    fn ordinary_text_decodes_to_nothing() {
        for s in ["hello world", "", "café", "\u{1F600}", "Москва"] {
            assert!(decode_smuggled(s).is_empty(), "{s:?}");
        }
    }

    #[test]
    fn several_runs_are_reported_in_order() {
        let s = format!("a{}b{}c", tags("one"), zw("hi"));
        let found = decode_smuggled(&s);
        assert_eq!(found.len(), 2);
        assert_eq!(found[0].text.as_deref(), Some("one"));
        assert_eq!(found[1].text.as_deref(), Some("hi"));
        assert!(found[0].start < found[1].start);
    }

    /// The span must index the input, so a caller can slice it.
    #[test]
    fn the_span_indexes_the_input() {
        let s = format!("hello{}world", tags("hi"));
        let found = decode_smuggled(&s);
        assert_eq!(found.len(), 1);
        let (start, end) = (found[0].start, found[0].end);
        assert_eq!(&s[..start], "hello");
        assert_eq!(&s[end..], "world");
        assert_eq!(s[start..end].chars().count(), 2);
    }
}
