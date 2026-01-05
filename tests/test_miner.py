import pytest
from szz_llm_project.miner import GitMiner

def test_miner_initialization():
    """Verifica che il miner venga inizializzato correttamente."""
    miner = GitMiner(".")
    assert miner.repo_path == "."

def test_get_fixing_commits_type():
    """Verifica che il miner restituisca una lista."""
    miner = GitMiner(".")
    fixes = miner.get_fixing_commits()
    assert isinstance(fixes, list)