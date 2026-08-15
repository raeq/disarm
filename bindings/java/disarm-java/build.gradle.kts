plugins {
    `java-library`
    jacoco
    `maven-publish`
    signing
}

group = "dev.disarm"
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

// Native libs are staged into build/nativeLib (NOT a source dir) and added to the
// main JAR + test runtime classpath — never the -sources JAR (they are binaries).
val nativeLibDir = layout.buildDirectory.dir("nativeLib")

val cargoBuild = tasks.register<Exec>("cargoBuild") {
    group = "native"
    description = "Compile the Rust JNI cdylib (release) for the host platform."
    workingDir = rustDir.asFile
    commandLine("cargo", "build", "--release")
    inputs.dir(rustDir.dir("src"))
    inputs.file(rustDir.file("Cargo.toml"))
    outputs.file(rustDir.dir("target/release").file(builtLibName))
}

val stageNativeLib = tasks.register<Copy>("stageNativeLib") {
    group = "native"
    description = "Stage the host cdylib into build/nativeLib/com/disarm/native/<os>-<arch>/."
    dependsOn(cargoBuild)
    from(rustDir.dir("target/release").file(builtLibName))
    into(nativeLibDir.map { it.dir("com/disarm/native/$hostOsArch") })
}

// Release mode: CI stages all 5 prebuilt libs into build/nativeLib and passes
// -Pdisarm.nativePrebuilt, so the fat JAR carries every platform; the host-only
// cargo build is then skipped. Dev/CI-`check` builds the host lib as usual.
val nativePrebuilt = providers.gradleProperty("disarm.nativePrebuilt").isPresent

tasks.named<Jar>("jar") {
    if (!nativePrebuilt) dependsOn(stageNativeLib)
    from(nativeLibDir) // build/nativeLib/com/disarm/native/... -> jar's com/disarm/native/...
}

tasks.test {
    if (!nativePrebuilt) dependsOn(stageNativeLib)
    classpath += files(nativeLibDir) // NativeLoader resolves the lib from this resource root
    useJUnitPlatform()
    testLogging {
        events("passed", "skipped", "failed")
    }
    finalizedBy(tasks.jacocoTestReport)
}

// ── Coverage (JaCoCo) ───────────────────────────────────────────────────────────

jacoco {
    toolVersion = "0.8.13" // supports the Java 21 class-file format
}

tasks.jacocoTestReport {
    dependsOn(tasks.test)
    reports {
        xml.required = true
        html.required = true
    }
}

tasks.jacocoTestCoverageVerification {
    dependsOn(tasks.test)
    violationRules {
        rule {
            limit {
                counter = "LINE"
                minimum = "0.90".toBigDecimal()
            }
        }
    }
}

tasks.check {
    dependsOn(tasks.jacocoTestCoverageVerification)
}

// ── Publishing (Maven Central via the Sonatype Central Portal) ──────────────────
//
// The published `com.disarm:disarm` is the FAT JAR: the JNI shim's per-platform
// native libraries live under /com/disarm/native/<os>-<arch>/ (the jar `from`
// above), and the NativeLoader extracts + loads the right one at runtime (the
// sqlite-jdbc model). `publish` writes signed, checksummed artifacts into a local
// staging repo (build/staging-deploy) in Maven layout; the release workflow zips
// that and uploads it to the Central Portal. `publishToMavenLocal` validates the
// artifacts/POM locally without any credentials.
publishing {
    publications {
        create<MavenPublication>("maven") {
            from(components["java"])
            artifactId = "disarm"
            pom {
                name.set("disarm")
                description.set("Unicode confusable / text-security building blocks — JVM binding (native Rust core)")
                url.set("https://github.com/raeq/disarm")
                licenses {
                    license {
                        name.set("MIT License")
                        url.set("https://opensource.org/licenses/MIT")
                    }
                }
                developers {
                    developer {
                        id.set("raeq")
                        name.set("Richard Quinn")
                    }
                }
                scm {
                    url.set("https://github.com/raeq/disarm")
                    connection.set("scm:git:https://github.com/raeq/disarm.git")
                    developerConnection.set("scm:git:ssh://git@github.com/raeq/disarm.git")
                }
            }
        }
    }
    repositories {
        // Local staging repo; the workflow bundles this and POSTs it to the Portal.
        maven {
            name = "staging"
            url = rootProject.layout.buildDirectory.dir("staging-deploy").get().asFile.toURI()
        }
    }
}

// Sign only when a key is supplied (the release workflow). Local publish tasks run
// unsigned so publishToMavenLocal works without GPG.
signing {
    val signingKey = providers.gradleProperty("signingInMemoryKey").orNull
    val signingPassword = providers.gradleProperty("signingInMemoryKeyPassword").orNull
    if (signingKey != null) {
        useInMemoryPgpKeys(signingKey, signingPassword)
        sign(publishing.publications["maven"])
    }
}
