from pydriller import Repository


class GitMiner:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def get_fixing_commits(self):
        fixing_hashes = []
        # Analizza tutti i commit
        for commit in Repository(self.repo_path).traverse_commits():
            msg = commit.msg.lower()
            # si cercano termini come 'fix' o 'bug'
            if "fix" in msg or "bug" in msg or "issue" in msg:
                fixing_hashes.append(commit.hash)

        return fixing_hashes

    def get_fix_details(self, commit_hash):
        """
        Per un dato commit, estrae i file modificati e le linee cancellate/modificate.
        """
        for commit in Repository(self.repo_path, single=commit_hash).traverse_commits():
            modifications = []
            for mod in commit.modifications:
                # SZZ analizza le linee rimosse perché sono quelle che contenevano il bug
                modifications.append({
                    'file': mod.new_path,
                    'deleted_lines': mod.diff_parsed['deleted']  # Lista di (numero_linea, contenuto)
                })
            return modifications

    def get_commit_diff(self, commit_hash):
        """
        Estrae il diff testuale completo di un commit per l'analisi LLM.
        """
        for commit in Repository(self.repo_path, single=commit_hash).traverse_commits():
            diff_text = ""
            for mod in commit.modifications:
                if mod.diff:
                    diff_text += f"File: {mod.new_path}\n{mod.diff}\n"
            return commit.msg, diff_text

    def get_bug_inducing_commits(self, fix_commit_hash):
        """
        Analizza le linee eliminate in un fix e identifica i commit che le hanno create.
        Questo implementa la fase di tracciamento dell'algoritmo SZZ.
        """
        bics = set()
        # Analizziamo il commit di fix specifico
        for commit in Repository(self.repo_path, single=fix_commit_hash).traverse_commits():
            for mod in commit.modifications:
                # Analizziamo solo le linee eliminate (potenziale origine del bug)
                deleted_lines = mod.diff_parsed['deleted']
                if not deleted_lines:
                    continue

                # Usiamo le funzionalità SCM per il 'blame'
                # Nota: PyDriller espone il blame tramite l'oggetto commit o repository
                try:
                    # Otteniamo la storia delle linee rimosse
                    blame = Repository(self.repo_path).git.get_blame(mod.old_path, fix_commit_hash)
                    for line_num, content in deleted_lines:
                        # Identifichiamo l'hash del commit che ha modificato per ultimo quella linea
                        if line_num <= len(blame):
                            bic_info = blame[line_num - 1]
                            bic_hash = bic_info.split(' ')[0]
                            bics.add(bic_hash)
                except Exception as e:
                    print(f"Errore durante il blame sul file {mod.old_path}: {e}")

        return list(bics)