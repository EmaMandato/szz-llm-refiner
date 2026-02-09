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
    val bugInducingCommits: List<String>,
    @SerializedName("skipped_reason")
    val skippedReason: String? = null
)

data class FilterStats(
    @SerializedName("skipped_by_message")
    val skippedByMessage: Int = 0,
    @SerializedName("skipped_by_llm")
    val skippedByLlm: Int = 0,
    @SerializedName("bics_filtered_by_blacklist")
    val bicsFilteredByBlacklist: Int = 0,
    @SerializedName("bics_filtered_by_message")
    val bicsFilteredByMessage: Int = 0,
    @SerializedName("bics_filtered_by_cosmetic")
    val bicsFilteredByCosmetic: Int = 0
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
    val errors: List<String>,
    @SerializedName("filter_stats")
    val filterStats: FilterStats? = null,
    @SerializedName("selection_strategy")
    val selectionStrategy: String = "all",
    @SerializedName("selection_params")
    val selectionParams: Map<String, String?> = emptyMap()
)

data class AnalysisError(
    val status: String? = null,
    val error: String? = null
)

/**
 * Tag information from repository
 */
data class TagInfo(
    val name: String,
    val hash: String,
    val date: String? = null
)

data class TagsResponse(
    val tags: List<TagInfo>
)

/**
 * Selection strategy for commit filtering
 */
enum class SelectionStrategy(val displayName: String) {
    ALL("All Commits"),
    DATE_RANGE("Date Range"),
    TAG_RANGE("Tag/Release Range");

    override fun toString() = displayName
}

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
    val pythonPath: String = "python",
    // Selection strategy
    val selectionStrategy: SelectionStrategy = SelectionStrategy.ALL,
    // Date range parameters
    val since: String? = null,  // Format: YYYY-MM-DD
    val until: String? = null,  // Format: YYYY-MM-DD
    // Tag range parameters
    val fromTag: String? = null,
    val toTag: String? = null
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