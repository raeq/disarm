//! Decimal numbering systems — UTS #39 §5.3 *Mixed Numbers* (#777).
//!
//! UTS #39 defines a check that an identifier should not carry digits from more than one
//! decimal numbering system. `1٢۳４५` reads as `12345` and is five systems: ASCII,
//! Arabic-Indic, Extended Arabic-Indic, fullwidth, and Devanagari.
//!
//! A system is a run of ten code points with `Numeric_Type=Decimal` and values 0–9, and
//! its identity is the code point of its **zero** — for any digit in it, `cp - value`.
//! UCD 17.0.0 has 77 of them and every run is complete, so the table is just the zeros
//! and membership is arithmetic. (UTS #39 and #777 both say 76; that is UCD 16.0.0.)

// The zeros, generated from `src/tables/data/decimal_digit_zeros.tsv` by build.rs.
include!(concat!(env!("OUT_DIR"), "/decimal_digit_zeros.rs"));

/// The decimal numbering system `ch` belongs to, identified by its zero.
///
/// `None` for anything that is not a decimal digit. The subtraction alone would answer
/// for any code point; the table is what makes the answer mean "a real system".
#[must_use]
pub(crate) fn decimal_system(ch: char) -> Option<u32> {
    let cp = ch as u32;
    let idx = match DECIMAL_DIGIT_ZEROS.binary_search(&cp) {
        Ok(i) => i,
        Err(0) => return None,
        Err(i) => i - 1,
    };
    let zero = DECIMAL_DIGIT_ZEROS[idx];
    (cp - zero < 10).then_some(zero)
}

/// How many distinct decimal numbering systems `text` draws digits from.
///
/// Zero when it has no decimal digits. One is the ordinary case — including an entirely
/// non-ASCII one, since `٢٠٢٤` is a perfectly good year.
#[must_use]
pub(crate) fn system_count(text: &str) -> usize {
    let mut seen: [u32; 8] = [0; 8];
    let mut n = 0usize;
    for ch in text.chars() {
        let Some(zero) = decimal_system(ch) else {
            continue;
        };
        // A fixed array rather than a set: the answer is interesting at 2, so a token
        // reaching 8 distinct systems is already far past every threshold and stopping
        // there costs nothing. No allocation on a path that runs per token.
        if seen[..n].contains(&zero) {
            continue;
        }
        if n == seen.len() {
            return seen.len();
        }
        seen[n] = zero;
        n += 1;
    }
    n
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_non_digit_belongs_to_no_system() {
        for ch in ['a', 'Ω', '中', ' ', '\u{0301}', '\u{200b}'] {
            assert_eq!(decimal_system(ch), None, "{ch:?}");
        }
    }

    #[test]
    fn every_digit_of_a_system_reports_the_same_zero() {
        for zero in DECIMAL_DIGIT_ZEROS {
            for offset in 0..10u32 {
                let ch = char::from_u32(zero + offset).expect("digits are scalar values");
                assert_eq!(decimal_system(ch), Some(zero), "U+{:04X}", zero + offset);
            }
        }
    }

    #[test]
    fn the_code_point_after_a_system_is_not_in_it() {
        // The check the arithmetic alone would get wrong: `zero + 10` is one past the
        // run, and without the ten-wide bound it would report the system.
        for zero in DECIMAL_DIGIT_ZEROS {
            let Some(ch) = char::from_u32(zero + 10) else {
                continue;
            };
            assert_ne!(decimal_system(ch), Some(zero), "U+{:04X}", zero + 10);
        }
    }

    #[test]
    fn system_count_is_the_number_of_systems_not_of_digits() {
        assert_eq!(system_count(""), 0);
        assert_eq!(system_count("hello"), 0);
        assert_eq!(system_count("2024"), 1);
        assert_eq!(system_count("\u{0662}\u{0660}\u{0662}\u{0664}"), 1); // ٢٠٢٤
        assert_eq!(system_count("12\u{0663}"), 2); // ASCII + Arabic-Indic
        assert_eq!(system_count("1\u{0662}\u{06F3}\u{FF14}\u{0968}"), 5);
    }
}
