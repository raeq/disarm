rootProject.name = "disarm-java-binding"

// Layer B/C — idiomatic Java (owns the JNI shim + native loader).
include("disarm-java")

// Layer D — idiomatic Kotlin (extension functions + default args over disarm-java).
// Plain-JVM for now; structured to become the `jvmMain` actual of a KMP split if
// iOS is committed later (see the plan's iOS decision).
include("disarm-kotlin")
