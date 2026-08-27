package dev.disarm;

import java.util.List;

/**
 * One group of distinct inputs that reduce to the same identity key (#620).
 *
 * <p>A group is reported only when it holds two or more <em>distinct</em> inputs. The same
 * string appearing twice is the same name twice, which a reservation table already handles;
 * the hazard is two names that differ and occupy one slot.
 *
 * @param key     the reduced form every member of the group shares
 * @param values  the distinct inputs that reduce to it, in order of first appearance
 * @param indices every position in the input list that belongs to this group, ascending.
 *                Not parallel to {@code values}: a value repeated verbatim appears once
 *                there and once per occurrence here.
 */
public record KeyCollision(String key, List<String> values, List<Long> indices) {}
