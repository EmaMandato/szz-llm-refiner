package it.unisannio.ingsw2.szzllm

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import it.unisannio.ingsw2.szzllm.ui.SzzToolWindowPanel

/**
 * Factory for creating the SZZ-LLM Tool Window.
 */
class SzzToolWindowFactory : ToolWindowFactory {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = SzzToolWindowPanel(project)

        val contentFactory = ContentFactory.getInstance()
        val content = contentFactory.createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)
    }

    override fun shouldBeAvailable(project: Project): Boolean {
        // Only show if project has a .git directory
        val basePath = project.basePath ?: return false
        val gitDir = java.io.File(basePath, ".git")
        return gitDir.exists() && gitDir.isDirectory
    }
}
