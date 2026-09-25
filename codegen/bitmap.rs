//! One bit per BMP code point, emitted as a `static [u64; 1024]`: the shape of every
//! build-time "may this character need work?" table the scanners test before a lookup.

use std::fmt::Write as _;

/// Append `static {name}: [u64; 1024]` to `code`, bit `cp` set where `set(U+cp)`.
pub(crate) fn emit_bmp_bitmap(
    code: &mut String,
    name: &str,
    meaning: &str,
    set: impl Fn(char) -> bool,
) {
    let mut words = [0u64; 1024];
    for cp in 0..0x1_0000u32 {
        if let Some(c) = char::from_u32(cp) {
            if set(c) {
                words[(cp >> 6) as usize] |= 1 << (cp & 63);
            }
        }
    }
    writeln!(
        code,
        "/// Bit `cp` set: {meaning}.\nstatic {name}: [u64; 1024] = ["
    )
    .unwrap();
    for chunk in words.chunks(4) {
        // Grouped by 16 bits: clippy's `unreadable_literal` reads the generated file.
        let row: Vec<String> = chunk
            .iter()
            .map(|w| {
                format!(
                    "0x{:04X}_{:04X}_{:04X}_{:04X}",
                    w >> 48,
                    (w >> 32) & 0xFFFF,
                    (w >> 16) & 0xFFFF,
                    w & 0xFFFF
                )
            })
            .collect();
        writeln!(code, "    {},", row.join(", ")).unwrap();
    }
    code.push_str("];\n");
}
