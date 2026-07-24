plugins {
    `java-library`
}

group = "com.disarm"
version = "0.11.0" // lockstep with the core (see RELEASING.md); a 7th version-bump site.

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21) // the supported floor
    }
    withSourcesJar()
    withJavadocJar()
}

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(platform("org.junit:junit-bom:5.11.4"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

// ── Native (Rust JNI) build + staging ───────────────────────────────────────────
//
// For a local/dev build we compile the host-platform cdylib and stage it into the
// binding's resources at /com/disarm/native/<os>-<arch>/, exactly where the
// production fat JAR will carry per-platform libraries — so tests exercise the real
// NativeLoader resource-extraction path, not a dev override. Cross-platform fan-out
// (all 5 targets) is a release-workflow concern (Phase 4).

val rustDir = layout.projectDirectory.dir("../rust")

/** `<os>-<arch>` tag matching NativeLoader's tokens for the *build* host. */
val hostOsArch: String = run {
    val os = System.getProperty("os.name").lowercase()
    val arch = System.getProperty("os.arch").lowercase()
    val osTok = when {
        os.contains("mac") || os.contains("darwin") -> "darwin"
        os.contains("win") -> "windows"
        else -> "linux"
    }
    val archTok = when (arch) {
        "aarch64", "arm64" -> "aarch64"
        "x86_64", "amd64" -> "x86_64"
        else -> arch
    }
    "$osTok-$archTok"
}

/** The cdylib filename cargo emits for the host (crate lib name = `disarm_jni`). */
val builtLibName: String = when {
    hostOsArch.startsWith("darwin") -> "libdisarm_jni.dylib"
    hostOsArch.startsWith("windows") -> "disarm_jni.dll"
    else -> "libdisarm_jni.so"
}

val cargoBuild by tasks.registering(Exec::class) {
    group = "native"
    description = "Compile the Rust JNI cdylib (release) for the host platform."
    workingDir = rustDir.asFile
    commandLine("cargo", "build", "--release")
    inputs.dir(rustDir.dir("src"))
    inputs.file(rustDir.file("Cargo.toml"))
    outputs.file(rustDir.dir("target/release").file(builtLibName))
}

val stageNativeLib by tasks.registering(Copy::class) {
    group = "native"
    description = "Stage the host cdylib into resources at /com/disarm/native/<os>-<arch>/."
    dependsOn(cargoBuild)
    from(rustDir.dir("target/release").file(builtLibName))
    into(layout.projectDirectory.dir("src/main/resources/com/disarm/native/$hostOsArch"))
}

tasks.named("processResources") {
    dependsOn(stageNativeLib)
}

tasks.test {
    useJUnitPlatform()
    testLogging {
        events("passed", "skipped", "failed")
    }
}
