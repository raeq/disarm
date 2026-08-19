package dev.disarm;

/**
 * How {@link Disarm#normalizeConfusables(String, TargetScript, DigitPolicy)} treats
 * non-Latin <b>digits</b>.
 *
 * <p>disarm and upstream TR39 disagree on about 45 rows, and both readings are
 * defensible. The divergence used to be fixed in the table with no way to select the
 * other side, which read as a defect to anyone scoring disarm against a TR39-derived
 * benchmark.
 */
public enum DigitPolicy {
    /**
     * A non-Latin digit folds to the ASCII <b>digit</b> — {@code ०} becomes {@code 0}.
     * The default, and the right reading for prose: a Devanagari zero in running text is
     * a zero, and folding it to a letter corrupts the number.
     */
    NUMERIC("numeric"),

    /**
     * Upstream TR39's targets, which fold several digits to a Latin <b>letter</b> —
     * {@code ०} to {@code o}, {@code ೦} to {@code O}, {@code ١} to {@code l}. Correct for
     * an identifier <i>skeleton</i>, whose only job is to make two confusable identifiers
     * collide; it does not care whether the collision target reads sensibly.
     */
    TR39("tr39");

    private final String token;

    DigitPolicy(String token) {
        this.token = token;
    }

    String token() {
        return token;
    }
}
