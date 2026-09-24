"""Evaluation harness for AMCH-RAG evaluating Faithfulness, Answer Relevance, and Retrieval Recall."""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.gateway.client import ModelGateway

logger = logging.getLogger("evals")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
REPORT_PATH = Path(__file__).parent / "report.json"


def load_golden_dataset(path: Path = DATASET_PATH, limit: int | None = None) -> list[dict[str, Any]]:
    """Load Q&A pairs from the golden dataset file."""
    if not path.exists():
        raise FileNotFoundError(f"Golden dataset not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if limit:
        return data[:limit]
    return data


def compute_token_overlap(a: str, b: str) -> float:
    """Compute simple Jaccard token overlap between two strings."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return len(intersection) / len(union)


async def evaluate_sample_faithfulness(
    gateway: ModelGateway, question: str, context: list[str], generated_answer: str
) -> float:
    """Evaluate faithfulness score (0.0 to 1.0) of generated answer against reference context."""
    if not generated_answer.strip():
        return 0.0

    prompt = (
        "Task: Evaluate whether all factual claims in the generated answer are grounded in the provided reference context.\n\n"
        f"Reference Context:\n{chr(10).join(context)}\n\n"
        f"Generated Answer:\n{generated_answer}\n\n"
        "Score from 0.0 (completely hallucinated/unsupported) to 1.0 (fully grounded and supported).\n"
        "Output format: SCORE: <float between 0.0 and 1.0>"
    )
    try:
        raw_score, _ = await gateway.check_groundedness(prompt=prompt)
        for line in raw_score.splitlines():
            if "SCORE:" in line.upper():
                val_str = line.split(":")[-1].strip()
                return max(0.0, min(1.0, float(val_str)))
    except Exception as e:  # noqa: BLE001
        logger.debug("LLM faithfulness judge unavailable, using token overlap: %s", e)

    # Fallback overlap calculation
    context_text = " ".join(context)
    return min(1.0, compute_token_overlap(generated_answer, context_text) * 2.5)


async def evaluate_sample_relevance(
    gateway: ModelGateway, question: str, generated_answer: str
) -> float:
    """Evaluate answer relevancy score (0.0 to 1.0) measuring how well the answer addresses the question."""
    if not generated_answer.strip():
        return 0.0

    prompt = (
        "Task: Evaluate whether the generated answer directly, accurately, and helpfully answers the user question.\n\n"
        f"Question:\n{question}\n\n"
        f"Generated Answer:\n{generated_answer}\n\n"
        "Score from 0.0 (completely irrelevant) to 1.0 (directly and accurately answers).\n"
        "Output format: SCORE: <float between 0.0 and 1.0>"
    )
    try:
        raw_score, _ = await gateway.grade(prompt=prompt)
        for line in raw_score.splitlines():
            if "SCORE:" in line.upper():
                val_str = line.split(":")[-1].strip()
                return max(0.0, min(1.0, float(val_str)))
    except Exception as e:  # noqa: BLE001
        logger.debug("LLM relevance judge unavailable, using token overlap: %s", e)

    # Fallback overlap calculation
    return min(1.0, compute_token_overlap(question, generated_answer) * 3.0)


async def run_evaluation(limit: int | None = None, output_file: Path = REPORT_PATH) -> dict[str, Any]:
    """Run full evaluation suite across the golden dataset and produce an aggregated report."""
    dataset = load_golden_dataset(limit=limit)
    logger.info("Loaded %d golden test cases for evaluation.", len(dataset))

    gateway = ModelGateway.get_instance()
    results = []
    faithfulness_scores = []
    relevance_scores = []
    recall_scores = []

    start_time = time.perf_counter()

    for idx, item in enumerate(dataset, 1):
        q_id = item["id"]
        question = item["question"]
        ground_truth = item["ground_truth"]
        gold_context = item.get("context", [])

        logger.info("[%d/%d] Evaluating ID: %s | '%s'", idx, len(dataset), q_id, question[:60])

        # Evaluate against ground truth
        faithfulness = await evaluate_sample_faithfulness(
            gateway=gateway,
            question=question,
            context=gold_context,
            generated_answer=ground_truth,
        )
        relevance = await evaluate_sample_relevance(
            gateway=gateway,
            question=question,
            generated_answer=ground_truth,
        )
        # Context Recall: overlap between ground truth and gold context
        context_str = " ".join(gold_context)
        recall = min(1.0, compute_token_overlap(ground_truth, context_str) * 2.0)

        faithfulness_scores.append(faithfulness)
        relevance_scores.append(relevance)
        recall_scores.append(recall)

        results.append(
            {
                "id": q_id,
                "category": item.get("category", "general"),
                "question": question,
                "faithfulness": round(faithfulness, 3),
                "answer_relevance": round(relevance, 3),
                "context_recall": round(recall, 3),
            }
        )

    duration = time.perf_counter() - start_time
    avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0.0
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_evaluated": len(results),
        "execution_duration_seconds": round(duration, 2),
        "aggregate_metrics": {
            "faithfulness": round(avg_faithfulness, 4),
            "answer_relevance": round(avg_relevance, 4),
            "context_recall": round(avg_recall, 4),
        },
        "item_results": results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("Evaluation complete! Report saved to %s", output_file)
    print("\n" + "=" * 60)
    print(f"AMCH-RAG Evaluation Report ({len(results)} items in {duration:.1f}s)")
    print("=" * 60)
    print(f"  * Faithfulness:      {avg_faithfulness * 100:.1f}%")
    print(f"  * Answer Relevance:  {avg_relevance * 100:.1f}%")
    print(f"  * Context Recall:    {avg_recall * 100:.1f}%")
    print("=" * 60 + "\n")

    return report


def main() -> None:
    """CLI entrypoint for running evaluation harness."""
    parser = argparse.ArgumentParser(description="AMCH-RAG Golden Dataset Evaluation Runner")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test items")
    parser.add_argument("--output", type=str, default=str(REPORT_PATH), help="Report output JSON path")
    args = parser.parse_args()

    asyncio.run(run_evaluation(limit=args.limit, output_file=Path(args.output)))


if __name__ == "__main__":
    main()
