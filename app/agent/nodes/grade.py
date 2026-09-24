"""CRAG Grader node evaluating chunk relevance via LLM-as-judge."""

import asyncio
import logging
import re
from typing import Any

from app.agent.state import AgentState, GradeType
from app.gateway.client import ModelGateway
from app.retrieval.models import RetrievedChunk

logger = logging.getLogger(__name__)

GRADER_SYSTEM_INSTRUCTION = """You are an expert relevance evaluator for an enterprise RAG system.
Evaluate whether the retrieved passage contains facts or context that help answer the user's question.
Be objective. If the passage is completely off-topic or irrelevant, mark it irrelevant.
If it partially addresses the question or provides useful background, mark it ambiguous.
If it directly provides information to answer the question, mark it relevant.

Respond in this exact format:
GRADE: <relevant|ambiguous|irrelevant>
REASON: <one sentence justification>"""


class GradeNode:
    """Evaluates each retrieved chunk for relevance and filters out irrelevant passages."""

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self.gateway = gateway or ModelGateway.get_instance()

    async def _grade_single_chunk(self, query: str, chunk: RetrievedChunk) -> GradeType:
        """Evaluate a single chunk's relevance against the query."""
        prompt = (
            f"Question: {query}\n\n"
            f"Retrieved passage:\n{chunk.content.strip()[:1000]}\n\n"
            "Does this passage contain information that helps answer the question?"
        )

        try:
            response_text, _provider = await self.gateway.generate(
                prompt=prompt,
                purpose="grading",
                system_instruction=GRADER_SYSTEM_INSTRUCTION,
                temperature=0.0,
            )
            # Parse GRADE: <grade>
            match = re.search(r"GRADE:\s*(relevant|ambiguous|irrelevant)", response_text, re.IGNORECASE)
            if match:
                grade = match.group(1).lower()
                return grade  # type: ignore[return-value]

            # Heuristic match if format was slightly deviated
            lower_text = response_text.lower()
            if "relevant" in lower_text and "irrelevant" not in lower_text:
                return "relevant"
            if "irrelevant" in lower_text:
                return "irrelevant"
            if "ambiguous" in lower_text:
                return "ambiguous"

            logger.warning(f"Could not parse grade from LLM response: '{response_text}', defaulting to relevant")
            return "relevant"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Grader LLM call failed for chunk {chunk.chunk_id}: {e}. Defaulting to relevant.")
            return "relevant"

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Grade all retrieved chunks concurrently and filter out irrelevant chunks."""
        chunks = state.get("retrieved_docs", [])
        query = (state.get("rewritten_query") or state.get("query", "")).strip()

        if not chunks:
            logger.info("GradeNode received 0 chunks, passing through empty grades")
            return {"relevance_grades": [], "retrieved_docs": []}

        logger.info(f"GradeNode evaluating {len(chunks)} chunks for query: '{query}'")

        # Concurrently grade all candidate chunks
        tasks = [self._grade_single_chunk(query, chunk) for chunk in chunks]
        grades = await asyncio.gather(*tasks)

        logger.info(f"GradeNode assigned grades: {list(grades)}")

        # Keep relevant and ambiguous chunks; filter out purely irrelevant ones
        filtered_chunks: list[RetrievedChunk] = []
        for chunk, grade in zip(chunks, grades):
            if grade in ("relevant", "ambiguous"):
                filtered_chunks.append(chunk)

        # If some were relevant/ambiguous, retain them; otherwise leave filtered_chunks empty
        return {
            "relevance_grades": list(grades),
            "retrieved_docs": filtered_chunks,
        }
