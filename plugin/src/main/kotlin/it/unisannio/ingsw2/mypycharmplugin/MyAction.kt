package it.unisannio.ingsw2.mypycharmplugin

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.ui.Messages

class MyAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        Messages.showMessageDialog(
            e.project,
            "Ciao dal tuo plugin Kotlin!",
            "Hello",
            Messages.getInformationIcon()
        )
    }
}