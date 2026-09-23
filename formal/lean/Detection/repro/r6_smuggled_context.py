"""Finding 6: a payload next to a carrier of its own scheme does not round-trip, and the
zero-width case reports text nobody encoded."""

import disarm


def vs(p):  # variation_bytes, as documented
    return "".join(chr(0xFE00 + b) if b < 16 else chr(0xE0100 + b - 16) for b in p.encode())


def zw(p):  # zero_width_binary: U+200B = 0, U+200C = 1, MSB first
    return "".join(
        "\u200c" if (b >> (7 - i)) & 1 else "\u200b" for b in p.encode() for i in range(8)
    )


for s in [
    "x" + vs("hi"),
    "\u2764\ufe0f" + vs("hi"),
    "x" + zw("hi"),
    "a\u200b" + zw("hi"),
    "a\u200c" + zw("hi"),
]:
    print(
        [(p.scheme, p.data, p.text) for p in disarm.decode_smuggled(s)],
        disarm.inspect_anomalies(s).kinds,
    )
