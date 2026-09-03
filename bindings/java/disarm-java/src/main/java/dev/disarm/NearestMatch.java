package dev.disarm;

/**
 * A candidate name and how far {@link Disarm#nearestMatch} found it from the value asked
 * about (#894).
 *
 * <p>A record rather than a pair: {@code (String, long)} at a call site says nothing about
 * which number is which.
 *
 * @param value    the candidate, in the spelling the caller supplied
 * @param distance its edit distance from the value asked about; {@code 0} means the value
 *                 <em>is</em> this candidate, which {@link Disarm#nearestMatch} reports
 */
public record NearestMatch(String value, long distance) {}
