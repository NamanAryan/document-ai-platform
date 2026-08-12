# Document AI Platform

An intelligent Retrieval-Augmented Generation (RAG) application that allows users to upload documents and ask natural language questions about their content. The platform performs semantic search over uploaded documents and generates context-aware responses with source citations using a locally hosted Large Language Model (LLM).

---

## Overview

Organizations often manage hundreds of pages of manuals, policies, technical documents, and reports. Finding specific information manually can be slow and inefficient.

Document AI Platform solves this problem by converting uploaded documents into searchable semantic embeddings, allowing users to retrieve information instantly using natural language queries.

Unlike traditional keyword search, this application understands the meaning of a question and retrieves the most relevant document sections before generating an answer.

---

## Features

- Upload PDF, DOCX and TXT documents
- Semantic document search using vector embeddings
- Retrieval-Augmented Generation (RAG)
- Local vector database using ChromaDB
- Context-aware question answering
- Real-time streaming responses
- Source citation for every generated answer
- Local-first architecture for improved privacy
- Analytics Dashboard
  - Total Documents Processed
  - Total Pages Analysed
  - Frequently Asked Questions
  - Search Statistics

---

## System Architecture

```
                User
                  │
                  ▼
        HTML / CSS / JavaScript
                  │
                  ▼
             FastAPI Backend
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
Document Upload         User Question
        │                     │
        ▼                     ▼
Document Loader       Query Embedding
        │                     │
        ▼                     ▼
 Text Chunking         Vector Search
        │                     │
        ▼                     ▼
Embedding Generation  Retrieve Top K Chunks
        │                     │
        └──────────┬──────────┘
                   ▼
              LangChain RAG
                   │
                   ▼
              Ollama LLM
                   │
                   ▼
        Response + Source Citation
                   │
                   ▼
               Frontend
```

---

## Tech Stack

### Backend

- Python
- FastAPI
- LangChain
- ChromaDB

### Frontend

- HTML
- CSS
- JavaScript

### AI

- Ollama
- Local Embedding Model
- Retrieval-Augmented Generation (RAG)

### Database

- ChromaDB Vector Database

---

## Project Structure

```
docaiapp/

├── app.py
├── analytics/
├── frontend/
├── ingestion/
│   ├── loader.py
│   ├── chunker.py
│   └── embedder.py
├── retrieval/
├── generation/
├── documents/
├── chroma_db/
├── utils/
├── tests/
└── requirements.txt
```

---

## How It Works

### 1. Document Upload

- User uploads a document.
- The document loader extracts its contents.
- Text is divided into overlapping chunks.
- Each chunk is converted into vector embeddings.
- Embeddings and metadata are stored inside ChromaDB.

---

### 2. Question Answering

- User submits a natural language question.
- The question is converted into an embedding.
- ChromaDB retrieves the most relevant chunks.
- LangChain constructs the prompt.
- Ollama generates an answer using only the retrieved context.
- The answer and source citations are streamed back to the frontend.

---

## Installation

Clone the repository

```bash
git clone https://github.com/alonasingh/document-ai-platform.git
cd document-ai-platform
```

Create a virtual environment

```bash
python3 -m venv venv
```

Activate it

### macOS / Linux

```bash
source venv/bin/activate
```

### Windows

```bash
venv\Scripts\activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

## Install Ollama

Download and install Ollama

https://ollama.com/download

Pull the required model

```bash
ollama pull llama3.2
```

Start Ollama

```bash
ollama serve
```

---

## Run the Application

Start FastAPI

```bash
uvicorn app:main --reload
```

Open your browser

```
http://localhost:8000
```

---

## Future Improvements

- Cloud vector database support
- Background indexing using Celery
- Multi-user authentication
- Role-based access control
- Document versioning
- OCR support for scanned PDFs
- Cloud deployment
- Enterprise-scale monitoring
- Distributed vector search
- Caching frequently asked queries

---

## Learning Outcomes

This project provided hands-on experience with:

- Retrieval-Augmented Generation (RAG)
- FastAPI backend development
- LangChain orchestration
- Vector databases
- Semantic search
- LLM integration
- REST APIs
- Streaming responses
- Prompt engineering
- AI application architecture

---

## Author

**Alona Singh & Naman Aryan**

B.Tech Information Technology

Manipal Institute of Technology
 
GitHub: https://github.com/alonasingh https://github.com/NamanAryan
