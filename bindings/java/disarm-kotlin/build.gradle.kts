plugins {
    kotlin("jvm") // version declared in the root build (applied here)
    jacoco
    `maven-publish`
    signing
}

group = "dev.disarm"
version = "0.12.0" // lockstep with the core

kotlin {
    jvmToolchain(21)
}

java {
    withSourcesJar()
    withJavadocJar() // empty (Kotlin uses KDoc); Central accepts it
}

repositories {
    mavenCentral()
}

dependencies {
    // The idiomatic Kotlin layer delegates to the Java facade, which owns the JNI
    // shim + native loader (transitively on the test classpath, native lib and all).
    api(project(":disarm-java"))

    testImplementation(kotlin("test"))
    testImplementation(platform("org.junit:junit-bom:5.11.4"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.test {
    useJUnitPlatform()
    testLogging {
        events("passed", "skipped", "failed")
    }
    finalizedBy(tasks.jacocoTestReport)
}

jacoco {
    toolVersion = "0.8.13"
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

// ── Publishing ──────────────────────────────────────────────────────────────────
// A thin artifact that depends (api) on dev.disarm:disarm, so consumers get the
// native fat JAR transitively. The project() dependency is resolved to
// dev.disarm:disarm:<version> in the generated POM by Gradle's native maven-publish.
publishing {
    publications {
        create<MavenPublication>("maven") {
            from(components["java"])
            artifactId = "disarm-kotlin"
            pom {
                name.set("disarm-kotlin")
                description.set("Idiomatic Kotlin API for disarm — Unicode confusable / text-security building blocks")
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
        maven {
            name = "staging"
            url = rootProject.layout.buildDirectory.dir("staging-deploy").get().asFile.toURI()
        }
    }
}

signing {
    val signingKey = providers.gradleProperty("signingInMemoryKey").orNull
    val signingPassword = providers.gradleProperty("signingInMemoryKeyPassword").orNull
    if (signingKey != null) {
        useInMemoryPgpKeys(signingKey, signingPassword)
        sign(publishing.publications["maven"])
    }
}
