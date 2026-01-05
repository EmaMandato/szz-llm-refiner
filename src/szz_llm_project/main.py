import sys
from .miner import GitMiner
from .llm_refiner import LLMRefiner


def main():
    print("=== SZZ-LLM-Refiner: Workflow Completo ===")

    # Percorso del repository passato come argomento [cite: 1315]
    path = sys.argv[1] if len(sys.argv) > 1 else "."

    miner = GitMiner(path)
    refiner = LLMRefiner()

    # 1. Mining dei fix [cite: 6]
    potential_fixes = miner.get_fixing_commits()
    print(f"Trovati {len(potential_fixes)} potenziali fix commit.")

    # 2. Refinement con LLM (Analisi Statica Automatica) [cite: 73]
    confirmed_bugs = []
    print("\nInizio raffinamento con LLM sui primi 5 commit...")
    for h in potential_fixes[:5]:
        msg, diff = miner.get_commit_diff(h)
        print(f"Analizzando {h[:8]}...")

        if refiner.is_real_bug_fix(msg, diff):
            print(f"  [+] Confermato come BUG")
            confirmed_bugs.append(h)
        else:
            print(f"  [-] Scartato (Refactoring/Altro)")

    # 3. Identificazione dei BIC (SZZ Stage 3)
    print("\nIdentificazione dei commit che hanno introdotto il bug (BIC):")
    for bug_hash in confirmed_bugs:
        bics = miner.get_bug_inducing_commits(bug_hash)
        print(f"Fix Commit: {bug_hash[:8]}")
        print(f"  -> Sospetti BIC: {bics}")


if __name__ == "__main__":
    main()