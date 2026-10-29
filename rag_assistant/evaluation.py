"""Measure retrieval relevance separately from final-answer quality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .generation import GroundedAnswer
from .retrieval import RetrievedChunk


@dataclass(frozen=True)
class RetrievalMetrics:
    """Standard search metrics used to tune retrieval with labelled queries."""
    precision_at_k: float
    recall_at_k: float
    mean_reciprocal_rank: float
    no_result_rate: float


def evaluate_retrieval(results: Sequence[Sequence[RetrievedChunk]], relevant_ids: Sequence[set[str]], k: int = 5) -> RetrievalMetrics:
    """Compute precision@k, recall@k, MRR, and the no-result rate."""
    if len(results) != len(relevant_ids) or not results:
        raise ValueError("results and relevant_ids must have equal non-zero length")
    precisions, recalls, reciprocal, no_result = [], [], [], 0
    # Compare returned chunk IDs against human-labelled relevant chunk IDs.
    for retrieved, relevant in zip(results, relevant_ids):
        top = [str(item.record.metadata.get("chunk_id")) for item in retrieved[:k]]
        hits = [item for item in top if item in relevant]
        precisions.append(len(hits) / max(1, len(top)))
        recalls.append(len(set(hits)) / max(1, len(relevant)))
        if not top:
            no_result += 1
        reciprocal.append(next((1 / (i + 1) for i, item in enumerate(top) if item in relevant), 0))
    count = len(results)
    return RetrievalMetrics(sum(precisions) / count, sum(recalls) / count,
                            sum(reciprocal) / count, no_result / count)


@dataclass(frozen=True)
class AnswerQuality:
    """Grounding, citation, and refusal checks for one generated answer."""
    grounded: bool
    citation_accuracy: float
    refusal_correct: bool


def evaluate_answer(answer: GroundedAnswer, supported_ids: set[str], *, should_refuse: bool = False) -> AnswerQuality:
    """Check that answer citations are supported and refusals are appropriate."""
    cited = {citation.chunk_id for citation in answer.citations}
    accuracy = len(cited & supported_ids) / max(1, len(cited))
    grounded = answer.status != "answered" or bool(cited & supported_ids)
    refusal_correct = (answer.status == "insufficient_evidence") == should_refuse
    return AnswerQuality(grounded, accuracy, refusal_correct)

