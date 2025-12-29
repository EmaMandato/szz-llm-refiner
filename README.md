# SZZ-LLM-Refiner

## Overview
**SZZ-LLM-Refiner** is an advanced software engineering tool designed to identify **bug-inducing commits** within Git repositories. It implements the classic **SZZ algorithm** and enhances its precision by integrating a **Large Language Model (LLM)**—specifically `qwen2.5-coder:7b`—to filter out false positives during the refinement phase.

This project was developed as part of the **Software Engineering 2** curriculum, emphasizing modern development practices such as automated build systems, comprehensive testing, and continuous integration.

## Key Features
* **Git Mining:** Efficient extraction of commit history and bug-fixing patterns using PyDriller.
* **AI-Powered Refinement:** Leverages local LLM inference to analyze code changes and distinguish between actual bugs and refactorings.
* [cite_start]**Build Automation:** Fully managed via **Poetry** and `pyproject.toml` for deterministic dependency management and reproducibility[cite: 1300, 1301].
* [cite_start]**Quality Assurance:** Implements Unit Testing, White Box Testing, and Mutation Testing as required by the course standards[cite: 75, 807].

## Getting Started

### Prerequisites
* Python 3.10+
* Poetry (Build Automation Tool)
* Ollama (running `qwen2.5-coder:7b` locally)

### Installation
[cite_start]Following the build automation principles[cite: 1204, 1302]:
```bash
# Clone the repository
git clone [https://github.com/your-username/szz-llm-refiner.git](https://github.com/your-username/szz-llm-refiner.git)

# Install dependencies and setup the virtual environment
poetry install