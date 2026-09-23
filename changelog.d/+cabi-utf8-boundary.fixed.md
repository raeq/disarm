- **The C ABI read bytes that are not UTF-8 as if they were.** Found by the bindings harness
  (`formal/bindings`). safer-ffi's `char_p::Ref::to_str` does not validate, so a C
  caller passing Latin-1 or truncated input handed the core text that was not UTF-8,
  which is undefined behaviour: `disarm_strip_bidi("caf\xE9")` crashed,
  `disarm_fold_case` aborted with a panic that could not unwind, and
  `disarm_canonicalize` returned bytes that were not UTF-8. Every argument is now
  decoded at the boundary with each malformed sequence read as U+FFFD, the contract the
  other bindings already follow, so the call proceeds. `disarm.h` gains the argument and
  result contract in the `disarm_string_free` comment: pointer arguments other than the
  nullable ones must be non-NULL, and returned strings are read-only until freed. No
  signature changes.
