- **`sanitize_filename` could return a Windows device name when the stem sanitized to
  nothing (Lean model, finding 1).** `sanitize_filename("*.con")` returned `con`, as did
  `"_.con"`, `"/.aux"`, `"../.con"` and 185 single characters before `.con`, on the
  universal and Windows platforms alike. Both reserved-name checks read the empty stem,
  and `finalize_name` stripped the extension's dot after them. The check now reads the
  name as it is returned, the part Windows matches (before the first dot, trailing
  spaces ignored), so `"*.con"` gives `_con`, and `"nul.tar.gz"` is still caught.
- **`sanitize_filename` validates `separator` (Lean model, finding 2).** It is inserted
  after the illegal characters are removed and nothing checked it: `separator="/"` turned
  `"../etc/passwd"` into `/etc/passwd`, `"\x00"` put NUL in the name, and `" "` let
  `"con _"` truncate to a bare `con`. A separator must now be printable, non-space ASCII
  with no character illegal on the platform and no `/` or `\`, or the call raises
  `InvalidArgumentError` (Rust: `ErrorKind::InvalidArgument`, code
  `invalid_filename_separator`) in every binding, the way `strip_log_injection` refuses
  a bad `replacement`. `""` is still allowed. A non-ASCII separator is refused too: it
  could carry a bidi control into the name, and the next call transliterated it anyway.
- **`sanitize_filename` returns a fixed point (Lean model, finding 3).** #570 fixed one
  way a second call changed the name; four more remained, such as `"_.x.*"` giving
  `_.x` then `x`, `("ab_cd", max_length=3, preserve_extension=False)` giving `ab_` then
  `ab`, and `("a.bcd.txt", max_length=6)` giving `a..txt`. The sanitizing pass now runs
  again on its own output until it stops changing (at most eight passes; the model's
  8.5-million-case grid needs at most four), so idempotence holds by construction rather
  than case by case, and the passes after the first skip normalization and
  transliteration, which are the identity on the ASCII they see. A stem made only of
  separators now keeps one instead of vanishing, so `"_.x"` stays `_.x` (it gave `x`)
  and `("PRN.txt", max_length=5)` stays `_.txt` rather than collapsing to `txt` on the
  next call. Outputs change only where they were unsafe or not fixed points, plus that
  all-separator stem.
- **An explicit encoding is no longer overridden by a byte-order mark (Lean model,
  finding 14).** `decode_to_utf8(b"\xfe\xff\x00A", "utf-8", strict=True)` returned
  `("A", False)`: the WHATWG sniff decoded bytes that are not UTF-8 as UTF-16BE, and
  `strict` had nothing to catch. With an explicit encoding only that encoding's own BOM
  is removed now, and any other is data, so that call raises. A UTF-16 label that names
  no byte order (`"utf-16"`, `"unicode"`, `"ucs-2"`) still takes it from a UTF-16 BOM,
  as Python's `utf-16` codec does. Auto-detection keeps the sniff (#710).
- **One typed `%` no longer lets a manufactured one through (Lean model, finding 15).**
  #721 neutralized the `%` compatibility folding makes from fullwidth input only when
  the input had no `%` at all, so `"%"` followed by fullwidth `%2E%2E%2F` still gave
  `%%2E%2E%2Fetc.txt`. The rule is now per character: every `%` in the output is one the
  input contained (or part of the separator). `docs/limitations.md` and the docstrings
  say so.
