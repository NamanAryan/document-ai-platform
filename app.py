"""
api.py — FastAPI backend for DocAIApp.

Endpoints
---------
    POST /index              Index documents from a local folder.
    GET  /documents          List all indexed documents.
    POST /ask                Ask a one-shot question.
    POST /chat               Ask a question with conversation history.
    GET  /health             Health-check endpoint.
"""

import os
import time
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Union

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from utils.config import settings
from ingestion.embedder import active_embedding_model
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("docaiapp")


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    filename: str
    status: str
    message: str


class AskRequest(BaseModel):
    """Request body for the /ask endpoint."""
    question: str = Field(..., description="The question to ask.")
    doc_filter: Optional[str] = Field(
        default=None,
        description="Optional filename to restrict retrieval to a single document.",
    )


class AskResponse(BaseModel):
    answer: str
    sources: list[str] = []


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""
    question: str = Field(..., description="The current question to ask.")
    doc_filter: Optional[str] = Field(
        default=None,
        description="Optional filename to restrict retrieval.",
    )
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Previous conversation turns for context.",
    )


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []


class DocumentListResponse(BaseModel):
    documents: list[str]
    count: int

class FAQResponse(BaseModel):
    questions: list[str]

class HealthResponse(BaseModel):
    status: str
    has_documents: bool
    docs_dir: str
    chroma_dir: str


# ---------------------------------------------------------------------------
# Shared resources (vector store) — initialised once at startup
# ---------------------------------------------------------------------------

_vector_store = None
_analytics = None
_faq_manager = None


def _get_vector_store():
    """Lazy-initialise and return the singleton VectorStoreManager."""
    global _vector_store
    if _vector_store is None:
        from retrieval.vector_store import VectorStoreManager
        _vector_store = VectorStoreManager()
    return _vector_store


def _get_analytics():
    """Lazy-initialise and return the singleton DocumentAnalytics."""
    global _analytics
    if _analytics is None:
        from analytics.analytics import DocumentAnalytics
        _analytics = DocumentAnalytics()
    return _analytics


def _get_faq_manager():
    """Lazy-initialise and return the singleton FAQManager."""
    global _faq_manager
    if _faq_manager is None:
        from analytics.faq_manager import FAQManager
        _faq_manager = FAQManager()
    return _faq_manager


@asynccontextmanager
async def lifespan(main: FastAPI):
    """Warm up the vector store, LLM, and analytics on startup."""
    logger.info("Starting up: Warming up vector store and LLM...")
    _get_vector_store()
    _get_analytics()
    # Pre-initialise the LLM so the first question is instant
    from generation.llm import get_llm
    get_llm()
    yield


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

main = FastAPI(
    title="DocAIApp API",
    description=(
        "A local-first AI document Q&A API.  "
        "Index documents from a local folder, then ask questions via REST endpoints."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — "*" for local development; a split frontend/backend deployment
# should set CORS_ALLOW_ORIGINS to the frontend origin.  Credentials cannot
# be combined with a wildcard origin, so they are enabled only when the
# allowed origins are named explicitly.
_allow_wildcard = "*" in settings.cors_allow_origins
main.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=not _allow_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"CORS allowed origins: {settings.cors_allow_origins}")

# Serve the frontend static files (CSS, JS).  These are optional: when the
# frontend is hosted separately (Vercel) the backend is API-only.
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
FRONTEND_AVAILABLE = (FRONTEND_DIR / "index.html").exists()

if FRONTEND_AVAILABLE:
    main.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@main.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend index.html, or a pointer to the docs if API-only."""
    if not FRONTEND_AVAILABLE:
        return {"service": "DocAIApp API", "docs": "/docs", "health": "/health"}
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@main.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Return service health and basic config info."""
    logger.info("Health check requested")
    vs = _get_vector_store()
    return HealthResponse(
        status="ok",
        has_documents=vs.has_documents(),
        docs_dir=str(Path(settings.docs_dir).resolve()),
        chroma_dir=str(Path(settings.chroma_persist_dir).resolve()),
    )


@main.get("/documents", response_model=DocumentListResponse, tags=["Documents"])
async def list_documents():
    """List all currently indexed documents."""
    vs = _get_vector_store()
    docs = vs.list_indexed_documents()
    return DocumentListResponse(documents=docs, count=len(docs))


@main.delete("/documents/{filename}", tags=["Documents"])
async def delete_document(filename: str):
    """Delete a document from the vector store and the filesystem."""
    vs = _get_vector_store()
    analytics = _get_analytics()
    
    deleted_from_vs = vs.delete_document(filename)
    
    docs_dir = Path(settings.docs_dir).resolve()
    file_path = docs_dir / filename
    
    deleted_from_fs = False
    if file_path.exists() and file_path.is_file():
        try:
            file_path.unlink()
            deleted_from_fs = True
        except Exception as e:
            logger.error(f"Failed to delete file {filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete file from filesystem: {e}")
            
    if not deleted_from_vs and not deleted_from_fs:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    if deleted_from_vs:
        analytics.remove_document(filename)
        _get_faq_manager().remove_faqs(filename)
        
    return {"message": f"Document '{filename}' deleted successfully."}


@main.post("/upload", response_model=UploadResponse, tags=["Documents"])
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload a document, save it, and index it into the vector store immediately."""
    from ingestion.loader import DocumentLoader, UnsupportedFileTypeError
    from ingestion.chunker import TextChunker
    import shutil
    
    docs_dir = Path(settings.docs_dir).resolve()
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    filename = file.filename

    file_path = docs_dir / filename
    logger.info(f"Uploading file: {filename}")
    
    # Save file to disk
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        logger.error(f"Failed to save file {filename}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")
    
    vs = _get_vector_store()
    if vs.collection_exists(str(file_path)):
        return UploadResponse(filename=filename, status="skipped", message="File already indexed.")
        
    loader = DocumentLoader()
    chunker = TextChunker()
    
    try:
        doc_data = loader.load(file_path)
        metadata = {
            "filename": doc_data["filename"],
            "file_type": doc_data["file_type"],
            "filepath": doc_data["filepath"],
            "mtime": str(os.path.getmtime(file_path)),
        }
        chunks = chunker.chunk(doc_data["text"], metadata)
        vs.add_documents(chunks)
        _get_analytics().add_document(
            doc_data["filename"],
            doc_data.get("page_count", 0),
            file_type=doc_data.get("file_type", "?"),
            size_bytes=file_path.stat().st_size,
        )
        
        def generate_and_save_faq(filename: str):
            from generation.chain import generate_faqs
            try:
                faqs = generate_faqs(_get_vector_store(), doc_filter=filename)
                _get_faq_manager().save_faqs(filename, faqs)
            except Exception as e:
                logger.error(f"Background FAQ generation failed for {filename}: {e}")
                
        background_tasks.add_task(generate_and_save_faq, doc_data["filename"])
        
        logger.info(f"Successfully indexed {filename}")
        return UploadResponse(filename=filename, status="success", message="File indexed successfully.")
    except UnsupportedFileTypeError as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        logger.error(f"Failed to index {filename}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to index file: {exc}")


def _active_llm_description() -> dict:
    """Describe the LLM actually in use, falling back to configured values."""
    import generation.llm as llm_module

    instance = getattr(llm_module, "_llm", None)
    backend = type(instance).__name__ if instance is not None else "not initialised"

    model = settings.ollama_model
    if instance is not None:
        # ChatOllama exposes .model; ChatGoogleGenerativeAI exposes .model too.
        model = getattr(instance, "model", model) or model

    return {
        "backend": backend,
        "model": model,
        "temperature": getattr(instance, "temperature", None) if instance else None,
    }


@main.get("/analytics", tags=["Analytics"])
async def get_analytics():
    """Return detailed indexing, chunking and retrieval statistics."""
    vs = _get_vector_store()
    analytics = _get_analytics()
    analytics.sync(vs.list_indexed_documents())

    doc_stats = analytics.get_analytics()
    index = vs.stats()
    per_doc_index = index.get("per_document", {})
    llm_info = _active_llm_description()

    # Merge the persisted document records with the live per-document
    # chunk counts pulled from Chroma.
    documents = []
    for name, record in sorted(doc_stats["documents"].items()):
        indexed = per_doc_index.get(name, {})
        documents.append({
            "filename": name,
            "file_type": record.get("file_type") or indexed.get("file_type", "?"),
            "pages": record.get("pages", 0),
            "size_bytes": record.get("size_bytes", 0),
            "indexed_at": record.get("indexed_at"),
            "chunks": indexed.get("chunks", 0),
            "characters": indexed.get("characters", 0),
            "avg_chunk_chars": indexed.get("avg_chunk_chars", 0),
        })

    total_chunks = index.get("vector_count", 0)
    total_docs = doc_stats["total_documents"]
    total_chars = index.get("total_characters", 0)
    chunk_size = settings.chunk_size
    overlap = settings.chunk_overlap

    return {
        # Kept flat at the top level for backwards compatibility with any
        # existing consumer of the original two-field response.
        "total_documents": total_docs,
        "total_pages": doc_stats["total_pages"],
        "totals": {
            "documents": total_docs,
            "pages": doc_stats["total_pages"],
            "chunks": total_chunks,
            "characters": total_chars,
            "tokens_est": round(total_chars / 4),
            "source_bytes": doc_stats["total_bytes"],
            "index_size_bytes": index.get("index_size_bytes", 0),
            "avg_chunks_per_doc": round(total_chunks / total_docs, 1) if total_docs else 0,
        },
        "pipeline": {
            "chunk_size": chunk_size,
            "chunk_overlap": overlap,
            "overlap_pct": round(overlap / chunk_size * 100, 1) if chunk_size else 0,
            "top_k": settings.top_k_results,
            "splitter": "RecursiveCharacterTextSplitter",
            "separators": ["\\n\\n", "\\n", ". ", " ", ""],
            "llm_backend": llm_info["backend"],
            "llm_model": llm_info["model"],
            "temperature": llm_info["temperature"],
            "embedding_model": active_embedding_model(),
            "embedding_dimensions": index.get("embedding_dimensions"),
            "distance_metric": index.get("distance_metric"),
            "collection": index.get("collection"),
            "persist_dir": index.get("persist_dir"),
        },
        "chunking": {
            "distribution": index.get("chunk_distribution"),
            "histogram": index.get("chunk_histogram", []),
        },
        "documents": documents,
        "queries": analytics.get_query_stats(),
    }

@main.get("/faq/dynamic", response_model=FAQResponse, tags=["Q&A"])
async def get_dynamic_faqs(doc_filter: Optional[str] = None):
    """Dynamically generate FAQs based on the indexed documents."""
    vs = _get_vector_store()
    if not vs.has_documents():
        return FAQResponse(questions=[])
        
    faq_manager = _get_faq_manager()
    cache_key = doc_filter if doc_filter else "__global__"
    cached_faqs = faq_manager.get_faqs(cache_key)
    
    if cached_faqs:
        return FAQResponse(questions=cached_faqs)
        
    from generation.chain import generate_faqs
    import asyncio
    
    loop = asyncio.get_running_loop()
    faqs = await loop.run_in_executor(None, generate_faqs, vs, doc_filter)
    
    faq_manager.save_faqs(cache_key, faqs)
    return FAQResponse(questions=faqs)

@main.post("/ask", response_model=AskResponse, tags=["Q&A"])
async def ask_question(request: AskRequest):
    """Answer a one-shot question using the RAG pipeline."""
    from generation.chain import ask

    vs = _get_vector_store()

    if not vs.has_documents():
        raise HTTPException(
            status_code=400,
            detail="No documents indexed yet. Call POST /index first.",
        )

    started = time.perf_counter()
    result = ask(request.question, vs, doc_filter=request.doc_filter)
    _get_analytics().record_query(
        request.question,
        latency_ms=(time.perf_counter() - started) * 1000,
        chunks_retrieved=result.get("chunk_count", 0),
        sources=result.get("sources", []),
        doc_filter=request.doc_filter,
        answer_chars=len(result.get("answer", "")),
    )
    return AskResponse(answer=result["answer"], sources=result["sources"])


@main.post("/chat", response_model=ChatResponse, tags=["Q&A"])
async def chat(request: ChatRequest):
    """Answer a question with optional conversation history.

    The history is sent for context but the current RAG pipeline
    handles each question independently against the vector store.
    Future versions can incorporate history into the prompt.
    """
    from generation.chain import ask

    vs = _get_vector_store()

    if not vs.has_documents():
        raise HTTPException(
            status_code=400,
            detail="No documents indexed yet. Call POST /index first.",
        )

    result = ask(request.question, vs, doc_filter=request.doc_filter)
    return ChatResponse(answer=result["answer"], sources=result["sources"])


@main.post("/ask/stream", tags=["Q&A"])
async def ask_question_stream(request: AskRequest):
    """Stream the answer token-by-token using Server-Sent Events.

    The response is a text/event-stream where each SSE data line is a
    JSON object with either a ``token`` key (incremental text) or a
    final ``done`` event containing the full answer and sources.
    """
    logger.info(f"Streaming question received: '{request.question}'")
    import json
    from fastapi.responses import StreamingResponse
    from langchain_core.output_parsers import StrOutputParser
    from generation.llm import get_llm
    from generation.chain import RAG_PROMPT, _format_docs, _extract_sources

    vs = _get_vector_store()

    if not vs.has_documents():
        raise HTTPException(
            status_code=400,
            detail="No documents indexed yet. Call POST /index first.",
        )

    docs = vs.similarity_search(request.question, doc_filter=request.doc_filter)
    logger.info(f"Found {len(docs)} documents for context")

    if not docs:
        async def no_docs():
            msg = json.dumps({
                "done": True,
                "answer": "No relevant documents were found for your question.",
                "sources": [],
            })
            yield f"data: {msg}\n\n"
        return StreamingResponse(no_docs(), media_type="text/event-stream")

    sources = _extract_sources(docs)
    context = _format_docs(docs)
    llm = get_llm()
    chain = RAG_PROMPT | llm | StrOutputParser()

    async def token_generator():
        started = time.perf_counter()
        full_answer = []
        for chunk in chain.stream({"context": context, "question": request.question}):
            full_answer.append(chunk)
            yield f"data: {json.dumps({'token': chunk})}\n\n"
        answer = ''.join(full_answer)
        # Final event with complete answer and sources
        yield f"data: {json.dumps({'done': True, 'answer': answer, 'sources': sources})}\n\n"

        _get_analytics().record_query(
            request.question,
            latency_ms=(time.perf_counter() - started) * 1000,
            chunks_retrieved=len(docs),
            sources=sources,
            doc_filter=request.doc_filter,
            answer_chars=len(answer),
        )

    return StreamingResponse(token_generator(), media_type="text/event-stream")
