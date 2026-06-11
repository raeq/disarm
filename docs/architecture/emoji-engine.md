# Architecture: Emoji Engine

How disarm converts emoji sequences to text descriptions.

## Problem space

Emoji are not single codepoints. A "family" emoji can be a ZWJ (Zero-Width Joiner) sequence of 7+ codepoints; a flag is two Regional Indicator codepoints; a keycap is a digit + U+FE0F + U+20E3. The engine must match the longest valid sequence at each position, handle orphaned modifiers and variation selectors gracefully, and support user-supplied providers for custom naming conventions.

## Longest-match-first scanning

`match_emoji_at()` implements a greedy longest-match scanner:

1. If the current character is a known multi-sequence starter (`is_emoji_multi_starter`), try window sizes from `MAX_EMOJI_SEQ_LEN` down to 2, encoding each candidate window as a `HEXCODEPOINT_HEXCODEPOINT_...` key and probing the `EMOJI_MULTI` PHF map. The first hit wins.
2. If no multi-codepoint sequence matched, try the single-codepoint `EMOJI_SINGLE` PHF map.
3. If neither matched, the character falls through to error handling.

The descending-length loop ensures that a ZWJ family sequence is matched as one unit rather than being broken into its component person emoji. Incomplete sequences (those ending with ZWJ or a variation selector) are skipped during the scan, preventing partial matches from consuming codepoints that belong to a longer valid sequence.

## Variation selector and modifier cleanup

After any match (multi or single), the engine consumes trailing orphaned ZWJ characters (U+200D), variation selectors (U+FE0F / U+FE0E), skin-tone modifiers (U+1F3FB–U+1F3FF), tag characters (U+E0020–U+E007F), and combining enclosing keycap (U+20E3). This prevents leftover modifiers from appearing as garbage in the output.

Orphaned variation selectors and ZWJ characters that appear *before* any emoji match are also skipped in the main loop, handling cases where input text contains stray formatting codepoints.

## Skin-tone stripping

When `strip_modifiers=True`, the engine strips the `: skin-tone` suffix from CLDR names by searching for `": "` in the matched name. This produces base emoji names (`"thumbs up"`) instead of modified variants (`"thumbs up: medium-dark skin tone"`), which is useful for analytics and indexing where skin-tone distinctions are noise.

## Provider protocol

The `EmojiProvider` protocol allows users to inject custom naming logic. Provider resolution follows a strict priority chain:

1. **Per-call provider** (`demojize(text, provider=my_obj)`) — highest priority.
2. **Global provider** (`set_emoji_provider(my_obj)`) — process-wide default, stored in a `RwLock<Option<PyObject>>`.
3. **Built-in CLDR tables** — fallback.

The Python provider's `lookup(sequence: list[int]) -> str | None` method receives codepoints as a list of integers and returns either a name string or `None` to decline. The engine tries the provider with the same longest-match-first strategy, iterating window sizes from `MAX_EMOJI_SEQ_LEN` down to 1.

**Design tradeoff**: custom providers require a Python callback per attempt, which is orders of magnitude slower than the PHF lookup. The provider is tried first (before built-in tables) so it can override any built-in name, but this means provider-equipped calls pay the Python call overhead even for emoji the provider doesn't know about. For bulk workloads, the pure-Rust `demojize_rust()` function (used internally by `TextPipeline`) bypasses the provider system entirely.

## Error handling

Codepoints in emoji ranges (`is_emoji_codepoint`) that don't match any table entry are handled by the same three-mode system as transliteration: `"replace"` (substitute a placeholder), `"ignore"` (drop silently), or `"preserve"` (keep the raw codepoint). This covers future emoji added in newer Unicode versions that aren't yet in disarm's data files.

## Pure-Rust path

`demojize_rust()` is a separate function that skips all Python provider logic and GIL interaction. It is used by `TextPipeline.process()` when the `demojize=True` step is enabled, ensuring that pipeline execution stays entirely within Rust. Unknown emoji are silently dropped (equivalent to `errors="ignore"`) in this path.
