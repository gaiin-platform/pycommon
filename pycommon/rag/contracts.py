"""Shared contracts for namespace-aware, page-oriented RAG processing.

These contracts deliberately separate embedding storage identity from the
canonical object identity used by permissions, aliases, and progress records.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

# The one embedding model the global2 pipeline is built on. It is a constant,
# not a setting: the request format, the stored vectors and the index dimension
# all belong to this model, and vectors from another model cannot be searched
# with these, so changing it would mean re-embedding every document.
NOVA_EMBEDDING_MODEL_ID = "amazon.nova-2-multimodal-embeddings-v1:0"


class EmbeddingNamespace(str, Enum):
    """Storage namespace for embeddings, not an authorization boundary."""

    GLOBAL = "global"
    GLOBAL2 = "global2"


def normalize_source_id(source_id: str) -> str:
    """Normalize an embedding/source identifier at the API boundary.

    Only the protocol prefix is removed. Bucket names and path components are
    otherwise preserved so callers can decide whether a value is a shared
    object ID or an embedding ID.
    """
    if not isinstance(source_id, str):
        raise TypeError("source_id must be a string")
    normalized = source_id.strip()
    if "://" in normalized:
        normalized = normalized.split("://", 1)[1]
    return normalized


def namespace_for_source(source_id: str) -> EmbeddingNamespace:
    """Return the embedding namespace, defaulting unknown IDs to legacy."""
    normalized = normalize_source_id(source_id)
    if normalized == EmbeddingNamespace.GLOBAL2.value or normalized.startswith(
        "global2/"
    ):
        return EmbeddingNamespace.GLOBAL2
    return EmbeddingNamespace.GLOBAL


def generation_fingerprint(
    *,
    content_hash: str,
    source_version: str = "",
    pipeline_version: str = "global2-v1",
    model_id: str = "",
    embedding_dimension: Optional[int] = None,
    embedding_purpose: str = "",
    representation: str = "page",
) -> str:
    """Build a stable fingerprint for one independently processable generation."""
    payload = {
        "content_hash": content_hash,
        "source_version": source_version,
        "pipeline_version": pipeline_version,
        "model_id": model_id,
        "embedding_dimension": embedding_dimension,
        "embedding_purpose": embedding_purpose,
        "representation": representation,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def page_id(source_id: str, page_number: int, generation_id: str = "") -> str:
    """Return a deterministic page identity within a document generation."""
    if page_number < 1:
        raise ValueError("page_number must be >= 1")
    normalized = normalize_source_id(source_id)
    suffix = f":generation:{generation_id}" if generation_id else ""
    return f"{normalized}:page:{page_number}{suffix}"


@dataclass(frozen=True)
class PageInput:
    """Page-local source material used for content and QA processing."""

    source_id: str
    page_number: int
    text: str = ""
    text_location: str = ""
    image_location: str = ""
    extraction_method: str = ""
    generation_id: str = ""
    locations: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    @property
    def id(self) -> str:
        return page_id(self.source_id, self.page_number, self.generation_id)

    def qa_input(self) -> Dict[str, Any]:
        """Return the page input contract consumed by QA generation."""
        return {
            "page_id": self.id,
            "page_number": self.page_number,
            "source_id": normalize_source_id(self.source_id),
            "generation_id": self.generation_id,
            "text": self.text,
            "text_location": self.text_location,
            "image_location": self.image_location,
            "extraction_method": self.extraction_method,
            "locations": [dict(location) for location in self.locations],
        }


def build_page_input(
    source_id: str,
    page_number: int,
    *,
    text: str = "",
    text_location: str = "",
    image_location: str = "",
    extraction_method: str = "",
    generation_id: str = "",
    locations: Optional[Sequence[Mapping[str, Any]]] = None,
) -> PageInput:
    """Construct a page input while preserving page-local provenance."""
    return PageInput(
        source_id=normalize_source_id(source_id),
        page_number=page_number,
        text=text,
        text_location=text_location,
        image_location=image_location,
        extraction_method=extraction_method,
        generation_id=generation_id,
        locations=tuple(dict(location) for location in (locations or ())),
    )
