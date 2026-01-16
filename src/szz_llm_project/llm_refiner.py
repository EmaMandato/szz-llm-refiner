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
            # Configurazione per rendere l'output deterministico
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,  # Forza il modello a scegliere sempre la parola più probabile
                    "num_predict": 5,    # Limita la lunghezza della risposta (ci serve solo una parola)
                    "seed": 42           # Un seed fisso aiuta ulteriormente la riproducibilità
                }
            }

            response = requests.post(self.url, json=payload, timeout=30)
            # Converte la risposta in maiuscolo per il confronto
            result = response.json().get("response", "").upper().strip()

            # Restituisce True solo se la risposta inizia esattamente con BUG
            return result.startswith("BUG")

        except Exception as e:
            # In caso di errore (es. Ollama spento), restituisce False per default
            print(f"Errore LLM: {e}")
            return False