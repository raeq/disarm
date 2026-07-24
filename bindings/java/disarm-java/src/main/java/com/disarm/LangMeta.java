package com.disarm;

/**
 * Static facts about a language profile (the {@code lang} codes accepted across the
 * API). Returned by {@link Disarm#langInfo(String)}.
 *
 * @param name    the language's English name (e.g. {@code "German"})
 * @param script  the primary script it is written in (e.g. {@code "Latin"})
 * @param region  the region/locale it is associated with
 * @param context context-aware transliteration support: {@code "none"}, {@code "partial"}, or {@code "full"}
 */
public record LangMeta(String name, String script, String region, String context) {}
