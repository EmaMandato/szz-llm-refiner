from pydriller import Repository


class GitMiner:
    def _init_(self, repo_path: str):
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