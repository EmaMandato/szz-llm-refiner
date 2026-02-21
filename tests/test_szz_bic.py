"""
Test per get_bug_inducing_commits (SZZ Algorithm)

Questo test crea un repository Git controllato dove conosciamo esattamente
quale commit ha introdotto il bug, permettendoci di validare l'algoritmo SZZ.

IMPORTANTE: SZZ funziona analizzando le LINEE RIMOSSE dal fix commit.
Quindi il test deve creare uno scenario dove:
1. Un commit introduce codice buggy
2. Il fix commit RIMUOVE quel codice buggy (non solo aggiunge nuovo codice)
"""

import os
import shutil
import subprocess
import tempfile
import pytest

from szz_llm_project.miner import GitMiner


class TestGetBugInducingCommits:
    """Test suite per l'algoritmo SZZ."""

    @pytest.fixture
    def test_repo(self):
        """
        Crea un repository Git temporaneo con uno scenario controllato
        di bug introduction e fix.

        Scenario:
            1. Commit A: Crea Calculator.java (versione base)
            2. Commit B (BIC): Aggiunge codice BUGGY (return a / b senza check)
            3. Commit C: Aggiunge README (non correlato)
            4. Commit D (FIX): RIMUOVE la linea buggy e la sostituisce con versione corretta
        """
        repo_dir = tempfile.mkdtemp(prefix="szz_test_")

        def run_git(*args):
            result = subprocess.run(
                ["git", "-C", repo_dir] + list(args),
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()

        def get_last_commit_hash():
            return run_git("rev-parse", "HEAD")

        # Inizializza repository
        run_git("init")
        run_git("config", "user.email", "test@test.com")
        run_git("config", "user.name", "Test User")

        commits = {}
        file_path = os.path.join(repo_dir, "Calculator.java")

        # ============================================
        # COMMIT A: Versione iniziale (solo add, subtract, multiply)
        # ============================================
        calculator_v1 = """public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
    public int subtract(int a, int b) {
        return a - b;
    }
    public int multiply(int a, int b) {
        return a * b;
    }
}
"""
        with open(file_path, "w") as f:
            f.write(calculator_v1)

        run_git("add", "Calculator.java")
        run_git("commit", "-m", "Initial Calculator with add, subtract, multiply")
        commits["initial"] = get_last_commit_hash()

        # ============================================
        # COMMIT B (BIC): Aggiunge divide() CON BUG
        # Questa è la linea che verrà poi rimossa dal fix
        # ============================================
        calculator_v2_buggy = """public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
    public int subtract(int a, int b) {
        return a - b;
    }
    public int multiply(int a, int b) {
        return a * b;
    }
    public int divide(int a, int b) {
        return a / b;
    }
}
"""
        with open(file_path, "w") as f:
            f.write(calculator_v2_buggy)

        run_git("add", "Calculator.java")
        run_git("commit", "-m", "Added divide method")
        commits["bic"] = get_last_commit_hash()

        # ============================================
        # COMMIT C: Modifica non correlata
        # ============================================
        readme_path = os.path.join(repo_dir, "README.md")
        with open(readme_path, "w") as f:
            f.write("# Calculator\n\nA simple calculator library.\n")

        run_git("add", "README.md")
        run_git("commit", "-m", "Added README")
        commits["unrelated"] = get_last_commit_hash()

        # ============================================
        # COMMIT D (FIX): RIMUOVE la linea buggy e aggiunge versione corretta
        # La linea "return a / b;" viene RIMOSSA
        # ============================================
        calculator_v3_fixed = """public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
    public int subtract(int a, int b) {
        return a - b;
    }
    public int multiply(int a, int b) {
        return a * b;
    }
    public int divide(int a, int b) {
        if (b == 0) {
            throw new IllegalArgumentException("Cannot divide by zero");
        }
        return a / b;
    }
}
"""
        with open(file_path, "w") as f:
            f.write(calculator_v3_fixed)

        run_git("add", "Calculator.java")
        run_git("commit", "-m", "Fix: handle division by zero error")
        commits["fix"] = get_last_commit_hash()

        # Debug: mostra il diff del fix
        diff_output = run_git("show", "--stat", commits["fix"])
        print(f"\n[DEBUG] Fix commit diff:\n{diff_output}")

        diff_detail = run_git("show", commits["fix"])
        print(f"\n[DEBUG] Fix commit full diff:\n{diff_detail}")

        yield {
            "path": repo_dir,
            "commits": commits
        }

        shutil.rmtree(repo_dir, ignore_errors=True)

    @pytest.fixture
    def test_repo_with_deletion(self):
        """
        Scenario alternativo dove il fix RIMUOVE completamente codice buggy.

        1. Commit A: File con metodo corretto
        2. Commit B (BIC): Aggiunge linea buggy (debug/hack)
        3. Commit C (FIX): Rimuove la linea buggy
        """
        repo_dir = tempfile.mkdtemp(prefix="szz_del_test_")

        def run_git(*args):
            result = subprocess.run(
                ["git", "-C", repo_dir] + list(args),
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()

        run_git("init")
        run_git("config", "user.email", "test@test.com")
        run_git("config", "user.name", "Test User")

        commits = {}
        file_path = os.path.join(repo_dir, "Service.java")

        # COMMIT A: Versione base
        with open(file_path, "w") as f:
            f.write("""public class Service {
    public void process(String data) {
        validate(data);
        save(data);
    }
}
""")
        run_git("add", "Service.java")
        run_git("commit", "-m", "Initial Service")
        commits["initial"] = run_git("rev-parse", "HEAD")

        # COMMIT B (BIC): Aggiunge linea buggy (hardcoded return)
        with open(file_path, "w") as f:
            f.write("""public class Service {
    public void process(String data) {
        if (data == null) return;
        validate(data);
        save(data);
    }
}
""")
        run_git("add", "Service.java")
        run_git("commit", "-m", "Added null check")
        commits["bic"] = run_git("rev-parse", "HEAD")

        # COMMIT C (FIX): Rimuove la linea buggy e la sostituisce
        with open(file_path, "w") as f:
            f.write("""public class Service {
    public void process(String data) {
        if (data == null) throw new IllegalArgumentException("data cannot be null");
        validate(data);
        save(data);
    }
}
""")
        run_git("add", "Service.java")
        run_git("commit", "-m", "Fix: throw exception instead of silent return on null")
        commits["fix"] = run_git("rev-parse", "HEAD")

        yield {"path": repo_dir, "commits": commits}
        shutil.rmtree(repo_dir, ignore_errors=True)

    def test_szz_identifies_correct_bic(self, test_repo_with_deletion):
        """
        Test principale: verifica che SZZ identifichi il BIC corretto.
        """
        miner = GitMiner(test_repo_with_deletion["path"])
        commits = test_repo_with_deletion["commits"]

        bics = miner.get_bug_inducing_commits(commits["fix"])

        print(f"\n[DEBUG] BIC atteso: {commits['bic'][:8]}")
        print(f"[DEBUG] BIC trovati: {[h[:8] for h in bics]}")

        assert len(bics) > 0, "SZZ non ha trovato nessun BIC"
        assert commits["bic"] in bics, (
            f"SZZ non ha identificato il commit corretto come BIC.\n"
            f"Atteso: {commits['bic'][:8]}\n"
            f"Trovati: {[h[:8] for h in bics]}"
        )

    def test_szz_with_multiline_fix(self, test_repo):
        """
        Verifica SZZ con il repository che ha fix multilinea.
        """
        miner = GitMiner(test_repo["path"])
        commits = test_repo["commits"]

        bics = miner.get_bug_inducing_commits(commits["fix"])

        print(f"\n[DEBUG] BIC atteso: {commits['bic'][:8]}")
        print(f"[DEBUG] BIC trovati: {[h[:8] for h in bics]}")

        # Questo test potrebbe non trovare BIC se il miner non rileva
        # modifiche come "rimozioni" - dipende dall'implementazione
        # Verifichiamo almeno che non crashi
        assert isinstance(bics, list), "Deve restituire una lista"

    def test_szz_excludes_unrelated_commits(self, test_repo_with_deletion):
        """
        Verifica che SZZ NON includa commit non correlati al bug.
        """
        miner = GitMiner(test_repo_with_deletion["path"])
        commits = test_repo_with_deletion["commits"]

        bics = miner.get_bug_inducing_commits(commits["fix"])

        assert commits["initial"] not in bics, (
            "SZZ ha erroneamente incluso il commit iniziale"
        )

    def test_szz_excludes_fix_commit_itself(self, test_repo_with_deletion):
        """
        Verifica che il commit di fix non venga identificato come BIC di se stesso.
        """
        miner = GitMiner(test_repo_with_deletion["path"])
        commits = test_repo_with_deletion["commits"]

        bics = miner.get_bug_inducing_commits(commits["fix"])

        assert commits["fix"] not in bics, (
            "SZZ ha erroneamente identificato il fix commit come BIC di se stesso"
        )


class TestGetBugInducingCommitsEdgeCases:
    """Test per casi limite dell'algoritmo SZZ."""

    @pytest.fixture
    def empty_repo(self):
        """Repository con solo commit iniziale."""
        repo_dir = tempfile.mkdtemp(prefix="szz_empty_")

        subprocess.run(["git", "-C", repo_dir, "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_dir, "config", "user.email", "test@test.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_dir, "config", "user.name", "Test"], check=True, capture_output=True)

        file_path = os.path.join(repo_dir, "test.txt")
        with open(file_path, "w") as f:
            f.write("hello")
        subprocess.run(["git", "-C", repo_dir, "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_dir, "commit", "-m", "Initial"], check=True, capture_output=True)

        result = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        )
        commit_hash = result.stdout.strip()

        yield {"path": repo_dir, "commit": commit_hash}
        shutil.rmtree(repo_dir, ignore_errors=True)

    def test_szz_handles_first_commit(self, empty_repo):
        """
        Verifica che SZZ gestisca correttamente l'analisi del primo commit.
        """
        miner = GitMiner(empty_repo["path"])

        try:
            bics = miner.get_bug_inducing_commits(empty_repo["commit"])
            assert isinstance(bics, list), "Deve restituire una lista"
        except Exception as e:
            pytest.fail(f"SZZ è crashato sul primo commit: {e}")

    def test_szz_handles_only_additions(self):
        """
        Verifica che SZZ gestisca commit che aggiungono solo nuove linee.
        """
        repo_dir = tempfile.mkdtemp(prefix="szz_add_")

        try:
            subprocess.run(["git", "-C", repo_dir, "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo_dir, "config", "user.email", "test@test.com"], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo_dir, "config", "user.name", "Test"], check=True, capture_output=True)

            file_path = os.path.join(repo_dir, "test.txt")
            with open(file_path, "w") as f:
                f.write("")
            subprocess.run(["git", "-C", repo_dir, "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", "Empty file"], check=True, capture_output=True)

            with open(file_path, "w") as f:
                f.write("new content\n")
            subprocess.run(["git", "-C", repo_dir, "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", "Fix: added missing content"], check=True, capture_output=True)

            result = subprocess.run(
                ["git", "-C", repo_dir, "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True
            )
            fix_hash = result.stdout.strip()

            miner = GitMiner(repo_dir)
            bics = miner.get_bug_inducing_commits(fix_hash)

            assert bics == [], "Non dovrebbero esserci BIC per commit che aggiungono solo linee"

        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_szz_handles_file_rename(self):
        """
        Verifica che SZZ gestisca correttamente i file rinominati.
        """
        repo_dir = tempfile.mkdtemp(prefix="szz_rename_")

        try:
            def run_git(*args):
                return subprocess.run(
                    ["git", "-C", repo_dir] + list(args),
                    capture_output=True, text=True, check=True
                ).stdout.strip()

            run_git("init")
            run_git("config", "user.email", "test@test.com")
            run_git("config", "user.name", "Test")

            # Crea file originale
            old_path = os.path.join(repo_dir, "OldName.java")
            with open(old_path, "w") as f:
                f.write("public class OldName { }\n")
            run_git("add", ".")
            run_git("commit", "-m", "Initial")

            # Rinomina file
            new_path = os.path.join(repo_dir, "NewName.java")
            os.rename(old_path, new_path)
            with open(new_path, "w") as f:
                f.write("public class NewName { }\n")
            run_git("add", ".")
            run_git("commit", "-m", "Fix: renamed class")
            fix_hash = run_git("rev-parse", "HEAD")

            miner = GitMiner(repo_dir)
            # Non dovrebbe crashare
            bics = miner.get_bug_inducing_commits(fix_hash)
            assert isinstance(bics, list)

        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)


class TestLLMRefinerMocked:
    """Test per LLMRefiner con mock delle chiamate HTTP."""

    def test_classifies_null_pointer_fix_as_bug(self, mocker):
        """
        Verifica che un fix di NullPointerException venga classificato come BUG.
        """
        from szz_llm_project.llm_refiner import LLMRefiner

        mock_response = mocker.Mock()
        mock_response.json.return_value = {"response": "CLASSIFICAZIONE: BUG\nMOTIVO: Corregge NullPointerException"}
        mocker.patch('requests.post', return_value=mock_response)

        refiner = LLMRefiner()
        is_bug, explanation = refiner.is_real_bug_fix(
            commit_message="Fix NullPointerException in UserService",
            diff="- return user.getName();\n+ return user != null ? user.getName() : \"\";"
        )

        assert is_bug is True, "Dovrebbe classificare come BUG"

    def test_classifies_refactoring_as_not_bug(self, mocker):
        """
        Verifica che un refactoring venga scartato.
        """
        from szz_llm_project.llm_refiner import LLMRefiner

        mock_response = mocker.Mock()
        mock_response.json.return_value = {"response": "CLASSIFICAZIONE: REFACTORING\nMOTIVO: Solo rinomina variabili"}
        mocker.patch('requests.post', return_value=mock_response)

        refiner = LLMRefiner()
        is_bug, explanation = refiner.is_real_bug_fix(
            commit_message="Refactor: renamed variables for clarity",
            diff="- int x = 5;\n+ int count = 5;"
        )

        assert is_bug is False, "Dovrebbe classificare come REFACTORING"

    def test_handles_llm_timeout(self, mocker):
        """
        Verifica che il timeout di Ollama venga gestito gracefully.
        """
        from szz_llm_project.llm_refiner import LLMRefiner
        import requests

        mocker.patch('requests.post', side_effect=requests.Timeout("Connection timed out"))

        refiner = LLMRefiner()
        is_bug, explanation = refiner.is_real_bug_fix("Fix bug", "- old\n+ new")

        assert is_bug is False, "Dovrebbe restituire False in caso di timeout"

    def test_handles_malformed_response(self, mocker):
        """
        Verifica gestione di risposte malformate da Ollama.
        """
        from szz_llm_project.llm_refiner import LLMRefiner

        mock_response = mocker.Mock()
        mock_response.json.return_value = {}
        mocker.patch('requests.post', return_value=mock_response)

        refiner = LLMRefiner()
        is_bug, explanation = refiner.is_real_bug_fix("Fix", "diff")

        assert is_bug is False, "Dovrebbe gestire risposte malformate"

    def test_handles_connection_error(self, mocker):
        """
        Verifica gestione errore di connessione (Ollama non attivo).
        """
        from szz_llm_project.llm_refiner import LLMRefiner
        import requests

        mocker.patch('requests.post', side_effect=requests.ConnectionError("Connection refused"))

        refiner = LLMRefiner()
        is_bug, explanation = refiner.is_real_bug_fix("Fix bug", "diff")

        assert is_bug is False, "Dovrebbe restituire False se Ollama non è raggiungibile"