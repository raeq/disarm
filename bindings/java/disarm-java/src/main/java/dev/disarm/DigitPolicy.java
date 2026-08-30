package dev.disarm;

/**
 * How {@link Disarm#normalizeConfusables(String, TargetScript, DigitPolicy)} treats
 * non-Latin <b>digits</b>.
 *
 * <p>disarm and upstream TR39 disagree on 45 rows, and both readings are
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
     * Upstream TR39's targets, which fold most of these digits to a Latin <b>letter</b> —
     * {@code ०} to {@code o}, {@code ೦} to {@code O}, {@code ١} to {@code l}. Correct for
     * an identifier <i>skeleton</i>, whose only job is to make two confusable identifiers
     * collide; it does not care whether the collision target reads sensibly.
     *
     * <p>Scoped to {@link TargetScript#LATIN}: the override rows are generated from the
     * Latin table and carry TR39's Latin-script targets, so with
     * {@link TargetScript#CYRILLIC} this policy is a no-op.
     */
    TR39("tr39"),

    /**
     * Leave the digit alone — {@code ०} stays {@code ०} (#648).
     *
     * <p>The other two both rewrite a non-Latin numeral and neither keeps the script:
     * {@code २०२४} becomes {@code २0२४} under {@link #NUMERIC} and {@code २o२४} under
     * {@link #TR39}, both mixed-script numerals. This declines the digit rows and folds
     * everything else as usual, under every target script.
     */
    PRESERVE("preserve");

    private final String token;

    DigitPolicy(String token) {
        this.token = token;
    }

    String token() {
        return token;
    }
}
