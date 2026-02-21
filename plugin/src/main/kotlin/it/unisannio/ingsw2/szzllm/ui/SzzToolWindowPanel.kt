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
import java.awt.event.MouseAdapter
import java.awt.event.MouseEvent
import java.io.BufferedReader
import java.io.InputStreamReader
import java.text.SimpleDateFormat
import java.util.*
import javax.swing.*
import javax.swing.table.AbstractTableModel
import javax.swing.table.DefaultTableCellRenderer

class SzzToolWindowPanel(private val project: Project) : SimpleToolWindowPanel(true, true) {

    private val analyzerService = SzzAnalyzerService.getInstance(project)

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

    private val sourceComboBox = JComboBox(arrayOf("Current Project", "Remote URL")).apply {
        preferredSize = Dimension(130, preferredSize.height)
    }
    private val urlField = JBTextField().apply {
        emptyText.text = "https://github.com/user/repo"
        preferredSize = Dimension(300, preferredSize.height)
        isEnabled = false
    }

    private val branchComboBox = JComboBox<String>().apply {
        isEditable = true
        preferredSize = Dimension(150, preferredSize.height)
        addItem("main")
        addItem("master")
    }
    private val refreshBranchButton = JButton(AllIcons.Actions.Refresh).apply {
        toolTipText = "Fetch branches"
        preferredSize = Dimension(28, 28)
    }

    private val strategyComboBox = JComboBox(SelectionStrategy.values()).apply {
        preferredSize = Dimension(150, preferredSize.height)
    }

    private val dateRangePanel = JPanel(FlowLayout(FlowLayout.LEFT, 5, 0))
    private val sinceField = JBTextField(10).apply { emptyText.text = "YYYY-MM-DD" }
    private val untilField = JBTextField(10).apply { emptyText.text = "YYYY-MM-DD" }

    private val selectionOptionsPanel = JPanel(CardLayout())
    private val limitSpinner = JSpinner(SpinnerNumberModel(10, 0, 10000, 1))
    private val skipLlmCheckbox = JCheckBox("Skip LLM")

    init {
        resultsTable = JBTable(resultsModel)
        setupUI()
        setupListeners()
    }

    private fun setupUI() {
        setToolbar(createToolbar().component)
        val mainPanel = JPanel(BorderLayout())
        mainPanel.add(createConfigPanel(), BorderLayout.NORTH)

        val splitter = JBSplitter(true, 0.6f)
        val resultsPanel = JPanel(BorderLayout())
        resultsPanel.add(createStatusPanel(), BorderLayout.NORTH)
        setupTable()
        resultsPanel.add(JBScrollPane(resultsTable), BorderLayout.CENTER)
        splitter.firstComponent = resultsPanel

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
        return ActionManager.getInstance().createActionToolbar("SzzLlmToolbar", actionGroup, true)
    }

    private fun createConfigPanel(): JPanel {
        val panel = JPanel()
        panel.layout = BoxLayout(panel, BoxLayout.Y_AXIS)
        panel.border = JBUI.Borders.empty(5, 10)

        // Row 1: Repository
        val sourcePanel = JPanel(FlowLayout(FlowLayout.LEFT, 10, 5))
        sourcePanel.add(JBLabel("Repository:"))
        sourcePanel.add(sourceComboBox)
        sourcePanel.add(urlField)
        sourceComboBox.addActionListener {
            urlField.isEnabled = sourceComboBox.selectedIndex == 1
            if (!urlField.isEnabled) urlField.text = ""
        }
        panel.add(sourcePanel)

        // Row 2: Branch
        val branchPanel = JPanel(FlowLayout(FlowLayout.LEFT, 10, 5))
        branchPanel.add(JBLabel("Branch:"))
        branchPanel.add(branchComboBox)
        branchPanel.add(refreshBranchButton)
        refreshBranchButton.addActionListener { fetchBranches() }
        panel.add(branchPanel)

        // Row 3: Selection strategy
        val strategyPanel = JPanel(FlowLayout(FlowLayout.LEFT, 10, 5))
        strategyPanel.add(JBLabel("Selection:"))
        strategyPanel.add(strategyComboBox)

        dateRangePanel.add(JBLabel("From:"))
        dateRangePanel.add(sinceField)
        dateRangePanel.add(JBLabel("To:"))
        dateRangePanel.add(untilField)
        dateRangePanel.add(JButton("Today").apply {
            preferredSize = Dimension(70, preferredSize.height)
            addActionListener { untilField.text = SimpleDateFormat("yyyy-MM-dd").format(Date()) }
        })

        val emptyPanel = JPanel(FlowLayout(FlowLayout.LEFT, 5, 0))
        emptyPanel.add(JBLabel("(Analyze recent commits)"))

        selectionOptionsPanel.add(emptyPanel, SelectionStrategy.ALL.name)
        selectionOptionsPanel.add(dateRangePanel, SelectionStrategy.DATE_RANGE.name)
        strategyPanel.add(selectionOptionsPanel)

        strategyComboBox.addActionListener {
            val selected = strategyComboBox.selectedItem as SelectionStrategy
            (selectionOptionsPanel.layout as CardLayout).show(selectionOptionsPanel, selected.name)
        }
        panel.add(strategyPanel)

        // Row 4: Options
        val optionsPanel = JPanel(FlowLayout(FlowLayout.LEFT, 10, 5))
        optionsPanel.add(JBLabel("Limit:"))
        optionsPanel.add(limitSpinner)
        optionsPanel.add(JBLabel("(0=all)"))
        optionsPanel.add(Box.createHorizontalStrut(20))
        optionsPanel.add(skipLlmCheckbox)
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
        refreshBranchButton.isEnabled = false
        statusLabel.text = "Fetching branches..."
        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                val branches = if (sourceComboBox.selectedIndex == 1) {
                    fetchRemoteBranches(urlField.text.trim())
                } else {
                    fetchLocalBranches(project.basePath ?: "")
                }
                SwingUtilities.invokeLater {
                    branchComboBox.removeAllItems()
                    branches.forEach { branchComboBox.addItem(it) }
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
        val process = ProcessBuilder("git", "-C", repoPath, "branch", "-a").redirectErrorStream(true).start()
        val branches = mutableListOf<String>()
        BufferedReader(InputStreamReader(process.inputStream)).use { reader ->
            reader.lineSequence().forEach { line ->
                var branch = line.trim().removePrefix("* ").removePrefix("remotes/origin/").trim()
                if (!branch.contains("HEAD") && branch.isNotEmpty()) {
                    if (branch.contains("/")) branch = branch.substringAfterLast("/")
                    if (branch !in branches) branches.add(branch)
                }
            }
        }
        process.waitFor()
        return branches.sorted()
    }

    private fun fetchRemoteBranches(url: String): List<String> {
        val process = ProcessBuilder("git", "ls-remote", "--heads", url).redirectErrorStream(true).start()
        val branches = mutableListOf<String>()
        BufferedReader(InputStreamReader(process.inputStream)).use { reader ->
            reader.lineSequence().forEach { line ->
                if (line.contains("refs/heads/")) {
                    branches.add(line.substringAfter("refs/heads/").trim())
                }
            }
        }
        process.waitFor()
        return branches.sorted()
    }

    private fun setupTable() {
        resultsTable.apply {
            setShowGrid(true)
            gridColor = JBColor.border()
            rowHeight = 28
            columnModel.getColumn(0).preferredWidth = 100
            columnModel.getColumn(1).preferredWidth = 80
            columnModel.getColumn(2).preferredWidth = 400
            columnModel.getColumn(3).preferredWidth = 80

            // Renderer per colonna Type (colorata)
            columnModel.getColumn(1).cellRenderer = object : DefaultTableCellRenderer() {
                override fun getTableCellRendererComponent(table: JTable, value: Any?, isSelected: Boolean, hasFocus: Boolean, row: Int, column: Int): Component {
                    val comp = super.getTableCellRendererComponent(table, value, isSelected, hasFocus, row, column)
                    if (!isSelected) foreground = when (value) { "BUG" -> JBColor.RED; "SKIPPED" -> JBColor.ORANGE; else -> JBColor.GRAY }
                    return comp
                }
            }

            // Renderer per colonna BICs (cliccabile, stile link)
            columnModel.getColumn(3).cellRenderer = object : DefaultTableCellRenderer() {
                override fun getTableCellRendererComponent(table: JTable, value: Any?, isSelected: Boolean, hasFocus: Boolean, row: Int, column: Int): Component {
                    val comp = super.getTableCellRendererComponent(table, value, isSelected, hasFocus, row, column)
                    val strValue = value?.toString() ?: "-"
                    if (strValue != "-" && strValue != "0") {
                        text = "<html><u>$strValue</u></html>"
                        foreground = if (isSelected) table.selectionForeground else JBColor.BLUE
                        cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)
                    } else {
                        foreground = if (isSelected) table.selectionForeground else JBColor.GRAY
                    }
                    horizontalAlignment = CENTER
                    return comp
                }
            }

            // Mouse listener per click su colonna BICs
            addMouseListener(object : MouseAdapter() {
                override fun mouseClicked(e: MouseEvent) {
                    val row = rowAtPoint(e.point)
                    val col = columnAtPoint(e.point)
                    if (row >= 0 && col == 3) { // Colonna BICs
                        val result = resultsModel.getResultAt(row)
                        if (result.isBug && result.bugInducingCommits.isNotEmpty()) {
                            showBicPopup(e, result.bugInducingCommits)
                        }
                    }
                }
            })

            selectionModel.addListSelectionListener { e ->
                if (!e.valueIsAdjusting && selectedRow >= 0) showResultDetails(resultsModel.getResultAt(selectedRow))
            }
        }
    }

    private fun showBicPopup(e: MouseEvent, bics: List<String>) {
        val popup = JPopupMenu()

        // Header
        val headerItem = JMenuItem("Bug-Inducing Commits (${bics.size})")
        headerItem.isEnabled = false
        headerItem.font = headerItem.font.deriveFont(Font.BOLD)
        popup.add(headerItem)
        popup.addSeparator()

        // Lista BICs (max 15 visibili nel popup)
        bics.take(15).forEach { bic ->
            val shortHash = bic.take(8)
            val fullHash = bic.take(40)
            val item = JMenuItem(shortHash)
            item.toolTipText = "Click to copy: $fullHash"
            item.addActionListener {
                // Copia l'hash negli appunti
                val clipboard = Toolkit.getDefaultToolkit().systemClipboard
                clipboard.setContents(java.awt.datatransfer.StringSelection(fullHash), null)
                statusLabel.text = "Copied: $shortHash"
                statusLabel.foreground = JBColor(Color(0, 128, 0), Color(100, 200, 100))
            }
            popup.add(item)
        }

        if (bics.size > 15) {
            popup.addSeparator()
            val moreItem = JMenuItem("... and ${bics.size - 15} more (see Details)")
            moreItem.isEnabled = false
            popup.add(moreItem)
        }

        popup.show(e.component, e.x, e.y)
    }

    private fun setupListeners() {
        analyzerService.addListener(object : SzzAnalyzerService.AnalysisListener {
            override fun onProgressUpdate(progress: AnalysisProgress) {
                SwingUtilities.invokeLater { updateProgress(progress) }
            }
            override fun onAnalysisComplete(report: AnalysisReport) {
                SwingUtilities.invokeLater {
                    resultsModel.setResults(report.results)
                    updateProgress(AnalysisProgress(AnalysisStatus.COMPLETED, "Completed: ${report.confirmedBugs} bugs in ${report.analyzedCommits} commits", percentage = 100))
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
            }
            AnalysisStatus.COMPLETED -> {
                statusLabel.text = progress.message
                statusLabel.foreground = JBColor(Color(0, 128, 0), Color(100, 200, 100))
                progressBar.isVisible = false
            }
            else -> {
                statusLabel.text = progress.message
                statusLabel.foreground = JBColor.RED
                progressBar.isVisible = false
            }
        }
    }

    private fun showResultDetails(result: AnalysisResult) {
        detailsArea.text = buildString {
            appendLine("=".repeat(50))
            appendLine("FIX COMMIT: ${result.fixCommit}")
            appendLine("=".repeat(50))
            appendLine("\nType: ${if (result.skippedReason != null) "SKIPPED (${result.skippedReason})" else if (result.isBug) "BUG FIX" else "REFACTORING"}")

            // Mostra la spiegazione LLM se disponibile
            if (!result.llmExplanation.isNullOrBlank()) {
                appendLine("\nLLM Explanation:")
                appendLine("  ${result.llmExplanation}")
            }

            appendLine("\nCommit Message:")
            appendLine("  ${result.commitMessage}")

            if (result.isBug && result.bugInducingCommits.isNotEmpty()) {
                appendLine("\nBug-Inducing Commits (${result.bugInducingCommits.size}):")
                appendLine("-".repeat(40))
                result.bugInducingCommits.forEachIndexed { index, bic ->
                    appendLine("  ${index + 1}. $bic")
                }
            }
        }
        detailsArea.caretPosition = 0
    }

    private fun buildSummaryText(report: AnalysisReport) = buildString {
        appendLine("=".repeat(50))
        appendLine("SZZ-LLM ANALYSIS SUMMARY")
        appendLine("=".repeat(50))
        appendLine("\nRepository: ${report.repository}")
        appendLine("Branch: ${report.branch}")
        appendLine("Selection: ${report.selectionStrategy}")
        appendLine("\nStatistics:")
        appendLine("  - Total potential fixes: ${report.totalPotentialFixes}")
        appendLine("  - Commits analyzed: ${report.analyzedCommits}")
        appendLine("  - Confirmed bugs: ${report.confirmedBugs}")
    }

    private fun runAnalysis() {
        val isRemote = sourceComboBox.selectedIndex == 1
        val repoPath = if (isRemote) "" else (project.basePath ?: "")
        val repoUrl = if (isRemote) urlField.text.trim() else null

        if (isRemote && repoUrl.isNullOrEmpty()) {
            statusLabel.text = "Error: Enter repository URL"
            statusLabel.foreground = JBColor.RED
            return
        }

        val strategy = strategyComboBox.selectedItem as SelectionStrategy
        var since: String? = null
        var until: String? = null

        when (strategy) {
            SelectionStrategy.DATE_RANGE -> {
                since = sinceField.text.trim().takeIf { it.isNotEmpty() }
                until = untilField.text.trim().takeIf { it.isNotEmpty() }
                if (since == null && until == null) {
                    statusLabel.text = "Error: Enter at least one date"
                    statusLabel.foreground = JBColor.RED
                    return
                }
            }
            SelectionStrategy.ALL -> {}
        }

        outputArea.text = ""
        resultsModel.clear()
        detailsArea.text = ""

        analyzerService.runAnalysis(AnalysisConfig(
            repoPath = repoPath,
            repoUrl = repoUrl,
            branch = branchComboBox.selectedItem?.toString() ?: "main",
            limit = limitSpinner.value as Int,
            skipLlm = skipLlmCheckbox.isSelected,
            selectionStrategy = strategy,
            since = since,
            until = until
        ))
    }

    private inner class RunAnalysisAction : AnAction("Run", "Start analysis", AllIcons.Actions.Execute) {
        override fun actionPerformed(e: AnActionEvent) = runAnalysis()
        override fun update(e: AnActionEvent) { e.presentation.isEnabled = !analyzerService.isRunning() }
        override fun getActionUpdateThread() = ActionUpdateThread.BGT
    }

    private inner class StopAnalysisAction : AnAction("Stop", "Cancel", AllIcons.Actions.Suspend) {
        override fun actionPerformed(e: AnActionEvent) = analyzerService.cancelAnalysis()
        override fun update(e: AnActionEvent) { e.presentation.isEnabled = analyzerService.isRunning() }
        override fun getActionUpdateThread() = ActionUpdateThread.BGT
    }

    private inner class ClearResultsAction : AnAction("Clear", "Clear results", AllIcons.Actions.GC) {
        override fun actionPerformed(e: AnActionEvent) {
            resultsModel.clear()
            detailsArea.text = ""
            outputArea.text = ""
            statusLabel.text = "Ready"
        }
        override fun getActionUpdateThread() = ActionUpdateThread.BGT
    }
}

class ResultsTableModel : AbstractTableModel() {
    private val columns = arrayOf("Commit", "Type", "Message", "BICs")
    private val results = mutableListOf<AnalysisResult>()
    override fun getRowCount() = results.size
    override fun getColumnCount() = columns.size
    override fun getColumnName(column: Int) = columns[column]
    override fun getValueAt(row: Int, col: Int): Any = when (col) {
        0 -> results[row].fixCommit.take(8)
        1 -> if (results[row].skippedReason != null) "SKIPPED" else if (results[row].isBug) "BUG" else "REFACTOR"
        2 -> results[row].commitMessage.take(80)
        3 -> if (results[row].isBug) results[row].bugInducingCommits.size.toString() else "-"
        else -> ""
    }
    fun setResults(newResults: List<AnalysisResult>) { results.clear(); results.addAll(newResults); fireTableDataChanged() }
    fun getResultAt(index: Int) = results[index]
    fun clear() { results.clear(); fireTableDataChanged() }
}