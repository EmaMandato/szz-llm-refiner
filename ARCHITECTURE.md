# SZZ-LLM-Refiner - Documentazione Architetturale

## Indice

1. [Panoramica del Progetto](#1-panoramica-del-progetto)
2. [Struttura del Progetto](#2-struttura-del-progetto)
3. [Architettura e Componenti](#3-architettura-e-componenti)
4. [Build Automation](#4-build-automation)
5. [Flusso di Lavoro](#5-flusso-di-lavoro)
6. [Testing](#6-testing)
7. [CI/CD Pipeline](#7-cicd-pipeline)
8. [Tecnologie Utilizzate](#8-tecnologie-utilizzate)
9. [Configurazione](#9-configurazione)

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
- Filtraggio dei falsi positivi tramite LLM
- Output in formato JSON/text
- Plugin PyCharm per integrazione IDE

---

## 2. Struttura del Progetto

```
szz-llm-refiner/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Pipeline CI GitHub Actions
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
│       ├── main.py                # Entry point CLI
│       ├── miner.py               # Modulo Git mining
│       └── llm_refiner.py         # Modulo LLM refinement
│
├── tests/                         # Test suite
│   ├── test_miner.py              # Test base GitMiner
│   ├── test_refiner.py            # Test base LLMRefiner
│   ├── test_szz_bic.py            # Test SZZ + mock LLM
│   └── test_miner_coverage.py     # Test coverage aggiuntivi
│
├── pyproject.toml                 # Configurazione Poetry
├── poetry.lock                    # Lock delle dipendenze
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
| `--skip-llm` | Salta raffinamento LLM | false |

#### `miner.py` - Git Mining e Algoritmo SZZ

**Classe:** `GitMiner`

**Responsabilità:**
- Estrazione fixing commits tramite analisi messaggi (keywords: "fix", "bug", "issue")
- Estrazione diff e metadati commit
- Implementazione algoritmo SZZ con git blame

**Metodi principali:**

| Metodo | Descrizione |
|--------|-------------|
| `get_fixing_commits()` | Identifica fix commits via keyword matching |
| `get_commit_diff(hash)` | Estrae messaggio e diff completo |
| `get_bug_inducing_commits(fix_commit)` | Traccia bug-inducing via git blame |
| `get_fix_details(hash)` | Estrae file modificati e righe eliminate |

**Algoritmo SZZ:**
1. Usa `git diff` con `unified=0` per identificare righe eliminate
2. Per ogni range di righe eliminate, esegue `git blame` per trovare il commit introduttore
3. Restituisce set unico di hash commit bug-inducing

#### `llm_refiner.py` - Raffinamento LLM

**Classe:** `LLMRefiner`

**Responsabilità:**
- Filtraggio falsi positivi tramite analisi LLM
- Distinzione tra fix reali e refactoring/documentazione

**Metodo principale:**
- `is_real_bug_fix(commit_message, diff)`: Interroga API Ollama

**Integrazione:**
- Comunica con Ollama HTTP API a `http://localhost:11434/api/generate`
- Invia prompt chiedendo classificazione "BUG" o "REFACTORING"

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
- Rendering colorato (rosso per BUG, grigio per REFACTORING)
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

#### `AnalysisModels.kt` - Data Models (~72 righe)

**Data classes Kotlin con annotazioni Gson:**
- `AnalysisResult`: Dettagli fix commit
- `AnalysisReport`: Report analisi completo
- `AnalysisConfig`: Parametri configurazione
- `AnalysisProgress`: Tracking progresso
- `AnalysisStatus`: Enum (IDLE, RUNNING, COMPLETED, FAILED, CANCELLED)
- `AnalysisError`: Modello risposta errore

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

| Modulo | Coverage |
|--------|----------|
| `llm_refiner.py` | **100%** |
| `miner.py` | **87%** |
| **Totale** | **88%** |

### 6.2 Struttura Test

```
tests/
├── test_miner.py              # Test base GitMiner
├── test_refiner.py            # Test base LLMRefiner  
├── test_szz_bic.py            # Test SZZ algorithm + LLM mock
└── test_miner_coverage.py     # Test coverage aggiuntivi
```

### 6.3 Tipologie di Test Implementate

#### 6.3.1 White-Box Testing

Test basati sulla conoscenza della struttura interna del codice. Verificano i singoli metodi e i diversi branch condizionali.

| Classe Test | Funzione Testata | Cosa Verifica |
|-------------|------------------|---------------|
| `TestGetFixingCommits` | `get_fixing_commits()` | Identificazione commit con keyword "fix", "bug", "issue" |
| `TestGetFixDetails` | `get_fix_details()` | Estrazione file modificati e linee cancellate |
| `TestGetCommitDiff` | `get_commit_diff()` | Restituzione messaggio e diff testuale |
| `TestGetBugInducingCommitsBranches` | `get_bug_inducing_commits()` | Copertura branch condizionali |
| `TestRunGit` | `_run_git()` | Robustezza helper Git |

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
| `test_classifies_null_pointer_fix_as_bug` | Risposta "BUG" | `is_real_bug_fix()` → `True` |
| `test_classifies_refactoring_as_not_bug` | Risposta "REFACTORING" | `is_real_bug_fix()` → `False` |
| `test_handles_llm_timeout` | Timeout connessione | Gestione graceful → `False` |
| `test_handles_malformed_response` | JSON invalido | Gestione errore → `False` |
| `test_handles_connection_error` | Ollama non raggiungibile | Gestione errore → `False` |

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
| Test totali | **36** |
| Test passati | **36** |
| Coverage statement | **88%** |
| Coverage branch | **88%** |
| File di test | **4** |
| Classi di test | **9** |

### 6.8 File Generati

| File/Cartella | Descrizione | Git |
|---------------|-------------|-----|
| `htmlcov/` | Report coverage HTML interattivo | `.gitignore` |
| `.coverage` | Database coverage pytest-cov | `.gitignore` |
| `.pytest_cache/` | Cache pytest | `.gitignore` |

---

## 7. CI/CD Pipeline

### GitHub Actions

**File:** `.github/workflows/ci.yml`
**Trigger:** Push su main e pull request

**Pipeline Steps:**

```yaml
1. Checkout code
2. Setup Python 3.10
3. Install Poetry
4. Install dependencies: poetry install
5. Run tests with coverage: poetry run pytest --cov=src
```

### Obiettivi

- Setup ambiente deterministico
- Testing automatizzato con metriche coverage
- Report coverage per quality assurance

---

## 8. Tecnologie Utilizzate

### 8.1 Stack Python

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

### 8.2 Stack Plugin

| Componente | Tecnologia | Versione |
|------------|-----------|----------|
| Linguaggio | Kotlin | 2.1.0 |
| JDK | Java | 21 |
| Build System | Gradle | 8.x |
| IDE Platform | IntelliJ | 2025.1 |
| Target IDE | PyCharm Professional | 2025.1 |
| JSON Parsing | Gson | 2.10.1 |
| UI Framework | IntelliJ Swing | Platform SDK |

### 8.3 Servizi Esterni

- **Git**: Operazioni command-line per analisi repository
- **Ollama**: Server inferenza LLM locale (qwen2.5-coder:7b)
- **GitHub**: Version control e CI/CD

---

## 9. Configurazione

### 9.1 File di Configurazione

| File | Scopo |
|------|-------|
| `pyproject.toml` | Config Poetry, dipendenze, entry points |
| `poetry.lock` | Versioni dipendenze locked |
| `build.gradle.kts` | Config build plugin, SDK IDE |
| `settings.gradle.kts` | Repository plugin Gradle |
| `plugin.xml` | Manifest plugin (UI, actions, services) |
| `.github/workflows/ci.yml` | Pipeline CI GitHub Actions |
| `gradle.properties` | Ottimizzazioni Gradle |

### 9.2 Entry Points

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

### 9.3 Requisiti Sistema

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
| File sorgente Python | 3 |
| File sorgente Kotlin | 7 |
| File test | 4 |
| Test totali | 36 |
| Coverage | 88% |
| Dimensione sorgenti Python | ~60 KB |
| Dimensione test | ~25 KB |

---

## Cronologia Commit Recenti

```
28cb331 - fix(plugin): disable instrumentCode task and fix JSON parsing
8ba90ed - fix: separate progress output (stderr) from JSON output (stdout)
7323360 - kotlin classes
af225e2 - feat(plugin): rewrite PyCharm plugin as SZZ-LLM Bug Analyzer
6b5c29a - feat(cli): add CLI with URL cloning and JSON output for plugin integration
```
