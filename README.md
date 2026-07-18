# DocAIApp

A **local-first, CLI-based AI document Q&A application** powered by LangChain, ChromaDB, and Ollama (with Google Gemini fallback).

Index your PDF, DOCX, and TXT documents from a local folder, then ask natural-language questions — all from the terminal.

---

## Features

-  **Multi-format ingestion** — PDF, DOCX, TXT with automatic detection
-  **Smart chunking** — Paragraph- and sentence-aware text splitting with configurable overlap
-  **Vector search** — ChromaDB-backed similarity search with persistent storage
-  **Dual LLM support** — Ollama (local, private) with automatic Google Gemini fallback
-  **Interactive chat** — REPL mode for conversational Q&A sessions
-  **Deduplication** — Skips already-indexed files based on path and modification time
-  **Rich terminal output** — Spinners, tables, and coloured output via `rich`

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.10+** | Required for `type \| None` syntax |
| **Ollama** (recommended) | Install from [ollama.com](https://ollama.com). Pull models: `ollama pull llama3` and `ollama pull nomic-embed-text` |
| **Google Gemini API key** (optional) | Fallback LLM if Ollama is unavailable. Get a key at [ai.google.dev](https://ai.google.dev) |

---

## Installation

```bash
# 1. Clone or navigate to the project directory
cd docaiapp

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
copy .env.example .env       # Windows
# cp .env.example .env       # macOS / Linux

# 5. Edit .env with your settings (especially GEMINI_API_KEY if not using Ollama)
```

### Ollama Setup

```bash
# Install Ollama, then pull the required models:
ollama pull llama3            # Chat / generation model
ollama pull nomic-embed-text  # Embedding model

# Verify Ollama is running:
ollama list
```

---

## Configuration

All settings are controlled via the `.env` file:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(none)* | Google Gemini API key (fallback LLM) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3` | Ollama model for generation |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model for embeddings |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB persistence directory |
| `CHUNK_SIZE` | `500` | Max characters per text chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `TOP_K_RESULTS` | `5` | Number of chunks retrieved per query |
| `DOCS_DIR` | `./documents` | Default document scan directory |

---

## Usage

### Index Documents

Scan a local folder and index all supported documents:

```bash
# Index from a specific folder
python main.py index --path /path/to/your/documents

# Index from the default DOCS_DIR (set in .env)
python main.py index
```

Already-indexed files are automatically skipped. Modified files are re-indexed.

### List Indexed Documents

```bash
python main.py list
```

### Ask a Question

```bash
python main.py ask "What are the key findings in the report?"
```

### Interactive Chat

```bash
python main.py chat
```

Type questions at the `You:` prompt. Type `exit` or `quit` (or press `Ctrl+C`) to leave.

---

## Project Structure

```
docaiapp/
├── main.py                  # CLI entry point (argparse + rich)
├── ingestion/
│   ├── loader.py            # PDF, DOCX, TXT loading
│   ├── chunker.py           # Text splitting with overlap
│   └── embedder.py          # Ollama embedding wrapper
├── retrieval/
│   ├── vector_store.py      # ChromaDB storage & search
│   └── retriever.py         # Similarity retrieval
├── generation/
│   ├── llm.py               # Ollama + Gemini fallback
│   └── chain.py             # LangChain RAG chain
├── utils/
│   └── config.py            # .env loader & settings singleton
├── tests/
│   └── test_pipeline.py     # End-to-end integration test
├── .env.example
├── requirements.txt
└── README.md
```

---

## Running Tests

```bash
python tests/test_pipeline.py
```

This creates temporary test files, runs the full pipeline (load → chunk → embed → ask), and verifies the output.

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `ConnectionError` on indexing | Ensure Ollama is running: `ollama serve` |
| `RuntimeError: Neither Ollama nor Gemini` | Start Ollama or set `GEMINI_API_KEY` in `.env` |
| `No documents indexed yet` | Run `python main.py index --path <folder>` first |
| Encrypted PDF errors | Only PDFs with empty or no passwords are supported |

---

## License

This project is provided as-is for educational and personal use.
