package dev.disarm;

/**
 * An upstream confusable source the bundled table does not fold, located in the input.
 * Returned by {@link Disarm#findUnmappedConfusables(String)}. Mirrors
 * {@link Untranslatable}, its transliteration analogue.
 *
 * @param character the unmapped character
 * @param offset    its byte offset in the input string
 */
public record UnmappedConfusable(String character, long offset) {}
