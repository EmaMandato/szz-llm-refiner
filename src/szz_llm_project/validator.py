"""
Validation module for SZZ-LLM.
Compares LLM predictions against ground truth datasets to calculate metrics.

Supported dataset formats:
1. Simple CSV: commit_hash, is_bug (true/false)
2. Defects4J JSON: from defects4j-dissection project
3. SZZ benchmark JSON: from LLM4SZZ paper datasets
"""
import json
import csv
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from .miner import GitMiner
from .llm_refiner import LLMRefiner


@dataclass
class ValidationMetrics:
    """Metrics from validation run."""
    total_samples: int
    true_positives: int   # LLM says BUG, ground truth is BUG
    true_negatives: int   # LLM says REFACTORING, ground truth is REFACTORING
    false_positives: int  # LLM says BUG, ground truth is REFACTORING
    false_negatives: int  # LLM says REFACTORING, ground truth is BUG
    precision: float
    recall: float
    f1_score: float
    accuracy: float

    def to_dict(self):
        return asdict(self)


@dataclass
class ValidationResult:
    """Result of a single validation sample."""
    commit_hash: str
    ground_truth: bool  # True = BUG, False = REFACTORING
    prediction: bool    # True = BUG, False = REFACTORING
    correct: bool
    commit_message: Optional[str] = None


def calculate_metrics(results: list[ValidationResult]) -> ValidationMetrics:
    """Calculate precision, recall, F1, and accuracy from validation results."""
    tp = sum(1 for r in results if r.ground_truth and r.prediction)
    tn = sum(1 for r in results if not r.ground_truth and not r.prediction)
    fp = sum(1 for r in results if not r.ground_truth and r.prediction)
    fn = sum(1 for r in results if r.ground_truth and not r.prediction)

    total = len(results)

    # Precision: TP / (TP + FP)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0

    # Recall: TP / (TP + FN)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    # F1: 2 * (precision * recall) / (precision + recall)
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Accuracy: (TP + TN) / total
    accuracy = (tp + tn) / total if total > 0 else 0.0

    return ValidationMetrics(
        total_samples=total,
        true_positives=tp,
        true_negatives=tn,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
        accuracy=round(accuracy, 4)
    )


def load_ground_truth_csv(csv_path: str) -> dict[str, bool]:
    """
    Load ground truth from a CSV file.

    Expected format:
    commit_hash,is_bug
    abc123,true
    def456,false

    Returns: dict mapping commit_hash -> is_bug (boolean)
    """
    ground_truth = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            commit_hash = row.get('commit_hash') or row.get('hash') or row.get('commit')
            is_bug_str = row.get('is_bug') or row.get('label') or row.get('type')

            if commit_hash and is_bug_str:
                # Normalize to boolean
                is_bug = is_bug_str.lower().strip() in ('true', 'bug', 'yes', '1', 'bugfix')
                ground_truth[commit_hash.strip()] = is_bug

    return ground_truth


def load_ground_truth_json(json_path: str) -> dict[str, bool]:
    """
    Load ground truth from a JSON file.

    Supports multiple formats:
    1. Simple: {"commits": [{"hash": "abc", "is_bug": true}, ...]}
    2. Defects4J style: [{"bugId": "Chart-1", "revisionId": "abc", ...}, ...]
    3. LLM4SZZ style: [{"fix_commit": "abc", "is_bug_fix": true}, ...]

    Returns: dict mapping commit_hash -> is_bug (boolean)
    """
    ground_truth = {}

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle different JSON structures
    if isinstance(data, dict):
        if 'commits' in data:
            items = data['commits']
        elif 'samples' in data:
            items = data['samples']
        else:
            items = list(data.values()) if all(isinstance(v, dict) for v in data.values()) else []
    else:
        items = data  # Assume it's a list

    for item in items:
        if not isinstance(item, dict):
            continue

        # Try different field names for commit hash
        commit_hash = (
            item.get('commit_hash') or
            item.get('hash') or
            item.get('commit') or
            item.get('fix_commit') or
            item.get('revisionId') or
            item.get('sha')
        )

        # Try different field names for bug label
        is_bug = None
        if 'is_bug' in item:
            is_bug = item['is_bug']
        elif 'is_bug_fix' in item:
            is_bug = item['is_bug_fix']
        elif 'label' in item:
            label = item['label']
            is_bug = label.lower() in ('bug', 'bugfix', 'true', '1') if isinstance(label, str) else bool(label)
        elif 'type' in item:
            is_bug = item['type'].lower() in ('bug', 'bugfix')
        elif 'bugId' in item:
            # Defects4J: all entries are bugs by definition
            is_bug = True

        if commit_hash and is_bug is not None:
            ground_truth[str(commit_hash).strip()] = bool(is_bug)

    return ground_truth


def load_ground_truth(file_path: str) -> dict[str, bool]:
    """
    Load ground truth from file, auto-detecting format.

    Returns: dict mapping commit_hash -> is_bug (boolean)
    """
    path = Path(file_path)

    if path.suffix.lower() == '.csv':
        return load_ground_truth_csv(file_path)
    elif path.suffix.lower() == '.json':
        return load_ground_truth_json(file_path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}. Use .csv or .json")


def run_validation(
    repo_path: str,
    ground_truth_file: str,
    model: str = "qwen2.5-coder:7b",
    limit: int = 0,
    verbose: bool = False
) -> tuple[ValidationMetrics, list[ValidationResult]]:
    """
    Run validation against a ground truth dataset.

    Args:
        repo_path: Path to the git repository
        ground_truth_file: Path to CSV or JSON with labeled commits
        model: Ollama model to use
        limit: Max samples to validate (0 = all)
        verbose: Print progress

    Returns:
        Tuple of (metrics, individual_results)
    """
    # Load ground truth
    ground_truth = load_ground_truth(ground_truth_file)

    if not ground_truth:
        raise ValueError(f"No valid samples found in {ground_truth_file}")

    if verbose:
        print(f"Loaded {len(ground_truth)} labeled samples from {ground_truth_file}")

    # Initialize components
    miner = GitMiner(repo_path)
    refiner = LLMRefiner(model=model)

    results = []
    samples = list(ground_truth.items())

    if limit > 0:
        samples = samples[:limit]

    for i, (commit_hash, is_bug_gt) in enumerate(samples, 1):
        if verbose:
            print(f"[{i}/{len(samples)}] Validating {commit_hash[:8]}...", end=" ")

        try:
            # Get commit data
            msg, diff = miner.get_commit_diff(commit_hash)

            # Get LLM prediction
            prediction = refiner.is_real_bug_fix(msg, diff)

            correct = prediction == is_bug_gt

            results.append(ValidationResult(
                commit_hash=commit_hash,
                ground_truth=is_bug_gt,
                prediction=prediction,
                correct=correct,
                commit_message=msg[:100] if msg else None
            ))

            if verbose:
                status = "✓" if correct else "✗"
                gt_label = "BUG" if is_bug_gt else "REF"
                pred_label = "BUG" if prediction else "REF"
                print(f"{status} (GT: {gt_label}, Pred: {pred_label})")

        except Exception as e:
            if verbose:
                print(f"ERROR: {e}")
            # Skip commits we can't find in the repo
            continue

    if not results:
        raise ValueError("No commits from ground truth found in repository")

    metrics = calculate_metrics(results)

    return metrics, results


def print_validation_report(
    metrics: ValidationMetrics,
    results: list[ValidationResult],
    show_errors: bool = True
):
    """Print a formatted validation report."""
    print("\n" + "=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)

    print(f"\nTotal samples validated: {metrics.total_samples}")
    print(f"\nConfusion Matrix:")
    print(f"                    Predicted")
    print(f"                  BUG     REF")
    print(f"  Actual BUG      {metrics.true_positives:4}    {metrics.false_negatives:4}")
    print(f"  Actual REF      {metrics.false_positives:4}    {metrics.true_negatives:4}")

    print(f"\nMetrics:")
    print(f"  Precision: {metrics.precision:.2%}")
    print(f"  Recall:    {metrics.recall:.2%}")
    print(f"  F1 Score:  {metrics.f1_score:.2%}")
    print(f"  Accuracy:  {metrics.accuracy:.2%}")

    if show_errors:
        errors = [r for r in results if not r.correct]
        if errors:
            print(f"\nMisclassified commits ({len(errors)}):")
            print("-" * 60)
            for r in errors[:10]:  # Show max 10
                gt = "BUG" if r.ground_truth else "REF"
                pred = "BUG" if r.prediction else "REF"
                msg = r.commit_message[:50] if r.commit_message else "N/A"
                print(f"  {r.commit_hash[:8]}: GT={gt}, Pred={pred}")
                print(f"    {msg}...")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")

    print("\n" + "=" * 60)
