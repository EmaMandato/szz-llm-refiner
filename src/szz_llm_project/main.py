import sys
import os
import json
import shutil
import tempfile
import argparse
import subprocess
from dataclasses import dataclass, asdict
from typing import Optional
from .miner import GitMiner
from .llm_refiner import LLMRefiner


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


def run_analysis(
        repo_path: str,
        branch: str = "main",
        limit: int = 10,
        model: str = "qwen2.5-coder:7b",
        output_format: str = "text",
        skip_llm: bool = False
) -> AnalysisReport:
    """
    Esegue l'analisi SZZ completa.
    """
    errors = []
    results = []

    miner = GitMiner(repo_path)
    refiner = LLMRefiner(model=model) if not skip_llm else None

    # 1. Mining dei fix
    log("Scanning repository for fix commits...")
    potential_fixes = miner.get_fixing_commits()
    log(f"Found {len(potential_fixes)} potential fix commits.")

    if limit > 0:
        potential_fixes = potential_fixes[:limit]

    # 2. Analisi di ogni commit
    confirmed_bugs = []

    log(f"Analyzing {len(potential_fixes)} commits...")

    for i, commit_hash in enumerate(potential_fixes, 1):
        log(f"[{i}/{len(potential_fixes)}] Analyzing {commit_hash[:8]}...")

        try:
            msg, diff = miner.get_commit_diff(commit_hash)

            # Refinement con LLM (se abilitato)
            if refiner and not skip_llm:
                is_bug = refiner.is_real_bug_fix(msg, diff)
                status = "BUG" if is_bug else "REFACTORING"
                log(f"    LLM verdict: {status}")
            else:
                # Senza LLM, considera tutti come potenziali bug
                is_bug = True
                log(f"    Skipped LLM (assuming BUG)")

            # 3. SZZ per i bug confermati
            bics = []
            if is_bug:
                confirmed_bugs.append(commit_hash)
                bics = miner.get_bug_inducing_commits(commit_hash)
                if bics:
                    log(f"    Found {len(bics)} bug-inducing commits")

            results.append(asdict(AnalysisResult(
                fix_commit=commit_hash,
                commit_message=msg[:200],  # Tronca messaggi lunghi
                is_bug=is_bug,
                bug_inducing_commits=bics
            )))

        except Exception as e:
            error_msg = f"Error analyzing {commit_hash[:8]}: {str(e)}"
            log(f"    ERROR: {e}")
            errors.append(error_msg)

    return AnalysisReport(
        repository=repo_path,
        branch=branch,
        total_potential_fixes=len(miner.get_fixing_commits()),
        analyzed_commits=len(potential_fixes),
        confirmed_bugs=len(confirmed_bugs),
        results=results,
        errors=errors
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
    print(f"Total potential fixes found: {report.total_potential_fixes}")
    print(f"Commits analyzed: {report.analyzed_commits}")
    print(f"Confirmed bugs: {report.confirmed_bugs}")

    print("\n" + "-" * 60)
    print("RESULTS")
    print("-" * 60)

    for r in report.results:
        status = "BUG" if r["is_bug"] else "REFACTORING"
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


def main():
    global _json_output

    parser = argparse.ArgumentParser(
        description="SZZ-LLM: Bug-inducing commit detection with LLM refinement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  szz-run ./my-repo                          # Analyze local repository
  szz-run --url https://github.com/user/repo # Clone and analyze
  szz-run ./repo --limit 50 --output json    # Analyze 50 commits, JSON output
  szz-run ./repo --skip-llm                  # Skip LLM refinement
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

        # Run analysis
        report = run_analysis(
            repo_path=repo_path,
            branch=args.branch,
            limit=args.limit,
            model=args.model,
            output_format=args.output,
            skip_llm=args.skip_llm
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