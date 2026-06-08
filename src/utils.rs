/// Shared utility functions used across multiple modules.
/// Find the largest byte index `<= index` that lies on a UTF-8 char boundary.
///
/// Equivalent to the nightly-only `str::floor_char_boundary()`.
/// Returns `s.len()` when `index >= s.len()`.
pub fn floor_char_boundary(s: &str, index: usize) -> usize {
    if index >= s.len() {
        s.len()
    } else {
        let mut i = index;
        while i > 0 && !s.is_char_boundary(i) {
            i -= 1;
        }
        i
    }
}

/// Levenshtein edit distance between two strings (O(a·b) time, O(b) space).
/// Intended for short inputs such as language or encoding codes.
pub fn edit_distance(a: &str, b: &str) -> usize {
    // Collect only `b` (O(b) working memory); stream `a` char by char.
    let b: Vec<char> = b.chars().collect();
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    let mut curr = vec![0usize; b.len() + 1];
    for (i, ca) in a.chars().enumerate() {
        curr[0] = i + 1;
        for (j, &cb) in b.iter().enumerate() {
            let cost = usize::from(ca != cb);
            curr[j + 1] = (prev[j + 1] + 1).min(curr[j] + 1).min(prev[j] + cost);
        }
        std::mem::swap(&mut prev, &mut curr);
    }
    prev[b.len()]
}

/// Return the candidate closest to `got` (case-insensitively) within a small
/// edit-distance threshold, for a "did you mean …?" hint — or `None` if nothing
/// is close enough. Returns the candidate's original spelling.
///
/// The threshold (≤ 2 edits, and the edits must be a minority of the longer
/// string) keeps it from suggesting an unrelated code for a wildly-wrong input
/// (e.g. `"xx"` gets no suggestion, but `"ge"` → `"de"`).
pub fn closest_match<'a>(
    got: &str,
    candidates: impl IntoIterator<Item = &'a str>,
) -> Option<String> {
    let got_lower = got.to_lowercase();
    let mut best: Option<(usize, &str)> = None;
    for c in candidates {
        let d = edit_distance(&got_lower, &c.to_lowercase());
        if d == 0 {
            continue; // identical apart from case — the caller already rejected `got`
        }
        match best {
            Some((bd, _)) if d >= bd => {}
            _ => best = Some((d, c)),
        }
    }
    // Guard in the same units as `edit_distance` (chars, not bytes), so the
    // threshold stays consistent for non-ASCII inputs.
    best.filter(|&(d, c)| {
        let max_len = got.chars().count().max(c.chars().count());
        d <= 2 && d * 2 < max_len + 1
    })
    .map(|(_, c)| c.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_edit_distance() {
        assert_eq!(edit_distance("de", "de"), 0);
        assert_eq!(edit_distance("ge", "de"), 1);
        assert_eq!(edit_distance("", "abc"), 3);
        assert_eq!(edit_distance("kitten", "sitting"), 3);
    }

    #[test]
    fn test_closest_match() {
        let langs = ["de", "fr", "ru", "ja", "zh", "es"];
        assert_eq!(closest_match("ge", langs).as_deref(), Some("de")); // 1 edit
        assert_eq!(closest_match("rus", langs).as_deref(), Some("ru")); // 1 edit
        assert_eq!(closest_match("xx", langs), None); // too far
        assert_eq!(closest_match("de", langs), None); // identical → no hint
        assert_eq!(closest_match("DE", langs), None); // case-insensitive identity
        assert_eq!(closest_match("zzzz", langs), None); // nothing close
    }

    #[test]
    fn test_closest_match_guard_is_char_based() {
        // The length guard counts chars, not bytes (#211 review): a 1-char input
        // one edit from a 1-char candidate is a complete change → no suggestion,
        // even though the multi-byte form has a larger byte length.
        assert_eq!(closest_match("é", ["e", "a"]), None);
        assert_eq!(edit_distance("café", "cafe"), 1); // counts the é→e as one edit
    }

    #[test]
    fn test_floor_char_boundary_ascii() {
        assert_eq!(floor_char_boundary("hello", 3), 3);
        assert_eq!(floor_char_boundary("hello", 10), 5); // beyond len
        assert_eq!(floor_char_boundary("hello", 0), 0);
    }

    #[test]
    fn test_floor_char_boundary_multibyte() {
        let s = "caf\u{00e9}"; // 5 bytes: c(1) a(1) f(1) é(2)
        assert_eq!(floor_char_boundary(s, 5), 5); // full string
        assert_eq!(floor_char_boundary(s, 4), 3); // mid-'é', rounds down
        assert_eq!(floor_char_boundary(s, 3), 3); // start of 'é'
    }

    #[test]
    fn test_floor_char_boundary_cjk() {
        let s = "\u{4e16}\u{754c}"; // 6 bytes: 世(3) 界(3)
        assert_eq!(floor_char_boundary(s, 6), 6);
        assert_eq!(floor_char_boundary(s, 5), 3); // mid-second char
        assert_eq!(floor_char_boundary(s, 4), 3);
        assert_eq!(floor_char_boundary(s, 3), 3);
        assert_eq!(floor_char_boundary(s, 2), 0); // mid-first char
        assert_eq!(floor_char_boundary(s, 1), 0);
    }

    #[test]
    fn test_floor_char_boundary_empty() {
        assert_eq!(floor_char_boundary("", 0), 0);
        assert_eq!(floor_char_boundary("", 5), 0);
    }
}
