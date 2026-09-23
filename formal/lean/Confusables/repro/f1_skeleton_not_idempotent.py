#!/usr/bin/env python3
"""F1: skeleton_key is not idempotent, and two confusable inputs miss each other.

The model's minimal witnesses (Checks.lean F1a/F1b/F1c/F1d), reproduced on the library.
Exits 0 when every failure reproduces (i.e. the bug is present), 1 once it is fixed.
"""

import disarm

sk = disarm.skeleton_key
reproduced = []

# (a) full case folding emits a decomposed sequence (U+0390 -> U+03B9 U+0308 U+0301); the
#     fold maps the iota to 'i' and nothing composes it again until the next call.
k = sk("\u0390")
print("a  sk('\\u0390')      =", ascii(k), "  sk(sk(.)) =", ascii(sk(k)))
reproduced.append(k == "i\u0308\u0301" and sk(k) == "\u1e2f")

# (b) the fold emits a base beside a mark it composes with ('\u00a5' -> 'Y', then Y+grave).
k = sk("\u00a5\u0300")
print("b  sk('\\u00a5\\u0300') =", ascii(k), "  sk(sk(.)) =", ascii(sk(k)))
reproduced.append(k == "y\u0300" and sk(k) == "\u00fd")
# ...and that key is flagged by the library's own detector:
print("   is_confusable(key) =", disarm.is_confusable(k))
reproduced.append(disarm.is_confusable(k))

# (c) StripControl runs after the last fold, so a removed control joins a base to a mark.
k = sk("a\x01\u0300")
print("c  sk('a\\x01\\u0300') =", ascii(k), "  sk(sk(.)) =", ascii(sk(k)))
reproduced.append(k == "a\u0300" and sk(k) == "\u00e0")

# The consequence for a spoof key: two inputs that should collide do not.
# U+04AA + cedilla is the #522 example (it composes to a confusable); U+00E7 is its target.
x, y = "\u04aa\u0327", "\u00e7"
print(f"   sk({ascii(x)}) = {ascii(sk(x))}   sk({ascii(y)}) = {ascii(sk(y))}")
reproduced.append(sk(x) != sk(y) and sk(sk(x)) == sk(y))
# A control character inserted between a letter and its accent changes the key.
x, y = "caf" + "e\x01\u0301", "caf\u00e9"
print(f"   sk({ascii(x)}) = {ascii(sk(x))}   sk({ascii(y)}) = {ascii(sk(y))}")
reproduced.append(sk(x) != sk(y))

print("reproduced:", all(reproduced), reproduced)
raise SystemExit(0 if all(reproduced) else 1)
