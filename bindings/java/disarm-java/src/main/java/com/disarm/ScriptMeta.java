package com.disarm;

/**
 * Static facts about a Unicode script known to the transliteration tables.
 * Returned by {@link Disarm#scriptInfo(String)}.
 *
 * @param name         the script's name (e.g. {@code "Coptic"})
 * @param defaultLang  the default language code for the script, or {@code null}
 * @param example      a short example string in the script
 * @param contextAware whether transliteration of this script is context-aware
 */
public record ScriptMeta(String name, String defaultLang, String example, boolean contextAware) {}
