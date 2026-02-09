import sys
import os
import json
import shutil
import tempfile
import argparse
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List
from .miner import GitMiner
from .llm_refiner import LLMRefiner
from .validator import run_validation, print_validation_report


# Global flag for JSON output mode
_json_output = False


def log(message: str):
    """Print to stderr if JSON mode, stdout otherwise."""
    if _json_output:
        print(message, file=sys.stderr, flush=True)
    else:
        print(message, flush=True)


@dataclass
class AnalysisResult:
    """Struttura dati per i risultati dell'analisi."""
    fix_commit: str
    commit_message: str
    is_bug: bool
    bug_inducing_commits: list[str]
    skipped_reason: Optional[str] = None  # Motivo se scartato


@dataclass
class FilterStats:
    """Statistiche sui filtri applicati."""
    skipped_by_message: int = 0
    skipped_by_llm: int = 0
    bics_filtered_by_blacklist: int = 0
    bics_filtered_by_message: int = 0
    bics_filtered_by_cosmetic: int = 0


@dataclass
class AnalysisReport:
    """Report completo dell'analisi."""
    repository: str
    branch: str
    total_potential_fixes: int
    analyzed_commits: int
    confirmed_bugs: int
    results: list[dict]
    errors: list[str]
    filter_stats: dict = field(default_factory=dict)
    selection_strategy: str = "all"  # "all", "date_range", "tag_range"
    selection_params: dict = field(default_factory=dict)  # Parametri usati per la selezione


def clone_repository(url: str, branch: str = "main", dest: Optional[str] = None) -> str:
    """
    Clona un repository Git da URL.
    Restituisce il percorso della directory clonata.
    """
    if dest is None:
        dest = tempfile.mkdtemp(prefix="szz_repo_")

    log(f"Cloning {url} (branch: {branch})...")

    result = subprocess.run(
        ["git", "clone", "--branch", branch, "--single-branch", "--depth", "1000", url, dest],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        # Prova senza specificare il branch (usa default)
        log(f"Branch '{branch}' non trovato, provo con branch default...")
        shutil.rmtree(dest, ignore_errors=True)
        dest = tempfile.mkdtemp(prefix="szz_repo_")

        result = subprocess.run(
            ["git", "clone", "--single-branch", "--depth", "1000", url, dest],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"Errore clone: {result.stderr}")

    log(f"Repository clonato in: {dest}")
    return dest


def check_git_installed() -> bool:
    """Verifica che git sia installato e accessibile."""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_ollama_running(url: str = "http://localhost:11434") -> bool:
    """Verifica che Ollama sia in esecuzione."""
    try:
        import requests
        response = requests.get(f"{url}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False


def get_tags_list(repo_path: str) -> List[dict]:
    """
    Restituisce la lista dei tag del repository.
    Usato per l'opzione --list-tags.
    """
    miner = GitMiner(repo_path)
    return miner.get_tags()


def run_analysis(
        repo_path: str,
        branch: str = "main",
        limit: int = 10,
        model: str = "qwen2.5-coder:7b",
        output_format: str = "text",
        skip_llm: bool = False,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        from_tag: Optional[str] = None,
        to_tag: Optional[str] = None
) -> AnalysisReport:
    """
    Esegue l'analisi SZZ completa con il nuovo flusso di filtri.

    Flusso:
    1. Mining dei potenziali fix commits (con filtri data/tag)
    2. Pre-filtro sul messaggio (scarta refactor/docs/style)
    3. Validazione LLM dei fix commits
    4. SZZ con git blame
    5. Filtro BIC: blacklist, messaggio, modifiche cosmetiche
    """
    errors = []
    results = []
    filter_stats = FilterStats()

    # Blacklist: commit scartati che non devono apparire come BIC
    blacklist = set()

    miner = GitMiner(repo_path)
    refiner = LLMRefiner(model=model) if not skip_llm else None

    # Determina la strategia di selezione
    if from_tag and to_tag:
        selection_strategy = "tag_range"
        selection_params = {"from_tag": from_tag, "to_tag": to_tag}
        log(f"Selection strategy: Tag range ({from_tag} → {to_tag})")
    elif since or until:
        selection_strategy = "date_range"
        selection_params = {
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None
        }
        date_from = since.date() if since else "beginning"
        date_to = until.date() if until else "now"
        log(f"Selection strategy: Date range ({date_from} → {date_to})")
    else:
        selection_strategy = "all"
        selection_params = {}
        log("Selection strategy: All commits")

    # ========================================
    # STEP 1: Mining dei potenziali fix
    # ========================================
    log("\nScanning repository for fix commits...")
    potential_fixes = miner.get_fixing_commits(
        since=since,
        until=until,
        from_tag=from_tag,
        to_tag=to_tag
    )
    total_potential = len(potential_fixes)
    log(f"Found {total_potential} potential fix commits.")

    if limit > 0:
        potential_fixes = potential_fixes[:limit]

    # ========================================
    # STEP 2 & 3: Pre-filtro e validazione LLM
    # ========================================
    confirmed_fixes = []

    log(f"\nAnalyzing {len(potential_fixes)} commits...")
    log("=" * 50)

    for i, commit_hash in enumerate(potential_fixes, 1):
        msg, diff = miner.get_commit_diff(commit_hash)
        short_hash = commit_hash[:8]

        log(f"\n[{i}/{len(potential_fixes)}] {short_hash}: {msg[:50].strip()}...")

        # ----------------------------------------
        # STEP 2: Pre-filtro sul messaggio (veloce)
        # ----------------------------------------
        if miner.should_skip_by_message(msg):
            log(f"    ⏭️  SKIP (messaggio indica refactor/docs/style)")
            blacklist.add(commit_hash)
            filter_stats.skipped_by_message += 1

            results.append(asdict(AnalysisResult(
                fix_commit=commit_hash,
                commit_message=msg[:200],
                is_bug=False,
                bug_inducing_commits=[],
                skipped_reason="pre-filter:message"
            )))
            continue

        # ----------------------------------------
        # STEP 3: Validazione LLM
        # ----------------------------------------
        if refiner and not skip_llm:
            is_bug = refiner.is_real_bug_fix(msg, diff)

            if not is_bug:
                log(f"    ⏭️  SKIP (LLM: REFACTORING)")
                blacklist.add(commit_hash)
                filter_stats.skipped_by_llm += 1

                results.append(asdict(AnalysisResult(
                    fix_commit=commit_hash,
                    commit_message=msg[:200],
                    is_bug=False,
                    bug_inducing_commits=[],
                    skipped_reason="llm:refactoring"
                )))
                continue
            else:
                log(f"    ✅ LLM: BUG FIX confermato")
        else:
            # Senza LLM, considera come bug se ha passato il pre-filtro
            is_bug = True
            log(f"    ⚠️  LLM skippato (assumo BUG)")

        # ----------------------------------------
        # STEP 4 & 5: SZZ con filtri sui BIC
        # ----------------------------------------
        confirmed_fixes.append(commit_hash)

        log(f"    🔍 Eseguo SZZ blame...")
        bics = miner.get_bug_inducing_commits(commit_hash, blacklist)

        if bics:
            log(f"    📍 Trovati {len(bics)} bug-inducing commits")
            for bic in bics[:3]:  # Mostra max 3
                bic_msg = miner.get_commit_message(bic)[:40].strip()
                log(f"       - {bic[:8]}: {bic_msg}...")
            if len(bics) > 3:
                log(f"       ... e altri {len(bics) - 3}")
        else:
            log(f"    📍 Nessun BIC trovato (o tutti filtrati)")

        results.append(asdict(AnalysisResult(
            fix_commit=commit_hash,
            commit_message=msg[:200],
            is_bug=True,
            bug_inducing_commits=bics,
            skipped_reason=None
        )))

    log("\n" + "=" * 50)

    return AnalysisReport(
        repository=repo_path,
        branch=branch,
        total_potential_fixes=total_potential,
        analyzed_commits=len(potential_fixes),
        confirmed_bugs=len(confirmed_fixes),
        results=results,
        errors=errors,
        filter_stats=asdict(filter_stats),
        selection_strategy=selection_strategy,
        selection_params=selection_params
    )


def print_report(report: AnalysisReport, output_format: str = "text"):
    """Stampa il report nel formato richiesto."""

    if output_format == "json":
        # JSON va su stdout (pulito, senza altri messaggi)
        print(json.dumps(asdict(report), indent=2))
        return

    # Formato testuale
    print("\n" + "=" * 60)
    print("SZZ-LLM ANALYSIS REPORT")
    print("=" * 60)
    print(f"Repository: {report.repository}")
    print(f"Branch: {report.branch}")
    print(f"Selection: {report.selection_strategy}")
    if report.selection_params:
        for key, value in report.selection_params.items():
            if value:
                print(f"  - {key}: {value}")
    print(f"Total potential fixes found: {report.total_potential_fixes}")
    print(f"Commits analyzed: {report.analyzed_commits}")
    print(f"Confirmed bugs: {report.confirmed_bugs}")

    # Statistiche filtri
    if report.filter_stats:
        print("\n" + "-" * 60)
        print("FILTER STATISTICS")
        print("-" * 60)
        stats = report.filter_stats
        print(f"  Skipped by message (pre-filter): {stats.get('skipped_by_message', 0)}")
        print(f"  Skipped by LLM (refactoring): {stats.get('skipped_by_llm', 0)}")
        print(f"  BICs filtered by blacklist: {stats.get('bics_filtered_by_blacklist', 0)}")
        print(f"  BICs filtered by message: {stats.get('bics_filtered_by_message', 0)}")
        print(f"  BICs filtered by cosmetic: {stats.get('bics_filtered_by_cosmetic', 0)}")

    print("\n" + "-" * 60)
    print("RESULTS")
    print("-" * 60)

    for r in report.results:
        if r.get("skipped_reason"):
            status = f"SKIPPED ({r['skipped_reason']})"
        elif r["is_bug"]:
            status = "BUG"
        else:
            status = "REFACTORING"

        print(f"\n[{status}] {r['fix_commit'][:8]}")
        print(f"  Message: {r['commit_message'][:80]}...")

        if r["is_bug"] and r["bug_inducing_commits"]:
            print(f"  Bug-inducing commits ({len(r['bug_inducing_commits'])}):")
            for bic in r["bug_inducing_commits"][:5]:  # Max 5
                print(f"    - {bic[:12]}")
            if len(r["bug_inducing_commits"]) > 5:
                print(f"    ... and {len(r['bug_inducing_commits']) - 5} more")

    if report.errors:
        print("\n" + "-" * 60)
        print("ERRORS")
        print("-" * 60)
        for err in report.errors:
            print(f"  ! {err}")

    print("\n" + "=" * 60)


def parse_date(date_str: str) -> datetime:
    """
    Converte una stringa data in oggetto datetime.
    Supporta formati: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, ISO format
    """
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # Prova ISO format
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        pass

    raise ValueError(f"Formato data non riconosciuto: {date_str}. Usa YYYY-MM-DD")


def main():
    global _json_output

    parser = argparse.ArgumentParser(
        description="SZZ-LLM: Bug-inducing commit detection with LLM refinement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze local repository (latest commits)
  szz-run ./my-repo --limit 10

  # Analyze commits between dates
  szz-run ./repo --since 2024-01-01 --until 2024-06-30

  # Analyze commits between tags/releases
  szz-run ./repo --from-tag v1.0.0 --to-tag v2.0.0

  # List available tags
  szz-run ./repo --list-tags

  # Clone and analyze remote repository
  szz-run --url https://github.com/user/repo --from-tag v1.0 --to-tag v1.1

  # JSON output for plugin integration
  szz-run ./repo --output json --from-tag v1.0 --to-tag v2.0

  # Validate LLM accuracy against a labeled dataset
  szz-run ./repo --validate ground_truth.csv
  szz-run ./repo --validate defects4j-bugs.json --validation-limit 50
        """
    )

    # Positional argument (legacy support)
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Local repository path (optional if --url is provided)"
    )

    # Repository options
    parser.add_argument(
        "--url", "-u",
        help="Git repository URL to clone and analyze"
    )
    parser.add_argument(
        "--branch", "-b",
        default="main",
        help="Branch to analyze (default: main)"
    )

    # Selection strategy options
    selection_group = parser.add_argument_group("Selection Strategy")
    selection_group.add_argument(
        "--since",
        help="Analyze commits after this date (YYYY-MM-DD)"
    )
    selection_group.add_argument(
        "--until",
        help="Analyze commits before this date (YYYY-MM-DD)"
    )
    selection_group.add_argument(
        "--from-tag",
        help="Start tag for range analysis (older tag)"
    )
    selection_group.add_argument(
        "--to-tag",
        help="End tag for range analysis (newer tag)"
    )
    selection_group.add_argument(
        "--list-tags",
        action="store_true",
        help="List available tags and exit"
    )

    # Analysis options
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Maximum number of commits to analyze (default: 10, 0 = all)"
    )
    parser.add_argument(
        "--model", "-m",
        default="qwen2.5-coder:7b",
        help="Ollama model for LLM refinement (default: qwen2.5-coder:7b)"
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM refinement (faster, but less accurate)"
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--output-file", "-f",
        help="Save output to file"
    )

    # Validation options
    validation_group = parser.add_argument_group("Validation Mode")
    validation_group.add_argument(
        "--validate",
        metavar="GROUND_TRUTH_FILE",
        help="Run validation against a labeled dataset (CSV or JSON)"
    )
    validation_group.add_argument(
        "--validation-limit",
        type=int,
        default=0,
        help="Max samples to validate (default: 0 = all)"
    )

    args = parser.parse_args()

    # Set JSON output mode (affects log() function)
    _json_output = (args.output == "json")

    # Validation
    if not args.path and not args.url:
        parser.error("Either path or --url must be provided")

    # Check git
    if not check_git_installed():
        if _json_output:
            print(json.dumps({"status": "error", "error": "Git is not installed or not in PATH"}))
        else:
            print("ERROR: Git is not installed or not in PATH")
        sys.exit(1)

    # Validate selection strategy
    if (args.from_tag and not args.to_tag) or (args.to_tag and not args.from_tag):
        parser.error("--from-tag and --to-tag must be used together")

    if (args.from_tag or args.to_tag) and (args.since or args.until):
        parser.error("Cannot use both tag range and date range. Choose one strategy.")

    # Check Ollama (if LLM is enabled)
    if not args.skip_llm and not check_ollama_running():
        log("WARNING: Ollama is not running. LLM refinement will fail.")
        log("Start Ollama or use --skip-llm flag.")

    # Determine repo path
    repo_path = args.path
    cloned = False

    try:
        if args.url:
            repo_path = clone_repository(args.url, args.branch)
            cloned = True
        elif not os.path.isdir(repo_path):
            raise ValueError(f"Directory not found: {repo_path}")

        # Handle --list-tags
        if args.list_tags:
            tags = get_tags_list(repo_path)
            if _json_output:
                print(json.dumps({"tags": tags}))
            else:
                print("Available tags:")
                for tag in tags:
                    date_str = tag.get("date", "")[:10] if tag.get("date") else "unknown date"
                    print(f"  {tag['name']:30} {date_str}")
            return

        # Handle --validate mode
        if args.validate:
            log(f"Running validation against: {args.validate}")
            log(f"Model: {args.model}")

            metrics, results = run_validation(
                repo_path=repo_path,
                ground_truth_file=args.validate,
                model=args.model,
                limit=args.validation_limit,
                verbose=not _json_output
            )

            if _json_output:
                output = {
                    "status": "success",
                    "metrics": metrics.to_dict(),
                    "results": [
                        {
                            "commit": r.commit_hash,
                            "ground_truth": "BUG" if r.ground_truth else "REFACTORING",
                            "prediction": "BUG" if r.prediction else "REFACTORING",
                            "correct": r.correct
                        }
                        for r in results
                    ]
                }
                print(json.dumps(output, indent=2))
            else:
                print_validation_report(metrics, results)

            return

        # Parse dates
        since = parse_date(args.since) if args.since else None
        until = parse_date(args.until) if args.until else None

        # Run analysis
        report = run_analysis(
            repo_path=repo_path,
            branch=args.branch,
            limit=args.limit,
            model=args.model,
            output_format=args.output,
            skip_llm=args.skip_llm,
            since=since,
            until=until,
            from_tag=args.from_tag,
            to_tag=args.to_tag
        )

        # Output
        if args.output_file:
            with open(args.output_file, "w", encoding="utf-8") as f:
                if args.output == "json":
                    json.dump(asdict(report), f, indent=2)
                else:
                    # Redirect stdout to file
                    old_stdout = sys.stdout
                    sys.stdout = f
                    print_report(report, args.output)
                    sys.stdout = old_stdout
            log(f"Report saved to: {args.output_file}")
        else:
            print_report(report, args.output)

    except Exception as e:
        if _json_output:
            print(json.dumps({"status": "error", "error": str(e)}))
        else:
            print(f"FATAL ERROR: {e}")
        sys.exit(1)

    finally:
        # Cleanup cloned repo
        if cloned and repo_path:
            log("Cleaning up temporary directory...")
            shutil.rmtree(repo_path, ignore_errors=True)


if __name__ == "__main__":
    main()