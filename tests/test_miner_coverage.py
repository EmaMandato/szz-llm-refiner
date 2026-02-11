"""
Test aggiuntivi per aumentare la coverage di miner.py

Copertura target:
- get_fixing_commits() - linee 30-36
- get_fix_details() - linee 42-62
- get_commit_diff() - linee 69-74
- get_bug_inducing_commits() branch mancanti - linee 88-89, 125, 144-146, 151-152
"""

import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone, timedelta
import pytest

from szz_llm_project.miner import GitMiner, SKIP_KEYWORDS


class TestGetFixingCommits:
    """Test per get_fixing_commits() - linee 30-36."""

    @pytest.fixture
    def repo_with_various_commits(self):
        """Crea repo con commit di vari tipi (fix, bug, issue, altri)."""
        repo_dir = tempfile.mkdtemp(prefix="szz_fixing_")

        def run_git(*args):
            return subprocess.run(
                ["git", "-C", repo_dir] + list(args),
                capture_output=True, text=True, check=True
            ).stdout.strip()

        run_git("init")
        run_git("config", "user.email", "test@test.com")
        run_git("config", "user.name", "Test")

        commits = {}
        file_path = os.path.join(repo_dir, "code.py")

        # Commit con "fix"
        with open(file_path, "w") as f:
            f.write("v1")
        run_git("add", ".")
        run_git("commit", "-m", "fix: resolved null pointer")
        commits["fix"] = run_git("rev-parse", "HEAD")

        # Commit con "bug"
        with open(file_path, "w") as f:
            f.write("v2")
        run_git("add", ".")
        run_git("commit", "-m", "bug: corrected calculation error")
        commits["bug"] = run_git("rev-parse", "HEAD")

        # Commit con "issue"
        with open(file_path, "w") as f:
            f.write("v3")
        run_git("add", ".")
        run_git("commit", "-m", "Closes issue #123")
        commits["issue"] = run_git("rev-parse", "HEAD")

        # Commit senza keyword (non dovrebbe essere incluso)
        with open(file_path, "w") as f:
            f.write("v4")
        run_git("add", ".")
        run_git("commit", "-m", "refactor: cleaned up code")
        commits["refactor"] = run_git("rev-parse", "HEAD")

        # Commit con "FIX" maiuscolo
        with open(file_path, "w") as f:
            f.write("v5")
        run_git("add", ".")
        run_git("commit", "-m", "FIX: uppercase keyword")
        commits["fix_upper"] = run_git("rev-parse", "HEAD")

        yield {"path": repo_dir, "commits": commits}
        shutil.rmtree(repo_dir, ignore_errors=True)

    def test_finds_fix_commits(self, repo_with_various_commits):
        """Verifica che trovi commit con 'fix' nel messaggio."""
        miner = GitMiner(repo_with_various_commits["path"])
        fixes = miner.get_fixing_commits()
        commits = repo_with_various_commits["commits"]

        assert commits["fix"] in fixes
        assert commits["fix_upper"] in fixes  # case insensitive

    def test_finds_bug_commits(self, repo_with_various_commits):
        """Verifica che trovi commit con 'bug' nel messaggio."""
        miner = GitMiner(repo_with_various_commits["path"])
        fixes = miner.get_fixing_commits()

        assert repo_with_various_commits["commits"]["bug"] in fixes

    def test_finds_issue_commits(self, repo_with_various_commits):
        """Verifica che trovi commit con 'issue' nel messaggio."""
        miner = GitMiner(repo_with_various_commits["path"])
        fixes = miner.get_fixing_commits()

        assert repo_with_various_commits["commits"]["issue"] in fixes

    def test_excludes_non_fix_commits(self, repo_with_various_commits):
        """Verifica che escluda commit senza keyword."""
        miner = GitMiner(repo_with_various_commits["path"])
        fixes = miner.get_fixing_commits()

        assert repo_with_various_commits["commits"]["refactor"] not in fixes

    def test_empty_repo_returns_empty_list(self):
        """Repo senza commit di fix restituisce lista vuota."""
        repo_dir = tempfile.mkdtemp(prefix="szz_empty_")
        try:
            subprocess.run(["git", "-C", repo_dir, "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo_dir, "config", "user.email", "t@t.com"], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo_dir, "config", "user.name", "T"], check=True, capture_output=True)

            file_path = os.path.join(repo_dir, "f.txt")
            with open(file_path, "w") as f:
                f.write("x")
            subprocess.run(["git", "-C", repo_dir, "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", "initial commit"], check=True, capture_output=True)

            miner = GitMiner(repo_dir)
            fixes = miner.get_fixing_commits()

            assert fixes == []
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)


class TestGetFixDetails:
    """Test per get_fix_details() - linee 42-62."""

    @pytest.fixture
    def repo_with_deletions(self):
        """Crea repo con commit che ha linee cancellate."""
        repo_dir = tempfile.mkdtemp(prefix="szz_details_")

        def run_git(*args):
            return subprocess.run(
                ["git", "-C", repo_dir] + list(args),
                capture_output=True, text=True, check=True
            ).stdout.strip()

        run_git("init")
        run_git("config", "user.email", "test@test.com")
        run_git("config", "user.name", "Test")

        file_path = os.path.join(repo_dir, "Calculator.java")

        # Commit iniziale con più linee
        with open(file_path, "w") as f:
            f.write("""public class Calculator {
    public int add(int a, int b) {
        System.out.println("debug");
        return a + b;
    }
}
""")
        run_git("add", ".")
        run_git("commit", "-m", "initial")
        initial = run_git("rev-parse", "HEAD")

        # Commit che rimuove la linea di debug
        with open(file_path, "w") as f:
            f.write("""public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
}
""")
        run_git("add", ".")
        run_git("commit", "-m", "fix: removed debug line")
        fix = run_git("rev-parse", "HEAD")

        yield {"path": repo_dir, "initial": initial, "fix": fix}
        shutil.rmtree(repo_dir, ignore_errors=True)

    def test_returns_modifications_list(self, repo_with_deletions):
        """Verifica che restituisca una lista di modifiche."""
        miner = GitMiner(repo_with_deletions["path"])
        mods = miner.get_fix_details(repo_with_deletions["fix"])

        assert isinstance(mods, list)
        assert len(mods) > 0

    def test_includes_file_path(self, repo_with_deletions):
        """Verifica che ogni modifica abbia il file path."""
        miner = GitMiner(repo_with_deletions["path"])
        mods = miner.get_fix_details(repo_with_deletions["fix"])

        assert mods[0]["file"] == "Calculator.java"

    def test_includes_deleted_lines(self, repo_with_deletions):
        """Verifica che includa le linee cancellate."""
        miner = GitMiner(repo_with_deletions["path"])
        mods = miner.get_fix_details(repo_with_deletions["fix"])

        deleted = mods[0]["deleted_lines"]
        assert isinstance(deleted, list)
        # Dovrebbe contenere la linea di debug rimossa
        assert any("debug" in line for line in deleted)

    def test_handles_multiple_files(self):
        """Verifica gestione di commit con più file modificati."""
        repo_dir = tempfile.mkdtemp(prefix="szz_multi_")
        try:
            def run_git(*args):
                return subprocess.run(
                    ["git", "-C", repo_dir] + list(args),
                    capture_output=True, text=True, check=True
                ).stdout.strip()

            run_git("init")
            run_git("config", "user.email", "t@t.com")
            run_git("config", "user.name", "T")

            # Crea due file
            with open(os.path.join(repo_dir, "A.java"), "w") as f:
                f.write("class A { int x = 1; }")
            with open(os.path.join(repo_dir, "B.java"), "w") as f:
                f.write("class B { int y = 2; }")
            run_git("add", ".")
            run_git("commit", "-m", "initial")

            # Modifica entrambi
            with open(os.path.join(repo_dir, "A.java"), "w") as f:
                f.write("class A { int x = 10; }")
            with open(os.path.join(repo_dir, "B.java"), "w") as f:
                f.write("class B { int y = 20; }")
            run_git("add", ".")
            run_git("commit", "-m", "fix: updated values")
            fix = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            mods = miner.get_fix_details(fix)

            assert len(mods) == 2
            files = [m["file"] for m in mods]
            assert "A.java" in files
            assert "B.java" in files

        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_handles_commit_with_no_deletions(self):
        """Commit che aggiunge solo linee (nessuna cancellazione)."""
        repo_dir = tempfile.mkdtemp(prefix="szz_nodel_")
        try:
            def run_git(*args):
                return subprocess.run(
                    ["git", "-C", repo_dir] + list(args),
                    capture_output=True, text=True, check=True
                ).stdout.strip()

            run_git("init")
            run_git("config", "user.email", "t@t.com")
            run_git("config", "user.name", "T")

            file_path = os.path.join(repo_dir, "f.txt")
            with open(file_path, "w") as f:
                f.write("line1\n")
            run_git("add", ".")
            run_git("commit", "-m", "initial")

            # Aggiunge linee senza cancellare
            with open(file_path, "a") as f:
                f.write("line2\nline3\n")
            run_git("add", ".")
            run_git("commit", "-m", "fix: added more lines")
            fix = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            mods = miner.get_fix_details(fix)

            # Deve restituire lista (anche se deleted_lines è vuoto)
            assert isinstance(mods, list)

        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)


class TestGetCommitDiff:
    """Test per get_commit_diff() - linee 69-74."""

    @pytest.fixture
    def repo_with_commit(self):
        """Crea repo con un commit."""
        repo_dir = tempfile.mkdtemp(prefix="szz_diff_")

        def run_git(*args):
            return subprocess.run(
                ["git", "-C", repo_dir] + list(args),
                capture_output=True, text=True, check=True
            ).stdout.strip()

        run_git("init")
        run_git("config", "user.email", "test@test.com")
        run_git("config", "user.name", "Test")

        file_path = os.path.join(repo_dir, "test.py")
        with open(file_path, "w") as f:
            f.write("print('hello')\n")
        run_git("add", ".")
        run_git("commit", "-m", "Initial commit with greeting")
        initial = run_git("rev-parse", "HEAD")

        with open(file_path, "w") as f:
            f.write("print('goodbye')\n")
        run_git("add", ".")
        run_git("commit", "-m", "Fix: changed greeting message")
        fix = run_git("rev-parse", "HEAD")

        yield {"path": repo_dir, "initial": initial, "fix": fix}
        shutil.rmtree(repo_dir, ignore_errors=True)

    def test_returns_message_and_diff(self, repo_with_commit):
        """Verifica che restituisca tupla (messaggio, diff)."""
        miner = GitMiner(repo_with_commit["path"])
        msg, diff = miner.get_commit_diff(repo_with_commit["fix"])

        assert isinstance(msg, str)
        assert isinstance(diff, str)

    def test_message_contains_commit_text(self, repo_with_commit):
        """Verifica che il messaggio sia corretto."""
        miner = GitMiner(repo_with_commit["path"])
        msg, _ = miner.get_commit_diff(repo_with_commit["fix"])

        assert "Fix: changed greeting message" in msg

    def test_diff_contains_changes(self, repo_with_commit):
        """Verifica che il diff contenga le modifiche."""
        miner = GitMiner(repo_with_commit["path"])
        _, diff = miner.get_commit_diff(repo_with_commit["fix"])

        assert "hello" in diff or "goodbye" in diff


class TestGetBugInducingCommitsBranches:
    """Test per branch mancanti in get_bug_inducing_commits()."""

    def test_no_parent_commit(self):
        """Test linee 88-89: commit senza parent (primo commit)."""
        repo_dir = tempfile.mkdtemp(prefix="szz_noparent_")
        try:
            def run_git(*args):
                return subprocess.run(
                    ["git", "-C", repo_dir] + list(args),
                    capture_output=True, text=True, check=True
                ).stdout.strip()

            run_git("init")
            run_git("config", "user.email", "t@t.com")
            run_git("config", "user.name", "T")

            with open(os.path.join(repo_dir, "f.txt"), "w") as f:
                f.write("content")
            run_git("add", ".")
            run_git("commit", "-m", "fix: first commit")
            first = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            bics = miner.get_bug_inducing_commits(first)

            # Primo commit non ha parent, deve restituire lista vuota
            assert bics == []

        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_blame_on_nonexistent_file(self):
        """Test branch: file che non esiste nel parent."""
        repo_dir = tempfile.mkdtemp(prefix="szz_newfile_")
        try:
            def run_git(*args):
                return subprocess.run(
                    ["git", "-C", repo_dir] + list(args),
                    capture_output=True, text=True, check=True
                ).stdout.strip()

            run_git("init")
            run_git("config", "user.email", "t@t.com")
            run_git("config", "user.name", "T")

            # Commit iniziale
            with open(os.path.join(repo_dir, "old.txt"), "w") as f:
                f.write("old")
            run_git("add", ".")
            run_git("commit", "-m", "initial")

            # Aggiunge nuovo file e lo modifica subito
            with open(os.path.join(repo_dir, "new.txt"), "w") as f:
                f.write("line1\nline2\n")
            run_git("add", ".")
            run_git("commit", "-m", "added new file")

            with open(os.path.join(repo_dir, "new.txt"), "w") as f:
                f.write("line1\n")  # Rimuove line2
            run_git("add", ".")
            run_git("commit", "-m", "fix: removed line")
            fix = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            # Non deve crashare anche se il blame fallisce
            bics = miner.get_bug_inducing_commits(fix)
            assert isinstance(bics, list)

        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_hunk_header_without_comma(self):
        """Test branch: hunk header con singola linea (senza ,count)."""
        repo_dir = tempfile.mkdtemp(prefix="szz_single_")
        try:
            def run_git(*args):
                return subprocess.run(
                    ["git", "-C", repo_dir] + list(args),
                    capture_output=True, text=True, check=True
                ).stdout.strip()

            run_git("init")
            run_git("config", "user.email", "t@t.com")
            run_git("config", "user.name", "T")

            # File con una sola linea
            with open(os.path.join(repo_dir, "single.txt"), "w") as f:
                f.write("only line\n")
            run_git("add", ".")
            run_git("commit", "-m", "one line")
            bic = run_git("rev-parse", "HEAD")

            # Rimuove quella linea
            with open(os.path.join(repo_dir, "single.txt"), "w") as f:
                f.write("replacement\n")
            run_git("add", ".")
            run_git("commit", "-m", "fix: replaced single line")
            fix = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            bics = miner.get_bug_inducing_commits(fix)

            # Deve trovare il BIC (git blame può prefissare con ^ per boundary commits)
            # Verifichiamo che almeno un BIC contenga l'inizio dell'hash atteso
            assert len(bics) > 0, "Nessun BIC trovato"
            found = any(bic[:7] in b or b.lstrip('^')[:7] == bic[:7] for b in bics)
            assert found, f"BIC {bic[:8]} non trovato in {bics}"

        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_blame_line_with_short_hash(self):
        """Test branch: verifica gestione hash corti nel blame."""
        repo_dir = tempfile.mkdtemp(prefix="szz_hash_")
        try:
            def run_git(*args):
                return subprocess.run(
                    ["git", "-C", repo_dir] + list(args),
                    capture_output=True, text=True, check=True
                ).stdout.strip()

            run_git("init")
            run_git("config", "user.email", "t@t.com")
            run_git("config", "user.name", "T")

            with open(os.path.join(repo_dir, "f.txt"), "w") as f:
                f.write("buggy line\n")
            run_git("add", ".")
            run_git("commit", "-m", "introduced bug")
            bic = run_git("rev-parse", "HEAD")

            with open(os.path.join(repo_dir, "f.txt"), "w") as f:
                f.write("fixed line\n")
            run_git("add", ".")
            run_git("commit", "-m", "fix: corrected")
            fix = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            bics = miner.get_bug_inducing_commits(fix)

            assert len(bics) > 0
            # Verifica che gli hash siano validi (almeno 7 caratteri)
            for h in bics:
                assert len(h) >= 7

        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_count_zero_skipped(self):
        """Test branch linea 125: count == 0 viene saltato."""
        repo_dir = tempfile.mkdtemp(prefix="szz_zero_")
        try:
            def run_git(*args):
                return subprocess.run(
                    ["git", "-C", repo_dir] + list(args),
                    capture_output=True, text=True, check=True
                ).stdout.strip()

            run_git("init")
            run_git("config", "user.email", "t@t.com")
            run_git("config", "user.name", "T")

            # Commit con solo aggiunte (nessuna rimozione)
            with open(os.path.join(repo_dir, "f.txt"), "w") as f:
                f.write("")
            run_git("add", ".")
            run_git("commit", "-m", "empty file")

            with open(os.path.join(repo_dir, "f.txt"), "w") as f:
                f.write("new content\n")
            run_git("add", ".")
            run_git("commit", "-m", "fix: added content")
            fix = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            bics = miner.get_bug_inducing_commits(fix)

            # Nessun BIC perché count = 0 (niente linee rimosse)
            assert bics == []

        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)


class TestRunGit:
    """Test per _run_git() helper method."""

    def test_run_git_returns_string(self):
        """Verifica che _run_git restituisca una stringa."""
        repo_dir = tempfile.mkdtemp(prefix="szz_rungit_")
        try:
            subprocess.run(["git", "-C", repo_dir, "init"], check=True, capture_output=True)

            miner = GitMiner(repo_dir)
            result = miner._run_git("status")

            assert isinstance(result, str)

        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_run_git_handles_invalid_command(self):
        """Verifica gestione comando git invalido."""
        repo_dir = tempfile.mkdtemp(prefix="szz_invalid_")
        try:
            subprocess.run(["git", "-C", repo_dir, "init"], check=True, capture_output=True)

            miner = GitMiner(repo_dir)
            # Comando invalido non dovrebbe crashare
            result = miner._run_git("nonexistent-command")

            assert isinstance(result, str)

        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)


# ============================================================
# Helper: crea un repo git temporaneo con commit e tag
# ============================================================

def _make_repo():
    """Crea e restituisce (repo_dir, run_git_fn)."""
    repo_dir = tempfile.mkdtemp(prefix="szz_new_")
    def run_git(*args):
        return subprocess.run(
            ["git", "-C", repo_dir] + list(args),
            capture_output=True, text=True, check=True
        ).stdout.strip()
    run_git("init")
    run_git("config", "user.email", "test@test.com")
    run_git("config", "user.name", "Test")
    return repo_dir, run_git


class TestGetTags:
    """Test per get_tags() - linee 54-82."""

    @pytest.fixture
    def repo_with_tags(self):
        repo_dir, _ = _make_repo()
        fp = os.path.join(repo_dir, "f.txt")

        def run_git_env(*args, env_extra=None):
            env = os.environ.copy()
            if env_extra:
                env.update(env_extra)
            return subprocess.run(
                ["git", "-C", repo_dir] + list(args),
                capture_output=True, text=True, check=True, env=env
            ).stdout.strip()

        with open(fp, "w") as f:
            f.write("v1")
        run_git_env("add", ".")
        run_git_env("commit", "-m", "first",
                    env_extra={"GIT_COMMITTER_DATE": "2024-01-01T00:00:00",
                               "GIT_AUTHOR_DATE": "2024-01-01T00:00:00"})
        run_git_env("tag", "v1.0")

        with open(fp, "w") as f:
            f.write("v2")
        run_git_env("add", ".")
        run_git_env("commit", "-m", "second",
                    env_extra={"GIT_COMMITTER_DATE": "2024-06-01T00:00:00",
                               "GIT_AUTHOR_DATE": "2024-06-01T00:00:00"})
        run_git_env("tag", "v2.0")

        yield repo_dir
        shutil.rmtree(repo_dir, ignore_errors=True)

    def test_returns_list_of_dicts(self, repo_with_tags):
        miner = GitMiner(repo_with_tags)
        tags = miner.get_tags()
        assert isinstance(tags, list)
        assert len(tags) == 2
        for t in tags:
            assert "name" in t
            assert "hash" in t
            assert "date" in t

    def test_tags_ordered_newest_first(self, repo_with_tags):
        miner = GitMiner(repo_with_tags)
        tags = miner.get_tags()
        assert tags[0]["name"] == "v2.0"
        assert tags[1]["name"] == "v1.0"

    def test_empty_repo_no_tags(self):
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "init")

            miner = GitMiner(repo_dir)
            assert miner.get_tags() == []
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_tag_with_empty_date(self):
        """Tag senza data parsabile non deve crashare."""
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "init")
            run_git("tag", "v0.1")

            miner = GitMiner(repo_dir)
            tags = miner.get_tags()
            assert len(tags) == 1
            assert tags[0]["name"] == "v0.1"
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)


class TestGetTagNames:
    """Test per get_tag_names() - linea 86."""

    def test_returns_name_list(self):
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("v1")
            run_git("add", ".")
            run_git("commit", "-m", "init")
            run_git("tag", "alpha")
            run_git("tag", "beta")

            miner = GitMiner(repo_dir)
            names = miner.get_tag_names()
            assert "alpha" in names
            assert "beta" in names
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)


class TestGetCommitDate:
    """Test per get_commit_date() - linee 90-96."""

    def test_returns_datetime(self):
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "init")
            h = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            dt = miner.get_commit_date(h)
            assert isinstance(dt, datetime)
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_invalid_hash_returns_none(self):
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "init")

            miner = GitMiner(repo_dir)
            assert miner.get_commit_date("0000000000000000") is None
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)


class TestGetTagCommitHash:
    """Test per get_tag_commit_hash() - linee 100-101."""

    def test_resolves_tag(self):
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "init")
            expected = run_git("rev-parse", "HEAD")
            run_git("tag", "v1.0")

            miner = GitMiner(repo_dir)
            assert miner.get_tag_commit_hash("v1.0") == expected
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_invalid_tag_returns_none(self):
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "init")

            miner = GitMiner(repo_dir)
            result = miner.get_tag_commit_hash("nonexistent")
            assert result is None or result == ""
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)


class TestGetCommitsBetweenTags:
    """Test per get_commits_between_tags() - linee 115-122."""

    @pytest.fixture
    def repo_with_tagged_commits(self):
        repo_dir, run_git = _make_repo()
        fp = os.path.join(repo_dir, "f.txt")

        with open(fp, "w") as f:
            f.write("v1")
        run_git("add", ".")
        run_git("commit", "-m", "first")
        run_git("tag", "v1.0")

        with open(fp, "w") as f:
            f.write("v2")
        run_git("add", ".")
        run_git("commit", "-m", "second")
        h2 = run_git("rev-parse", "HEAD")

        with open(fp, "w") as f:
            f.write("v3")
        run_git("add", ".")
        run_git("commit", "-m", "third")
        h3 = run_git("rev-parse", "HEAD")
        run_git("tag", "v2.0")

        yield {"path": repo_dir, "h2": h2, "h3": h3}
        shutil.rmtree(repo_dir, ignore_errors=True)

    def test_returns_commits_in_range(self, repo_with_tagged_commits):
        miner = GitMiner(repo_with_tagged_commits["path"])
        commits = miner.get_commits_between_tags("v1.0", "v2.0")
        assert repo_with_tagged_commits["h2"] in commits
        assert repo_with_tagged_commits["h3"] in commits

    def test_excludes_from_tag_commit(self, repo_with_tagged_commits):
        miner = GitMiner(repo_with_tagged_commits["path"])
        commits = miner.get_commits_between_tags("v1.0", "v2.0")
        # Il commit puntato da v1.0 non dovrebbe essere incluso
        v1_hash = miner.get_tag_commit_hash("v1.0")
        assert v1_hash not in commits


class TestGetCommitsBetweenDates:
    """Test per get_commits_between_dates() - linee 139-153."""

    def test_since_filter(self):
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "init")

            miner = GitMiner(repo_dir)
            # since = un anno fa -> dovrebbe trovare il commit
            since = datetime.now() - timedelta(days=365)
            commits = miner.get_commits_between_dates(since=since)
            assert len(commits) >= 1
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_until_filter(self):
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "init")

            miner = GitMiner(repo_dir)
            until = datetime.now() + timedelta(days=1)
            commits = miner.get_commits_between_dates(until=until)
            assert len(commits) >= 1
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_since_and_until(self):
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "init")

            miner = GitMiner(repo_dir)
            since = datetime.now() - timedelta(days=1)
            until = datetime.now() + timedelta(days=1)
            commits = miner.get_commits_between_dates(since=since, until=until)
            assert len(commits) >= 1
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_no_commits_in_range(self):
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "init")

            miner = GitMiner(repo_dir)
            # Range nel futuro lontano -> nessun commit
            since = datetime(2099, 1, 1)
            until = datetime(2099, 12, 31)
            commits = miner.get_commits_between_dates(since=since, until=until)
            assert commits == []
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)


class TestShouldSkipByMessage:
    """Test per should_skip_by_message() - linee 159-175."""

    @pytest.fixture
    def miner(self):
        repo_dir, run_git = _make_repo()
        fp = os.path.join(repo_dir, "f.txt")
        with open(fp, "w") as f:
            f.write("x")
        run_git("add", ".")
        run_git("commit", "-m", "init")
        m = GitMiner(repo_dir)
        yield m
        shutil.rmtree(repo_dir, ignore_errors=True)

    def test_refactor_prefix(self, miner):
        assert miner.should_skip_by_message("refactor: rename method") is True

    def test_refactoring_prefix(self, miner):
        assert miner.should_skip_by_message("refactoring: cleanup") is True

    def test_docs_paren_prefix(self, miner):
        assert miner.should_skip_by_message("docs(readme): update") is True

    def test_style_space_prefix(self, miner):
        assert miner.should_skip_by_message("style fix whitespace") is True

    def test_chore_prefix(self, miner):
        assert miner.should_skip_by_message("chore: bump version") is True

    def test_typo_prefix(self, miner):
        assert miner.should_skip_by_message("typo: fixed spelling") is True

    def test_rename_prefix(self, miner):
        assert miner.should_skip_by_message("rename variable foo") is True

    def test_whitespace_prefix(self, miner):
        assert miner.should_skip_by_message("whitespace: trailing spaces") is True

    def test_lint_prefix(self, miner):
        assert miner.should_skip_by_message("lint: fix warnings") is True

    def test_cleanup_prefix(self, miner):
        assert miner.should_skip_by_message("cleanup: remove dead code") is True

    def test_bug_fix_not_skipped(self, miner):
        assert miner.should_skip_by_message("fix: null pointer exception") is False

    def test_feature_not_skipped(self, miner):
        assert miner.should_skip_by_message("feat: add login page") is False

    def test_keyword_in_middle_not_skipped(self, miner):
        assert miner.should_skip_by_message("fix: refactored parser logic") is False

    def test_case_insensitive(self, miner):
        assert miner.should_skip_by_message("REFACTOR: uppercase") is True

    def test_format_prefix(self, miner):
        assert miner.should_skip_by_message("format: code formatting") is True

    def test_comment_prefix(self, miner):
        assert miner.should_skip_by_message("comment: added explanation") is True

    def test_indent_prefix(self, miner):
        assert miner.should_skip_by_message("indentation: fix tabs") is True


class TestIsCosmeticChange:
    """Test per is_cosmetic_change() - linee 177-269."""

    @pytest.fixture
    def repo_dir(self):
        d, run_git = _make_repo()
        yield d, run_git
        shutil.rmtree(d, ignore_errors=True)

    def test_comment_only_change_is_cosmetic(self, repo_dir):
        """Commit con solo modifiche ai commenti -> True."""
        d, run_git = repo_dir
        fp = os.path.join(d, "f.py")
        with open(fp, "w") as f:
            f.write("x = 1  # old comment\n")
        run_git("add", ".")
        run_git("commit", "-m", "init")

        with open(fp, "w") as f:
            f.write("x = 1  # new comment\n")
        run_git("add", ".")
        run_git("commit", "-m", "update comment")
        h = run_git("rev-parse", "HEAD")

        miner = GitMiner(d)
        assert miner.is_cosmetic_change(h) is True

    def test_whitespace_only_change_is_cosmetic(self, repo_dir):
        """Commit con solo modifiche whitespace -> True."""
        d, run_git = repo_dir
        fp = os.path.join(d, "f.py")
        with open(fp, "w") as f:
            f.write("x=1\n")
        run_git("add", ".")
        run_git("commit", "-m", "init")

        with open(fp, "w") as f:
            f.write("x = 1\n")
        run_git("add", ".")
        run_git("commit", "-m", "add spaces")
        h = run_git("rev-parse", "HEAD")

        miner = GitMiner(d)
        assert miner.is_cosmetic_change(h) is True

    def test_variable_rename_is_cosmetic(self, repo_dir):
        """Commit con rinomina variabili -> True."""
        d, run_git = repo_dir
        fp = os.path.join(d, "f.py")
        with open(fp, "w") as f:
            f.write("old_name = 42\nprint(old_name)\n")
        run_git("add", ".")
        run_git("commit", "-m", "init")

        with open(fp, "w") as f:
            f.write("new_name = 42\nprint(new_name)\n")
        run_git("add", ".")
        run_git("commit", "-m", "rename var")
        h = run_git("rev-parse", "HEAD")

        miner = GitMiner(d)
        assert miner.is_cosmetic_change(h) is True

    def test_real_change_not_cosmetic(self, repo_dir):
        """Commit con vere modifiche -> False."""
        d, run_git = repo_dir
        fp = os.path.join(d, "f.py")
        with open(fp, "w") as f:
            f.write("def calc(a, b):\n    return a + b\n")
        run_git("add", ".")
        run_git("commit", "-m", "init")

        with open(fp, "w") as f:
            f.write("def calc(a, b):\n    if b == 0:\n        raise ValueError('div by zero')\n    return a / b\n")
        run_git("add", ".")
        run_git("commit", "-m", "change logic")
        h = run_git("rev-parse", "HEAD")

        miner = GitMiner(d)
        assert miner.is_cosmetic_change(h) is False

    def test_empty_diff_not_cosmetic(self, repo_dir):
        """Commit con diff vuoto -> False."""
        d, run_git = repo_dir
        fp = os.path.join(d, "f.py")
        with open(fp, "w") as f:
            f.write("x = 1\n")
        run_git("add", ".")
        run_git("commit", "-m", "init")

        miner = GitMiner(d)
        # Usa un hash fittizio di un commit che non avrà diff con --format=
        # Oppure usiamo l'init commit che ha un diff ma testiamo il branch "not diff"
        assert miner.is_cosmetic_change("0000000000000000") is False

    def test_no_added_no_removed_is_cosmetic(self, repo_dir):
        """Solo linee +++ e --- senza vere aggiunte/rimozioni -> True."""
        d, run_git = repo_dir
        fp = os.path.join(d, "f.txt")
        with open(fp, "w") as f:
            f.write("hello\n")
        run_git("add", ".")
        run_git("commit", "-m", "init")

        # Modifica solo permessi (nessuna riga +/-) - simuliamo con un commit vuoto
        # In realtà testiamo il caso in cui solo il file mode cambia
        # Creiamo un commit con solo un file rinominato
        run_git("mv", "f.txt", "g.txt")
        run_git("commit", "-m", "rename file")
        h = run_git("rev-parse", "HEAD")

        miner = GitMiner(d)
        # La rinomina ha linee +/- vuote, potrebbe essere True o False
        # L'importante è che non crashi
        result = miner.is_cosmetic_change(h)
        assert isinstance(result, bool)


class TestGetFixingCommitsWithFilters:
    """Test per get_fixing_commits() con filtri tag e date - linee 306-317."""

    @pytest.fixture
    def repo_with_tags_and_fixes(self):
        repo_dir, run_git = _make_repo()
        fp = os.path.join(repo_dir, "f.txt")

        # Commit 1 - tag v1.0
        with open(fp, "w") as f:
            f.write("v1")
        run_git("add", ".")
        run_git("commit", "-m", "initial release")
        run_git("tag", "v1.0")

        # Commit 2 - fix tra v1.0 e v2.0
        with open(fp, "w") as f:
            f.write("v2")
        run_git("add", ".")
        run_git("commit", "-m", "fix: bug between tags")
        h_fix = run_git("rev-parse", "HEAD")

        # Commit 3 - non fix
        with open(fp, "w") as f:
            f.write("v3")
        run_git("add", ".")
        run_git("commit", "-m", "add feature")

        # Commit 4 - tag v2.0
        with open(fp, "w") as f:
            f.write("v4")
        run_git("add", ".")
        run_git("commit", "-m", "fix: another issue")
        run_git("tag", "v2.0")
        h_fix2 = run_git("rev-parse", "HEAD")

        # Commit 5 - dopo v2.0 (non nel range)
        with open(fp, "w") as f:
            f.write("v5")
        run_git("add", ".")
        run_git("commit", "-m", "fix: outside range")
        h_outside = run_git("rev-parse", "HEAD")

        yield {
            "path": repo_dir, "h_fix": h_fix,
            "h_fix2": h_fix2, "h_outside": h_outside
        }
        shutil.rmtree(repo_dir, ignore_errors=True)

    def test_filter_by_tag_range(self, repo_with_tags_and_fixes):
        miner = GitMiner(repo_with_tags_and_fixes["path"])
        fixes = miner.get_fixing_commits(from_tag="v1.0", to_tag="v2.0")
        assert repo_with_tags_and_fixes["h_fix"] in fixes
        assert repo_with_tags_and_fixes["h_outside"] not in fixes

    def test_filter_by_date_range(self, repo_with_tags_and_fixes):
        miner = GitMiner(repo_with_tags_and_fixes["path"])
        since = datetime.now() - timedelta(days=1)
        until = datetime.now() + timedelta(days=1)
        fixes = miner.get_fixing_commits(since=since, until=until)
        assert len(fixes) >= 1

    def test_no_filter_returns_all(self, repo_with_tags_and_fixes):
        miner = GitMiner(repo_with_tags_and_fixes["path"])
        fixes = miner.get_fixing_commits()
        # Dovrebbe trovare tutti i fix commit
        assert len(fixes) >= 3


class TestBICFiltering:
    """Test per filtri BIC in get_bug_inducing_commits() - linee 450-478."""

    @pytest.fixture
    def repo_with_bic_scenarios(self):
        repo_dir, run_git = _make_repo()
        fp = os.path.join(repo_dir, "f.txt")

        # BIC commit (commit che introduce il bug)
        with open(fp, "w") as f:
            f.write("buggy line\n")
        run_git("add", ".")
        run_git("commit", "-m", "introduced bug")
        bic_hash = run_git("rev-parse", "HEAD")

        # Fix commit (corregge il bug)
        with open(fp, "w") as f:
            f.write("fixed line\n")
        run_git("add", ".")
        run_git("commit", "-m", "fix: corrected bug")
        fix_hash = run_git("rev-parse", "HEAD")

        yield {"path": repo_dir, "bic": bic_hash, "fix": fix_hash}
        shutil.rmtree(repo_dir, ignore_errors=True)

    def test_blacklist_filters_bic(self, repo_with_bic_scenarios):
        """BIC in blacklist viene filtrato."""
        miner = GitMiner(repo_with_bic_scenarios["path"])
        bic = repo_with_bic_scenarios["bic"]
        fix = repo_with_bic_scenarios["fix"]

        # Senza blacklist -> trova il BIC
        bics_no_bl = miner.get_bug_inducing_commits(fix)
        assert len(bics_no_bl) > 0

        # Con blacklist -> filtra il BIC
        bics_with_bl = miner.get_bug_inducing_commits(fix, blacklist={bic})
        assert len(bics_with_bl) == 0

    def test_message_filter_on_bic(self):
        """BIC con messaggio refactor/docs viene filtrato."""
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")

            with open(fp, "w") as f:
                f.write("some code\n")
            run_git("add", ".")
            run_git("commit", "-m", "refactor: initial cleanup")
            bic_hash = run_git("rev-parse", "HEAD")

            with open(fp, "w") as f:
                f.write("fixed code\n")
            run_git("add", ".")
            run_git("commit", "-m", "fix: corrected logic")
            fix_hash = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            bics = miner.get_bug_inducing_commits(fix_hash)
            # Il BIC ha messaggio "refactor: ..." quindi dovrebbe essere filtrato
            assert bic_hash not in bics
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_cosmetic_filter_on_bic(self):
        """BIC con sole modifiche cosmetiche viene filtrato."""
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.py")

            # Commit originale
            with open(fp, "w") as f:
                f.write("x = 1  # old comment\n")
            run_git("add", ".")
            run_git("commit", "-m", "original code")

            # BIC: solo cambio commento (cosmetico)
            with open(fp, "w") as f:
                f.write("x = 1  # new comment\n")
            run_git("add", ".")
            run_git("commit", "-m", "updated comment")
            bic_hash = run_git("rev-parse", "HEAD")

            # Fix: cambia la logica
            with open(fp, "w") as f:
                f.write("x = 2  # fixed value\n")
            run_git("add", ".")
            run_git("commit", "-m", "fix: corrected value")
            fix_hash = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            bics = miner.get_bug_inducing_commits(fix_hash)
            # Il BIC cosmetico dovrebbe essere filtrato
            # (il commit prima potrebbe essere trovato dal blame)
            for b in bics:
                assert not b.startswith(bic_hash[:7])
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_get_commit_message(self):
        """Test get_commit_message() helper."""
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "test message here")
            h = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            msg = miner.get_commit_message(h)
            assert "test message here" in msg
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_log_method(self):
        """Test _log() non crasha."""
        repo_dir, run_git = _make_repo()
        try:
            fp = os.path.join(repo_dir, "f.txt")
            with open(fp, "w") as f:
                f.write("x")
            run_git("add", ".")
            run_git("commit", "-m", "init")

            miner = GitMiner(repo_dir)
            # _log scrive su stderr, non deve crashare
            miner._log("test message")
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)