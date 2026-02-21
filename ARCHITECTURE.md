# SZZ-LLM-Refiner - Documentazione Architetturale

## Indice

1. [Panoramica del Progetto](#1-panoramica-del-progetto)
2. [Struttura del Progetto](#2-struttura-del-progetto)
3. [Architettura e Componenti](#3-architettura-e-componenti)
4. [Build Automation](#4-build-automation)
5. [Flusso di Lavoro](#5-flusso-di-lavoro)
6. [Testing](#6-testing)
7. [Datasets e Validazione](#7-datasets-e-validazione)
8. [CI/CD Pipeline](#8-cicd-pipeline)
9. [Tecnologie Utilizzate](#9-tecnologie-utilizzate)
10. [Configurazione](#10-configurazione)

---

## 1. Panoramica del Progetto

**SZZ-LLM-Refiner** è uno strumento di Software Engineering progettato per identificare i **bug-inducing commits** nei repository Git. Combina l'algoritmo classico **SZZ** (Software Change and Blame) con il **raffinamento basato su LLM** (Large Language Model) utilizzando Qwen2.5-Coder per migliorare significativamente la precisione filtrando i falsi positivi.

### Scopo

Il progetto è stato sviluppato come parte del corso di **Ingegneria del Software 2**, enfatizzando pratiche di sviluppo moderne tra cui:
- Sistemi di build automatizzati
- Testing completo
- Integrazione continua

### Funzionalità Principali

- Estrazione di fixing commits tramite keyword matching
- Implementazione dell'algoritmo SZZ con git blame
- Filtraggio dei falsi positivi tramite LLM con spiegazione della classificazione
- Sistema di filtri multi-livello (messaggi, modifiche cosmetiche, blacklist)
- Selezione commit per range di date
- Sistema di validazione con dataset benchmark (Defects4J, ICSE2021)
- Calcolo metriche (Precision, Recall, F1, Accuracy)
- Output in formato JSON/text
- Plugin PyCharm per integrazione IDE con:
  - Visualizzazione spiegazioni LLM per ogni classificazione
  - BIC cliccabili con popup dettagli e copia hash

---

## 2. Struttura del Progetto

```
szz-llm-refiner/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Pipeline CI GitHub Actions
│
├── datasets/                      # Dataset di benchmark per validazione
│   ├── defects4j-bugs.json        # Dataset Defects4J (395 bug Java)
│   ├── icse2021-overall.json      # Dataset ICSE 2021 completo
│   ├── icse2021-java.json         # Subset Java ICSE 2021
│   ├── icse2021_ground_truth.csv  # Ground truth estratto
│   └── icse2021_repos.txt         # Lista repository ICSE 2021
│
├── examples/                      # Esempi di configurazione
│   ├── sample_ground_truth.csv    # Esempio formato CSV
│   └── sample_ground_truth.json   # Esempio formato JSON
│
├── scripts/                       # Script di utilità
│   └── convert_datasets.py        # Conversione dataset benchmark
│
├── plugin/                        # Plugin PyCharm (Kotlin)
│   ├── src/main/kotlin/
│   │   └── it/unisannio/ingsw2/szzllm/
│   │       ├── SzzToolWindowFactory.kt      # Factory tool window
│   │       ├── SzzRunAction.kt              # Action handler
│   │       ├── SzzSettings.kt               # Settings persistenti
│   │       ├── SzzSettingsConfigurable.kt   # UI settings
│   │       ├── model/
│   │       │   └── AnalysisModels.kt        # Data models
│   │       ├── services/
│   │       │   └── SzzAnalyzerService.kt    # Servizio analisi
│   │       └── ui/
│   │           └── SzzToolWindowPanel.kt    # UI principale
│   ├── src/main/resources/
│   │   └── META-INF/plugin.xml              # Manifest plugin
│   ├── build.gradle.kts                     # Configurazione Gradle
│   └── settings.gradle.kts
│
├── src/
│   └── szz_llm_project/           # Engine Python (CLI)
│       ├── __init__.py
│       ├── main.py                # Entry point CLI e orchestrazione
│       ├── miner.py               # Modulo Git mining e filtri
│       ├── llm_refiner.py         # Modulo LLM refinement
│       └── validator.py           # Modulo validazione con ground truth
│
├── tests/                         # Test suite
│   ├── test_miner.py              # Test base GitMiner
│   ├── test_refiner.py            # Test base LLMRefiner
│   ├── test_szz_bic.py            # Test SZZ + mock LLM
│   ├── test_miner_coverage.py     # Test coverage miner (tag, date, filtri, BIC)
│   ├── test_validator.py          # Test modulo validazione
│   └── test_main.py               # Test CLI e orchestrazione
│
├── pyproject.toml                 # Configurazione Poetry
├── poetry.lock                    # Lock delle dipendenze
├── sbom.json                      # Software Bill of Materials (SBOM)
├── ARCHITECTURE.md                # Documentazione architetturale
├── README.md                      # Documentazione progetto
└── LICENSE
```

---

## 3. Architettura e Componenti

### 3.1 Architettura Generale

Il progetto è strutturato su **due livelli**:

```
┌─────────────────────────────────────────────────────────────────┐
│                         PyCharm IDE                              │
├─────────────────────────────────────────────────────────────────┤
│  Tool Window Panel (Kotlin UI)                                   │
│  ├─ Selezione Repository (Locale/Remoto)                        │
│  ├─ Selezione Branch (Fetch dinamico)                           │
│  ├─ Configurazione Analisi (Limit, Skip LLM)                    │
│  └─ Visualizzazione Risultati & Dettagli                        │
└────────────────────┬────────────────────────────────────────────┘
                     │ (esegue subprocess)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  SzzAnalyzerService (Kotlin Process Manager)                     │
│  ├─ Costruisce command line con parametri                       │
│  ├─ Esegue: python -m szz_llm_project.main                      │
│  ├─ Parsa stdout (JSON) & stderr (progresso)                    │
│  └─ Notifica UI di progresso & risultati                        │
└────────────────────┬────────────────────────────────────────────┘
                     │ (Python subprocess)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│          Python Engine (CLI - szz_llm_project)                   │
├─────────────────────────────────────────────────────────────────┤
│  main.py → miner.py → llm_refiner.py                            │
└────────────────────┬────────────────────────────────────────────┘
                     │ (REST API)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Ollama (Local LLM Inference)                                    │
│  - Model: qwen2.5-coder:7b                                       │
│  - URL: http://localhost:11434                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Python Engine (CLI)

#### `main.py` - Entry Point e Orchestrazione

**Responsabilità:**
- Parsing argomenti CLI (repository, branch, limit, model, output format)
- Orchestrazione pipeline: Mining → LLM Refinement → SZZ
- Clonazione repository remoti
- Generazione report (text/JSON)
- Cleanup repository temporanei

**Classi principali:**
- `AnalysisResult`: Data model per singola analisi commit
- `AnalysisReport`: Struttura report completa

**Argomenti CLI supportati:**

| Argomento | Descrizione | Default |
|-----------|-------------|---------|
| `--url`, `-u` | URL repository Git | - |
| `--branch`, `-b` | Branch da analizzare | main |
| `--limit`, `-l` | Max commit da analizzare | 10 |
| `--model`, `-m` | Modello Ollama | qwen2.5-coder:7b |
| `--output`, `-o` | Formato output (text/json) | text |
| `--output-file`, `-f` | Salva output su file | - |
| `--skip-llm` | Salta raffinamento LLM | false |
| `--since` | Analizza commit dopo questa data (YYYY-MM-DD) | - |
| `--until` | Analizza commit prima di questa data (YYYY-MM-DD) | - |
| `--validate` | Esegue validazione contro ground truth (CSV/JSON) | - |
| `--validation-limit` | Max campioni da validare | 0 (tutti) |

#### `miner.py` - Git Mining e Algoritmo SZZ

**Classe:** `GitMiner`

**Responsabilità:**
- Estrazione fixing commits tramite analisi messaggi (keywords: "fix", "bug", "issue")
- Estrazione diff e metadati commit
- Implementazione algoritmo SZZ con git blame

**Metodi principali:**

| Metodo | Descrizione |
|--------|-------------|
| `get_fixing_commits(since, until)` | Identifica fix commits via keyword matching con filtri |
| `get_commit_diff(hash)` | Estrae messaggio e diff completo |
| `get_bug_inducing_commits(fix_commit, blacklist)` | Traccia bug-inducing via git blame con filtri |
| `get_fix_details(hash)` | Estrae file modificati e righe eliminate |
| `get_commits_between_dates(since, until)` | Commit in un range di date |
| `get_commit_date(hash)` | Restituisce la data di un commit |
| `should_skip_by_message(msg)` | Pre-filtro veloce basato su keyword |
| `is_cosmetic_change(hash)` | Rileva modifiche solo cosmetiche (rename, commenti, whitespace) |
| `get_commit_message(hash)` | Restituisce solo il messaggio di un commit |

**Sistema di Filtri:**

Il miner implementa un sistema di filtri a più livelli per ridurre i falsi positivi:

1. **Pre-filtro messaggi** (`should_skip_by_message`):
   - Scarta commit con keyword: `refactor`, `style`, `docs`, `chore`, `typo`, `rename`, `whitespace`, `cleanup`, `lint`

2. **Filtro modifiche cosmetiche** (`is_cosmetic_change`):
   - Rileva rinomina di variabili (stessa struttura, nomi diversi)
   - Rileva modifiche solo ai commenti
   - Rileva modifiche solo di whitespace/formattazione

3. **Blacklist dinamica**:
   - I commit scartati come refactoring vengono aggiunti alla blacklist
   - I BIC trovati che matchano la blacklist vengono filtrati

**Algoritmo SZZ:**
1. Usa `git diff` con `unified=0` per identificare righe eliminate
2. Per ogni range di righe eliminate, esegue `git blame` per trovare il commit introduttore
3. Applica filtri sui BIC trovati (blacklist, messaggio, modifiche cosmetiche)
4. Restituisce set filtrato di hash commit bug-inducing

#### `llm_refiner.py` - Raffinamento LLM

**Classe:** `LLMRefiner`

**Responsabilità:**
- Filtraggio falsi positivi tramite analisi LLM
- Distinzione tra fix reali e refactoring/documentazione
- Generazione di spiegazioni per le classificazioni

**Metodo principale:**
- `is_real_bug_fix(commit_message, diff) -> Tuple[bool, str]`: Interroga API Ollama e restituisce:
  - `is_bug`: True se è un bug fix, False altrimenti
  - `explanation`: Breve spiegazione della classificazione generata dall'LLM

**Integrazione:**
- Comunica con Ollama HTTP API a `http://localhost:11434/api/generate`
- Invia prompt chiedendo classificazione "BUG" o "REFACTORING" con motivazione
- Il prompt richiede risposta nel formato:
  ```
  CLASSIFICAZIONE: BUG oppure REFACTORING
  MOTIVO: breve spiegazione (max 20 parole)
  ```

#### `validator.py` - Sistema di Validazione

**Classe:** `ValidationMetrics`, `ValidationResult`

**Responsabilità:**
- Calcolo metriche di validazione (Precision, Recall, F1, Accuracy)
- Caricamento ground truth da file CSV e JSON
- Supporto per diversi formati di dataset (Defects4J, ICSE2021, LLM4SZZ)
- Esecuzione validazione automatizzata contro dataset etichettati

**Data Classes:**

| Classe | Descrizione |
|--------|-------------|
| `ValidationMetrics` | Contiene TP, TN, FP, FN, precision, recall, F1, accuracy |
| `ValidationResult` | Risultato singola validazione (commit, ground truth, prediction) |

**Funzioni principali:**

| Funzione | Descrizione |
|----------|-------------|
| `load_ground_truth(file)` | Carica ground truth auto-detectando formato (CSV/JSON) |
| `load_ground_truth_csv(file)` | Carica da CSV (colonne: commit_hash, is_bug) |
| `load_ground_truth_json(file)` | Carica da JSON (supporta Defects4J, ICSE2021, LLM4SZZ) |
| `run_validation(repo, gt_file, model)` | Esegue validazione completa |
| `calculate_metrics(results)` | Calcola metriche da lista di risultati |
| `print_validation_report(metrics, results)` | Stampa report formattato |

**Formati Ground Truth supportati:**

1. **CSV semplice:**
   ```csv
   commit_hash,is_bug
   abc123,true
   def456,false
   ```

2. **JSON semplice:**
   ```json
   {"commits": [{"hash": "abc", "is_bug": true}]}
   ```

3. **Defects4J:**
   ```json
   [{"bugId": "Chart-1", "project": "Chart", ...}]
   ```

4. **ICSE2021/LLM4SZZ:**
   ```json
   [{"fix_commit": "abc", "is_bug_fix": true}]
   ```

### 3.3 Plugin PyCharm (Kotlin)

#### `SzzToolWindowFactory.kt` - Factory Tool Window

Crea e gestisce la tool window SZZ-LLM in PyCharm.

#### `SzzToolWindowPanel.kt` - UI Principale (~560 righe)

**Componenti UI:**
- Selettore sorgente repository (progetto locale o URL remoto)
- Dropdown branch con pulsante refresh
- Opzioni configurazione analisi
- Tabella risultati (commit fix con tipo e conteggio bug)
- Split view: Tabella risultati + pannello dettagli
- Log output per tracking progresso real-time

**Funzionalità:**
- Fetch dinamico branch via `git branch` e `git ls-remote`
- Modello tabella con hash, tipo, messaggio, conteggio BIC
- Rendering colorato (rosso per BUG, arancione per SKIPPED, grigio per REFACTORING)
- Colonna BIC cliccabile con popup che mostra la lista degli hash
- Copia hash negli appunti al click su un BIC nel popup
- Visualizzazione spiegazione LLM nel pannello dettagli
- Interfaccia a tab (Dettagli, Output Log)

#### `SzzAnalyzerService.kt` - Engine Analisi (~352 righe)

**Tipo:** Project-level service

**Responsabilità:**
- Esecuzione engine Python come subprocess
- Parsing output JSON da CLI
- Tracking progresso da stderr
- Gestione lifecycle processo (start, cancel, terminate)

**Funzionalità:**
- Task background con indicatore progresso
- Listener processo per separazione stdout/stderr
- Parsing JSON report con Gson
- Pattern regex per aggiornamenti progresso
- Sistema notifiche per completamento/errori

#### `SzzRunAction.kt` - Action Handler (~68 righe)

**Menu action:** "Run SZZ-LLM Analysis"
**Shortcut:** `Ctrl+Alt+Z`

#### `AnalysisModels.kt` - Data Models (~80 righe)

**Data classes Kotlin con annotazioni Gson:**
- `AnalysisResult`: Dettagli fix commit (include `llmExplanation` per la spiegazione LLM)
- `AnalysisReport`: Report analisi completo
- `AnalysisConfig`: Parametri configurazione
- `AnalysisProgress`: Tracking progresso
- `AnalysisStatus`: Enum (IDLE, RUNNING, COMPLETED, FAILED, CANCELLED)
- `AnalysisError`: Modello risposta errore

**Campi AnalysisResult:**
| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `fixCommit` | String | Hash del commit di fix |
| `commitMessage` | String | Messaggio del commit |
| `isBug` | Boolean | True se classificato come bug fix |
| `bugInducingCommits` | List<String> | Lista hash dei BIC |
| `skippedReason` | String? | Motivo skip (es. "pre-filter:message", "llm:refactoring") |
| `llmExplanation` | String? | Spiegazione generata dall'LLM per la classificazione |

#### `SzzSettings.kt` - Settings Persistenti (~46 righe)

**Tipo:** Application-level settings (XML storage)

**Parametri configurabili:**
- Python path
- Ollama URL e model
- Defaults analisi (branch, limit, skip LLM)
- Preferenze UI (show output log, auto-scroll)

#### `SzzSettingsConfigurable.kt` - UI Settings (~131 righe)

**Percorso IDE:** Settings → Tools → SZZ-LLM Analyzer

**Sezioni:**
- Python Configuration
- Ollama Configuration
- Analysis Defaults
- UI Preferences

---

## 4. Build Automation

### 4.1 Python - Poetry

**Build Tool:** Poetry 2.0+
**Python Version:** 3.10+

**File configurazione:** `pyproject.toml`

```toml
[tool.poetry.dependencies]
python = "^3.10"
pydriller = "^2.6"      # Analisi storia Git
requests = "^2.31"      # Comunicazione HTTP con Ollama
pydantic = "^2.0"       # Validazione dati

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"         # Unit testing
pytest-cov = "^4.1"     # Coverage e white-box testing
pytest-mock = "^3.15"   # Mocking per test unitari

[tool.poetry.scripts]
szz-run = "szz_llm_project.main:main"
```

**Comandi principali:**

```bash
# Installazione dipendenze
poetry install

# Esecuzione CLI
poetry run szz-run ./repo --limit 20

# Test con coverage
poetry run pytest --cov=src
```

### 4.2 Plugin - Gradle

**Build Tool:** Gradle 8.x
**Plugin:** IntelliJ Platform Gradle Plugin 2.10.5
**Linguaggio:** Kotlin 2.1.0
**JDK:** Java 21

**File configurazione:** `build.gradle.kts`

```kotlin
plugins {
    java
    id("org.jetbrains.kotlin.jvm") version "2.1.0"
    id("org.jetbrains.intellij.platform") version "2.10.5"
}

dependencies {
    intellijPlatform {
        pycharmProfessional("2025.1")
        bundledPlugin("PythonCore")
    }
    implementation("com.google.code.gson:gson:2.10.1")
}
```

**Comandi principali:**

```bash
# Build plugin
./gradlew build

# Run IDE con plugin
./gradlew runIde

# Build distribuzione
./gradlew buildPlugin
```

---

## 5. Flusso di Lavoro

### 5.1 Flusso Analisi Completo

```
1. UTENTE avvia analisi (CLI o Plugin)
         │
         ▼
2. MAIN.PY riceve parametri
         │
         ├─ Se URL remoto → clona repository
         │
         ▼
3. MINER estrae fixing commits
         │
         ├─ Cerca keywords: "fix", "bug", "issue"
         │
         ▼
4. Per ogni fixing commit:
         │
         ├─ Estrae diff
         │
         ├─ [Se LLM abilitato] REFINER classifica: BUG o REFACTORING
         │
         ├─ [Se BUG] MINER applica SZZ (git blame)
         │
         └─ Raccoglie bug-inducing commits
         │
         ▼
5. MAIN.PY genera report
         │
         ├─ stdout: JSON con risultati
         ├─ stderr: messaggi progresso
         │
         ▼
6. [Se Plugin] ANALYZER SERVICE parsa output
         │
         └─ Aggiorna UI con risultati
```

### 5.2 Comunicazione Plugin ↔ Engine

```
Plugin (Kotlin)                    Engine (Python)
      │                                   │
      │ ─── subprocess spawn ──────────► │
      │     python -m szz_llm_project... │
      │                                   │
      │ ◄──── stderr (progresso) ─────── │
      │       "Analyzing commit 1/10..." │
      │                                   │
      │ ◄──── stderr (progresso) ─────── │
      │       "Running LLM refinement..."│
      │                                   │
      │ ◄──── stdout (JSON) ───────────  │
      │       {"results": [...]}          │
      │                                   │
      ▼                                   ▼
   TERMINA                            EXIT
```

---

## 6. Testing

### 6.1 Panoramica

Il progetto implementa una suite di test completa utilizzando **pytest** come framework principale, con supporto per coverage analysis e mocking.

**Framework e Tool:**

| Tool | Versione | Scopo |
|------|----------|-------|
| pytest | 8.0+ | Framework testing |
| pytest-cov | 4.1+ | Coverage analysis |
| pytest-mock | 3.15+ | Mocking dependencies |

**Risultati Coverage:**

| Modulo | Stmts | Miss | Branch | Cover |
|--------|-------|------|--------|-------|
| `llm_refiner.py` | 15 | 0 | 0 | **100%** |
| `miner.py` | 221 | 19 | 118 | **89%** |
| `validator.py` | 148 | 0 | 54 | **99%** |
| `main.py` | 285 | 82 | 92 | **69%** |
| **Totale** | **669** | **101** | **264** | **83%** |

### 6.2 Struttura Test

```
tests/
├── test_miner.py              # Test base GitMiner
├── test_refiner.py            # Test base LLMRefiner
├── test_szz_bic.py            # Test SZZ algorithm + LLM mock
├── test_miner_coverage.py     # Test coverage miner (tag, date, filtri, BIC)
├── test_validator.py          # Test modulo validazione
└── test_main.py               # Test CLI e orchestrazione
```

### 6.3 Tipologie di Test Implementate

#### 6.3.1 White-Box Testing

Test basati sulla conoscenza della struttura interna del codice. Verificano i singoli metodi e i diversi branch condizionali.

**test_miner_coverage.py — GitMiner:**

| Classe Test | Funzione Testata | Cosa Verifica |
|-------------|------------------|---------------|
| `TestGetFixingCommits` | `get_fixing_commits()` | Identificazione commit con keyword "fix", "bug", "issue" |
| `TestGetFixDetails` | `get_fix_details()` | Estrazione file modificati e linee cancellate |
| `TestGetCommitDiff` | `get_commit_diff()` | Restituzione messaggio e diff testuale |
| `TestGetBugInducingCommitsBranches` | `get_bug_inducing_commits()` | Copertura branch condizionali |
| `TestRunGit` | `_run_git()` | Robustezza helper Git |
| `TestGetCommitDate` | `get_commit_date()` | Parsing data commit, hash invalido → None |
| `TestGetCommitsBetweenDates` | `get_commits_between_dates()` | Filtri since/until, range vuoto |
| `TestShouldSkipByMessage` | `should_skip_by_message()` | 18 test: tutti i pattern di skip (refactor, docs, style, ecc.) |
| `TestIsCosmeticChange` | `is_cosmetic_change()` | Commenti, whitespace, rinomina variabili, vere modifiche, diff vuoto |
| `TestGetFixingCommitsWithFilters` | `get_fixing_commits()` | Filtro per date range, nessun filtro |
| `TestBICFiltering` | `get_bug_inducing_commits()` | Blacklist, filtro messaggio BIC, filtro cosmetico BIC |

**test_validator.py — Validator:**

| Classe Test | Funzione Testata | Cosa Verifica |
|-------------|------------------|---------------|
| `TestCalculateMetrics` | `calculate_metrics()` | Calcolo TP/TN/FP/FN, precision, recall, F1, accuracy, lista vuota |
| `TestLoadGroundTruthCSV` | `load_ground_truth_csv()` | CSV standard, colonne alternative, valori yes/no, CSV vuoto |
| `TestLoadGroundTruthJSON` | `load_ground_truth_json()` | Formati Simple, Defects4J, LLM4SZZ, label stringa/numerico |
| `TestLoadGroundTruth` | `load_ground_truth()` | Auto-detect CSV/JSON, formato non supportato → ValueError |
| `TestRunValidation` | `run_validation()` | Validazione con mock, limit, verbose, errori, ground truth vuoto |
| `TestPrintValidationReport` | `print_validation_report()` | Report formattato, errori troncati, show_errors=False |

**test_main.py — CLI e Orchestrazione:**

| Classe Test | Funzione Testata | Cosa Verifica |
|-------------|------------------|---------------|
| `TestParseDate` | `parse_date()` | Formati YYYY-MM-DD, ISO, timezone, errori |
| `TestCheckGitInstalled` | `check_git_installed()` | Git presente, FileNotFoundError, returncode != 0 |
| `TestCheckOllamaRunning` | `check_ollama_running()` | Status 200, connessione rifiutata, status 500 |
| `TestCloneRepository` | `clone_repository()` | Clone OK, fallback branch, errore clone |
| `TestLog` | `log()` | Modalità stdout vs stderr (JSON mode) |
| `TestPrintReport` | `print_report()` | Formato text/JSON, selection params, errori, BIC troncati |
| `TestRunAnalysis` | `run_analysis()` | Skip LLM, skip messaggio, LLM refactoring/bug, strategie date |
| `TestAnalysisDataclasses` | Dataclass | AnalysisResult (con llm_explanation), FilterStats, AnalysisReport |

#### 6.3.2 Test di Integrazione

Test che verificano il funzionamento dell'intero algoritmo SZZ in scenari controllati.

**Classe:** `TestGetBugInducingCommits`

**Metodologia:**
1. Crea un repository Git temporaneo con storia controllata
2. Simula uno scenario realistico di introduzione e fix di un bug
3. Verifica che l'algoritmo SZZ identifichi correttamente il Bug-Inducing Commit

**Scenario di test:**
```
Commit A (initial): Classe Service con metodo process()
Commit B (BIC):     Aggiunge "if (data == null) return;"  ← BUG INTRODOTTO
Commit C (fix):     Sostituisce con "throw new Exception" ← FIX
```

**Test implementati:**
- `test_szz_identifies_correct_bic`: Verifica identificazione BIC corretto
- `test_szz_excludes_unrelated_commits`: Verifica esclusione commit non correlati
- `test_szz_excludes_fix_commit_itself`: Verifica che il fix non sia identificato come BIC

#### 6.3.3 Test con Mock

Test che simulano le dipendenze esterne (Ollama) per verificare il comportamento del componente LLMRefiner in isolamento.

**Classe:** `TestLLMRefinerMocked`

**Tecnica:** Utilizzo di `pytest-mock` per intercettare le chiamate HTTP a Ollama e simulare diverse risposte.

| Test | Scenario Simulato | Risultato Atteso |
|------|-------------------|------------------|
| `test_classifies_null_pointer_fix_as_bug` | Risposta "BUG" con motivo | `is_real_bug_fix()` → `(True, "...")` |
| `test_classifies_refactoring_as_not_bug` | Risposta "REFACTORING" con motivo | `is_real_bug_fix()` → `(False, "...")` |
| `test_handles_llm_timeout` | Timeout connessione | Gestione graceful → `(False, "Errore...")` |
| `test_handles_malformed_response` | JSON invalido | Gestione errore → `(False, "...")` |
| `test_handles_connection_error` | Ollama non raggiungibile | Gestione errore → `(False, "...")` |

**Vantaggi del mocking:**
- Test eseguibili senza Ollama attivo
- Esecuzione veloce (nessuna chiamata HTTP reale)
- Risultati deterministici e riproducibili
- Possibilità di simulare scenari di errore

#### 6.3.4 Test Edge Cases

Test per verificare il comportamento in situazioni limite.

| Test | Scenario | Verifica |
|------|----------|----------|
| `test_szz_handles_first_commit` | Commit senza parent | Non crasha, restituisce lista vuota |
| `test_szz_handles_only_additions` | Commit con solo aggiunte | Restituisce lista vuota (niente da tracciare) |
| `test_szz_handles_file_rename` | File rinominato | Gestione corretta senza crash |
| `test_no_parent_commit` | Primo commit del repository | Gestione caso limite |
| `test_count_zero_skipped` | Nessuna linea rimossa | Skip corretto del processing |
| `test_blame_on_nonexistent_file` | Blame su file inesistente | Gestione errore graceful |

### 6.4 Tecniche di Testing Applicate

| Tecnica | Descrizione | Applicazione nel Progetto |
|---------|-------------|---------------------------|
| **Statement Coverage** | Verifica che ogni linea sia eseguita almeno una volta | `pytest --cov` |
| **Branch Coverage** | Verifica che ogni ramo if/else sia attraversato | `pytest --cov-branch` |
| **Mocking** | Simulazione dipendenze esterne | `pytest-mock` per API Ollama |
| **Fixture** | Setup/teardown automatico per ogni test | Repository Git temporanei |
| **Equivalence Partitioning** | Input divisi in classi equivalenti | Commit fix/bug/issue/refactor |
| **Boundary Value Analysis** | Test ai valori limite | Primo commit, file vuoti, hash corti |

### 6.5 Dettaglio Classi di Test

#### `TestGetFixingCommits`

**Cosa testa:** La funzione `get_fixing_commits()` che identifica i potenziali fix commit.

**Come funziona:**
1. Crea repository con commit di diversi tipi (fix, bug, issue, refactor)
2. Esegue `get_fixing_commits()`
3. Verifica che includa solo commit con keyword corrette
4. Verifica case-insensitivity ("FIX" = "fix")

**Perché è importante:** È il primo step dell'algoritmo SZZ; se fallisce, l'intera pipeline è compromessa.

#### `TestGetFixDetails`

**Cosa testa:** La funzione `get_fix_details()` che estrae le modifiche da un commit.

**Come funziona:**
1. Crea repository con file contenente linea di debug
2. Crea commit che rimuove quella linea
3. Verifica estrazione corretta di file path e linee cancellate

**Perché è importante:** Fornisce i dati necessari per il git blame; errori qui causano BIC mancanti o errati.

#### `TestGetBugInducingCommitsBranches`

**Cosa testa:** I diversi percorsi di esecuzione in `get_bug_inducing_commits()`.

**Branch coperti:**
- Commit senza parent (`if not parent: return []`)
- Nessuna linea rimossa (`if count > 0`)
- Hunk header con/senza virgola (`-10,5` vs `-10`)
- Gestione errori blame

**Perché è importante:** Garantisce robustezza in tutti gli scenari possibili.

#### `TestShouldSkipByMessage`

**Cosa testa:** Il pre-filtro `should_skip_by_message()` con 18 scenari.

**Come funziona:**
1. Verifica ogni keyword di `SKIP_KEYWORDS` con i 3 pattern (prefisso con `:`, con `(`, con spazio)
2. Verifica case-insensitivity
3. Verifica che messaggi di bug fix e feature NON vengano scartati
4. Verifica che keyword nel mezzo del messaggio non triggerino lo skip

#### `TestIsCosmeticChange`

**Cosa testa:** Il rilevamento di modifiche cosmetiche via `is_cosmetic_change()`.

**Scenari coperti:**
- Commit con sole modifiche ai commenti → `True`
- Commit con sole modifiche whitespace → `True`
- Commit con rinomina variabili → `True`
- Commit con vere modifiche logiche → `False`
- Commit con diff vuoto → `False`

#### `TestBICFiltering`

**Cosa testa:** I filtri applicati ai Bug-Inducing Commits trovati dall'SZZ.

**Filtri verificati:**
- **Blacklist**: BIC presente nella blacklist viene scartato
- **Messaggio**: BIC con messaggio "refactor:/docs:/style:" viene scartato
- **Cosmetic**: BIC con sole modifiche cosmetiche viene scartato

#### `TestRunValidation`

**Cosa testa:** L'esecuzione end-to-end della validazione con mock di GitMiner e LLMRefiner.

**Scenari coperti:**
- Validazione base con predizioni miste
- Limite campioni (`limit`)
- Modalità verbose con output su stdout
- Gestione errori su singoli commit (skip graceful)
- Ground truth vuoto → `ValueError`
- Nessun commit trovato nel repo → `ValueError`

#### `TestRunAnalysis`

**Cosa testa:** La pipeline completa di analisi in `run_analysis()`.

**Scenari coperti:**
- Analisi senza LLM (`skip_llm=True`)
- Skip per pre-filtro messaggio
- LLM classifica come REFACTORING (con spiegazione)
- LLM conferma BUG con SZZ (con spiegazione)
- Strategia selezione per date range
- `limit=0` (analizza tutti i commit)

### 6.6 Esecuzione Test

```bash
# Esegui tutti i test
pytest tests/ -v

# Esegui con coverage testuale
pytest tests/ --cov=szz_llm_project --cov-branch --cov-report=term-missing

# Genera report HTML coverage
pytest tests/ --cov=szz_llm_project --cov-report=html

# Apri report HTML (Windows)
Invoke-Item htmlcov\index.html

# Esegui singolo file di test
pytest tests/test_szz_bic.py -v

# Esegui singolo test
pytest tests/test_szz_bic.py::TestGetBugInducingCommits::test_szz_identifies_correct_bic -v
```

### 6.7 Metriche di Testing

| Metrica | Valore |
|---------|--------|
| Test totali | **147** |
| Test passati | **147** |
| Coverage totale | **83%** |
| Coverage branch | **83%** |
| File di test | **6** |
| Classi di test | **20** |

### 6.8 File Generati

| File/Cartella | Descrizione | Git |
|---------------|-------------|-----|
| `htmlcov/` | Report coverage HTML interattivo | `.gitignore` |
| `.coverage` | Database coverage pytest-cov | `.gitignore` |
| `.pytest_cache/` | Cache pytest | `.gitignore` |

---

## 7. Datasets e Validazione

### 7.1 Dataset Disponibili

Il progetto include dataset pubblici per la validazione dell'algoritmo SZZ-LLM:

| Dataset | File | Descrizione | Campioni |
|---------|------|-------------|----------|
| **Defects4J** | `defects4j-bugs.json` | Bug reali da progetti Java open-source | 395 |
| **ICSE 2021** | `icse2021-overall.json` | Dataset completo paper ICSE 2021 SZZ evaluation | ~1900 |
| **ICSE 2021 Java** | `icse2021-java.json` | Subset solo progetti Java | - |

### 7.2 Struttura Dataset

**Defects4J:**
- Contiene SOLO bug confermati (utile per testare recall, non precision)
- Campi: `bugId`, `project`, `diff`, `failingTests`
- Progetti: Chart, Closure, Lang, Math, Mockito, Time

**ICSE 2021:**
- Fix commits etichettati manualmente con BIC associati
- Campi: `repository`, `fix.commit.hash`, `fix.commit.message`, `bug_inducing_commits`
- Include 1625 repository GitHub unici

### 7.3 Script di Conversione

Lo script `scripts/convert_datasets.py` converte i dataset nel formato di validazione:

```bash
# Converti Defects4J
python scripts/convert_datasets.py defects4j datasets/defects4j-bugs.json -o ground_truth.csv

# Converti ICSE 2021
python scripts/convert_datasets.py icse2021 datasets/icse2021-overall.json -o ground_truth.csv

# Estrai lista repository
python scripts/convert_datasets.py repos datasets/icse2021-overall.json -o repos.txt
```

### 7.4 Esecuzione Validazione

```bash
# Validazione base
szz-run ./repo --validate ground_truth.csv

# Con limite campioni
szz-run ./repo --validate defects4j.json --validation-limit 50

# Output JSON
szz-run ./repo --validate ground_truth.csv --output json
```

### 7.5 Metriche Calcolate

| Metrica | Formula | Descrizione |
|---------|---------|-------------|
| **Precision** | TP / (TP + FP) | % di predizioni BUG che sono corrette |
| **Recall** | TP / (TP + FN) | % di bug reali identificati |
| **F1 Score** | 2 × (P × R) / (P + R) | Media armonica di precision e recall |
| **Accuracy** | (TP + TN) / Total | % di predizioni corrette totali |

### 7.6 Esempio Output Validazione

```
============================================================
VALIDATION REPORT
============================================================

Total samples validated: 100

Confusion Matrix:
                    Predicted
                  BUG     REF
  Actual BUG       72       8
  Actual REF        5      15

Metrics:
  Precision: 93.51%
  Recall:    90.00%
  F1 Score:  91.72%
  Accuracy:  87.00%
============================================================
```

---

## 8. CI/CD Pipeline

### 8.1 GitHub Actions

**File:** `.github/workflows/ci.yml`
**Trigger:** Push su main e pull request

**Pipeline Steps:**

```yaml
1. Checkout code
2. Setup Python 3.12
3. Install Poetry
4. Install dependencies: poetry install
5. Run tests with coverage (threshold 80%, branch coverage, report XML + HTML)
6. Upload artifact: coverage-report (coverage.xml + htmlcov/)
```

### Obiettivi

- Setup ambiente deterministico
- Testing automatizzato con metriche coverage (soglia minima 80%)
- Report coverage in formato XML e HTML interattivo
- Artifact scaricabile dalla pagina del workflow run

---

## 9. Tecnologie Utilizzate

### 9.1 Stack Python

| Componente | Tecnologia | Versione |
|------------|-----------|----------|
| Linguaggio | Python | 3.10+ |
| Build Tool | Poetry | 2.0+ |
| Git Mining | PyDriller | 2.6+ |
| HTTP Client | requests | 2.31+ |
| Data Validation | Pydantic | 2.0+ |
| Testing | pytest | 8.0+ |
| Coverage | pytest-cov | 4.1+ |
| Mocking | pytest-mock | 3.15+ |

### 9.2 Stack Plugin

| Componente | Tecnologia | Versione |
|------------|-----------|----------|
| Linguaggio | Kotlin | 2.1.0 |
| JDK | Java | 21 |
| Build System | Gradle | 8.x |
| IDE Platform | IntelliJ | 2025.1 |
| Target IDE | PyCharm Professional | 2025.1 |
| JSON Parsing | Gson | 2.10.1 |
| UI Framework | IntelliJ Swing | Platform SDK |

### 9.3 Servizi Esterni

- **Git**: Operazioni command-line per analisi repository
- **Ollama**: Server inferenza LLM locale (qwen2.5-coder:7b)
- **GitHub**: Version control e CI/CD

---

## 10. Configurazione

### 10.1 File di Configurazione

| File | Scopo |
|------|-------|
| `pyproject.toml` | Config Poetry, dipendenze, entry points |
| `poetry.lock` | Versioni dipendenze locked |
| `build.gradle.kts` | Config build plugin, SDK IDE |
| `settings.gradle.kts` | Repository plugin Gradle |
| `plugin.xml` | Manifest plugin (UI, actions, services) |
| `.github/workflows/ci.yml` | Pipeline CI GitHub Actions |
| `gradle.properties` | Ottimizzazioni Gradle |

### 10.2 Entry Points

#### CLI Python

```bash
# Repository locale
szz-run ./my-repo

# Repository remoto
szz-run --url https://github.com/user/repo

# Con opzioni
szz-run ./repo --limit 50 --output json --skip-llm
```

#### Plugin PyCharm

- **Tools Menu**: "Run SZZ-LLM Analysis"
- **Keyboard Shortcut**: `Ctrl+Alt+Z`
- **VCS Menu**: "Find Bug-Inducing Commits"
- **Context Menu**: Right-click → "Analyze with SZZ-LLM"
- **Tool Window**: "SZZ-LLM Analyzer" (pannello bottom)
- **Settings**: IDE Settings → Tools → SZZ-LLM Analyzer

### 10.3 Requisiti Sistema

**Python Engine:**
- Python 3.10+
- Poetry 2.0+
- Git CLI
- Ollama con modello qwen2.5-coder:7b (opzionale)

**Plugin:**
- PyCharm Professional 2025.1
- Java 21 (per sviluppo)

---

## Statistiche Progetto

| Metrica | Valore |
|---------|--------|
| File sorgente Python | 4 |
| File sorgente Kotlin | 7 |
| File test | 6 |
| Test totali | 147 |
| Coverage | 83% |
| Dataset campioni | ~2300 |

---

## Cronologia Commit Recenti

```
f61361d - feat: add datasets, validation system and enhanced mining capabilities
e8b3037 - update version
f218a99 - ci: add test coverage with 80% threshold
9ec1037 - fix: update Python SDK version and add tests for bug-inducing commits
446090d - feat(plugin): add remote repository support and improve UI/UX
28cb331 - fix(plugin): disable instrumentCode task and fix JSON parsing
```
