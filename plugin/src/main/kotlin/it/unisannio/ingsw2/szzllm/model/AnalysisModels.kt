package it.unisannio.ingsw2.szzllm.model

import com.google.gson.annotations.SerializedName

/**
 * Data models for SZZ-LLM analysis results.
 * These mirror the Python engine's output structure.
 */

data class AnalysisResult(
    @SerializedName("fix_commit")
    val fixCommit: String,
    @SerializedName("commit_message")
    val commitMessage: String,
    @SerializedName("is_bug")
    val isBug: Boolean,
    @SerializedName("bug_inducing_commits")
    val bugInducingCommits: List<String>
)

data class AnalysisReport(
    val repository: String,
    val branch: String,
    @SerializedName("total_potential_fixes")
    val totalPotentialFixes: Int,
    @SerializedName("analyzed_commits")
    val analyzedCommits: Int,
    @SerializedName("confirmed_bugs")
    val confirmedBugs: Int,
    val results: List<AnalysisResult>,
    val errors: List<String>
)

data class AnalysisError(
    val status: String? = null,
    val error: String? = null
)

/**
 * Configuration for running the analysis
 */
data class AnalysisConfig(
    val repoPath: String = "",
    val repoUrl: String? = null,
    val branch: String = "main",
    val limit: Int = 10,
    val model: String = "qwen2.5-coder:7b",
    val skipLlm: Boolean = false,
    val pythonPath: String = "python"
)

/**
 * Status of the analysis process
 */
enum class AnalysisStatus {
    IDLE,
    RUNNING,
    COMPLETED,
    FAILED,
    CANCELLED
}

/**
 * Progress update during analysis
 */
data class AnalysisProgress(
    val status: AnalysisStatus,
    val message: String,
    val currentCommit: Int = 0,
    val totalCommits: Int = 0,
    val percentage: Int = 0
)