# ADR-0001: Use retrieval-augmented generation for policy answers

- **Status:** Accepted for Sprint 2
- **Date:** 6 October 2026
- **Owners:** Hrithik, Rohit, and Nikhil

## Context

The product must answer customer questions using approved product catalogues,
return policies, and seller agreements. A general-purpose LLM may produce a
plausible response that is vague, outdated, or unsupported. Customers and
support agents must be able to verify an answer against its source.

## Decision

Use retrieval-augmented generation with two separately testable paths:

1. an offline ingestion path that validates, cleans, chunks, embeds, versions,
   and indexes approved documents; and
2. an online query path that retrieves and reranks permitted evidence before
   asking the LLM for a structured, cited answer.

Generation is allowed only when the evidence gate is satisfied. Otherwise the
application asks for clarification or returns an insufficient-evidence refusal.

Infrastructure remains provider-neutral. Stable chunk metadata and response
contracts isolate the UI and orchestration code from the selected embedding
model, vector database, and LLM.

## Consequences

### Positive

- Answers can be traced to approved source passages.
- Retrieval and answer failures can be measured independently.
- Policies can be updated without retraining a model.
- Provider components can be replaced behind stable interfaces.

### Trade-offs

- Ingestion, indexing, evaluation, and document-version management add
  complexity.
- Retrieval can still miss relevant evidence and therefore needs a labelled
  evaluation set.
- Citations must be validated; asking an LLM to format them is not sufficient.
- Latency includes query embedding, retrieval, optional reranking, and
  generation.

## Alternatives considered

| Alternative | Reason rejected for V1 |
|---|---|
| Direct LLM prompting without retrieval | Cannot reliably prove that policy claims came from approved current documents |
| Fine-tuning on policy documents | Harder to update and cite, and does not guarantee factual grounding |
| Keyword search only | Useful as a hybrid signal but insufficient for paraphrased customer questions |
| Rule-only chatbot | Predictable but expensive to maintain across varied natural-language questions and changing documents |

## Review trigger

Revisit this decision if measured retrieval quality cannot meet the agreed
baseline, document-level authorization cannot be enforced, or the required
latency cannot be achieved after tuning and caching.
