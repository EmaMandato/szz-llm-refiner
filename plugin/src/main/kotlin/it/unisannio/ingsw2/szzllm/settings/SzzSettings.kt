package it.unisannio.ingsw2.szzllm.settings

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.util.xmlb.XmlSerializerUtil

/**
 * Persistent application-level settings for SZZ-LLM Analyzer.
 */
@State(
    name = "SzzLlmSettings",
    storages = [Storage("SzzLlmSettings.xml")]
)
class SzzSettings : PersistentStateComponent<SzzSettings> {

    // Python configuration
    var pythonPath: String = "python"

    // Ollama configuration
    var ollamaUrl: String = "http://localhost:11434"
    var ollamaModel: String = "qwen2.5-coder:7b"

    // Analysis defaults
    var defaultBranch: String = "main"
    var defaultLimit: Int = 10
    var skipLlmByDefault: Boolean = false

    // UI preferences
    var showOutputLog: Boolean = true
    var autoScrollOutput: Boolean = true

    companion object {
        fun getInstance(): SzzSettings {
            return ApplicationManager.getApplication().getService(SzzSettings::class.java)
        }
    }

    override fun getState(): SzzSettings = this

    override fun loadState(state: SzzSettings) {
        XmlSerializerUtil.copyBean(state, this)
    }
}
