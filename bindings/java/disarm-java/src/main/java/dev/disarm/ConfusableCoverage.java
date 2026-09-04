package dev.disarm;

/**
 * Per-script confusable coverage — the denominator {@code unmappedConfusables} does not
 * have (#963).
 *
 * <p>{@code folded} counts sources any bundled table reaches, not sources folded
 * <em>toward</em> this script: Greek is 71 of 159, because the Latin table folds Greek
 * letters that look Latin.
 *
 * @param script the script the figures are about, in disarm's spelling
 * @param sources TR39 sources whose prototype is in this script
 * @param folded how many of those {@code sources} a bundled fold table reaches
 */
public record ConfusableCoverage(String script, int sources, int folded) {}
