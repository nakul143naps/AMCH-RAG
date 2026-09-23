"""Tests and precision evaluation for local cross-encoder RerankerService."""

from pathlib import Path

from qdrant_client import QdrantClient

from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.models import RetrievedChunk
from app.retrieval.reranker import RerankerService
from app.retrieval.retriever import HybridRetriever
from app.retrieval.vector_store import VectorStoreManager


def test_reranker_scoring_separation():
    """Verify that RerankerService assigns high probability to relevant chunks and near-zero to distractors."""
    reranker = RerankerService.get_instance()

    query = "What causes myocardial infarction?"
    chunks = [
        RetrievedChunk(
            chunk_id="chunk-distractor",
            score=0.5,
            content="Chocolate chip cookie recipes call for flour, brown sugar, eggs, and vanilla extract.",
            doc_id="doc-baking",
            source="recipes.txt",
            source_type="txt",
        ),
        RetrievedChunk(
            chunk_id="chunk-target",
            score=0.5,
            content="Myocardial infarction is primarily caused by atherosclerosis leading to thrombus formation in the coronary arteries.",
            doc_id="doc-cardio",
            source="cardiology.md",
            source_type="md",
        ),
    ]

    reranked = reranker.rerank(query=query, chunks=chunks, top_k=2)

    assert len(reranked) == 2
    assert reranked[0].chunk_id == "chunk-target"
    assert reranked[0].score > 0.8
    assert reranked[1].chunk_id == "chunk-distractor"
    assert reranked[1].score < 0.1


def test_reranker_disambiguation_against_keyword_distractors():
    """Verify cross-attention correctly separates true answer from dense/keyword overlapping distractors."""
    reranker = RerankerService.get_instance()

    query = "cardiovascular complications after heart attack"
    chunks = [
        RetrievedChunk(
            chunk_id="distractor-1",
            score=0.55,
            content="Tissue necrosis caused by local hypoxia is termed infarction, which is also observed in acute renal failure.",
            doc_id="doc-renal",
            source="renal.txt",
            source_type="txt",
        ),
        RetrievedChunk(
            chunk_id="distractor-2",
            score=0.54,
            content="Post-operative bacterial infection complications frequently arise after orthopedic knee arthroplasty.",
            doc_id="doc-ortho",
            source="ortho.txt",
            source_type="txt",
        ),
        RetrievedChunk(
            chunk_id="target",
            score=0.50,  # Initially lower RRF rank
            content="Following an acute myocardial infarction, major cardiovascular complications include ventricular arrhythmias, cardiogenic shock, and ventricular free-wall rupture.",
            doc_id="doc-cardio",
            source="cardiology.txt",
            source_type="txt",
        ),
    ]

    reranked = reranker.rerank(query=query, chunks=chunks, top_k=1)
    assert len(reranked) == 1
    assert reranked[0].chunk_id == "target"
    assert "arrhythmias" in reranked[0].content


def test_eval_compare_precision_with_and_without_reranking():
    """Eval benchmark comparing Top-1 precision on a test set with vs. without cross-encoder reranking."""
    reranker = RerankerService.get_instance()

    # Evaluation dataset: (query, list_of_candidate_chunks_with_baseline_order, target_id)
    eval_cases = [
        {
            "query": "symptoms of cardiac arrest",
            "candidates": [
                RetrievedChunk(
                    chunk_id="c1",
                    score=0.030,
                    content="Arrest warrants are issued by a judge following probable cause demonstrations in criminal law.",
                    doc_id="d1",
                    source="law.txt",
                    source_type="txt",
                ),
                RetrievedChunk(
                    chunk_id="c2",
                    score=0.025,
                    content="Sudden cardiac arrest is marked by immediate loss of consciousness, absence of pulse, and abnormal or stopped breathing.",
                    doc_id="d2",
                    source="emergency.txt",
                    source_type="txt",
                ),
            ],
            "target_id": "c2",
        },
        {
            "query": "treatment for anaphylactic shock",
            "candidates": [
                RetrievedChunk(
                    chunk_id="a1",
                    score=0.032,
                    content="Electric shock treatment (ECT) is used in psychiatric care for treatment-resistant major depression.",
                    doc_id="d3",
                    source="psychiatry.txt",
                    source_type="txt",
                ),
                RetrievedChunk(
                    chunk_id="a2",
                    score=0.026,
                    content="First-line emergency treatment for anaphylactic shock is intramuscular epinephrine injection into the anterolateral thigh.",
                    doc_id="d4",
                    source="allergy.txt",
                    source_type="txt",
                ),
            ],
            "target_id": "a2",
        },
    ]

    # Baseline without reranking: takes the initial candidate ranking (top candidate)
    baseline_top1_correct = 0
    for case in eval_cases:
        if case["candidates"][0].chunk_id == case["target_id"]:
            baseline_top1_correct += 1
    baseline_precision = baseline_top1_correct / len(eval_cases)

    # With cross-encoder reranking
    reranked_top1_correct = 0
    for case in eval_cases:
        reranked = reranker.rerank(
            query=case["query"], chunks=case["candidates"], top_k=1
        )
        if reranked and reranked[0].chunk_id == case["target_id"]:
            reranked_top1_correct += 1
    reranked_precision = reranked_top1_correct / len(eval_cases)

    # Baseline is confused by keyword traps (0% top-1 precision)
    assert baseline_precision == 0.0
    # Cross-encoder resolves query-passage semantic relationship (100% top-1 precision)
    assert reranked_precision == 1.0
    assert reranked_precision > baseline_precision


def test_hybrid_retriever_rerank_integration(tmp_path: Path):
    """Integration test verifying HybridRetriever rerank toggle."""
    test_client = QdrantClient(":memory:")
    vector_mgr = VectorStoreManager.get_instance(client=test_client)
    vector_mgr.ensure_collections()

    pipeline = IngestionPipeline(vector_mgr=vector_mgr)

    doc_path = tmp_path / "cardiology_protocol.md"
    doc_path.write_text(
        "# Emergency Protocol\n"
        "Administer oxygen and sublingual nitroglycerin for acute angina symptoms.\n\n"
        "Ventricular fibrillation requires immediate defibrillation and CPR initiation.",
        encoding="utf-8",
    )
    pipeline.process_file(file_path=doc_path, source_name="cardiology_protocol.md")

    retriever = HybridRetriever(vector_mgr=vector_mgr)

    # 1. Retrieve with rerank=True (default)
    reranked_results = retriever.retrieve(
        query="defibrillation for ventricular fibrillation", limit=2, rerank=True
    )
    assert len(reranked_results) > 0
    assert "defibrillation" in reranked_results[0].content

    # 2. Retrieve with rerank=False
    unreranked_results = retriever.retrieve(
        query="defibrillation for ventricular fibrillation", limit=2, rerank=False
    )
    assert len(unreranked_results) > 0
