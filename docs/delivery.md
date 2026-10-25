# Delivery and operating notes

The service exposes `GET /health`, `POST /query`, and `POST /documents`. The
browser UI calls only these application endpoints; provider credentials remain
server-side. Query responses contain a request ID, status, answer, and
validated citations.

Run the automated checks with:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_docs.py
```

The implementation uses standard-library HTTP primitives so the contract can
later be mounted behind FastAPI or another server without changing callers.
Caching is bounded by TTL, logs contain request IDs/status/latency, and upload
activation rejects empty documents so the last known-good version is preserved.

