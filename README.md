# E-commerce Policy Assistant

A retrieval-augmented generation (RAG) application that answers customer
questions using approved product catalogues, return policies, and seller
agreements. Answers are grounded in retrieved evidence and include source
citations; when the available documents do not support an answer, the system
must respond with a safe refusal.

## Project documentation

- [Product requirements](PRD.md)
- [Sprint 2 delivery plan](docs/sprint-2-plan.md)
- [RAG architecture](docs/architecture.md)
- [Architecture decision record](docs/decisions/0001-grounded-rag-architecture.md)

## Team

| Member | Ownership |
|---|---|
| Hrithik (`hrithik18k`) | UI/UX, documentation, evaluation, and QA |
| Rohit (`itisrohit`) | LLM integration and RAG generation |
| Nikhil (`Nikhil2510192`) | Document ingestion, retrieval, vector storage, and backend APIs |

## Sprint outcome

By the end of Sprint 2, a user must be able to upload approved source
documents, ask an e-commerce policy question, receive a grounded answer with
verifiable citations, and get a clear refusal when the evidence is
insufficient. See the [delivery plan](docs/sprint-2-plan.md) for milestones,
ownership, dependencies, and the definition of done.

## Documentation validation

The documentation check uses only the Python standard library:

```bash
python scripts/validate_docs.py
```

## RAG implementation

The implementation uses Groq exclusively for remote generation through the
provider-neutral pipeline in `rag_assistant.pipeline.RAGPipeline`. Configure
`GROQ_API_KEY` and `GROQ_MODEL` from `.env.example`; credentials remain
server-side. The default model is `openai/gpt-oss-20b`.

Groq does not currently expose a documented embeddings endpoint in the API
used here, so retrieval embeddings remain local and deterministic. No second
remote model provider is called.

The pipeline embeds a question, ranks and reranks approved chunks, assembles
source-bounded context within the model budget, generates a structured answer,
validates citation IDs, and refuses when evidence is weak. A
`FollowUpRewriter` can turn a conversational follow-up into a standalone
retrieval query, while `EvidenceGate` prevents unsupported questions from
reaching generation.

Rohit (`itisrohit`) owns the LLM and RAG implementation. The work is delivered
in five cumulative pull requests, each listing and closing its corresponding
assigned issues.
