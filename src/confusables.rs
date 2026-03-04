use pyo3::prelude::*;

use crate::tables;

/// Replace Unicode confusable homoglyphs with target-script equivalents.
#[pyfunction]
#[pyo3(signature = (text, *, target_script="latin"))]
pub fn _normalize_confusables(text: &str, target_script: &str) -> PyResult<String> {
    let mut result = String::with_capacity(text.len());

    for ch in text.chars() {
        match tables::lookup_confusable(ch, target_script) {
            Some(replacement) => result.push_str(replacement),
            None => result.push(ch),
        }
    }

    Ok(result)
}

/// True if text contains any characters confusable with target-script characters.
#[pyfunction]
#[pyo3(signature = (text, *, target_script="latin"))]
pub fn _is_confusable(text: &str, target_script: &str) -> PyResult<bool> {
    for ch in text.chars() {
        if tables::lookup_confusable(ch, target_script).is_some() {
            return Ok(true);
        }
    }
    Ok(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normalize_confusables_cyrillic() {
        // Cyrillic 'а' (U+0430) → Latin 'a'
        let result = _normalize_confusables("\u{0430}", "latin").unwrap();
        assert_eq!(result, "a");
    }

    #[test]
    fn test_normalize_confusables_passthrough() {
        let result = _normalize_confusables("hello", "latin").unwrap();
        assert_eq!(result, "hello");
    }

    #[test]
    fn test_normalize_confusables_empty() {
        let result = _normalize_confusables("", "latin").unwrap();
        assert_eq!(result, "");
    }

    #[test]
    fn test_is_confusable_true() {
        // Cyrillic 'а' is confusable with Latin 'a'
        assert!(_is_confusable("\u{0430}", "latin").unwrap());
    }

    #[test]
    fn test_is_confusable_false() {
        assert!(!_is_confusable("hello", "latin").unwrap());
    }

    #[test]
    fn test_is_confusable_empty() {
        assert!(!_is_confusable("", "latin").unwrap());
    }
}
