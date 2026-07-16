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
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Union

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from utils.config import settings
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

# CORS — allow any origin for local development
main.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend static files (CSS, JS)
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
main.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@main.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend index.html at the root URL."""
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
        _get_analytics().add_document(doc_data["filename"], doc_data.get("page_count", 0))
        
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


@main.get("/analytics", tags=["Analytics"])
async def get_analytics():
    """Return the current document processing analytics."""
    vs = _get_vector_store()
    analytics = _get_analytics()
    analytics.sync(vs.list_indexed_documents())
    return analytics.get_analytics()

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

    result = ask(request.question, vs, doc_filter=request.doc_filter)
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
        full_answer = []
        for chunk in chain.stream({"context": context, "question": request.question}):
            full_answer.append(chunk)
            yield f"data: {json.dumps({'token': chunk})}\n\n"
        # Final event with complete answer and sources
        yield f"data: {json.dumps({'done': True, 'answer': ''.join(full_answer), 'sources': sources})}\n\n"

    return StreamingResponse(token_generator(), media_type="text/event-stream")
