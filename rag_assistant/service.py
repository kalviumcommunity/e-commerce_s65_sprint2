from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .generation import GroundedAnswer
from .ingestion import Chunk, Chunker, DocumentLoader
from .llm import LLMError
from .pipeline import RAGPipeline

logger = logging.getLogger("rag_assistant")


@dataclass(frozen=True)
class UploadResult:
    """Small JSON-friendly summary returned after successful indexing."""

    document_id: str
    version: str
    chunks: int
    status: str


class DocumentRegistry:
    """Track the active version and chunk count for each knowledge source.

    Interview explanation: this is the catalogue shown under "Approved
    sources" in the browser. A document is activated only after it produces
    valid chunks, so an empty upload cannot replace a working source.
    """

    def __init__(self):
        self._active: dict[str, tuple[str, list[Chunk]]] = {}

    def activate(self, document_id: str, version: str, chunks: list[Chunk]) -> UploadResult:
        """Mark a fully processed document version as searchable."""
        if not chunks:
            raise ValueError("cannot activate an empty document")
        self._active[document_id] = (version, chunks)
        return UploadResult(document_id, version, len(chunks), "active")

    def list(self) -> list[UploadResult]:
        """Return deterministic summaries for the browser source panel."""
        return [UploadResult(document_id, version, len(chunks), "active")
                for document_id, (version, chunks) in sorted(self._active.items())]


class ResponseCache:
    """Short-lived in-memory cache for identical questions and chat history.

    The cache improves response time and avoids paying for repeated Groq calls.
    Its TTL keeps answers from remaining indefinitely after policies change.
    """

    def __init__(self, ttl_seconds: float = 60):
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        """Return an unexpired copy so callers cannot mutate cached state."""
        item = self._items.get(key)
        if not item or time.time() - item[0] > self.ttl_seconds:
            return None
        return dict(item[1])

    def put(self, key: str, value: dict[str, Any]) -> None:
        """Store a defensive copy with the current insertion timestamp."""
        self._items[key] = (time.time(), dict(value))


class RAGService:
    """Application layer connecting browser/API requests to the RAG pipeline."""

    def __init__(self, pipeline: RAGPipeline, *, registry: DocumentRegistry | None = None,
                 cache: ResponseCache | None = None):
        self.pipeline = pipeline
        self.registry = registry or DocumentRegistry()
        self.cache = cache or ResponseCache()

    def query(self, question: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        """Return one UI-ready answer with citations and operational metadata."""
        # Reuse recent identical answers to reduce Groq calls and response time.
        key = json.dumps({"q": question, "h": history or []}, sort_keys=True)
        cached = self.cache.get(key)
        if cached:
            cached["cached"] = True
            return cached
        request_id = str(uuid.uuid4())
        started = time.perf_counter()

        # Run the technical RAG pipeline and convert its result into UI-ready JSON.
        answer = self.pipeline.answer(question, history)
        response = {"request_id": request_id, "answer": answer.answer, "status": answer.status,
                    "citations": [asdict(citation) for citation in answer.citations],
                    "cached": False, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
        self.cache.put(key, response)
        logger.info("rag_query request_id=%s status=%s latency_ms=%s", request_id, answer.status, response["latency_ms"])
        return response

    def upload(self, filename: str, content: str, *, document_id: str, version: str) -> dict[str, Any]:
        """Process an upload and atomically replace that document in search."""
        # Uploaded text follows the same load -> chunk -> embed -> activate flow.
        document = DocumentLoader().load(filename, content, document_id=document_id, version=version)
        chunks = Chunker().chunk(document)
        records = self.pipeline.embeddings.embed([chunk.text for chunk in chunks],
                                                  [chunk.metadata for chunk in chunks])
        # Replace only the matching document. All other approved sources remain
        # searchable, which allows safe policy-by-policy updates.
        existing = list(self.pipeline.corpus)
        self.pipeline.corpus = [record for record in existing
                                if record.metadata.get("document_id") != document_id] + records
        result = self.registry.activate(document_id, version, chunks)
        return asdict(result)


def make_handler(service: RAGService) -> type[BaseHTTPRequestHandler]:
    """Bind HTTP routes to one configured service without global state."""

    class Handler(BaseHTTPRequestHandler):
        def _write(self, status: int, value: dict[str, Any]) -> None:
            """Serialize every API response consistently as UTF-8 JSON."""
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            # Browser-facing read endpoints: health, active sources, and the UI.
            if self.path == "/health":
                self._write(200, {"status": "ok"})
            elif self.path == "/documents":
                self._write(200, {"documents": [asdict(item) for item in service.registry.list()]})
            elif self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            elif self.path in {"/", "/index.html"}:
                page = (Path(__file__).parent.parent / "web" / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
            else:
                self._write(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                if self.path == "/query":
                    # UI question -> RAG pipeline -> grounded answer with citations.
                    self._write(200, service.query(str(payload["question"]), payload.get("history")))
                elif self.path == "/documents":
                    # UI upload -> validated document -> searchable knowledge base.
                    self._write(201, service.upload(payload["filename"], payload["content"],
                                                    document_id=payload["document_id"], version=payload["version"]))
                else:
                    self._write(404, {"error": "not found"})
            except LLMError as exc:
                # Provider failures become a safe gateway error without secrets
                # or an internal stack trace reaching the browser.
                self._write(502, {"error": str(exc)})
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                # Invalid user payloads are client errors, not server crashes.
                self._write(400, {"error": str(exc)})

        def log_message(self, format: str, *args: Any) -> None:
            logger.info("http " + format, *args)

    return Handler


def serve(service: RAGService, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start a threaded local server so independent requests do not block."""
    ThreadingHTTPServer((host, port), make_handler(service)).serve_forever()

