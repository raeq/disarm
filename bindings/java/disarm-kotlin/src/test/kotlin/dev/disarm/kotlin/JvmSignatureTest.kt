package dev.disarm.kotlin

import dev.disarm.TargetScript
import kotlin.test.Test
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * #588: a Kotlin default argument compiles to ONE JVM method plus a synthetic `$default`
 * bridge, not to an overload per arity. Adding a defaulted parameter to a published
 * extension therefore deletes the JVM signature that shipped, and anything compiled
 * against the old artifact gets `NoSuchMethodError` — Java callers, and Kotlin callers
 * that have not been recompiled.
 *
 * It has happened twice, unnoticed both times. `dev.disarm:disarm-kotlin:0.13.0` shipped
 * `normalizeConfusables(String, TargetScript)` and `analyzeHostname(String)`; #574 and
 * #562 respectively gave each a defaulted parameter and removed those methods.
 *
 * #562 made the identical break in the C ABI, where it *was* caught and reverted by #580.
 * The C surface has a committed, drift-gated header; this one had nothing. These
 * assertions are that gate: they read the compiled `Disarm` class, so they fail on the
 * signature, not on the source text.
 */
class JvmSignatureTest {

    private fun hasMethod(name: String, vararg params: Class<*>): Boolean =
        try {
            Class.forName("dev.disarm.kotlin.Disarm").getMethod(name, *params)
            true
        } catch (_: NoSuchMethodException) {
            false
        }

    /** Shipped in 0.13.0; #574 added `digitPolicy` and deleted this arity. */
    @Test
    fun normalizeConfusablesKeepsItsTwoArgumentSignature() {
        assertTrue(
            hasMethod("normalizeConfusables", String::class.java, TargetScript::class.java),
            "Disarm.normalizeConfusables(String, TargetScript) is gone — it shipped in " +
                "0.13.0, so callers compiled against that artifact get NoSuchMethodError",
        )
    }

    /** Shipped in 0.13.0; #562 added `contractions` and deleted this arity. */
    @Test
    fun analyzeHostnameKeepsItsOneArgumentSignature() {
        assertTrue(
            hasMethod("analyzeHostname", String::class.java),
            "Disarm.analyzeHostname(String) is gone — it shipped in 0.13.0. #580 " +
                "reverted the identical break on the C ABI; this surface was missed",
        )
    }

    /**
     * The general rule, checked structurally: every public extension with a default
     * argument must expose the arity a caller can reach without passing that default.
     * Without `@JvmOverloads` only the widest arity exists, so this fails on the next
     * parameter added anywhere — which is the point.
     */
    @Test
    fun everyDefaultedExtensionExposesItsShorterArities() {
        val cls = Class.forName("dev.disarm.kotlin.Disarm")
        val byName = cls.methods.filter { !it.isSynthetic }.groupBy { it.name }
        val missing = mutableListOf<String>()
        for ((name, overloads) in byName) {
            // A `$default` bridge is emitted only for a function that HAS defaults.
            val hasDefaults = cls.methods.any { it.name == "$name\$default" }
            if (!hasDefaults) continue
            val widest = overloads.maxOf { it.parameterCount }
            if (overloads.none { it.parameterCount < widest }) {
                missing += "$name (only the $widest-arg form exists)"
            }
        }
        if (missing.isNotEmpty()) {
            fail(
                "These defaulted extensions expose no shorter arity, so adding their " +
                    "default deleted a JVM signature (#588). Annotate with " +
                    "@JvmOverloads:\n  " + missing.sorted().joinToString("\n  "),
            )
        }
    }
}
