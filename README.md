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
