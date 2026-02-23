"""
Setup Script — Index Medical Guidelines
========================================
One-time setup script that processes medical guideline documents and
indexes them into Azure AI Search for the RAG pipeline.

Run with: python setup_index.py

This script:
  1. Reads all medical guideline files from data/medical_guidelines/
  2. Extracts text (plain text directly, PDFs via Azure Document Intelligence)
  3. Chunks documents with overlap for optimal retrieval
  4. Creates or updates the Azure AI Search index with semantic configuration
  5. Uploads all document chunks to the index

AI-102 Concepts:
  - Knowledge Mining pipeline: Ingest → Enrich → Index → Query
  - Azure AI Document Intelligence for document cracking
  - Azure AI Search index creation with semantic ranking
  - Chunking strategy for RAG (Retrieval-Augmented Generation)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.document_processor import DocumentProcessor
from src.knowledge_indexer import KnowledgeIndexer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("setup_index")

GUIDELINES_DIR = PROJECT_ROOT / "data" / "medical_guidelines"


def main() -> None:
    """Run the full indexing pipeline."""
    logger.info("=" * 60)
    logger.info("  MEDICAL TRIAGE — Knowledge Base Indexing")
    logger.info("=" * 60)

    # Step 1: Initialize services
    logger.info("Initializing Document Processor and Knowledge Indexer...")
    processor = DocumentProcessor()
    indexer = KnowledgeIndexer()

    # Step 2: Create the search index
    logger.info("Creating / updating Azure AI Search index...")
    if indexer.create_index():
        logger.info("✅ Index created/updated successfully.")
    else:
        logger.warning(
            "⚠️  Could not create Azure AI Search index. "
            "If credentials are not configured, the system will use "
            "local fallback search at runtime."
        )

    # Step 3: Process all guideline documents
    logger.info("Processing medical guidelines from: %s", GUIDELINES_DIR)
    documents = processor.process_directory(str(GUIDELINES_DIR))
    logger.info("✅ Processed %d documents.", len(documents))

    if not documents:
        logger.error("No documents found. Check the data/medical_guidelines/ directory.")
        sys.exit(1)

    # Step 4: Chunk documents for indexing
    logger.info("Chunking documents (chunk_size=1000, overlap=200)...")
    all_chunks: list[dict] = []
    for doc in documents:
        chunks = processor.chunk_document(doc, chunk_size=1000, overlap=200)
        all_chunks.extend(chunks)
    logger.info("✅ Created %d chunks from %d documents.", len(all_chunks), len(documents))

    # Step 5: Upload to Azure AI Search
    logger.info("Uploading chunks to Azure AI Search...")
    uploaded = indexer.upload_documents(all_chunks)
    if uploaded > 0:
        logger.info("✅ Successfully uploaded %d/%d chunks.", uploaded, len(all_chunks))
    else:
        logger.warning(
            "⚠️  No chunks uploaded. If Azure AI Search is not configured, "
            "the system will fall back to local keyword search at runtime."
        )

    # Summary
    logger.info("=" * 60)
    logger.info("  INDEXING COMPLETE")
    logger.info("  Documents processed: %d", len(documents))
    logger.info("  Chunks created:      %d", len(all_chunks))
    logger.info("  Chunks uploaded:      %d", uploaded)
    logger.info("=" * 60)

    # Print document titles
    logger.info("Indexed documents:")
    for doc in documents:
        logger.info("  • %s (%s)", doc["title"], doc["source"])


if __name__ == "__main__":
    main()