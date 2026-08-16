package dev.disarm;

import java.util.List;

/**
 * Structured hostname homoglyph analysis (#549). Returned by {@link Disarm#analyzeHostname}.
 *
 * <p>{@code suspicious} is a <em>maximally conservative screen</em> — because the confusable
 * check is an any-character test and the most frequent Cyrillic/Greek letters are TR39
 * confusables, it flags essentially every non-Latin hostname — not a precise verdict. A
 * {@code false} is not a safety guarantee. {@code wholeScriptConfusable} is a graded signal,
 * deliberately <em>not</em> folded into {@code suspicious} (it fires on short non-Latin ccTLDs
 * and on real words); the precise policy is {@code wholeScriptConfusable(non-TLD label) &&
 * Latin TLD}, applied by the caller.
 *
 * @param suspicious                 overall verdict (a conservative screen, not a precise verdict)
 * @param scripts                    scripts across all labels, first-appearance order
 * @param mixedScript                whether any single label mixes more than one script
 * @param hasConfusables             whether any label contains a Latin-confusable character
 * @param bidiConflict               whether the host mixes strong LTR and RTL (folded into {@code suspicious})
 * @param crossLabelScript           whether the labels span more than one script (not folded in)
 * @param labelScripts               per-label resolved scripts, left to right
 * @param wholeScriptConfusable      whether any label is single-script, non-Latin, skeletoning to all-Latin (a signal, not folded in)
 * @param labelWholeScriptConfusable per-label whole-script-confusable flags, parallel to {@code labelScripts}
 * @param canonical                  the Latin-normalized form of the hostname
 */
public record HostnameAnalysis(
        boolean suspicious,
        List<String> scripts,
        boolean mixedScript,
        boolean hasConfusables,
        boolean bidiConflict,
        boolean crossLabelScript,
        List<List<String>> labelScripts,
        boolean wholeScriptConfusable,
        List<Boolean> labelWholeScriptConfusable,
        String canonical) {}
