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
            addParameter("-m")
            addParameter("szz_llm_project.main")
            addParameter(config.repoPath)
            addParameter("--branch")
            addParameter(config.branch)
            addParameter("--limit")
            addParameter(config.limit.toString())
            addParameter("--output")
            addParameter("json")

            if (config.skipLlm || settings.skipLlmByDefault) {
                addParameter("--skip-llm")
            } else {
                addParameter("--model")
                addParameter(settings.ollamaModel.ifEmpty { config.model })
            }

            charset = StandardCharsets.UTF_8
            workDirectory = File(config.repoPath)
        }

        log.info("Executing: ${commandLine.commandLineString}")
        indicator.text = "Running analysis on ${config.repoPath}..."

        val outputBuffer = StringBuilder()
        val errorBuffer = StringBuilder()
        var lastProgressMessage = ""

        val processHandler = OSProcessHandler(commandLine)
        currentProcess.set(processHandler)

        processHandler.addProcessListener(object : ProcessListener {
            override fun onTextAvailable(event: ProcessEvent, outputType: Key<*>) {
                val text = event.text.trim()
                if (text.isEmpty()) return

                when (outputType) {
                    ProcessOutputTypes.STDOUT -> {
                        outputBuffer.append(event.text)
                        // Notify listeners about output
                        analysisListeners.forEach { it.onOutputLine(text) }

                        // Parse progress from stdout
                        parseProgressFromOutput(text)?.let { progress ->
                            if (progress.message != lastProgressMessage) {
                                lastProgressMessage = progress.message
                                indicator.text = progress.message
                                indicator.fraction = progress.percentage / 100.0
                                notifyProgress(progress)
                            }
                        }
                    }
                    ProcessOutputTypes.STDERR -> {
                        errorBuffer.append(event.text)
                        log.warn("SZZ stderr: $text")
                    }
                }
            }

            override fun processTerminated(event: ProcessEvent) {
                val exitCode = event.exitCode
                log.info("SZZ process terminated with exit code: $exitCode")

                if (indicator.isCanceled) {
                    return
                }

                if (exitCode == 0) {
                    parseResult(outputBuffer.toString())
                } else {
                    val errorMsg = if (errorBuffer.isNotEmpty()) {
                        errorBuffer.toString()
                    } else {
                        "Process exited with code $exitCode"
                    }
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
            line.contains("Found") && line.contains("potential fix commits") -> {
                val countMatch = Regex("""Found (\d+) potential""").find(line)
                val count = countMatch?.groupValues?.get(1) ?: "?"
                AnalysisProgress(
                    status = AnalysisStatus.RUNNING,
                    message = "Found $count potential fix commits",
                    percentage = 15
                )
            }
            line.contains("LLM verdict") -> {
                val verdict = if (line.contains("BUG")) "BUG" else "REFACTORING"
                AnalysisProgress(
                    status = AnalysisStatus.RUNNING,
                    message = "LLM verdict: $verdict"
                )
            }
            else -> null
        }
    }

    private fun parseResult(output: String) {
        try {
            // Find the JSON part in the output (it should be at the end)
            val jsonStart = output.indexOf("{")
            if (jsonStart == -1) {
                notifyError("No JSON output found from analysis")
                return
            }

            val jsonContent = output.substring(jsonStart)

            // Try to parse as error first
            try {
                val error = gson.fromJson(jsonContent, AnalysisError::class.java)
                if (error.error != null) {
                    notifyError(error.error)
                    return
                }
            } catch (e: JsonSyntaxException) {
                // Not an error, continue parsing as report
            }

            // Parse as analysis report
            val report = gson.fromJson(jsonContent, AnalysisReport::class.java)
            currentReport.set(report)

            notifyProgress(AnalysisProgress(
                status = AnalysisStatus.COMPLETED,
                message = "Analysis completed: ${report.confirmedBugs} bugs found in ${report.analyzedCommits} commits",
                percentage = 100
            ))

            analysisListeners.forEach { it.onAnalysisComplete(report) }

            // Show notification
            NotificationGroupManager.getInstance()
                .getNotificationGroup("SZZ-LLM Notifications")
                .createNotification(
                    "SZZ-LLM Analysis Complete",
                    "Found ${report.confirmedBugs} confirmed bugs in ${report.analyzedCommits} commits analyzed",
                    NotificationType.INFORMATION
                )
                .notify(project)

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
