"""
generation/chain.py — RAG chain assembly using LangChain Expression Language.

Builds the full retrieval-augmented generation pipeline:
    retriever → format_docs → prompt → LLM → StrOutputParser
"""

import sys
import json
import re
from typing import Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from generation.llm import get_llm
from retrieval.vector_store import VectorStoreManager






RAG_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a helpful document assistant. Answer the user's question "
        "using ONLY the context provided below. Follow these rules strictly:\n"
        "1. Answer directly. Do NOT say 'according to the document' or "
        "'based on the provided context' or reference any filenames.\n"
        "2. When the answer has multiple items, steps, or options, format "
        "them as a clean numbered or bulleted list.\n"
        "3. Keep answers concise and well-structured.\n"
        "4. If the context does not contain enough information, say "
        "\"I don't have enough information to answer that.\""
    ),
    (
        "human",
        "Context:\n{context}\n\nQuestion: {question}"
    ),
])






def _format_docs(docs: list[Document]) -> str:
    """Concatenate retrieved documents into a single context string.

    Each chunk is labelled with its source filename for traceability.
    """
    parts: list[str] = []
    for doc in docs:
        source = doc.metadata.get("filename", "unknown")
        parts.append(f"[Source: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def _extract_sources(docs: list[Document]) -> list[str]:
    """Return a deduplicated, sorted list of source filenames."""
    seen: set[str] = set()
    sources: list[str] = []
    for doc in docs:
        name = doc.metadata.get("filename", "unknown")
        if name not in seen:
            seen.add(name)
            sources.append(name)
    return sources






def ask(question: str, vector_store: VectorStoreManager, doc_filter: Optional[str] = None) -> dict:
    """Run the full RAG pipeline for a single *question*.

    Args:
        question:     The user's natural-language question.
        vector_store: An initialised ``VectorStoreManager`` with indexed
                      documents.
        doc_filter:   Optional filename to filter the retrieved documents.

    Returns:
        A dict with keys:
            - ``answer`` (str): The LLM's response.
            - ``sources`` (list[str]): Unique source filenames.
    """
    try:

        docs = vector_store.similarity_search(question, doc_filter=doc_filter)

        if not docs:
            return {
                "answer": (
                    "No relevant documents were found for your question.  "
                    "Try indexing more documents or rephrasing your query."
                ),
                "sources": [],
            }


        llm = get_llm()
        chain = RAG_PROMPT | llm | StrOutputParser()

        context = _format_docs(docs)
        answer = chain.invoke({"context": context, "question": question})


        sources = _extract_sources(docs)

        return {"answer": answer, "sources": sources}

    except Exception as exc:
        print(f"[ERROR] RAG chain failed: {exc}", file=sys.stderr)
        return {
            "answer": (
                "Sorry, an error occurred while processing your question.  "
                f"Details: {exc}"
            ),
            "sources": [],
        }

def generate_faqs(vector_store: VectorStoreManager, doc_filter: Optional[str] = None) -> list[str]:
    """Generate dynamic FAQs based on indexed documents."""
    try:
        collection = vector_store._store._collection
        kwargs = {"limit": 5, "include": ["documents"]}
        if doc_filter:
            kwargs["where"] = {"filename": doc_filter}
        results = collection.get(**kwargs)
        docs = results.get("documents", [])
        
        if not docs:
            return []
            
        context = "\n\n---\n\n".join(docs)
        
        faq_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an AI assistant analyzing documents. Based on the following document excerpts, "
                "generate exactly 4 distinct frequently asked questions that a user might ask. "
                "Return the result STRICTLY as a JSON array of 4 strings. No markdown formatting, no explanations, just the raw JSON array."
            ),
            (
                "human",
                "Documents:\n{context}"
            ),
        ])
        
        llm = get_llm()
        chain = faq_prompt | llm | StrOutputParser()
        
        response = chain.invoke({"context": context})
        
        clean_json = re.sub(r'```(?:json)?', '', response).strip()
        clean_json = clean_json.strip('`')
        
        faqs = json.loads(clean_json)
        if isinstance(faqs, list) and all(isinstance(q, str) for q in faqs):
            return faqs[:4]
        return []
    except Exception as exc:
        print(f"[ERROR] Failed to generate dynamic FAQs: {exc}", file=sys.stderr)
        return []
