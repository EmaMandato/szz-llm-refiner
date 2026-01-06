package it.unisannio.ingsw2.szzllm.settings

import com.intellij.openapi.fileChooser.FileChooserDescriptorFactory
import com.intellij.openapi.options.Configurable
import com.intellij.openapi.ui.TextFieldWithBrowseButton
import com.intellij.ui.components.JBCheckBox
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBTextField
import com.intellij.util.ui.FormBuilder
import com.intellij.util.ui.JBUI
import java.awt.BorderLayout
import javax.swing.*

/**
 * Settings UI for SZZ-LLM Analyzer in IDE Settings > Tools.
 */
class SzzSettingsConfigurable : Configurable {

    private var mainPanel: JPanel? = null

    // UI Components
    private val pythonPathField = TextFieldWithBrowseButton()
    private val ollamaUrlField = JBTextField()
    private val ollamaModelField = JBTextField()
    private val defaultBranchField = JBTextField()
    private val defaultLimitSpinner = JSpinner(SpinnerNumberModel(10, 1, 1000, 1))
    private val skipLlmCheckbox = JBCheckBox("Skip LLM refinement by default")
    private val showOutputLogCheckbox = JBCheckBox("Show output log panel")
    private val autoScrollCheckbox = JBCheckBox("Auto-scroll output log")

    override fun getDisplayName(): String = "SZZ-LLM Analyzer"

    override fun createComponent(): JComponent {
        // Configure Python path browser
        pythonPathField.addBrowseFolderListener(
            "Select Python Executable",
            "Choose the Python interpreter to use",
            null,
            FileChooserDescriptorFactory.createSingleFileDescriptor()
        )

        mainPanel = FormBuilder.createFormBuilder()
            .addComponent(createSectionLabel("Python Configuration"))
            .addLabeledComponent(JBLabel("Python path:"), pythonPathField, 1, false)
            .addComponentToRightColumn(
                createHelpLabel("Path to Python executable (e.g., python, python3, or full path)"),
                0
            )

            .addSeparator()
            .addComponent(createSectionLabel("Ollama Configuration"))
            .addLabeledComponent(JBLabel("Ollama URL:"), ollamaUrlField, 1, false)
            .addLabeledComponent(JBLabel("Model:"), ollamaModelField, 1, false)
            .addComponentToRightColumn(
                createHelpLabel("LLM model for refinement (e.g., qwen2.5-coder:7b, codellama:7b)"),
                0
            )

            .addSeparator()
            .addComponent(createSectionLabel("Analysis Defaults"))
            .addLabeledComponent(JBLabel("Default branch:"), defaultBranchField, 1, false)
            .addLabeledComponent(JBLabel("Default commit limit:"), defaultLimitSpinner, 1, false)
            .addComponent(skipLlmCheckbox)

            .addSeparator()
            .addComponent(createSectionLabel("UI Preferences"))
            .addComponent(showOutputLogCheckbox)
            .addComponent(autoScrollCheckbox)

            .addComponentFillVertically(JPanel(), 0)
            .panel

        mainPanel!!.border = JBUI.Borders.empty(10)

        return mainPanel!!
    }

    private fun createSectionLabel(text: String): JComponent {
        val label = JBLabel(text)
        label.font = label.font.deriveFont(java.awt.Font.BOLD)
        label.border = JBUI.Borders.empty(10, 0, 5, 0)
        return label
    }

    private fun createHelpLabel(text: String): JComponent {
        val label = JBLabel("<html><font color='gray' size='-1'>$text</font></html>")
        label.border = JBUI.Borders.emptyLeft(5)
        return label
    }

    override fun isModified(): Boolean {
        val settings = SzzSettings.getInstance()
        return pythonPathField.text != settings.pythonPath ||
                ollamaUrlField.text != settings.ollamaUrl ||
                ollamaModelField.text != settings.ollamaModel ||
                defaultBranchField.text != settings.defaultBranch ||
                (defaultLimitSpinner.value as Int) != settings.defaultLimit ||
                skipLlmCheckbox.isSelected != settings.skipLlmByDefault ||
                showOutputLogCheckbox.isSelected != settings.showOutputLog ||
                autoScrollCheckbox.isSelected != settings.autoScrollOutput
    }

    override fun apply() {
        val settings = SzzSettings.getInstance()
        settings.pythonPath = pythonPathField.text
        settings.ollamaUrl = ollamaUrlField.text
        settings.ollamaModel = ollamaModelField.text
        settings.defaultBranch = defaultBranchField.text
        settings.defaultLimit = defaultLimitSpinner.value as Int
        settings.skipLlmByDefault = skipLlmCheckbox.isSelected
        settings.showOutputLog = showOutputLogCheckbox.isSelected
        settings.autoScrollOutput = autoScrollCheckbox.isSelected
    }

    override fun reset() {
        val settings = SzzSettings.getInstance()
        pythonPathField.text = settings.pythonPath
        ollamaUrlField.text = settings.ollamaUrl
        ollamaModelField.text = settings.ollamaModel
        defaultBranchField.text = settings.defaultBranch
        defaultLimitSpinner.value = settings.defaultLimit
        skipLlmCheckbox.isSelected = settings.skipLlmByDefault
        showOutputLogCheckbox.isSelected = settings.showOutputLog
        autoScrollCheckbox.isSelected = settings.autoScrollOutput
    }

    override fun disposeUIResources() {
        mainPanel = null
    }
}
