import pytest
from unittest.mock import patch
from szz_llm_project.llm_refiner import LLMRefiner


@patch('requests.post')
def test_is_real_bug_fix_positive(mock_post):
    """Verifica che il refiner riconosca correttamente un BUG tramite mock."""
    # Simuliamo la risposta di Ollama
    mock_post.return_value.json.return_value = {"response": "This is a BUG"}

    refiner = LLMRefiner()
    result = refiner.is_real_bug_fix("fix logic error", "diff code...")
    assert result is True


@patch('requests.post')
def test_is_real_bug_fix_negative(mock_post):
    """Verifica che il refiner riconosca un REFACTORING."""
    mock_post.return_value.json.return_value = {"response": "Just a REFACTORING"}

    refiner = LLMRefiner()
    result = refiner.is_real_bug_fix("update comments", "diff code...")
    assert result is False