from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from .generation import GroundedAnswer
from .ingestion import Chunk, Chunker, DocumentLoader
from .pipeline import RAGPipeline

logger = logging.getLogger("rag_assistant")


@dataclass(frozen=True)
class UploadResult:
    document_id: str
    version: str
    chunks: int
    status: str


class DocumentRegistry:
    def __init__(self):
        self._active: dict[str, tuple[str, list[Chunk]]] = {}

    def activate(self, document_id: str, version: str, chunks: list[Chunk]) -> UploadResult:
        if not chunks:
            raise ValueError("cannot activate an empty document")
        self._active[document_id] = (version, chunks)
        return UploadResult(document_id, version, len(chunks), "active")


class ResponseCache:
    def __init__(self, ttl_seconds: float = 60):
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        item = self._items.get(key)
        if not item or time.time() - item[0] > self.ttl_seconds:
            return None
        return dict(item[1])

    def put(self, key: str, value: dict[str, Any]) -> None:
        self._items[key] = (time.time(), dict(value))


class RAGService:
    def __init__(self, pipeline: RAGPipeline, *, registry: DocumentRegistry | None = None,
                 cache: ResponseCache | None = None):
        self.pipeline = pipeline
        self.registry = registry or DocumentRegistry()
        self.cache = cache or ResponseCache()

    def query(self, question: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        key = json.dumps({"q": question, "h": history or []}, sort_keys=True)
        cached = self.cache.get(key)
        if cached:
            cached["cached"] = True
            return cached
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        answer = self.pipeline.answer(question, history)
        response = {"request_id": request_id, "answer": answer.answer, "status": answer.status,
                    "citations": [asdict(citation) for citation in answer.citations],
                    "cached": False, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
        self.cache.put(key, response)
        logger.info("rag_query request_id=%s status=%s latency_ms=%s", request_id, answer.status, response["latency_ms"])
        return response

    def upload(self, filename: str, content: str, *, document_id: str, version: str) -> dict[str, Any]:
        document = DocumentLoader().load(filename, content, document_id=document_id, version=version)
        chunks = Chunker().chunk(document)
        result = self.registry.activate(document_id, version, chunks)
        return asdict(result)


def make_handler(service: RAGService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _write(self, status: int, value: dict[str, Any]) -> None:
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._write(200, {"status": "ok"})
            else:
                self._write(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                if self.path == "/query":
                    self._write(200, service.query(str(payload["question"]), payload.get("history")))
                elif self.path == "/documents":
                    self._write(201, service.upload(payload["filename"], payload["content"],
                                                    document_id=payload["document_id"], version=payload["version"]))
                else:
                    self._write(404, {"error": "not found"})
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self._write(400, {"error": str(exc)})

        def log_message(self, format: str, *args: Any) -> None:
            logger.info("http " + format, *args)

    return Handler


def serve(service: RAGService, host: str = "127.0.0.1", port: int = 8000) -> None:
    ThreadingHTTPServer((host, port), make_handler(service)).serve_forever()

