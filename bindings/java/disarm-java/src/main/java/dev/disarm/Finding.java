package dev.disarm;

/**
 * One reason a token is anomalous (a single finding within an {@link AnomalyReport}).
 *
 * @param kind   which branch fired ({@code "invisible"}, {@code "bidi"},
 *               {@code "zalgo"}, {@code "mixed_script"}, {@code "bidi_mixed"},
 *               {@code "leet"}, {@code "segmentation"})
 * @param token  the offending token, as it appeared
 * @param start  byte offset of the token start in the input
 * @param end    byte offset of the token end in the input
 * @param detail evidence: the codepoint, the scripts, or the decoded word
 * @param reason a plain-language sentence describing the finding
 */
public record Finding(
        String kind, String token, long start, long end, String detail, String reason) {}
