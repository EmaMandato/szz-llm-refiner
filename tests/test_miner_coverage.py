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
import pytest

from szz_llm_project.miner import GitMiner


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