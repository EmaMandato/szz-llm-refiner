plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "2.1.0"
    id("org.jetbrains.intellij.platform") version "2.2.1"
}

group = "it.unisannio.ingsw2"
version = "1.0.0"

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

dependencies {
    intellijPlatform {
        pycharmProfessional("2025.1")
        bundledPlugin("PythonCore")
        instrumentationTools()
    }

    // Gson for JSON parsing
    implementation("com.google.code.gson:gson:2.10.1")
}

kotlin {
    jvmToolchain(21)
}

tasks {
    patchPluginXml {
        sinceBuild.set("251")
        untilBuild.set("251.*")
        pluginDescription.set("""
            <h2>SZZ-LLM Bug Analyzer</h2>
            <p>Identifies bug-inducing commits in Git repositories using the SZZ algorithm
            with LLM-based refinement via Ollama.</p>

            <h3>Features:</h3>
            <ul>
                <li>Detect fix commits in Git repositories</li>
                <li>Use LLM (Qwen2.5-Coder) to filter false positives</li>
                <li>Identify bug-inducing commits via git blame</li>
                <li>Visualize results in a dedicated tool window</li>
            </ul>
        """.trimIndent())
    }

    buildSearchableOptions {
        enabled = false
    }
}
