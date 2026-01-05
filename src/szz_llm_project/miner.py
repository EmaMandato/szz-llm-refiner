import subprocess
from pydriller import Repository


class GitMiner:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def _run_git(self, *args):
        """Esegue un comando git e restituisce l'output."""
        result = subprocess.run(
            ["git", "-C", self.repo_path] + list(args),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        return result.stdout.strip()

    def get_fixing_commits(self):
        """
        Cerca tutti i commit che potrebbero essere fix di bug
        basandosi su parole chiave nel messaggio.
        """
        fixing_hashes = []
        for commit in Repository(self.repo_path).traverse_commits():
            msg = commit.msg.lower()
            if "fix" in msg or "bug" in msg or "issue" in msg:
                fixing_hashes.append(commit.hash)

        return fixing_hashes

    def get_fix_details(self, commit_hash):
        """
        Per un dato commit, estrae i file modificati e le linee cancellate/modificate.
        """
        modifications = []

        # Ottieni lista file modificati
        files = self._run_git("diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash)

        for file_path in files.splitlines():
            if not file_path:
                continue
            # Ottieni le linee cancellate dal diff
            diff = self._run_git("show", "--format=", "-U0", commit_hash, "--", file_path)
            deleted_lines = []
            for line in diff.splitlines():
                if line.startswith("-") and not line.startswith("---"):
                    deleted_lines.append(line[1:])

            modifications.append({
                'file': file_path,
                'deleted_lines': deleted_lines
            })

        return modifications

    def get_commit_diff(self, commit_hash):
        """
        Estrae il messaggio e il diff testuale di un commit.
        """
        # Messaggio del commit
        msg = self._run_git("log", "-1", "--format=%B", commit_hash)

        # Diff completo
        diff = self._run_git("show", "--format=", commit_hash)

        return msg, diff

    def get_bug_inducing_commits(self, fix_commit_hash):
        """
        Implementazione SZZ usando git blame.
        Identifica i commit che hanno introdotto le linee poi rimosse dal fix.
        """
        bics = set()
        print(f"  --> Analisi SZZ per {fix_commit_hash[:8]}...")

        try:
            # Ottieni il parent commit (stato prima del fix)
            parent = self._run_git("rev-parse", f"{fix_commit_hash}^")
            if not parent:
                print(f"      [!] Nessun parent commit trovato")
                return []

            # Ottieni i file modificati con le linee cambiate
            diff_output = self._run_git(
                "diff", parent, fix_commit_hash, "--unified=0", "--no-color"
            )

            current_file = None
            deleted_line_ranges = []  # [(file, start_line, count), ...]

            for line in diff_output.splitlines():
                # Nuovo file nel diff
                if line.startswith("--- a/"):
                    current_file = line[6:]
                # Hunk header: @@ -start,count +start,count @@
                elif line.startswith("@@") and current_file:
                    # Estrai le linee rimosse dal file originale
                    parts = line.split()
                    if len(parts) >= 2:
                        old_range = parts[1]  # es: -10,5 o -10
                        if old_range.startswith("-"):
                            old_range = old_range[1:]
                            if "," in old_range:
                                start, count = old_range.split(",")
                                start, count = int(start), int(count)
                            else:
                                start, count = int(old_range), 1

                            if count > 0:  # Solo se ci sono linee rimosse
                                deleted_line_ranges.append((current_file, start, count))

            print(f"      [Debug] Trovati {len(deleted_line_ranges)} range di linee rimosse")

            # Per ogni range di linee rimosse, fai blame sul parent
            for file_path, start_line, count in deleted_line_ranges:
                if count == 0:
                    continue

                end_line = start_line + count - 1

                try:
                    # Blame delle linee rimosse sul commit parent
                    blame_output = self._run_git(
                        "blame", "-l", f"-L{start_line},{end_line}", parent, "--", file_path
                    )

                    for blame_line in blame_output.splitlines():
                        if blame_line:
                            # Il primo campo è l'hash del commit
                            blamed_hash = blame_line.split()[0]
                            if blamed_hash and len(blamed_hash) >= 7:
                                # Ignora il fix commit stesso
                                if not blamed_hash.startswith(fix_commit_hash[:7]):
                                    bics.add(blamed_hash)

                except Exception as e:
                    # File potrebbe non esistere nel parent
                    continue

            if bics:
                print(f"      Trovati {len(bics)} potenziali BIC")

        except Exception as e:
            print(f"      [!] Errore critico SZZ: {e}")

        return list(bics)