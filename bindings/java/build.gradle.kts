// Root build for the JVM bindings (disarm-java + disarm-kotlin). Declares the shared
// Kotlin plugin version once (applied in the modules). Publishing uses Gradle's
// built-in `maven-publish` + `signing` (no external plugin — Gradle-9-native, and it
// resolves project() deps to POM coordinates correctly); the release workflow uploads
// the signed staging bundle to the Central Portal via its REST API.
plugins {
    kotlin("jvm") version "2.1.0" apply false
}
