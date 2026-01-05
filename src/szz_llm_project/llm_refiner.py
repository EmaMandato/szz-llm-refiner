import requests


class LLMRefiner:
    def __init__(self, model="qwen2.5-coder:7b"):
        self.url = "http://localhost:11434/api/generate"
        self.model = model

    def is_real_bug_fix(self, commit_message, diff):
        """
        Chiede all'LLM se il commit è un vero fix di un bug logico.
        """
        prompt = (
            f"Analizza questo commit message e il relativo diff di codice.\n"
            f"Messaggio: {commit_message}\n"
            f"Diff: {diff[:2000]}\n\n"  # Limitiamo il diff per non sovraccaricare il modello
            f"È una correzione di un bug logico o solo un refactoring/estetica?\n"
            f"Rispondi solo con una parola: 'BUG' o 'REFACTORING'."
        )

        try:
            response = requests.post(self.url, json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }, timeout=30)
            result = response.json().get("response", "").upper()
            return "BUG" in result
        except Exception as e:
            print(f"Errore LLM: {e}")
            return False