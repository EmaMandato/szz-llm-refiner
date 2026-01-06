package it.unisannio.ingsw2.szzllm.actions

import com.intellij.openapi.actionSystem.ActionUpdateThread
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.wm.ToolWindowManager
import it.unisannio.ingsw2.szzllm.model.AnalysisConfig
import it.unisannio.ingsw2.szzllm.services.SzzAnalyzerService
import java.io.File

/**
 * Action to run SZZ-LLM analysis from menus.
 * Opens the tool window and starts analysis on the current project.
 */
class SzzRunAction : AnAction() {

    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val basePath = project.basePath ?: return

        // Check if it's a git repository
        val gitDir = File(basePath, ".git")
        if (!gitDir.exists()) {
            com.intellij.openapi.ui.Messages.showWarningDialog(
                project,
                "This project is not a Git repository.\nSZZ-LLM requires a Git repository to analyze.",
                "SZZ-LLM: Not a Git Repository"
            )
            return
        }

        // Open tool window
        val toolWindow = ToolWindowManager.getInstance(project)
            .getToolWindow("SZZ-LLM Analyzer")

        if (toolWindow != null) {
            toolWindow.show {
                // Tool window is now visible, analysis can be triggered from the UI
            }
        } else {
            // Fallback: run analysis directly with defaults
            val service = SzzAnalyzerService.getInstance(project)
            if (!service.isRunning()) {
                service.runAnalysis(AnalysisConfig(
                    repoPath = basePath,
                    branch = "main",
                    limit = 10
                ))
            }
        }
    }

    override fun update(e: AnActionEvent) {
        val project = e.project
        val basePath = project?.basePath

        // Enable only if we have a project with a git repository
        e.presentation.isEnabled = if (basePath != null) {
            val gitDir = File(basePath, ".git")
            gitDir.exists() && gitDir.isDirectory
        } else {
            false
        }
    }

    override fun getActionUpdateThread() = ActionUpdateThread.BGT
}
