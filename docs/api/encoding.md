# Encoding Detection & Decoding

Functions for detecting and converting byte sequences to UTF-8. Uses the chardetng algorithm (Firefox's encoding detector) for auto-detection.

## detect_encoding

::: disarm.detect_encoding

```python
from disarm import detect_encoding

enc, confidence = detect_encoding(b"Hello World")
# enc = "UTF-8", confidence = 0.95

# Windows-1252 encoded text
enc, confidence = detect_encoding("café".encode("windows-1252"))
# enc = "windows-1252", confidence = 0.95
```

!!! warning
    Automatic encoding detection is inherently probabilistic. A high confidence score does not guarantee correctness. For critical pipelines, always prefer explicit encoding metadata (HTTP headers, BOM, schema definitions) over detection.

!!! note "Confidence is a fixed 0.95 (#194)"
    chardetng (since the 1.0 migration) does not expose a graded score — it reports a fixed `0.95` for every successful detection. The value is kept for API stability, but you cannot use it to rank detection quality. Consequently `min_confidence` below is an accept/reject switch, not a quality threshold.

---

## decode_to_utf8

::: disarm.decode_to_utf8

```python
from disarm import decode_to_utf8

# Explicit encoding
text, had_errors = decode_to_utf8(b"caf\xe9", "windows-1252")
# text = "café", had_errors = False

# Auto-detection (accepts the guess; detection confidence is always 0.95)
text, had_errors = decode_to_utf8(raw_bytes)

# min_confidence is an accept/reject switch, not a quality grade (#194):
# any value > 0.95 refuses auto-detection outright (use 1.0 to require an
# explicit encoding); any value <= 0.95 (the 0.95 default) accepts every guess.
text, had_errors = decode_to_utf8(raw_bytes, min_confidence=1.0)
# Raises DisarmError: detection's fixed 0.95 is below the required 1.0
```

`had_errors=False` is not a fidelity guarantee — windows-1252 and other single-byte encodings map every byte to a codepoint without inserting U+FFFD, so a wrong-encoding decode yields mojibake with `had_errors=False`. Pass `strict=True` to raise on U+FFFD insertion, but prefer explicit encoding metadata for critical data.

Supports all WHATWG encodings: UTF-8, windows-1252, ISO-8859-1, Shift_JIS, EUC-JP, EUC-KR, Big5, GB18030, and more.
