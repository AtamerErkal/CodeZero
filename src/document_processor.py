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
        self, document: dict, chunk_size: int = 600, overlap: int = 80
    ) -> list[dict]:
        """Split a document into overlapping chunks for search indexing.

        Uses a two-pass strategy:
          1. Split at section boundaries (ALL-CAPS headings, numbered sections)
             so each chunk stays within a coherent clinical topic.
          2. Within each section, split at sentence boundaries (not mid-word)
             to keep chunks semantically complete.
        Overlap is appended as the closing sentences of the previous chunk.

        AI-102: Chunking is essential for RAG pipelines. Overlap ensures
        context is not lost at chunk boundaries.

        Args:
            document: Dict with ``title``, ``content``, ``source``.
            chunk_size: Target maximum characters per chunk (default 600).
            overlap: Characters of overlap between consecutive chunks (default 80).

        Returns:
            List of chunk dicts with ``id``, ``title``, ``content``, ``source``.
        """
        import re

        content = document.get("content", "")
        title = document.get("title", "Unknown")
        source = document.get("source", "Unknown")

        if not content.strip():
            return []

        # ── Step 1: Split into logical sections ──────────────────────────────
        # A section boundary is a line that looks like a header:
        #   "1. OVERVIEW", "RED FLAGS", "TRIAGE LEVELS", etc.
        section_pattern = re.compile(
            r'(?m)^(?:\d+\.\s+[A-Z]|[A-Z][A-Z\s\-/]{4,})\S*.*$'
        )
        section_starts = [m.start() for m in section_pattern.finditer(content)]

        if not section_starts:
            # No section headers found — treat whole content as one section
            sections = [("", content)]
        else:
            sections: list[tuple[str, str]] = []
            for i, start in enumerate(section_starts):
                end = section_starts[i + 1] if i + 1 < len(section_starts) else len(content)
                header_line_end = content.find("\n", start)
                if header_line_end == -1:
                    header_line_end = start
                section_header = content[start:header_line_end].strip()
                section_body = content[start:end]
                sections.append((section_header, section_body))

        # ── Step 2: Chunk each section at sentence boundaries ─────────────────
        sentence_end = re.compile(r'(?<=[.!?])\s+')
        chunks: list[dict] = []
        chunk_idx = 0

        for section_header, section_text in sections:
            # Split section into sentences
            sentences = sentence_end.split(section_text)
            if not sentences:
                continue

            current_chunk = ""
            prev_tail = ""  # last ~overlap chars of previous chunk for overlap

            for sentence in sentences:
                candidate = (prev_tail + " " + sentence).strip() if prev_tail else sentence
                if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                    current_chunk = (current_chunk + " " + sentence).strip() if current_chunk else sentence
                else:
                    if current_chunk:
                        chunk_title = f"{title} — {section_header}" if section_header else title
                        chunks.append({
                            "id": f"{source}_chunk_{chunk_idx}",
                            "title": chunk_title,
                            "content": current_chunk,
                            "source": source,
                        })
                        chunk_idx += 1
                        # Carry overlap: last `overlap` chars of emitted chunk
                        prev_tail = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                    current_chunk = sentence

            # Flush last piece
            if current_chunk.strip():
                chunk_title = f"{title} — {section_header}" if section_header else title
                chunks.append({
                    "id": f"{source}_chunk_{chunk_idx}",
                    "title": chunk_title,
                    "content": current_chunk.strip(),
                    "source": source,
                })
                chunk_idx += 1

        # Fallback: if no chunks produced, return whole document as one chunk
        if not chunks:
            chunks.append({
                "id": f"{source}_chunk_0",
                "title": title,
                "content": content[:chunk_size],
                "source": source,
            })

        logger.debug("Document '%s' split into %d chunks", title, len(chunks))
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