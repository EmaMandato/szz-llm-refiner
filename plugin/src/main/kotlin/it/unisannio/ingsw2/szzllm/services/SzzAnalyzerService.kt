package it.unisannio.ingsw2.szzllm.services

import com.google.gson.Gson
import com.google.gson.JsonSyntaxException
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.execution.process.*
import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationType
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.util.Key
import it.unisannio.ingsw2.szzllm.model.*
import it.unisannio.ingsw2.szzllm.settings.SzzSettings
import java.io.File
import java.nio.charset.StandardCharsets
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/**
 * Service responsible for executing the SZZ-LLM Python engine.
 * Manages process lifecycle, output parsing, and progress reporting.
 */
@Service(Service.Level.PROJECT)
class SzzAnalyzerService(private val project: Project) {

    private val log = Logger.getInstance(SzzAnalyzerService::class.java)
    private val gson = Gson()

    private val isRunning = AtomicBoolean(false)
    private val currentProcess = AtomicReference<OSProcessHandler?>(null)
    private val currentReport = AtomicReference<AnalysisReport?>(null)
    private val analysisListeners = mutableListOf<AnalysisListener>()

    companion object {
        fun getInstance(project: Project): SzzAnalyzerService {
            return project.getService(SzzAnalyzerService::class.java)
        }
    }

    /**
     * Listener interface for analysis events
     */
    interface AnalysisListener {
        fun onProgressUpdate(progress: AnalysisProgress)
        fun onAnalysisComplete(report: AnalysisReport)
        fun onAnalysisError(error: String)
        fun onOutputLine(line: String)
    }

    fun addListener(listener: AnalysisListener) {
        analysisListeners.add(listener)
    }

    fun removeListener(listener: AnalysisListener) {
        analysisListeners.remove(listener)
    }

    fun isRunning(): Boolean = isRunning.get()

    fun getLastReport(): AnalysisReport? = currentReport.get()

    /**
     * Fetches available tags from a repository.
     * Can be used for both local and remote repositories.
     */
    fun fetchTags(
        repoPath: String?,
        repoUrl: String?,
        onSuccess: (List<TagInfo>) -> Unit,
        onError: (String) -> Unit
    ) {
        val settings = SzzSettings.getInstance()
        val pythonPath = settings.pythonPath.ifEmpty { "python" }

        val commandLine = GeneralCommandLine().apply {
            exePath = pythonPath
            addParameter("-u")
            addParameter("-m")
            addParameter("szz_llm_project.main")

            if (!repoUrl.isNullOrBlank()) {
                addParameter("--url")
                addParameter(repoUrl)
            } else if (!repoPath.isNullOrBlank()) {
                addParameter(repoPath)
            }

            addParameter("--list-tags")
            addParameter("--output")
            addParameter("json")

            charset = StandardCharsets.UTF_8
        }

        log.info("Fetching tags: ${commandLine.commandLineString}")

        Thread {
            try {
                val process = commandLine.createProcess()
                val output = process.inputStream.bufferedReader().readText()
                val exitCode = process.waitFor()

                if (exitCode == 0) {
                    try {
                        val response = gson.fromJson(output, TagsResponse::class.java)
                        onSuccess(response.tags)
                    } catch (e: Exception) {
                        log.error("Failed to parse tags response", e)
                        onError("Failed to parse tags: ${e.message}")
                    }
                } else {
                    val error = process.errorStream.bufferedReader().readText()
                    onError("Failed to fetch tags: $error")
                }
            } catch (e: Exception) {
                log.error("Error fetching tags", e)
                onError("Error: ${e.message}")
            }
        }.start()
    }

    /**
     * Runs the SZZ-LLM analysis on the specified repository.
     */
    fun runAnalysis(config: AnalysisConfig) {
        if (isRunning.getAndSet(true)) {
            notifyError("Analysis already in progress")
            return
        }

        ProgressManager.getInstance().run(object : Task.Backgroundable(
            project,
            "SZZ-LLM Analysis",
            true
        ) {
            override fun run(indicator: ProgressIndicator) {
                indicator.isIndeterminate = false
                indicator.text = "Starting SZZ-LLM analysis..."

                notifyProgress(AnalysisProgress(
                    status = AnalysisStatus.RUNNING,
                    message = "Initializing analysis..."
                ))

                try {
                    executeAnalysis(config, indicator)
                } catch (e: Exception) {
                    log.error("Analysis failed", e)
                    notifyError("Analysis failed: ${e.message}")
                } finally {
                    isRunning.set(false)
                    currentProcess.set(null)
                }
            }

            override fun onCancel() {
                cancelAnalysis()
            }
        })
    }

    /**
     * Cancels the running analysis
     */
    fun cancelAnalysis() {
        currentProcess.get()?.let { handler ->
            if (!handler.isProcessTerminated) {
                handler.destroyProcess()
                notifyProgress(AnalysisProgress(
                    status = AnalysisStatus.CANCELLED,
                    message = "Analysis cancelled by user"
                ))
            }
        }
        isRunning.set(false)
    }

    private fun executeAnalysis(config: AnalysisConfig, indicator: ProgressIndicator) {
        val settings = SzzSettings.getInstance()
        val pythonPath = settings.pythonPath.ifEmpty { "python" }

        // Build command line
        val commandLine = GeneralCommandLine().apply {
            exePath = pythonPath
            addParameter("-u")
            addParameter("-m")
            addParameter("szz_llm_project.main")

            // Use URL or local path
            if (!config.repoUrl.isNullOrBlank()) {
                addParameter("--url")
                addParameter(config.repoUrl)
            } else {
                addParameter(config.repoPath)
            }

            addParameter("--branch")
            addParameter(config.branch)
            addParameter("--limit")
            addParameter(config.limit.toString())
            addParameter("--output")
            addParameter("json")

            // Selection strategy parameters
            when (config.selectionStrategy) {
                SelectionStrategy.DATE_RANGE -> {
                    config.since?.let {
                        addParameter("--since")
                        addParameter(it)
                    }
                    config.until?.let {
                        addParameter("--until")
                        addParameter(it)
                    }
                }
                SelectionStrategy.TAG_RANGE -> {
                    config.fromTag?.let {
                        addParameter("--from-tag")
                        addParameter(it)
                    }
                    config.toTag?.let {
                        addParameter("--to-tag")
                        addParameter(it)
                    }
                }
                SelectionStrategy.ALL -> {
                    // No additional parameters needed
                }
            }

            if (config.skipLlm || settings.skipLlmByDefault) {
                addParameter("--skip-llm")
            } else {
                addParameter("--model")
                addParameter(settings.ollamaModel.ifEmpty { config.model })
            }

            charset = StandardCharsets.UTF_8

            // Set work directory only for local repos
            if (config.repoUrl.isNullOrBlank() && config.repoPath.isNotBlank()) {
                workDirectory = File(config.repoPath)
            }
        }

        val targetDescription = if (!config.repoUrl.isNullOrBlank()) {
            config.repoUrl
        } else {
            config.repoPath
        }

        // Log selection strategy
        val strategyInfo = when (config.selectionStrategy) {
            SelectionStrategy.DATE_RANGE -> "Date range: ${config.since ?: "start"} to ${config.until ?: "now"}"
            SelectionStrategy.TAG_RANGE -> "Tag range: ${config.fromTag} to ${config.toTag}"
            SelectionStrategy.ALL -> "All commits"
        }

        log.info("Executing: ${commandLine.commandLineString}")
        log.info("Selection strategy: $strategyInfo")
        indicator.text = "Running analysis on $targetDescription ($strategyInfo)..."

        val outputBuffer = StringBuilder()
        val errorBuffer = StringBuilder()
        var lastProgressMessage = ""

        val processHandler = OSProcessHandler(commandLine)
        currentProcess.set(processHandler)

        // Variabili locali per evitare spam di aggiornamenti identici
        var lastPercentage = -1

        processHandler.addProcessListener(object : ProcessListener {
            override fun onTextAvailable(event: ProcessEvent, outputType: Key<*>) {
                val text = event.text.trim()
                if (text.isEmpty()) return

                // Funzione helper locale
                fun tryUpdateProgress(line: String) {
                    // 1. Invia sempre la riga raw al log (per il tab Output Log)
                    analysisListeners.forEach { it.onOutputLine(line) }

                    // 2. Parsa la riga per cercare info di progresso (es. [1/10])
                    parseProgressFromOutput(line)?.let { progress ->

                        // Aggiorna solo se c'è una novità vera (messaggio o percentuale diversi)
                        if (progress.message != lastProgressMessage || progress.percentage != lastPercentage) {
                            lastProgressMessage = progress.message
                            lastPercentage = progress.percentage

                            // Aggiorna l'indicatore della task in background di IntelliJ
                            indicator.text = progress.message
                            indicator.fraction = progress.percentage / 100.0

                            // Notifica la UI (che aggiornerà la sua progressBar)
                            notifyProgress(progress)
                        }
                    }
                }

                when (outputType) {
                    ProcessOutputTypes.STDOUT -> {
                        outputBuffer.append(event.text)
                        // ORA ascoltiamo anche STDOUT per il progresso!
                        tryUpdateProgress(text)
                    }
                    ProcessOutputTypes.STDERR -> {
                        errorBuffer.append(event.text)
                        // Ascoltiamo anche STDERR
                        tryUpdateProgress(text)
                    }
                }
            }

            override fun processTerminated(event: ProcessEvent) {
                val exitCode = event.exitCode
                log.info("SZZ process terminated with exit code: $exitCode")

                if (indicator.isCanceled) return

                if (exitCode == 0) {
                    parseResult(outputBuffer.toString())
                } else {
                    val errorMsg = if (errorBuffer.isNotEmpty()) errorBuffer.toString() else "Process exited with code $exitCode"
                    notifyError(errorMsg)
                }
            }

            override fun startNotified(event: ProcessEvent) {
                log.info("SZZ process started")
            }
        })

        processHandler.startNotify()
        processHandler.waitFor()
    }

    private fun parseProgressFromOutput(line: String): AnalysisProgress? {
        // Parse progress messages like "[1/10] Analyzing abc123..."
        val commitPattern = Regex("""\[(\d+)/(\d+)\] Analyzing ([a-f0-9]+)""")
        commitPattern.find(line)?.let { match ->
            val current = match.groupValues[1].toInt()
            val total = match.groupValues[2].toInt()
            val hash = match.groupValues[3]
            return AnalysisProgress(
                status = AnalysisStatus.RUNNING,
                message = "Analyzing commit $hash...",
                currentCommit = current,
                totalCommits = total,
                percentage = (current * 100) / total
            )
        }

        // Parse other status messages
        return when {
            line.contains("Cloning") -> AnalysisProgress(
                status = AnalysisStatus.RUNNING,
                message = "Cloning repository...",
                percentage = 5
            )
            line.contains("Scanning repository") -> AnalysisProgress(
                status = AnalysisStatus.RUNNING,
                message = "Scanning for fix commits...",
                percentage = 10
            )
            line.contains("Selection strategy") -> {
                AnalysisProgress(
                    status = AnalysisStatus.RUNNING,
                    message = line.substringAfter("Selection strategy:").trim(),
                    percentage = 8
                )
            }
            line.contains("Found") && line.contains("potential fix commits") -> {
                val countMatch = Regex("""Found (\d+) potential""").find(line)
                val count = countMatch?.groupValues?.get(1) ?: "?"
                AnalysisProgress(
                    status = AnalysisStatus.RUNNING,
                    message = "Found $count potential fix commits",
                    percentage = 15
                )
            }
            line.contains("LLM verdict") || line.contains("LLM:") -> {
                val verdict = if (line.contains("BUG")) "BUG" else "REFACTORING"
                AnalysisProgress(
                    status = AnalysisStatus.RUNNING,
                    message = "LLM verdict: $verdict"
                )
            }
            line.contains("SKIP") -> {
                AnalysisProgress(
                    status = AnalysisStatus.RUNNING,
                    message = "Skipped (filtered)"
                )
            }
            else -> null
        }
    }

    private fun parseResult(output: String) {
        try {
            // 1. Trova l'inizio e la fine esatta del JSON per evitare testo sporco in coda
            val jsonStart = output.indexOf("{")
            val jsonEnd = output.lastIndexOf("}")

            if (jsonStart == -1 || jsonEnd == -1 || jsonEnd < jsonStart) {
                notifyError("No valid JSON output found from analysis")
                // Utile per il debug: stampa cosa ha ricevuto davvero
                log.warn("Received invalid output: $output")
                return
            }

            // Estrae SOLO il blocco JSON, ignorando tutto ciò che c'è prima o dopo
            val jsonContent = output.substring(jsonStart, jsonEnd + 1)

            // 2. Usa JsonReader con lenient = true per evitare MalformedJsonException
            val reader = com.google.gson.stream.JsonReader(java.io.StringReader(jsonContent))
            reader.isLenient = true

            // Parsing: prova prima a leggere come Report
            try {
                val report = gson.fromJson<AnalysisReport>(reader, AnalysisReport::class.java)

                // Controllo di sicurezza: se il report è vuoto o nullo
                if (report == null) {
                    throw Exception("Parsed report is null")
                }

                currentReport.set(report)

                notifyProgress(AnalysisProgress(
                    status = AnalysisStatus.COMPLETED,
                    message = "Analysis completed: ${report.confirmedBugs} bugs found in ${report.analyzedCommits} commits",
                    percentage = 100
                ))

                analysisListeners.forEach { it.onAnalysisComplete(report) }

                NotificationGroupManager.getInstance()
                    .getNotificationGroup("SZZ-LLM Notifications")
                    .createNotification(
                        "SZZ-LLM Analysis Complete",
                        "Found ${report.confirmedBugs} confirmed bugs in ${report.analyzedCommits} commits analyzed",
                        NotificationType.INFORMATION
                    )
                    .notify(project)

            } catch (e: Exception) {
                // Se fallisce come Report, proviamo a vedere se era un oggetto Errore
                // Ricreiamo il reader perché il precedente è stato consumato
                val errorReader = com.google.gson.stream.JsonReader(java.io.StringReader(jsonContent))
                errorReader.isLenient = true

                try {
                    val errorObj = gson.fromJson<AnalysisError>(errorReader, AnalysisError::class.java)
                    if (errorObj != null && !errorObj.error.isNullOrEmpty()) {
                        notifyError(errorObj.error)
                        return
                    }
                } catch (ignored: Exception) {
                    // Non era nemmeno un errore JSON standard
                }
                // Rilancia l'eccezione originale se non era un errore gestito
                throw e
            }

        } catch (e: Exception) {
            log.error("Failed to parse analysis result", e)
            notifyError("Failed to parse analysis result: ${e.message}")
        }
    }

    private fun notifyProgress(progress: AnalysisProgress) {
        analysisListeners.forEach { it.onProgressUpdate(progress) }
    }

    private fun notifyError(message: String) {
        notifyProgress(AnalysisProgress(
            status = AnalysisStatus.FAILED,
            message = message
        ))
        analysisListeners.forEach { it.onAnalysisError(message) }

        NotificationGroupManager.getInstance()
            .getNotificationGroup("SZZ-LLM Notifications")
            .createNotification(
                "SZZ-LLM Analysis Failed",
                message,
                NotificationType.ERROR
            )
            .notify(project)
    }
}