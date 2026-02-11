"""
Test per main.py - coverage delle funzioni CLI e orchestrazione.
"""

import json
import sys
import os
import subprocess
import tempfile
import shutil
from dataclasses import asdict
from datetime import datetime
from unittest.mock import patch, MagicMock
import pytest

from szz_llm_project.main import (
    parse_date,
    check_git_installed,
    check_ollama_running,
    clone_repository,
    get_tags_list,
    print_report,
    run_analysis,
    log,
    AnalysisResult,
    FilterStats,
    AnalysisReport,
)


class TestParseDate:
    """Test per parse_date() - linee 363-387."""

    def test_yyyy_mm_dd(self):
        dt = parse_date("2024-01-15")
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_iso_with_time(self):
        dt = parse_date("2024-06-30T12:30:00")
        assert dt.hour == 12
        assert dt.minute == 30

    def test_iso_with_timezone(self):
        dt = parse_date("2024-06-30T12:30:00+02:00")
        assert dt.year == 2024

    def test_datetime_with_space(self):
        dt = parse_date("2024-06-30 12:30:00")
        assert dt.hour == 12

    def test_iso_format_fallback(self):
        dt = parse_date("2024-03-15")
        assert dt.month == 3

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Formato data non riconosciuto"):
            parse_date("not-a-date")

    def test_invalid_partial_date_raises(self):
        with pytest.raises(ValueError):
            parse_date("2024/01/15")


class TestCheckGitInstalled:
    """Test per check_git_installed() - linee 98-108."""

    def test_git_installed(self):
        # Git è installato nella CI
        assert check_git_installed() is True

    def test_git_not_found(self):
        with patch("szz_llm_project.main.subprocess.run", side_effect=FileNotFoundError):
            assert check_git_installed() is False

    def test_git_bad_returncode(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("szz_llm_project.main.subprocess.run", return_value=mock_result):
            assert check_git_installed() is False


class TestCheckOllamaRunning:
    """Test per check_ollama_running() - linee 111-118."""

    def test_ollama_running(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch.dict("sys.modules", {"requests": MagicMock(get=MagicMock(return_value=mock_resp))}):
            assert check_ollama_running() is True

    def test_ollama_not_running(self):
        mock_requests = MagicMock()
        mock_requests.get.side_effect = Exception("connection refused")
        with patch.dict("sys.modules", {"requests": mock_requests}):
            assert check_ollama_running() is False

    def test_ollama_bad_status(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_resp
        with patch.dict("sys.modules", {"requests": mock_requests}):
            assert check_ollama_running() is False


class TestCloneRepository:
    """Test per clone_repository() - linee 63-95."""

    def test_successful_clone(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("szz_llm_project.main.subprocess.run", return_value=mock_result):
            dest = tempfile.mkdtemp(prefix="szz_clone_test_")
            try:
                path = clone_repository("https://example.com/repo.git", dest=dest)
                assert path == dest
            finally:
                shutil.rmtree(dest, ignore_errors=True)

    def test_branch_fallback(self):
        fail_result = MagicMock()
        fail_result.returncode = 1
        ok_result = MagicMock()
        ok_result.returncode = 0

        with patch("szz_llm_project.main.subprocess.run", side_effect=[fail_result, ok_result]):
            path = clone_repository("https://example.com/repo.git", branch="dev")
            assert path is not None
            # Cleanup tempdir created by clone_repository
            shutil.rmtree(path, ignore_errors=True)

    def test_clone_failure_raises(self):
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stderr = "fatal: repo not found"

        with patch("szz_llm_project.main.subprocess.run", return_value=fail_result):
            with pytest.raises(RuntimeError, match="Errore clone"):
                clone_repository("https://example.com/bad.git")


class TestGetTagsList:
    """Test per get_tags_list() - linee 121-127."""

    def test_delegates_to_miner(self):
        with patch("szz_llm_project.main.GitMiner") as MockMiner:
            mock_miner = MockMiner.return_value
            mock_miner.get_tags.return_value = [{"name": "v1.0", "hash": "abc", "date": ""}]

            result = get_tags_list("/fake/repo")
            assert len(result) == 1
            assert result[0]["name"] == "v1.0"


class TestLog:
    """Test per log() - linee 20-25."""

    def test_log_stdout(self, capsys):
        import szz_llm_project.main as main_mod
        old = main_mod._json_output
        main_mod._json_output = False
        try:
            log("hello stdout")
            out = capsys.readouterr().out
            assert "hello stdout" in out
        finally:
            main_mod._json_output = old

    def test_log_stderr_json_mode(self, capsys):
        import szz_llm_project.main as main_mod
        old = main_mod._json_output
        main_mod._json_output = True
        try:
            log("hello stderr")
            captured = capsys.readouterr()
            assert "hello stderr" in captured.err
        finally:
            main_mod._json_output = old


class TestPrintReport:
    """Test per print_report() - linee 296-360."""

    def _make_report(self, **kwargs):
        defaults = dict(
            repository="/repo",
            branch="main",
            total_potential_fixes=5,
            analyzed_commits=3,
            confirmed_bugs=2,
            results=[
                {
                    "fix_commit": "abc12345",
                    "commit_message": "fix: null pointer",
                    "is_bug": True,
                    "bug_inducing_commits": ["def456", "ghi789", "jkl012", "mno345", "pqr678", "stu901"],
                    "skipped_reason": None,
                },
                {
                    "fix_commit": "xyz98765",
                    "commit_message": "refactor: cleanup code",
                    "is_bug": False,
                    "bug_inducing_commits": [],
                    "skipped_reason": "pre-filter:message",
                },
            ],
            errors=[],
            filter_stats={
                "skipped_by_message": 1,
                "skipped_by_llm": 0,
                "bics_filtered_by_blacklist": 0,
                "bics_filtered_by_message": 0,
                "bics_filtered_by_cosmetic": 0,
            },
            selection_strategy="all",
            selection_params={},
        )
        defaults.update(kwargs)
        return AnalysisReport(**defaults)

    def test_text_format(self, capsys):
        report = self._make_report()
        print_report(report, "text")
        out = capsys.readouterr().out
        assert "SZZ-LLM ANALYSIS REPORT" in out
        assert "Repository:" in out
        assert "FILTER STATISTICS" in out
        assert "RESULTS" in out
        assert "BUG" in out
        assert "SKIPPED" in out

    def test_json_format(self, capsys):
        report = self._make_report()
        print_report(report, "json")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["repository"] == "/repo"
        assert data["confirmed_bugs"] == 2

    def test_text_with_selection_params(self, capsys):
        report = self._make_report(
            selection_strategy="tag_range",
            selection_params={"from_tag": "v1.0", "to_tag": "v2.0"}
        )
        print_report(report, "text")
        out = capsys.readouterr().out
        assert "tag_range" in out
        assert "v1.0" in out

    def test_text_with_errors(self, capsys):
        report = self._make_report(errors=["some error occurred"])
        print_report(report, "text")
        out = capsys.readouterr().out
        assert "ERRORS" in out
        assert "some error" in out

    def test_text_bics_truncated(self, capsys):
        report = self._make_report()
        print_report(report, "text")
        out = capsys.readouterr().out
        # 6 BICs ma mostra max 5 + "... and 1 more"
        assert "... and" in out

    def test_text_result_not_bug_not_skipped(self, capsys):
        report = self._make_report(
            results=[{
                "fix_commit": "abc",
                "commit_message": "some commit",
                "is_bug": False,
                "bug_inducing_commits": [],
                "skipped_reason": None,
            }]
        )
        print_report(report, "text")
        out = capsys.readouterr().out
        assert "REFACTORING" in out

    def test_text_no_filter_stats(self, capsys):
        report = self._make_report(filter_stats={})
        print_report(report, "text")
        out = capsys.readouterr().out
        assert "SZZ-LLM ANALYSIS REPORT" in out

    def test_selection_params_with_none_value(self, capsys):
        report = self._make_report(
            selection_strategy="date_range",
            selection_params={"since": "2024-01-01", "until": None}
        )
        print_report(report, "text")
        out = capsys.readouterr().out
        assert "since" in out


class TestRunAnalysis:
    """Test per run_analysis() - linee 130-293."""

    def test_basic_analysis_skip_llm(self):
        with patch("szz_llm_project.main.GitMiner") as MockMiner:
            mock_miner = MockMiner.return_value
            mock_miner.get_fixing_commits.return_value = ["abc123"]
            mock_miner.get_commit_diff.return_value = ("fix: bug", "diff")
            mock_miner.should_skip_by_message.return_value = False
            mock_miner.get_bug_inducing_commits.return_value = ["def456"]
            mock_miner.get_commit_message.return_value = "introduced bug"

            report = run_analysis("/fake/repo", skip_llm=True)

            assert report.total_potential_fixes == 1
            assert report.confirmed_bugs == 1
            assert len(report.results) == 1

    def test_analysis_with_message_skip(self):
        with patch("szz_llm_project.main.GitMiner") as MockMiner:
            mock_miner = MockMiner.return_value
            mock_miner.get_fixing_commits.return_value = ["abc123"]
            mock_miner.get_commit_diff.return_value = ("refactor: cleanup", "diff")
            mock_miner.should_skip_by_message.return_value = True

            report = run_analysis("/fake/repo", skip_llm=True)

            assert report.confirmed_bugs == 0
            assert report.filter_stats["skipped_by_message"] == 1

    def test_analysis_with_llm_refactoring(self):
        with patch("szz_llm_project.main.GitMiner") as MockMiner, \
             patch("szz_llm_project.main.LLMRefiner") as MockRefiner:

            mock_miner = MockMiner.return_value
            mock_miner.get_fixing_commits.return_value = ["abc123"]
            mock_miner.get_commit_diff.return_value = ("fix: minor", "diff")
            mock_miner.should_skip_by_message.return_value = False

            mock_refiner = MockRefiner.return_value
            mock_refiner.is_real_bug_fix.return_value = False

            report = run_analysis("/fake/repo", skip_llm=False)

            assert report.confirmed_bugs == 0
            assert report.filter_stats["skipped_by_llm"] == 1

    def test_analysis_with_llm_confirmed_bug(self):
        with patch("szz_llm_project.main.GitMiner") as MockMiner, \
             patch("szz_llm_project.main.LLMRefiner") as MockRefiner:

            mock_miner = MockMiner.return_value
            mock_miner.get_fixing_commits.return_value = ["abc123"]
            mock_miner.get_commit_diff.return_value = ("fix: NPE", "diff")
            mock_miner.should_skip_by_message.return_value = False
            mock_miner.get_bug_inducing_commits.return_value = ["bic1"]
            mock_miner.get_commit_message.return_value = "old commit"

            mock_refiner = MockRefiner.return_value
            mock_refiner.is_real_bug_fix.return_value = True

            report = run_analysis("/fake/repo", skip_llm=False)

            assert report.confirmed_bugs == 1
            assert report.results[0]["is_bug"] is True

    def test_analysis_tag_strategy(self):
        with patch("szz_llm_project.main.GitMiner") as MockMiner:
            mock_miner = MockMiner.return_value
            mock_miner.get_fixing_commits.return_value = []

            report = run_analysis(
                "/fake/repo", skip_llm=True,
                from_tag="v1.0", to_tag="v2.0"
            )

            assert report.selection_strategy == "tag_range"
            assert report.selection_params["from_tag"] == "v1.0"

    def test_analysis_date_strategy(self):
        since = datetime(2024, 1, 1)
        until = datetime(2024, 6, 30)

        with patch("szz_llm_project.main.GitMiner") as MockMiner:
            mock_miner = MockMiner.return_value
            mock_miner.get_fixing_commits.return_value = []

            report = run_analysis(
                "/fake/repo", skip_llm=True,
                since=since, until=until
            )

            assert report.selection_strategy == "date_range"

    def test_analysis_since_only(self):
        since = datetime(2024, 1, 1)
        with patch("szz_llm_project.main.GitMiner") as MockMiner:
            mock_miner = MockMiner.return_value
            mock_miner.get_fixing_commits.return_value = []

            report = run_analysis("/fake/repo", skip_llm=True, since=since)
            assert report.selection_strategy == "date_range"

    def test_analysis_limit_zero(self):
        with patch("szz_llm_project.main.GitMiner") as MockMiner:
            mock_miner = MockMiner.return_value
            mock_miner.get_fixing_commits.return_value = ["a", "b", "c"]
            mock_miner.get_commit_diff.return_value = ("fix: x", "d")
            mock_miner.should_skip_by_message.return_value = False
            mock_miner.get_bug_inducing_commits.return_value = []

            report = run_analysis("/fake/repo", skip_llm=True, limit=0)
            assert report.analyzed_commits == 3

    def test_analysis_no_bics(self):
        with patch("szz_llm_project.main.GitMiner") as MockMiner:
            mock_miner = MockMiner.return_value
            mock_miner.get_fixing_commits.return_value = ["abc"]
            mock_miner.get_commit_diff.return_value = ("fix: x", "d")
            mock_miner.should_skip_by_message.return_value = False
            mock_miner.get_bug_inducing_commits.return_value = []

            report = run_analysis("/fake/repo", skip_llm=True)
            assert report.results[0]["bug_inducing_commits"] == []

    def test_analysis_many_bics_logged(self):
        with patch("szz_llm_project.main.GitMiner") as MockMiner:
            mock_miner = MockMiner.return_value
            mock_miner.get_fixing_commits.return_value = ["abc"]
            mock_miner.get_commit_diff.return_value = ("fix: x", "d")
            mock_miner.should_skip_by_message.return_value = False
            mock_miner.get_bug_inducing_commits.return_value = ["b1", "b2", "b3", "b4"]
            mock_miner.get_commit_message.return_value = "old"

            report = run_analysis("/fake/repo", skip_llm=True)
            assert len(report.results[0]["bug_inducing_commits"]) == 4


class TestAnalysisDataclasses:
    """Test per AnalysisResult, FilterStats, AnalysisReport dataclass."""

    def test_analysis_result(self):
        r = AnalysisResult(
            fix_commit="abc",
            commit_message="fix: bug",
            is_bug=True,
            bug_inducing_commits=["def"],
            skipped_reason=None,
        )
        d = asdict(r)
        assert d["fix_commit"] == "abc"
        assert d["is_bug"] is True

    def test_analysis_result_skipped(self):
        r = AnalysisResult(
            fix_commit="abc",
            commit_message="refactor: x",
            is_bug=False,
            bug_inducing_commits=[],
            skipped_reason="pre-filter:message",
        )
        assert r.skipped_reason == "pre-filter:message"

    def test_filter_stats_defaults(self):
        s = FilterStats()
        assert s.skipped_by_message == 0
        assert s.skipped_by_llm == 0
        assert s.bics_filtered_by_blacklist == 0

    def test_analysis_report(self):
        r = AnalysisReport(
            repository="/repo",
            branch="main",
            total_potential_fixes=0,
            analyzed_commits=0,
            confirmed_bugs=0,
            results=[],
            errors=[],
        )
        assert r.selection_strategy == "all"
        assert r.selection_params == {}
        assert r.filter_stats == {}
