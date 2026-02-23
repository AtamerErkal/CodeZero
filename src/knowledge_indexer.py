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
        top: int = 3,
        use_semantic: bool = True,
    ) -> list[dict]:
        """Search the medical knowledge base.

        AI-102: Semantic search uses a deep-learning model to understand
        query intent and re-rank results. This is more effective than
        keyword search alone for natural-language medical queries.

        Args:
            query: Natural language search query.
            top: Maximum number of results.
            use_semantic: Whether to use semantic ranking.

        Returns:
            List of result dicts with title, content, source, and score.
        """
        if not self._initialized or self._search_client is None:
            logger.warning("Search client not available. Using local fallback.")
            return self._local_fallback_search(query, top)

        try:
            kwargs: dict = {
                "search_text": query,
                "select": [FIELD_TITLE, FIELD_CONTENT, FIELD_SOURCE],
                "top": top,
            }

            if use_semantic:
                kwargs["query_type"] = "semantic"
                kwargs["semantic_configuration_name"] = "medical-semantic-config"

            results = self._search_client.search(**kwargs)

            output: list[dict] = []
            for result in results:
                output.append(
                    {
                        "title": result.get(FIELD_TITLE, ""),
                        "content": result.get(FIELD_CONTENT, ""),
                        "source": result.get(FIELD_SOURCE, ""),
                        "score": getattr(result, "@search.score", 0.0),
                    }
                )
            logger.info("Search '%s' returned %d results.", query, len(output))
            return output

        except Exception as exc:
            logger.error("Search failed: %s", exc)
            return self._local_fallback_search(query, top)

    # ------------------------------------------------------------------
    # Fallback local search (demo / offline mode)
    # ------------------------------------------------------------------

    def _local_fallback_search(self, query: str, top: int = 3) -> list[dict]:
        """Simple keyword-based local search when Azure is unavailable.

        Reads guideline files from the data directory and returns those
        whose content contains any of the query keywords.

        Args:
            query: Search query string.
            top: Max results.

        Returns:
            Matching document chunks.
        """
        from pathlib import Path

        guidelines_dir = Path(__file__).parent.parent / "data" / "medical_guidelines"
        if not guidelines_dir.exists():
            return []

        keywords = [kw.lower() for kw in query.split() if len(kw) > 2]
        results: list[dict] = []

        for file_path in sorted(guidelines_dir.iterdir()):
            if file_path.suffix.lower() not in (".txt", ".md"):
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                content_lower = content.lower()
                score = sum(
                    content_lower.count(kw) for kw in keywords
                )
                if score > 0:
                    results.append(
                        {
                            "title": file_path.stem.replace("_", " ").title(),
                            "content": content,
                            "source": file_path.name,
                            "score": score,
                        }
                    )
            except Exception:
                continue

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top]