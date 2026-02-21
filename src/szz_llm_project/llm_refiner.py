import requests
from typing import Tuple, Optional


class LLMRefiner:
    def __init__(self, model="qwen2.5-coder:7b"):
        self.url = "http://localhost:11434/api/generate"
        self.model = model

    def is_real_bug_fix(self, commit_message, diff) -> Tuple[bool, Optional[str]]:
        """
        Chiede all'LLM se il commit è un vero fix di un bug logico.

        Returns:
            Tuple[bool, Optional[str]]: (is_bug, explanation)
                - is_bug: True se è un bug fix, False altrimenti
                - explanation: Breve spiegazione della classificazione
        """
        prompt = (
            f"Analizza rigorosamente questo commit.\n"
            f"Messaggio: {commit_message}\n"
            f"Diff: {diff[:2000]}\n\n"
            "Un BUG FIX deve correggere un errore logico (es. NullPointerException, calcolo errato, "
            "condizione sbagliata, crash, eccezione non gestita).\n"
            "Se è solo aggiunta di test, documentazione, refactoring, rename, o modifica stilistica, "
            "NON è un bug fix.\n\n"
            "Rispondi nel formato:\n"
            "CLASSIFICAZIONE: BUG oppure REFACTORING\n"
            "MOTIVO: breve spiegazione (max 20 parole)"
        )

        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 60,  # Aumentato per includere la spiegazione
                    "seed": 42
                }
            }

            response = requests.post(self.url, json=payload, timeout=30)
            result = response.json().get("response", "").strip()

            # Parse della risposta
            is_bug = "BUG" in result.upper() and "REFACTORING" not in result.upper().split("CLASSIFICAZIONE")[0]

            # Estrai il motivo dalla risposta
            explanation = self._extract_explanation(result)

            return is_bug, explanation

        except Exception as e:
            print(f"Errore LLM: {e}")
            return False, f"Errore LLM: {str(e)}"

    def _extract_explanation(self, response: str) -> str:
        """Estrae la spiegazione dalla risposta dell'LLM."""
        response_upper = response.upper()

        # Cerca "MOTIVO:" nella risposta
        if "MOTIVO:" in response_upper:
            idx = response_upper.index("MOTIVO:")
            explanation = response[idx + 7:].strip()
            # Prendi solo la prima riga
            explanation = explanation.split("\n")[0].strip()
            return explanation

        # Fallback: usa tutta la risposta dopo la classificazione
        for marker in ["BUG", "REFACTORING"]:
            if marker in response_upper:
                idx = response_upper.index(marker) + len(marker)
                rest = response[idx:].strip()
                # Rimuovi punteggiatura iniziale
                rest = rest.lstrip(":.- ")
                if rest:
                    return rest.split("\n")[0][:100]

        return "Nessuna spiegazione disponibile"
