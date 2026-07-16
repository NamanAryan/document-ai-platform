"""
tests/test_pipeline.py — End-to-end integration test for DocAIApp.

Creates a temporary directory with dummy content, runs the full pipeline
(scan → load → chunk → embed → ask), and asserts correctness.

Run with:
    python tests/test_pipeline.py
"""

import os
import sys
import tempfile


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def run_pipeline_test() -> None:
    """Execute the full RAG pipeline against dummy content."""

    from ingestion.loader import DocumentLoader
    from ingestion.chunker import TextChunker
    from retrieval.vector_store import VectorStoreManager
    from generation.chain import ask


    dummy_content = (
        "The capital of France is Paris. Paris is known for the Eiffel Tower, "
        "which was built in 1889 for the World's Fair.\n\n"
        "Python is a popular programming language created by Guido van Rossum. "
        "It was first released in 1991 and is widely used in data science.\n\n"
        "The Great Wall of China is over 13,000 miles long. It was built over "
        "many centuries to protect against invasions from northern nomadic groups."
    )

    with tempfile.TemporaryDirectory() as tmp_docs_dir:

        test_file = os.path.join(tmp_docs_dir, "test_document.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(dummy_content)

        print(f"[TEST] Created test file: {test_file}")


        loader = DocumentLoader()
        files = loader.scan_directory(tmp_docs_dir)
        assert len(files) == 1, f"Expected 1 file, got {len(files)}"
        print(f"[TEST] Scanned directory: found {len(files)} file(s)")


        doc_data = loader.load(files[0])
        assert doc_data["text"], "Loaded text should not be empty"
        assert doc_data["filename"] == "test_document.txt"
        print(f"[TEST] Loaded: {doc_data['filename']} ({doc_data['file_type']})")


        chunker = TextChunker()
        metadata = {
            "filename": doc_data["filename"],
            "file_type": doc_data["file_type"],
            "filepath": doc_data["filepath"],
            "mtime": str(os.path.getmtime(files[0])),
        }
        chunks = chunker.chunk(doc_data["text"], metadata)
        assert len(chunks) > 0, "Should produce at least one chunk"
        print(f"[TEST] Chunked into {len(chunks)} chunk(s)")


        with tempfile.TemporaryDirectory() as tmp_chroma_dir:
            vector_store = VectorStoreManager(persist_dir=tmp_chroma_dir)
            vector_store.add_documents(chunks)
            print(f"[TEST] Stored {len(chunks)} chunk(s) in ChromaDB")


            indexed = vector_store.list_indexed_documents()
            assert "test_document.txt" in indexed, (
                f"Expected 'test_document.txt' in indexed docs, got {indexed}"
            )
            print(f"[TEST] Indexed documents: {indexed}")


            result = ask("What is the capital of France?", vector_store)

            assert result["answer"], "Answer should not be empty"
            assert len(result["answer"]) > 0, "Answer string should have content"
            print(f"[TEST] Answer: {result['answer'][:120]}…")

            assert "test_document.txt" in result["sources"], (
                f"Expected 'test_document.txt' in sources, got {result['sources']}"
            )
            print(f"[TEST] Sources: {result['sources']}")

    print("\n✅ Pipeline test passed")


if __name__ == "__main__":
    try:
        run_pipeline_test()
    except AssertionError as e:
        print(f"\n❌ Test FAILED: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test ERROR: {e}", file=sys.stderr)
        sys.exit(1)
