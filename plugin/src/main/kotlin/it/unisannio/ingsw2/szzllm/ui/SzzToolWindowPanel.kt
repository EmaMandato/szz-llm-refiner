package it.unisannio.ingsw2.szzllm.ui

import com.intellij.icons.AllIcons
import com.intellij.openapi.actionSystem.*
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.ComboBox
import com.intellij.openapi.ui.SimpleToolWindowPanel
import com.intellij.ui.JBColor
import com.intellij.ui.JBSplitter
import com.intellij.ui.ScrollPaneFactory
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.components.JBTextArea
import com.intellij.ui.table.JBTable
import com.intellij.util.ui.JBUI
import it.unisannio.ingsw2.szzllm.model.*
import it.unisannio.ingsw2.szzllm.services.SzzAnalyzerService
import it.unisannio.ingsw2.szzllm.settings.SzzSettings
import java.awt.*
import javax.swing.*
import javax.swing.table.AbstractTableModel
import javax.swing.table.DefaultTableCellRenderer

/**
 * Main panel for the SZZ-LLM Tool Window.
 * Provides UI for configuring and running analysis, and displaying results.
 */
class SzzToolWindowPanel(private val project: Project) : SimpleToolWindowPanel(true, true) {

    private val analyzerService = SzzAnalyzerService.getInstance(project)

    // UI Components
    private val statusLabel = JBLabel("Ready")
    private val progressBar = JProgressBar(0, 100).apply { isVisible = false }
    private val resultsTable: JBTable
    private val resultsModel = ResultsTableModel()
    private val detailsArea = JBTextArea().apply {
        isEditable = false
        lineWrap = true
        wrapStyleWord = true
        font = Font(Font.MONOSPACED, Font.PLAIN, 12)
    }
    private val outputArea = JBTextArea().apply {
        isEditable = false
        font = Font(Font.MONOSPACED, Font.PLAIN, 11)
    }

    // Config components
    private val branchField = JTextField("main", 15)
    private val limitSpinner = JSpinner(SpinnerNumberModel(10, 1, 1000, 1))
    private val skipLlmCheckbox = JCheckBox("Skip LLM refinement")

    init {
        resultsTable = JBTable(resultsModel)
        setupUI()
        setupListeners()
    }

    private fun setupUI() {
        // Toolbar
        val toolbar = createToolbar()
        setToolbar(toolbar.component)

        // Main content
        val mainPanel = JPanel(BorderLayout())

        // Config panel at top
        val configPanel = createConfigPanel()
        mainPanel.add(configPanel, BorderLayout.NORTH)

        // Splitter for results and details
        val splitter = JBSplitter(true, 0.6f)

        // Results panel (table + progress)
        val resultsPanel = JPanel(BorderLayout())
        resultsPanel.add(createStatusPanel(), BorderLayout.NORTH)

        setupTable()
        resultsPanel.add(JBScrollPane(resultsTable), BorderLayout.CENTER)

        splitter.firstComponent = resultsPanel

        // Tabbed details panel
        val tabbedPane = JTabbedPane()
        tabbedPane.addTab("Details", ScrollPaneFactory.createScrollPane(detailsArea))
        tabbedPane.addTab("Output Log", ScrollPaneFactory.createScrollPane(outputArea))

        splitter.secondComponent = tabbedPane

        mainPanel.add(splitter, BorderLayout.CENTER)

        setContent(mainPanel)
    }

    private fun createToolbar(): ActionToolbar {
        val actionGroup = DefaultActionGroup().apply {
            add(RunAnalysisAction())
            add(StopAnalysisAction())
            addSeparator()
            add(ClearResultsAction())
        }

        return ActionManager.getInstance()
            .createActionToolbar("SzzLlmToolbar", actionGroup, true)
    }

    private fun createConfigPanel(): JPanel {
        val panel = JPanel(FlowLayout(FlowLayout.LEFT, 10, 5))
        panel.border = JBUI.Borders.empty(5, 10)

        panel.add(JBLabel("Branch:"))
        panel.add(branchField)

        panel.add(JBLabel("Limit:"))
        panel.add(limitSpinner)

        panel.add(skipLlmCheckbox)

        return panel
    }

    private fun createStatusPanel(): JPanel {
        val panel = JPanel(BorderLayout())
        panel.border = JBUI.Borders.empty(5, 10)

        statusLabel.font = statusLabel.font.deriveFont(Font.BOLD)
        panel.add(statusLabel, BorderLayout.WEST)

        progressBar.isStringPainted = true
        panel.add(progressBar, BorderLayout.CENTER)

        return panel
    }

    private fun setupTable() {
        resultsTable.apply {
            setShowGrid(true)
            gridColor = JBColor.border()
            rowHeight = 28
            tableHeader.reorderingAllowed = false

            // Column widths
            columnModel.getColumn(0).preferredWidth = 100  // Commit
            columnModel.getColumn(1).preferredWidth = 80   // Type
            columnModel.getColumn(2).preferredWidth = 400  // Message
            columnModel.getColumn(3).preferredWidth = 80   // BICs count

            // Type column renderer (colored)
            columnModel.getColumn(1).cellRenderer = object : DefaultTableCellRenderer() {
                override fun getTableCellRendererComponent(
                    table: JTable, value: Any?, isSelected: Boolean,
                    hasFocus: Boolean, row: Int, column: Int
                ): Component {
                    val comp = super.getTableCellRendererComponent(table, value, isSelected, hasFocus, row, column)
                    if (!isSelected) {
                        foreground = if (value == "BUG") JBColor.RED else JBColor.GRAY
                    }
                    return comp
                }
            }

            // Selection listener for details
            selectionModel.addListSelectionListener { e ->
                if (!e.valueIsAdjusting && selectedRow >= 0) {
                    showResultDetails(resultsModel.getResultAt(selectedRow))
                }
            }
        }
    }

    private fun setupListeners() {
        analyzerService.addListener(object : SzzAnalyzerService.AnalysisListener {
            override fun onProgressUpdate(progress: AnalysisProgress) {
                SwingUtilities.invokeLater {
                    updateProgress(progress)
                }
            }

            override fun onAnalysisComplete(report: AnalysisReport) {
                SwingUtilities.invokeLater {
                    resultsModel.setResults(report.results)
                    updateProgress(AnalysisProgress(
                        status = AnalysisStatus.COMPLETED,
                        message = "Completed: ${report.confirmedBugs} bugs in ${report.analyzedCommits} commits",
                        percentage = 100
                    ))

                    // Show summary in details
                    detailsArea.text = buildSummaryText(report)
                }
            }

            override fun onAnalysisError(error: String) {
                SwingUtilities.invokeLater {
                    statusLabel.text = "Error: $error"
                    statusLabel.foreground = JBColor.RED
                    progressBar.isVisible = false
                }
            }

            override fun onOutputLine(line: String) {
                SwingUtilities.invokeLater {
                    outputArea.append(line + "\n")
                    outputArea.caretPosition = outputArea.document.length
                }
            }
        })
    }

    private fun updateProgress(progress: AnalysisProgress) {
        when (progress.status) {
            AnalysisStatus.RUNNING -> {
                statusLabel.text = progress.message
                statusLabel.foreground = JBColor.foreground()
                progressBar.isVisible = true
                progressBar.value = progress.percentage
                progressBar.string = "${progress.percentage}%"
            }
            AnalysisStatus.COMPLETED -> {
                statusLabel.text = progress.message
                statusLabel.foreground = JBColor(Color(0, 128, 0), Color(100, 200, 100))
                progressBar.isVisible = false
            }
            AnalysisStatus.FAILED, AnalysisStatus.CANCELLED -> {
                statusLabel.text = progress.message
                statusLabel.foreground = JBColor.RED
                progressBar.isVisible = false
            }
            AnalysisStatus.IDLE -> {
                statusLabel.text = "Ready"
                statusLabel.foreground = JBColor.foreground()
                progressBar.isVisible = false
            }
        }
    }

    private fun showResultDetails(result: AnalysisResult) {
        val sb = StringBuilder()
        sb.appendLine("=".repeat(50))
        sb.appendLine("FIX COMMIT: ${result.fixCommit}")
        sb.appendLine("=".repeat(50))
        sb.appendLine()
        sb.appendLine("Type: ${if (result.isBug) "BUG FIX" else "REFACTORING"}")
        sb.appendLine()
        sb.appendLine("Commit Message:")
        sb.appendLine(result.commitMessage)
        sb.appendLine()

        if (result.isBug && result.bugInducingCommits.isNotEmpty()) {
            sb.appendLine("Bug-Inducing Commits (${result.bugInducingCommits.size}):")
            sb.appendLine("-".repeat(40))
            result.bugInducingCommits.forEach { bic ->
                sb.appendLine("  - $bic")
            }
        } else if (result.isBug) {
            sb.appendLine("No bug-inducing commits identified.")
        }

        detailsArea.text = sb.toString()
        detailsArea.caretPosition = 0
    }

    private fun buildSummaryText(report: AnalysisReport): String {
        return buildString {
            appendLine("=" .repeat(50))
            appendLine("SZZ-LLM ANALYSIS SUMMARY")
            appendLine("=".repeat(50))
            appendLine()
            appendLine("Repository: ${report.repository}")
            appendLine("Branch: ${report.branch}")
            appendLine()
            appendLine("Statistics:")
            appendLine("  - Total potential fixes: ${report.totalPotentialFixes}")
            appendLine("  - Commits analyzed: ${report.analyzedCommits}")
            appendLine("  - Confirmed bugs: ${report.confirmedBugs}")
            appendLine("  - Refactorings: ${report.analyzedCommits - report.confirmedBugs}")

            if (report.errors.isNotEmpty()) {
                appendLine()
                appendLine("Errors (${report.errors.size}):")
                report.errors.forEach { err ->
                    appendLine("  ! $err")
                }
            }

            appendLine()
            appendLine("Select a row in the table above to see details.")
        }
    }

    private fun runAnalysis() {
        val basePath = project.basePath
        if (basePath == null) {
            statusLabel.text = "Error: No project path"
            return
        }

        outputArea.text = "" // Clear log
        resultsModel.clear()
        detailsArea.text = ""

        val config = AnalysisConfig(
            repoPath = basePath,
            branch = branchField.text,
            limit = limitSpinner.value as Int,
            skipLlm = skipLlmCheckbox.isSelected
        )

        analyzerService.runAnalysis(config)
    }

    // Action classes
    private inner class RunAnalysisAction : AnAction(
        "Run Analysis",
        "Start SZZ-LLM analysis on current project",
        AllIcons.Actions.Execute
    ) {
        override fun actionPerformed(e: AnActionEvent) {
            runAnalysis()
        }

        override fun update(e: AnActionEvent) {
            e.presentation.isEnabled = !analyzerService.isRunning()
        }

        override fun getActionUpdateThread() = ActionUpdateThread.BGT
    }

    private inner class StopAnalysisAction : AnAction(
        "Stop Analysis",
        "Cancel running analysis",
        AllIcons.Actions.Suspend
    ) {
        override fun actionPerformed(e: AnActionEvent) {
            analyzerService.cancelAnalysis()
        }

        override fun update(e: AnActionEvent) {
            e.presentation.isEnabled = analyzerService.isRunning()
        }

        override fun getActionUpdateThread() = ActionUpdateThread.BGT
    }

    private inner class ClearResultsAction : AnAction(
        "Clear Results",
        "Clear analysis results",
        AllIcons.Actions.GC
    ) {
        override fun actionPerformed(e: AnActionEvent) {
            resultsModel.clear()
            detailsArea.text = ""
            outputArea.text = ""
            statusLabel.text = "Ready"
            statusLabel.foreground = JBColor.foreground()
        }

        override fun getActionUpdateThread() = ActionUpdateThread.BGT
    }
}

/**
 * Table model for analysis results
 */
class ResultsTableModel : AbstractTableModel() {
    private val columns = arrayOf("Commit", "Type", "Message", "BICs")
    private val results = mutableListOf<AnalysisResult>()

    override fun getRowCount() = results.size
    override fun getColumnCount() = columns.size
    override fun getColumnName(column: Int) = columns[column]

    override fun getValueAt(rowIndex: Int, columnIndex: Int): Any {
        val result = results[rowIndex]
        return when (columnIndex) {
            0 -> result.fixCommit.take(8)
            1 -> if (result.isBug) "BUG" else "REFACTOR"
            2 -> result.commitMessage.take(80)
            3 -> if (result.isBug) result.bugInducingCommits.size.toString() else "-"
            else -> ""
        }
    }

    fun setResults(newResults: List<AnalysisResult>) {
        results.clear()
        results.addAll(newResults)
        fireTableDataChanged()
    }

    fun getResultAt(index: Int): AnalysisResult = results[index]

    fun clear() {
        results.clear()
        fireTableDataChanged()
    }
}
