"""
Test per validator.py - coverage dei moduli di validazione.
"""

import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from szz_llm_project.validator import (
    ValidationMetrics,
    ValidationResult,
    calculate_metrics,
    load_ground_truth_csv,
    load_ground_truth_json,
    load_ground_truth,
    run_validation,
    print_validation_report,
)


class TestCalculateMetrics:
    """Test per calculate_metrics() - linee 46-77."""

    def test_perfect_predictions(self):
        results = [
            ValidationResult("a1", True, True, True),
            ValidationResult("a2", True, True, True),
            ValidationResult("a3", False, False, True),
        ]
        m = calculate_metrics(results)
        assert m.true_positives == 2
        assert m.true_negatives == 1
        assert m.false_positives == 0
        assert m.false_negatives == 0
        assert m.precision == 1.0
        assert m.recall == 1.0
        assert m.f1_score == 1.0
        assert m.accuracy == 1.0
        assert m.total_samples == 3

    def test_mixed_predictions(self):
        results = [
            ValidationResult("a1", True, True, True),    # TP
            ValidationResult("a2", True, False, False),   # FN
            ValidationResult("a3", False, True, False),   # FP
            ValidationResult("a4", False, False, True),   # TN
        ]
        m = calculate_metrics(results)
        assert m.true_positives == 1
        assert m.true_negatives == 1
        assert m.false_positives == 1
        assert m.false_negatives == 1
        assert m.precision == 0.5
        assert m.recall == 0.5
        assert m.accuracy == 0.5

    def test_no_positives(self):
        results = [
            ValidationResult("a1", False, False, True),
            ValidationResult("a2", False, False, True),
        ]
        m = calculate_metrics(results)
        assert m.precision == 0.0
        assert m.recall == 0.0
        assert m.f1_score == 0.0

    def test_empty_results(self):
        m = calculate_metrics([])
        assert m.total_samples == 0
        assert m.accuracy == 0.0

    def test_to_dict(self):
        results = [ValidationResult("a1", True, True, True)]
        m = calculate_metrics(results)
        d = m.to_dict()
        assert isinstance(d, dict)
        assert "precision" in d
        assert "recall" in d


class TestLoadGroundTruthCSV:
    """Test per load_ground_truth_csv() - linee 80-104."""

    def test_standard_csv(self):
        content = "commit_hash,is_bug\nabc123,true\ndef456,false\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            gt = load_ground_truth_csv(path)
            assert gt["abc123"] is True
            assert gt["def456"] is False
        finally:
            os.unlink(path)

    def test_alternative_column_names(self):
        content = "hash,label\nabc123,bug\ndef456,refactoring\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            gt = load_ground_truth_csv(path)
            assert gt["abc123"] is True
            assert gt["def456"] is False
        finally:
            os.unlink(path)

    def test_commit_column_name(self):
        content = "commit,type\nabc123,bugfix\ndef456,refactor\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            gt = load_ground_truth_csv(path)
            assert gt["abc123"] is True
            assert gt["def456"] is False
        finally:
            os.unlink(path)

    def test_yes_no_values(self):
        content = "commit_hash,is_bug\nabc123,yes\ndef456,no\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            gt = load_ground_truth_csv(path)
            assert gt["abc123"] is True
            assert gt["def456"] is False
        finally:
            os.unlink(path)

    def test_empty_csv(self):
        content = "commit_hash,is_bug\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            gt = load_ground_truth_csv(path)
            assert gt == {}
        finally:
            os.unlink(path)


class TestLoadGroundTruthJSON:
    """Test per load_ground_truth_json() - linee 107-166."""

    def test_simple_format(self):
        data = {"commits": [
            {"hash": "abc123", "is_bug": True},
            {"hash": "def456", "is_bug": False},
        ]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            gt = load_ground_truth_json(path)
            assert gt["abc123"] is True
            assert gt["def456"] is False
        finally:
            os.unlink(path)

    def test_samples_format(self):
        data = {"samples": [
            {"commit_hash": "abc", "is_bug": True},
        ]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            gt = load_ground_truth_json(path)
            assert gt["abc"] is True
        finally:
            os.unlink(path)

    def test_defects4j_format(self):
        data = [
            {"bugId": "Chart-1", "revisionId": "abc123"},
            {"bugId": "Chart-2", "revisionId": "def456"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            gt = load_ground_truth_json(path)
            assert gt["abc123"] is True
            assert gt["def456"] is True
        finally:
            os.unlink(path)

    def test_llm4szz_format(self):
        data = [
            {"fix_commit": "abc", "is_bug_fix": True},
            {"fix_commit": "def", "is_bug_fix": False},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            gt = load_ground_truth_json(path)
            assert gt["abc"] is True
            assert gt["def"] is False
        finally:
            os.unlink(path)

    def test_label_string_format(self):
        data = [
            {"sha": "abc", "label": "bug"},
            {"sha": "def", "label": "refactoring"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            gt = load_ground_truth_json(path)
            assert gt["abc"] is True
            assert gt["def"] is False
        finally:
            os.unlink(path)

    def test_type_field_format(self):
        data = [
            {"commit": "abc", "type": "bug"},
            {"commit": "def", "type": "feature"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            gt = load_ground_truth_json(path)
            assert gt["abc"] is True
            assert gt["def"] is False
        finally:
            os.unlink(path)

    def test_dict_values_format(self):
        data = {
            "item1": {"hash": "abc", "is_bug": True},
            "item2": {"hash": "def", "is_bug": False},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            gt = load_ground_truth_json(path)
            assert gt["abc"] is True
            assert gt["def"] is False
        finally:
            os.unlink(path)

    def test_label_numeric_format(self):
        data = [
            {"sha": "abc", "label": 1},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            gt = load_ground_truth_json(path)
            assert gt["abc"] is True
        finally:
            os.unlink(path)

    def test_non_dict_items_skipped(self):
        data = ["abc", "def"]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            gt = load_ground_truth_json(path)
            assert gt == {}
        finally:
            os.unlink(path)

    def test_dict_with_non_dict_values(self):
        data = {"key1": "value1", "key2": "value2"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            gt = load_ground_truth_json(path)
            assert gt == {}
        finally:
            os.unlink(path)


class TestLoadGroundTruth:
    """Test per load_ground_truth() - linee 169-182."""

    def test_csv_auto_detect(self):
        content = "commit_hash,is_bug\nabc,true\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            gt = load_ground_truth(path)
            assert gt["abc"] is True
        finally:
            os.unlink(path)

    def test_json_auto_detect(self):
        data = {"commits": [{"hash": "abc", "is_bug": True}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            gt = load_ground_truth(path)
            assert gt["abc"] is True
        finally:
            os.unlink(path)

    def test_unsupported_format_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write("<data/>")
            path = f.name
        try:
            with pytest.raises(ValueError, match="Unsupported file format"):
                load_ground_truth(path)
        finally:
            os.unlink(path)


class TestRunValidation:
    """Test per run_validation() - linee 185-262."""

    def test_basic_validation(self, tmp_path):
        # Crea ground truth CSV
        csv_file = tmp_path / "gt.csv"
        csv_file.write_text("commit_hash,is_bug\nabc123,true\ndef456,false\n")

        with patch("szz_llm_project.validator.GitMiner") as MockMiner, \
             patch("szz_llm_project.validator.LLMRefiner") as MockRefiner:

            mock_miner = MockMiner.return_value
            mock_miner.get_commit_diff.return_value = ("fix: bug", "diff content")

            mock_refiner = MockRefiner.return_value
            mock_refiner.is_real_bug_fix.side_effect = [True, False]

            metrics, results = run_validation(
                repo_path="/fake/repo",
                ground_truth_file=str(csv_file),
                model="test-model"
            )

            assert metrics.total_samples == 2
            assert len(results) == 2
            assert results[0].prediction is True
            assert results[1].prediction is False

    def test_validation_with_limit(self, tmp_path):
        csv_file = tmp_path / "gt.csv"
        csv_file.write_text("commit_hash,is_bug\na,true\nb,true\nc,false\n")

        with patch("szz_llm_project.validator.GitMiner") as MockMiner, \
             patch("szz_llm_project.validator.LLMRefiner") as MockRefiner:

            mock_miner = MockMiner.return_value
            mock_miner.get_commit_diff.return_value = ("msg", "diff")

            mock_refiner = MockRefiner.return_value
            mock_refiner.is_real_bug_fix.return_value = True

            metrics, results = run_validation(
                repo_path="/fake/repo",
                ground_truth_file=str(csv_file),
                limit=2
            )

            assert len(results) == 2

    def test_validation_verbose(self, tmp_path, capsys):
        csv_file = tmp_path / "gt.csv"
        csv_file.write_text("commit_hash,is_bug\nabc,true\n")

        with patch("szz_llm_project.validator.GitMiner") as MockMiner, \
             patch("szz_llm_project.validator.LLMRefiner") as MockRefiner:

            mock_miner = MockMiner.return_value
            mock_miner.get_commit_diff.return_value = ("fix msg", "diff")

            mock_refiner = MockRefiner.return_value
            mock_refiner.is_real_bug_fix.return_value = True

            run_validation(
                repo_path="/fake",
                ground_truth_file=str(csv_file),
                verbose=True
            )

            captured = capsys.readouterr()
            assert "Loaded" in captured.out
            assert "Validating" in captured.out

    def test_validation_with_error(self, tmp_path):
        csv_file = tmp_path / "gt.csv"
        csv_file.write_text("commit_hash,is_bug\nabc,true\ndef,false\n")

        with patch("szz_llm_project.validator.GitMiner") as MockMiner, \
             patch("szz_llm_project.validator.LLMRefiner") as MockRefiner:

            mock_miner = MockMiner.return_value
            # Prima chiamata OK, seconda lancia eccezione
            mock_miner.get_commit_diff.side_effect = [
                ("msg", "diff"),
                Exception("commit not found")
            ]

            mock_refiner = MockRefiner.return_value
            mock_refiner.is_real_bug_fix.return_value = True

            metrics, results = run_validation(
                repo_path="/fake",
                ground_truth_file=str(csv_file),
                verbose=True
            )

            assert len(results) == 1

    def test_empty_ground_truth_raises(self, tmp_path):
        csv_file = tmp_path / "gt.csv"
        csv_file.write_text("commit_hash,is_bug\n")

        with pytest.raises(ValueError, match="No valid samples"):
            run_validation("/fake", str(csv_file))

    def test_no_valid_commits_raises(self, tmp_path):
        csv_file = tmp_path / "gt.csv"
        csv_file.write_text("commit_hash,is_bug\nabc,true\n")

        with patch("szz_llm_project.validator.GitMiner") as MockMiner, \
             patch("szz_llm_project.validator.LLMRefiner") as MockRefiner:

            mock_miner = MockMiner.return_value
            mock_miner.get_commit_diff.side_effect = Exception("not found")

            with pytest.raises(ValueError, match="No commits from ground truth"):
                run_validation("/fake", str(csv_file))


class TestPrintValidationReport:
    """Test per print_validation_report() - linee 265-302."""

    def test_basic_report(self, capsys):
        metrics = ValidationMetrics(
            total_samples=4,
            true_positives=2,
            true_negatives=1,
            false_positives=1,
            false_negatives=0,
            precision=0.6667,
            recall=1.0,
            f1_score=0.8,
            accuracy=0.75,
        )
        results = [
            ValidationResult("abc", True, True, True, "fix: bug"),
            ValidationResult("def", True, True, True, "fix: another"),
            ValidationResult("ghi", False, True, False, "refactor: code"),
            ValidationResult("jkl", False, False, True, "docs: readme"),
        ]
        print_validation_report(metrics, results)
        out = capsys.readouterr().out
        assert "VALIDATION REPORT" in out
        assert "Precision" in out
        assert "Recall" in out
        assert "Misclassified" in out

    def test_report_no_errors(self, capsys):
        metrics = ValidationMetrics(
            total_samples=2,
            true_positives=1,
            true_negatives=1,
            false_positives=0,
            false_negatives=0,
            precision=1.0,
            recall=1.0,
            f1_score=1.0,
            accuracy=1.0,
        )
        results = [
            ValidationResult("abc", True, True, True),
            ValidationResult("def", False, False, True),
        ]
        print_validation_report(metrics, results)
        out = capsys.readouterr().out
        assert "VALIDATION REPORT" in out
        assert "Misclassified" not in out

    def test_report_show_errors_false(self, capsys):
        metrics = ValidationMetrics(
            total_samples=1, true_positives=0, true_negatives=0,
            false_positives=1, false_negatives=0,
            precision=0.0, recall=0.0, f1_score=0.0, accuracy=0.0,
        )
        results = [
            ValidationResult("abc", False, True, False, "some msg"),
        ]
        print_validation_report(metrics, results, show_errors=False)
        out = capsys.readouterr().out
        assert "Misclassified" not in out

    def test_report_many_errors_truncated(self, capsys):
        metrics = ValidationMetrics(
            total_samples=15, true_positives=0, true_negatives=0,
            false_positives=15, false_negatives=0,
            precision=0.0, recall=0.0, f1_score=0.0, accuracy=0.0,
        )
        results = [
            ValidationResult(f"hash{i}", False, True, False, f"msg {i}")
            for i in range(15)
        ]
        print_validation_report(metrics, results)
        out = capsys.readouterr().out
        assert "... and" in out

    def test_report_error_without_message(self, capsys):
        metrics = ValidationMetrics(
            total_samples=1, true_positives=0, true_negatives=0,
            false_positives=1, false_negatives=0,
            precision=0.0, recall=0.0, f1_score=0.0, accuracy=0.0,
        )
        results = [
            ValidationResult("abc", False, True, False, None),
        ]
        print_validation_report(metrics, results)
        out = capsys.readouterr().out
        assert "N/A" in out
