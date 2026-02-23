"""
Document Processor Module
=========================
Uses Azure AI Document Intelligence to extract structured text from medical
guideline documents (PDF, TXT, images). Extracted content is prepared for
indexing into Azure AI Search.

AI-102 Concepts:
  - Azure AI Document Intelligence (formerly Form Recognizer)
  - Prebuilt layout model for general document extraction
  - Custom models for structured medical forms (future extension)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Extracts text content from medical guideline documents.

    Supports plain-text files directly and PDF/image files via Azure
    Document Intelligence. Extracted text is chunked for search indexing.

    Attributes:
        endpoint: Azure Document Intelligence endpoint URL.
        key: Azure Document Intelligence API key.
        client: Azure Document Intelligence client instance.
    """

    def __init__(self) -> None:
        """Initialize the Document Processor with Azure credentials."""
        self.endpoint: str = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT", "")
        self.key: str = os.getenv("DOCUMENT_INTELLIGENCE_KEY", "")
        self.client = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Azure Document Intelligence client.

        AI-102: DocumentAnalysisClient is the main entry point for
        Document Intelligence operations. It uses the prebuilt-layout
        model for general document extraction.
        """
        if not self.endpoint or not self.key or self.key == "your-key":
            logger.warning(
                "Document Intelligence credentials not configured. "
                "PDF extraction will be unavailable; plain text files "
                "will still be processed."
            )
            return
        try:
            from azure.ai.formrecognizer import DocumentAnalysisClient
            from azure.core.credentials import AzureKeyCredential

            self.client = DocumentAnalysisClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.key),
            )
            logger.info("Document Intelligence client initialized.")
        except Exception as exc:
            logger.error("Failed to init Document Intelligence client: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_directory(self, directory: str) -> list[dict]:
        """Process all supported documents in a directory.

        Args:
            directory: Path to the folder containing guideline documents.

        Returns:
            List of dicts with keys ``title``, ``content``, and ``source``.
        """
        documents: list[dict] = []
        dir_path = Path(directory)

        if not dir_path.exists():
            logger.error("Directory not found: %s", directory)
            return documents

        for file_path in sorted(dir_path.iterdir()):
            if file_path.suffix.lower() in (".txt", ".md"):
                doc = self._process_text_file(file_path)
                if doc:
                    documents.append(doc)
            elif file_path.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg"):
                doc = self._process_with_doc_intelligence(file_path)
                if doc:
                    documents.append(doc)
            else:
                logger.debug("Skipping unsupported file: %s", file_path.name)

        logger.info("Processed %d documents from %s", len(documents), directory)
        return documents

    def chunk_document(
        self, document: dict, chunk_size: int = 1000, overlap: int = 200
    ) -> list[dict]:
        """Split a document into overlapping chunks for search indexing.

        AI-102: Chunking is essential for RAG pipelines. Overlap ensures
        context is not lost at chunk boundaries.

        Args:
            document: Dict with ``title``, ``content``, ``source``.
            chunk_size: Maximum characters per chunk.
            overlap: Overlapping characters between consecutive chunks.

        Returns:
            List of chunk dicts with ``id``, ``title``, ``content``, ``source``.
        """
        content = document.get("content", "")
        title = document.get("title", "Unknown")
        source = document.get("source", "Unknown")
        chunks: list[dict] = []

        if len(content) <= chunk_size:
            chunks.append(
                {
                    "id": f"{source}_chunk_0",
                    "title": title,
                    "content": content,
                    "source": source,
                }
            )
            return chunks

        start = 0
        chunk_idx = 0
        while start < len(content):
            end = start + chunk_size
            chunk_text = content[start:end]
            chunks.append(
                {
                    "id": f"{source}_chunk_{chunk_idx}",
                    "title": title,
                    "content": chunk_text,
                    "source": source,
                }
            )
            start += chunk_size - overlap
            chunk_idx += 1

        logger.debug(
            "Document '%s' split into %d chunks", title, len(chunks)
        )
        return chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_text_file(self, file_path: Path) -> Optional[dict]:
        """Read a plain-text or markdown file.

        Args:
            file_path: Path to the .txt or .md file.

        Returns:
            Document dict or ``None`` on failure.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            title = file_path.stem.replace("_", " ").title()
            return {
                "title": title,
                "content": content,
                "source": file_path.name,
            }
        except Exception as exc:
            logger.error("Error reading text file %s: %s", file_path.name, exc)
            return None

    def _process_with_doc_intelligence(self, file_path: Path) -> Optional[dict]:
        """Extract text from PDF/image via Azure Document Intelligence.

        AI-102: Uses the prebuilt-layout model which extracts text,
        tables, and structure information from documents without
        requiring a custom-trained model.

        Args:
            file_path: Path to the PDF or image file.

        Returns:
            Document dict or ``None`` on failure.
        """
        if self.client is None:
            logger.warning(
                "Document Intelligence client unavailable. Skipping %s",
                file_path.name,
            )
            return None

        try:
            with open(file_path, "rb") as fh:
                poller = self.client.begin_analyze_document(
                    "prebuilt-layout", document=fh
                )
            result = poller.result()

            # Concatenate all page text
            content_parts: list[str] = []
            for page in result.pages:
                for line in page.lines:
                    content_parts.append(line.content)

            content = "\n".join(content_parts)
            title = file_path.stem.replace("_", " ").title()
            return {
                "title": title,
                "content": content,
                "source": file_path.name,
            }
        except Exception as exc:
            logger.error(
                "Error processing %s with Document Intelligence: %s",
                file_path.name,
                exc,
            )
            return None