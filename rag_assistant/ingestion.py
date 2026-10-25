from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .embeddings import EmbeddingRecord
from .retrieval import RetrievedChunk, cosine_similarity


class IngestionError(ValueError):
    pass


@dataclass(frozen=True)
class Document:
    document_id: str
    version: str
    source: str
    text: str
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    metadata: Mapping[str, Any]


class DocumentLoader:
    SUPPORTED = {".txt", ".md", ".json", ".csv"}

    def load(self, name: str, content: str, *, document_id: str, version: str,
             metadata: Mapping[str, Any] | None = None) -> Document:
        extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ".txt"
        if extension not in self.SUPPORTED:
            raise IngestionError(f"unsupported document format: {extension}")
        if not content.strip():
            raise IngestionError("document content is empty")
        if extension == ".json":
            try:
                value = json.loads(content)
                content = json.dumps(value, ensure_ascii=False, indent=2)
            except json.JSONDecodeError as exc:
                raise IngestionError("invalid JSON document") from exc
        elif extension == ".csv":
            rows = list(csv.reader(io.StringIO(content)))
            content = "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)
        normalized = re.sub(r"[ \t]+", " ", content.replace("\r\n", "\n")).strip()
        checksum = hashlib.sha256(normalized.encode()).hexdigest()
        all_metadata = {"source": name, "checksum": checksum, "document_id": document_id,
                        "version": version, **(metadata or {})}
        return Document(document_id, version, name, normalized, all_metadata)


class Chunker:
    def __init__(self, max_words: int = 120, overlap_words: int = 20):
        if max_words <= 0 or overlap_words < 0 or overlap_words >= max_words:
            raise ValueError("overlap must be non-negative and smaller than max_words")
        self.max_words = max_words
        self.overlap_words = overlap_words

    def chunk(self, document: Document) -> list[Chunk]:
        words = document.text.split()
        result: list[Chunk] = []
        start = 0
        index = 0
        while start < len(words):
            end = min(len(words), start + self.max_words)
            text = " ".join(words[start:end])
            chunk_id = f"{document.document_id}:{document.version}:chunk-{index:04d}"
            metadata = {**document.metadata, "chunk_id": chunk_id, "position": index,
                        "location": f"words {start}-{end}"}
            result.append(Chunk(chunk_id, text, metadata))
            if end == len(words):
                break
            start = end - self.overlap_words
            index += 1
        return result


class InMemoryVectorStore:
    def __init__(self):
        self._records: dict[str, EmbeddingRecord] = {}

    def upsert(self, records: Iterable[EmbeddingRecord]) -> None:
        for record in records:
            chunk_id = str(record.metadata.get("chunk_id", record.text))
            self._records[chunk_id] = record

    def all(self) -> list[EmbeddingRecord]:
        return list(self._records.values())

    def search(self, query_vector: Sequence[float], *, top_k: int = 5,
               document_id: str | None = None) -> list[RetrievedChunk]:
        candidates = [record for record in self._records.values()
                      if document_id is None or record.metadata.get("document_id") == document_id]
        ranked = [RetrievedChunk(record, cosine_similarity(query_vector, record.vector)) for record in candidates]
        return sorted(ranked, key=lambda item: item.score, reverse=True)[:top_k]

    def hybrid_search(self, query: str, query_vector: Sequence[float], *, top_k: int = 5) -> list[RetrievedChunk]:
        terms = set(query.lower().split())
        scored = []
        for record in self._records.values():
            lexical = len(terms & set(record.text.lower().split())) / max(1, len(terms))
            score = .7 * cosine_similarity(query_vector, record.vector) + .3 * lexical
            scored.append(RetrievedChunk(record, score))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

