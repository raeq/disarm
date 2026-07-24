package com.disarm;

import java.util.List;

/**
 * How {@code lang: "auto"} detection resolves a text. Returned by
 * {@link Disarm#inspectAutoLang(String)}.
 *
 * @param script            the primary non-Latin script detected, or {@code null}
 * @param chosenLang        the language auto-detection chose, or {@code null}
 * @param reason            why that choice was made
 * @param discriminatorsHit the discriminator characters that drove the choice
 */
public record AutoLangInspection(
        String script, String chosenLang, String reason, List<String> discriminatorsHit) {}
