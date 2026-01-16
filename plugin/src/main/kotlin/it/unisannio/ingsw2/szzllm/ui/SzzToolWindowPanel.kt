package it.unisannio.ingsw2.szzllm.ui

import com.intellij.icons.AllIcons
import com.intellij.openapi.actionSystem.*
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.SimpleToolWindowPanel
import com.intellij.ui.JBColor
import com.intellij.ui.JBSplitter
import com.intellij.ui.ScrollPaneFactory
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.components.JBTextArea
import com.intellij.ui.components.JBTextField
import com.intellij.ui.table.JBTable
import com.intellij.util.ui.JBUI
import it.unisannio.ingsw2.szzllm.model.*
import it.unisannio.ingsw2.szzllm.services.SzzAnalyzerService
import java.awt.*
import java.io.BufferedReader
import java.io.InputStreamReader
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

    // Repository source selection
    private val sourceComboBox = JComboBox(arrayOf("Current Project", "Remote URL")).apply {
        preferredSize = Dimension(130, preferredSize.height)
    }
    private val urlField = JBTextField().apply {
        emptyText.text = "https://github.com/user/repo"
        preferredSize = Dimension(300, preferredSize.height)
        isEnabled = false
    }

    // Branch selection with refresh
    private val branchComboBox = JComboBox<String>().apply {
        isEditable = true  // Allow manual input if needed
        preferredSize = Dimension(150, preferredSize.height)
        addItem("main")
        addItem("master")
    }
    private val refreshBranchButton = JButton(AllIcons.Actions.Refresh).apply {
        toolTipText = "Fetch branches from repository"
        preferredSize = Dimension(28, 28)
        isFocusable = false
    }

    // Config components
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
        val panel = JPanel()
        panel.layout = BoxLayout(panel, BoxLayout.Y_AXIS)
        panel.border = JBUI.Borders.empty(5, 10)

        // Row 1: Repository source selection
        val sourcePanel = JPanel(FlowLayout(FlowLayout.LEFT, 10, 5))
        sourcePanel.add(JBLabel("Repository:"))
        sourcePanel.add(sourceComboBox)
        sourcePanel.add(urlField)

        // Enable/disable URL field based on selection
        sourceComboBox.addActionListener {
            val isRemote = sourceComboBox.selectedIndex == 1
            urlField.isEnabled = isRemote
            if (!isRemote) {
                urlField.text = ""
            }
        }

        panel.add(sourcePanel)

        // Row 2: Branch and analysis options
        val optionsPanel = JPanel(FlowLayout(FlowLayout.LEFT, 10, 5))
        optionsPanel.add(JBLabel("Branch:"))
        optionsPanel.add(branchComboBox)
        optionsPanel.add(refreshBranchButton)
        optionsPanel.add(Box.createHorizontalStrut(10))
        optionsPanel.add(JBLabel("Limit:"))
        optionsPanel.add(limitSpinner)
        optionsPanel.add(skipLlmCheckbox)

        // Refresh button action
        refreshBranchButton.addActionListener {
            fetchBranches()
        }

        panel.add(optionsPanel)

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

    private fun fetchBranches() {
        val isRemote = sourceComboBox.selectedIndex == 1

        // Disable button during fetch
        refreshBranchButton.isEnabled = false
        statusLabel.text = "Fetching branches..."
        statusLabel.foreground = JBColor.foreground()

        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                val branches = if (isRemote) {
                    val url = urlField.text.trim()
                    if (url.isEmpty()) {
                        throw IllegalArgumentException("Please enter a repository URL first")
                    }
                    fetchRemoteBranches(url)
                } else {
                    val basePath = project.basePath
                        ?: throw IllegalArgumentException("No project path")
                    fetchLocalBranches(basePath)
                }

                SwingUtilities.invokeLater {
                    branchComboBox.removeAllItems()
                    branches.forEach { branchComboBox.addItem(it) }

                    // Select main or master if available
                    val defaultBranch = branches.find { it == "main" || it == "master" }
                    if (defaultBranch != null) {
                        branchComboBox.selectedItem = defaultBranch
                    } else if (branches.isNotEmpty()) {
                        branchComboBox.selectedIndex = 0
                    }

                    statusLabel.text = "Found ${branches.size} branches"
                    statusLabel.foreground = JBColor(Color(0, 128, 0), Color(100, 200, 100))
                    refreshBranchButton.isEnabled = true
                }
            } catch (e: Exception) {
                SwingUtilities.invokeLater {
                    statusLabel.text = "Error: ${e.message}"
                    statusLabel.foreground = JBColor.RED
                    refreshBranchButton.isEnabled = true
                }
            }
        }
    }

    private fun fetchLocalBranches(repoPath: String): List<String> {
        val process = ProcessBuilder("git", "-C", repoPath, "branch", "-a")
            .redirectErrorStream(true)
            .start()

        val branches = mutableListOf<String>()
        BufferedReader(InputStreamReader(process.inputStream)).use { reader ->
            reader.lineSequence().forEach { line ->
                // Parse branch names, remove markers like * and remotes/origin/
                var branch = line.trim()
                    .removePrefix("* ")
                    .removePrefix("remotes/origin/")
                    .trim()

                // Skip HEAD references
                if (!branch.contains("HEAD") && branch.isNotEmpty()) {
                    // Normalize: take only the branch name
                    if (branch.contains("/")) {
                        branch = branch.substringAfterLast("/")
                    }
                    if (branch !in branches) {
                        branches.add(branch)
                    }
                }
            }
        }

        process.waitFor()
        return branches.sorted()
    }

    private fun fetchRemoteBranches(url: String): List<String> {
        val process = ProcessBuilder("git", "ls-remote", "--heads", url)
            .redirectErrorStream(true)
            .start()

        val branches = mutableListOf<String>()
        BufferedReader(InputStreamReader(process.inputStream)).use { reader ->
            reader.lineSequence().forEach { line ->
                // Format: <hash>\trefs/heads/<branch>
                if (line.contains("refs/heads/")) {
                    val branch = line.substringAfter("refs/heads/").trim()
                    if (branch.isNotEmpty()) {
                        branches.add(branch)
                    }
                }
            }
        }

        val exitCode = process.waitFor()
        if (exitCode != 0 || branches.isEmpty()) {
            throw RuntimeException("Failed to fetch branches. Check URL and network connection.")
        }

        return branches.sorted()
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
            appendLine("=".repeat(50))
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
        val isRemote = sourceComboBox.selectedIndex == 1

        val repoPath: String
        val repoUrl: String?

        if (isRemote) {
            // Remote URL mode
            val url = urlField.text.trim()
            if (url.isEmpty()) {
                statusLabel.text = "Error: Please enter a repository URL"
                statusLabel.foreground = JBColor.RED
                return
            }
            if (!url.startsWith("http://") && !url.startsWith("https://") && !url.startsWith("git@")) {
                statusLabel.text = "Error: Invalid URL format"
                statusLabel.foreground = JBColor.RED
                return
            }
            repoPath = ""
            repoUrl = url
        } else {
            // Current project mode
            val basePath = project.basePath
            if (basePath == null) {
                statusLabel.text = "Error: No project path"
                statusLabel.foreground = JBColor.RED
                return
            }

            // Check if .git exists
            val gitDir = java.io.File(basePath, ".git")
            if (!gitDir.exists()) {
                statusLabel.text = "Error: Current project is not a Git repository"
                statusLabel.foreground = JBColor.RED
                return
            }

            repoPath = basePath
            repoUrl = null
        }

        // Get selected branch
        val selectedBranch = branchComboBox.selectedItem?.toString()?.trim() ?: "main"
        if (selectedBranch.isEmpty()) {
            statusLabel.text = "Error: Please select a branch"
            statusLabel.foreground = JBColor.RED
            return
        }

        outputArea.text = "" // Clear log
        resultsModel.clear()
        detailsArea.text = ""

        val config = AnalysisConfig(
            repoPath = repoPath,
            repoUrl = repoUrl,
            branch = selectedBranch,
            limit = limitSpinner.value as Int,
            skipLlm = skipLlmCheckbox.isSelected
        )

        analyzerService.runAnalysis(config)
    }

    // Action classes
    private inner class RunAnalysisAction : AnAction(
        "Run Analysis",
        "Start SZZ-LLM analysis",
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