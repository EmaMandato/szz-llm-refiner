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