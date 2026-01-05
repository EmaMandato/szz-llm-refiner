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
            f"Analizza rigorosamente questo commit.\n"
            f"Messaggio: {commit_message}\n"
            f"Diff: {diff[:2000]}\n\n"
            "Un BUG FIX deve correggere un errore logico (es. NullPointerException, calcolo errato).\n"
            "Se è solo aggiunta di test, documentazione o refactoring, rispondi REFACTORING.\n"
            "Rispondi SOLO con 'BUG' o 'REFACTORING'."
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