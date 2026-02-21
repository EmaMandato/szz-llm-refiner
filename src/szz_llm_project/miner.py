import subprocess
import sys
import re
from datetime import datetime
from typing import Optional, List, Tuple
from pydriller import Repository


# Keywords che indicano commit da scartare (non sono bug fix)
SKIP_KEYWORDS = [
    "refactor", "refactoring",
    "style", "format", "formatting",
    "docs", "documentation", "comment", "comments",
    "chore", "typo", "typos",
    "rename", "renamed", "renaming",
    "whitespace", "indent", "indentation",
    "cleanup", "clean up", "clean-up",
    "lint", "linting"
]


class GitMiner:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def _log(self, message: str):
        """Stampa messaggi di debug su stderr."""
        print(message, file=sys.stderr, flush=True)

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

    # ==========================================
    # METODI PER DATE
    # ==========================================

    def get_commit_date(self, commit_hash: str) -> Optional[datetime]:
        """Restituisce la data di un commit."""
        date_str = self._run_git("log", "-1", "--format=%aI", commit_hash)
        if date_str:
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except:
                pass
        return None

    def get_commits_between_dates(
            self,
            since: Optional[datetime] = None,
            until: Optional[datetime] = None
    ) -> List[str]:
        """
        Restituisce gli hash dei commit in un range di date.

        Args:
            since: Data di inizio (inclusa)
            until: Data di fine (inclusa)

        Returns:
            Lista di hash commit
        """
        args = ["rev-list", "HEAD"]

        if since:
            args.append(f"--since={since.isoformat()}")
        if until:
            args.append(f"--until={until.isoformat()}")

        output = self._run_git(*args)

        commits = []
        for line in output.splitlines():
            if line.strip():
                commits.append(line.strip())

        return commits

    # ==========================================
    # METODI DI FILTRO
    # ==========================================

    def should_skip_by_message(self, commit_message: str) -> bool:
        """
        Pre-filtro veloce basato sul messaggio del commit.
        Restituisce True se il commit dovrebbe essere scartato (non è un bug fix).
        """
        msg_lower = commit_message.lower()

        # Controlla se il messaggio contiene keyword di skip
        for keyword in SKIP_KEYWORDS:
            # Controlla come prefisso (es. "refactor: ...")
            if msg_lower.startswith(f"{keyword}:") or msg_lower.startswith(f"{keyword}("):
                return True
            # Controlla come parola isolata all'inizio
            if msg_lower.startswith(keyword + " "):
                return True

        return False

    def is_cosmetic_change(self, commit_hash: str) -> bool:
        """
        Analizza il diff di un commit per determinare se contiene solo modifiche cosmetiche:
        - Rinomina di variabili
        - Modifiche ai commenti
        - Cambi di whitespace/formattazione

        Restituisce True se il commit è solo cosmetico.
        """
        diff = self._run_git("show", "--format=", "-U0", commit_hash)

        if not diff:
            return False

        added_lines = []
        removed_lines = []

        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:].strip())
            elif line.startswith("-") and not line.startswith("---"):
                removed_lines.append(line[1:].strip())

        if not added_lines and not removed_lines:
            return True  # Nessuna modifica sostanziale

        # Controlla se sono solo modifiche ai commenti
        comment_patterns = [
            r'^\s*//.*$',      # Commenti Java/C++ single line
            r'^\s*#.*$',       # Commenti Python/Shell
            r'^\s*/\*.*$',     # Inizio commento multi-line
            r'^\s*\*.*$',      # Continuazione commento multi-line
            r'^\s*\*/.*$',     # Fine commento multi-line
            r'^\s*""".*$',     # Docstring Python
            r"^\s*'''.*$",     # Docstring Python
        ]

        def is_comment_line(line: str) -> bool:
            for pattern in comment_patterns:
                if re.match(pattern, line):
                    return True
            return False

        # Se tutte le linee modificate sono commenti
        all_comments = all(
            is_comment_line(line) or line.strip() == ""
            for line in added_lines + removed_lines
        )
        if all_comments and (added_lines or removed_lines):
            return True

        # Controlla se è solo rinomina di variabili (stesso pattern, nome diverso)
        if len(added_lines) == len(removed_lines) and len(added_lines) > 0:
            # Normalizza rimuovendo identificatori per confronto strutturale
            def normalize_line(line: str) -> str:
                # Rimuove stringhe e numeri, mantiene struttura
                normalized = re.sub(r'"[^"]*"', '""', line)
                normalized = re.sub(r"'[^']*'", "''", normalized)
                normalized = re.sub(r'\b\d+\b', '0', normalized)
                # Rimuove spazi extra
                normalized = ' '.join(normalized.split())
                return normalized

            # Se la struttura è identica, probabilmente è solo rinomina
            structural_match = True
            for added, removed in zip(sorted(added_lines), sorted(removed_lines)):
                if normalize_line(added) != normalize_line(removed):
                    # Le strutture sono diverse, potrebbe essere un vero cambiamento
                    # Ma controlliamo se differiscono solo per un identificatore
                    added_tokens = set(re.findall(r'\b\w+\b', added))
                    removed_tokens = set(re.findall(r'\b\w+\b', removed))

                    # Se differiscono per più di 2 token, non è solo rinomina
                    diff_tokens = added_tokens.symmetric_difference(removed_tokens)
                    if len(diff_tokens) > 4:
                        structural_match = False
                        break

            if structural_match:
                return True

        # Controlla se sono solo modifiche di whitespace
        def remove_whitespace(line: str) -> str:
            return ''.join(line.split())

        if added_lines and removed_lines:
            added_no_ws = [remove_whitespace(l) for l in added_lines if l.strip()]
            removed_no_ws = [remove_whitespace(l) for l in removed_lines if l.strip()]

            if sorted(added_no_ws) == sorted(removed_no_ws):
                return True

        return False

    def get_commit_message(self, commit_hash: str) -> str:
        """Restituisce solo il messaggio di un commit."""
        return self._run_git("log", "-1", "--format=%B", commit_hash)

    # ==========================================
    # METODI PRINCIPALI
    # ==========================================

    def get_fixing_commits(
            self,
            since: Optional[datetime] = None,
            until: Optional[datetime] = None
    ) -> List[str]:
        """
        Cerca tutti i commit che potrebbero essere fix di bug
        basandosi su parole chiave nel messaggio.

        Supporta filtri per:
        - Range di date (since/until)

        Args:
            since: Data di inizio (opzionale)
            until: Data di fine (opzionale)

        Returns:
            Lista di hash dei commit che sono potenziali fix
        """
        fixing_hashes = []

        # Determina quali commit considerare
        if since or until:
            # Filtro per date
            candidate_commits = set(self.get_commits_between_dates(since, until))
            date_range = f"{since.date() if since else 'beginning'} to {until.date() if until else 'now'}"
            self._log(f"  [Filter] Commits in date range {date_range}: {len(candidate_commits)}")
        else:
            # Nessun filtro, considera tutti
            candidate_commits = None

        for commit in Repository(self.repo_path).traverse_commits():
            # Se c'è un filtro, verifica che il commit sia nei candidati
            if candidate_commits is not None and commit.hash not in candidate_commits:
                continue

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

        # Diff completo con 5 linee di contesto per migliorare l'analisi LLM
        diff = self._run_git("show", "--format=", "-U5", commit_hash)

        return msg, diff

    def get_bug_inducing_commits(self, fix_commit_hash, blacklist: set = None):
        """
        Implementazione SZZ usando git blame.
        Identifica i commit che hanno introdotto le linee poi rimosse dal fix.

        Args:
            fix_commit_hash: Hash del commit di fix da analizzare
            blacklist: Set di hash da ignorare (commit già scartati come refactoring)

        Returns:
            Lista di hash dei bug-inducing commits filtrati
        """
        if blacklist is None:
            blacklist = set()

        bics = set()
        self._log(f"  --> Analisi SZZ per {fix_commit_hash[:8]}...")

        try:
            # Ottieni il parent commit (stato prima del fix)
            parent = self._run_git("rev-parse", f"{fix_commit_hash}^")
            if not parent:
                self._log(f"      [!] Nessun parent commit trovato")
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

            self._log(f"      [Debug] Trovati {len(deleted_line_ranges)} range di linee rimosse")

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
                            # Il primo campo è l'hash del commit (rimuovi eventuale ^ prefix)
                            blamed_hash = blame_line.split()[0].lstrip('^')
                            if blamed_hash and len(blamed_hash) >= 7:
                                # Ignora il fix commit stesso
                                if not blamed_hash.startswith(fix_commit_hash[:7]):
                                    bics.add(blamed_hash)

                except Exception as e:
                    # File potrebbe non esistere nel parent
                    continue

            # Applica filtri sui BIC trovati
            filtered_bics = set()

            for bic in bics:
                # 1. Filtro blacklist
                if any(bic.startswith(bl[:7]) or bl.startswith(bic[:7]) for bl in blacklist):
                    self._log(f"      [Filtro] {bic[:8]} scartato (in blacklist)")
                    continue

                # 2. Filtro messaggio commit
                bic_message = self.get_commit_message(bic)
                if self.should_skip_by_message(bic_message):
                    self._log(f"      [Filtro] {bic[:8]} scartato (messaggio: refactor/docs/style)")
                    continue

                # 3. Filtro modifiche cosmetiche
                if self.is_cosmetic_change(bic):
                    self._log(f"      [Filtro] {bic[:8]} scartato (modifiche cosmetiche)")
                    continue

                filtered_bics.add(bic)

            if filtered_bics:
                self._log(f"      Trovati {len(filtered_bics)} BIC validi (filtrati {len(bics) - len(filtered_bics)})")
            elif bics:
                self._log(f"      Tutti i {len(bics)} BIC sono stati filtrati")

        except Exception as e:
            self._log(f"      [!] Errore critico SZZ: {e}")

        return list(filtered_bics)