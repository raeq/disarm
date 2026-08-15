package dev.disarm;

/**
 * A character with no transliteration, located in the input. Returned by
 * {@link Disarm#findUntranslatable(String)}.
 *
 * @param character the untranslatable character
 * @param offset    its byte offset in the input string
 */
public record Untranslatable(String character, long offset) {}
