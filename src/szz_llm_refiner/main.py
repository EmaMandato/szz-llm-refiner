import sys
from .miner import GitMiner


def main():
    print("=== SZZ-LLM-Refiner: Fase 1 (Mining) ===")

    # Prende il percorso del repository da riga di comando o usa quello corrente
    path = sys.argv[1] if len(sys.argv) > 1 else "."

    miner = GitMiner(path)
    fixes = miner.get_fixing_commits()

    print(f"Mining completato. Trovati {len(fixes)} potenziali bug-fixing commits.")
    # Mostriamo i primi 3 per test
    for h in fixes[:3]:
        print(f"Found fix: {h}")


if __name__ == "__main__":
    main()