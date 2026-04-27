"""
Knowledge Indexer Module
========================
Creates and manages an Azure AI Search index for the medical knowledge base.
Supports both keyword and semantic (vector) search for RAG grounding.

"""

from __future__ import annotations

import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Index field names
FIELD_ID = "id"
FIELD_TITLE = "title"
FIELD_CONTENT = "content"
FIELD_SOURCE = "source"


class KnowledgeIndexer:
    """Manages Azure AI Search index for medical guidelines.

    Handles index creation, document upload, and search queries used by
    the RAG pipeline in the triage engine.

    Attributes:
        endpoint: Azure AI Search endpoint URL.
        key: Azure AI Search admin key.
        index_name: Name of the search index.
    """

    def __init__(self) -> None:
        """Initialize the Knowledge Indexer with Azure credentials."""
        self.endpoint: str = os.getenv("SEARCH_ENDPOINT", "")
        self.key: str = os.getenv("SEARCH_KEY", "")
        self.index_name: str = os.getenv("SEARCH_INDEX_NAME", "medical-knowledge-index")
        self._index_client = None
        self._search_client = None
        self._initialized = False
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize Azure Search admin and query clients.

        AI-102: SearchIndexClient is used for index management (CRUD).
        SearchClient is used for querying documents.
        """
        if not self.endpoint or not self.key or self.key == "your-key":
            logger.warning(
                "Azure AI Search credentials not configured. "
                "Using fallback local search."
            )
            return
        try:
            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents import SearchClient
            from azure.search.documents.indexes import SearchIndexClient

            credential = AzureKeyCredential(self.key)
            self._index_client = SearchIndexClient(
                endpoint=self.endpoint, credential=credential
            )
            self._search_client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=credential,
            )
            self._initialized = True
            logger.info("Azure AI Search clients initialized.")
        except Exception as exc:
            logger.error("Failed to init Azure AI Search clients: %s", exc)

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def create_index(self) -> bool:
        """Create or update the search index with semantic configuration.

        AI-102: SemanticConfiguration enables semantic ranking, which
        uses deep-learning models to re-rank results for better relevance.
        SearchableField supports full-text search; SimpleField is for
        filtering and faceting.

        Returns:
            True if index was created/updated successfully.
        """
        if not self._initialized or self._index_client is None:
            logger.warning("Search client not initialized. Cannot create index.")
            return False

        try:
            from azure.search.documents.indexes.models import (
                SearchableField,
                SearchField,
                SearchFieldDataType,
                SearchIndex,
                SemanticConfiguration,
                SemanticField,
                SemanticPrioritizedFields,
                SemanticSearch,
                SimpleField,
            )

            fields = [
                SimpleField(
                    name=FIELD_ID,
                    type=SearchFieldDataType.String,
                    key=True,
                    filterable=True,
                ),
                SearchableField(
                    name=FIELD_TITLE,
                    type=SearchFieldDataType.String,
                    searchable=True,
                ),
                SearchableField(
                    name=FIELD_CONTENT,
                    type=SearchFieldDataType.String,
                    searchable=True,
                ),
                SimpleField(
                    name=FIELD_SOURCE,
                    type=SearchFieldDataType.String,
                    filterable=True,
                ),
            ]

            # AI-102: Semantic configuration tells the search service
            # which fields contain the most meaningful content for
            # semantic ranking.
            semantic_config = SemanticConfiguration(
                name="medical-semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name=FIELD_TITLE),
                    content_fields=[SemanticField(field_name=FIELD_CONTENT)],
                ),
            )

            semantic_search = SemanticSearch(
                configurations=[semantic_config],
                default_configuration_name="medical-semantic-config",
            )

            index = SearchIndex(
                name=self.index_name,
                fields=fields,
                semantic_search=semantic_search,
            )

            self._index_client.create_or_update_index(index)
            logger.info("Search index '%s' created/updated.", self.index_name)
            return True

        except Exception as exc:
            logger.error("Failed to create search index: %s", exc)
            return False

    def upload_documents(self, documents: list[dict]) -> int:
        """Upload documents to the search index.

        Args:
            documents: List of dicts with id, title, content, source.

        Returns:
            Number of successfully uploaded documents.
        """
        if not self._initialized or self._search_client is None:
            logger.warning("Search client not initialized. Cannot upload.")
            return 0

        try:
            # Sanitize IDs (Azure Search requires specific format)
            for doc in documents:
                doc["id"] = (
                    doc["id"]
                    .replace(" ", "_")
                    .replace(".", "_")
                    .replace("/", "_")
                )

            result = self._search_client.upload_documents(documents=documents)
            success_count = sum(1 for r in result if r.succeeded)
            logger.info(
                "Uploaded %d/%d documents to index.",
                success_count,
                len(documents),
            )
            return success_count

        except Exception as exc:
            logger.error("Failed to upload documents: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top: int = 4,
        use_semantic: bool = True,
        min_score: float = 0.0,
    ) -> list[dict]:
        """Search the medical knowledge base.

        AI-102: Semantic search uses a deep-learning model to understand
        query intent and re-rank results. This is more effective than
        keyword search alone for natural-language medical queries.

        Args:
            query: Natural language search query.
            top: Maximum number of results (default 4 for broader coverage).
            use_semantic: Whether to use semantic ranking.
            min_score: Minimum score threshold to filter low-relevance results.

        Returns:
            List of result dicts with title, content, source, and score.
            Results are deduplicated by source and sorted by score descending.
        """
        if not self._initialized or self._search_client is None:
            logger.warning("Search client not available. Using local fallback.")
            return self._local_fallback_search(query, top)

        try:
            kwargs: dict = {
                "search_text": query,
                "select": [FIELD_TITLE, FIELD_CONTENT, FIELD_SOURCE],
                "top": top + 2,  # Fetch extra to allow for dedup + filtering
            }

            if use_semantic:
                # FIX: azure-search-documents 11.4+ prefers QueryType enum.
                # We try the enum first and fall back to the string literal
                # for older SDK versions to maintain backward compatibility.
                try:
                    from azure.search.documents.models import QueryType
                    kwargs["query_type"] = QueryType.SEMANTIC
                except ImportError:
                    kwargs["query_type"] = "semantic"
                kwargs["semantic_configuration_name"] = "medical-semantic-config"

            results = self._search_client.search(**kwargs)

            output: list[dict] = []
            seen_sources: set[str] = set()

            for result in results:
                score = getattr(result, "@search.score", 0.0) or 0.0
                if score < min_score:
                    continue
                source = result.get(FIELD_SOURCE, "")
                # Keep the highest-scoring chunk per source to avoid redundancy
                if source in seen_sources:
                    continue
                seen_sources.add(source)
                output.append(
                    {
                        "title": result.get(FIELD_TITLE, ""),
                        "content": result.get(FIELD_CONTENT, ""),
                        "source": source,
                        "score": score,
                    }
                )
                if len(output) >= top:
                    break

            output.sort(key=lambda x: x["score"], reverse=True)
            logger.info(
                "Search '%s' returned %d results (semantic=%s).",
                query[:60], len(output), use_semantic,
            )
            return output

        except Exception as exc:
            logger.error("Search failed: %s", exc)
            return self._local_fallback_search(query, top)

    # ------------------------------------------------------------------
    # Fallback local search (demo / offline mode)
    # ------------------------------------------------------------------

    def _local_fallback_search(self, query: str, top: int = 4) -> list[dict]:
        """Chunk-based keyword search when Azure AI Search is unavailable.

        Splits each guideline file into sentence-boundary chunks, scores each
        chunk by weighted keyword frequency (query terms weighted higher for
        longer terms), and returns the top-scoring non-redundant chunks.

        This is a significant improvement over returning entire files — the
        caller receives focused, relevant passages rather than thousands of
        characters of raw protocol text.

        Args:
            query: Natural language search query.
            top: Max chunks to return.

        Returns:
            Matching document chunks sorted by relevance score descending.
        """
        import re
        from pathlib import Path

        guidelines_dir = Path(__file__).parent.parent / "data" / "medical_guidelines"
        if not guidelines_dir.exists():
            return []

        # Build keyword list: longer terms get higher weight
        raw_keywords = [kw.lower() for kw in re.split(r'\W+', query) if len(kw) > 2]
        # Remove duplicates, preserve order
        seen_kw: set[str] = set()
        keywords = []
        for kw in raw_keywords:
            if kw not in seen_kw:
                seen_kw.add(kw)
                keywords.append(kw)

        if not keywords:
            return []

        # Keyword weight: +1 for each extra char beyond 3
        kw_weights = {kw: 1 + max(0, len(kw) - 3) for kw in keywords}

        CHUNK_SIZE = 600
        sentence_end = re.compile(r'(?<=[.!?])\s+')
        all_chunks: list[dict] = []

        for file_path in sorted(guidelines_dir.iterdir()):
            if file_path.suffix.lower() not in (".txt", ".md"):
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                title = file_path.stem.replace("_", " ").title()
                source = file_path.name

                # Build sentence-boundary chunks
                sentences = sentence_end.split(content)
                current = ""
                for sentence in sentences:
                    if len(current) + len(sentence) + 1 <= CHUNK_SIZE:
                        current = (current + " " + sentence).strip() if current else sentence
                    else:
                        if current:
                            all_chunks.append({
                                "title": title,
                                "content": current,
                                "source": source,
                                "_raw_lower": current.lower(),
                            })
                        current = sentence
                if current.strip():
                    all_chunks.append({
                        "title": title,
                        "content": current.strip(),
                        "source": source,
                        "_raw_lower": current.lower(),
                    })

            except Exception:
                continue

        # Score each chunk
        scored: list[dict] = []
        for chunk in all_chunks:
            cl = chunk["_raw_lower"]
            score = sum(cl.count(kw) * w for kw, w in kw_weights.items())
            if score > 0:
                scored.append({
                    "title": chunk["title"],
                    "content": chunk["content"],
                    "source": chunk["source"],
                    "score": float(score),
                })

        # Sort and deduplicate by source (keep best chunk per file)
        scored.sort(key=lambda x: x["score"], reverse=True)
        seen_sources: set[str] = set()
        deduped: list[dict] = []
        for item in scored:
            if item["source"] not in seen_sources:
                seen_sources.add(item["source"])
                deduped.append(item)
            if len(deduped) >= top:
                break

        logger.info(
            "Local fallback search '%s' returned %d chunks from %d candidates.",
            query[:60], len(deduped), len(scored),
        )
        return deduped