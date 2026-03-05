"""Encoding detection and byte-to-Unicode decoding.

This module groups the byte-level operations that sit at the
bytes-to-Unicode boundary, conceptually distinct from the Unicode
text transforms in the main ``translit`` namespace.

Usage::

    from translit.codec import decode_to_utf8, detect_encoding

    encoding, confidence = detect_encoding(raw_bytes)
    text, had_errors = decode_to_utf8(raw_bytes, encoding="UTF-8")
"""

from translit import decode_to_utf8, detect_encoding

__all__ = [
    "decode_to_utf8",
    "detect_encoding",
]
