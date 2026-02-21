import pytest
from unittest.mock import patch
from szz_llm_project.llm_refiner import LLMRefiner


@patch('requests.post')
def test_is_real_bug_fix_positive(mock_post):
    """Verifica che il refiner riconosca correttamente un BUG tramite mock."""
    # Simuliamo la risposta di Ollama con classificazione e motivo
    mock_post.return_value.json.return_value = {
        "response": "CLASSIFICAZIONE: BUG\nMOTIVO: Corregge un errore logico"
    }

    refiner = LLMRefiner()
    is_bug, explanation = refiner.is_real_bug_fix("fix logic error", "diff code...")
    assert is_bug is True
    assert "errore logico" in explanation.lower() or explanation != ""


@patch('requests.post')
def test_is_real_bug_fix_negative(mock_post):
    """Verifica che il refiner riconosca un REFACTORING."""
    mock_post.return_value.json.return_value = {
        "response": "CLASSIFICAZIONE: REFACTORING\nMOTIVO: Solo aggiornamento commenti"
    }

    refiner = LLMRefiner()
    is_bug, explanation = refiner.is_real_bug_fix("update comments", "diff code...")
    assert is_bug is False
    assert explanation != ""


@patch('requests.post')
def test_is_real_bug_fix_handles_error(mock_post):
    """Verifica che il refiner gestisca errori gracefully."""
    mock_post.side_effect = Exception("Connection error")

    refiner = LLMRefiner()
    is_bug, explanation = refiner.is_real_bug_fix("fix something", "diff code...")
    assert is_bug is False
    assert "Errore" in explanation or "error" in explanation.lower()


@patch('requests.post')
def test_is_real_bug_fix_extracts_motivo(mock_post):
    """Verifica che il refiner estragga correttamente il motivo."""
    mock_post.return_value.json.return_value = {
        "response": "CLASSIFICAZIONE: BUG\nMOTIVO: Fix per NullPointerException"
    }

    refiner = LLMRefiner()
    is_bug, explanation = refiner.is_real_bug_fix("fix NPE", "diff code...")
    assert is_bug is True
    assert "NullPointerException" in explanation
