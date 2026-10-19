"""Reproducible real-text retrieval + explicitly synthetic rule ablations.

Run from backend: .venv/Scripts/python ../evaluation/scripts/benchmark.py
Requires the AWQ PDF downloaded by the documented command. No generation API is used.
"""

import asyncio
import csv
import hashlib
import json
import platform
import re
import sys
import time
import unicodedata
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import numpy as np  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from app.experiments import compare, verify_claim  # noqa: E402
from app.ingestion.parser import chunk_section  # noqa: E402
from app.retrieval import bm25, retrieval_metrics, rrf  # noqa: E402
from app.schemas import AtomicClaim, ExperimentRecord, Provenance  # noqa: E402
from app.services.providers import embed, rerank  # noqa: E402


def compact(text):
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", text).casefold())


async def main():
    source = ROOT / "backend/data/public/awq.pdf"
    annotation = json.loads((ROOT / "evaluation/datasets/awq-questions.json").read_text(encoding="utf-8"))
    corpus = []
    for page, content in enumerate(PdfReader(source).pages, 1):
        for n, text in enumerate(chunk_section(content.extract_text() or "", 1800, 200)):
            corpus.append(
                {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"awq:{page}:{n}")), "text": text, "page": page}
            )
    started = time.perf_counter()
    vectors = np.array(await embed([d["text"] for d in corpus]))
    offline_seconds = time.perf_counter() - started
    rows, missing = [], []
    for question in annotation["questions"]:
        anchor = compact(question["anchor"])
        relevant = [d["id"] for d in corpus if anchor in compact(d["text"])]
        if not relevant:
            missing.append(question["id"])
            continue
        start = time.perf_counter()
        vector = np.array((await embed([question["query"]]))[0])
        cosine = vectors @ vector / (np.linalg.norm(vectors, axis=1) * np.linalg.norm(vector))
        dense = [{**corpus[i], "score": float(cosine[i])} for i in np.argsort(-cosine)[:30]]
        dense_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        lexical = bm25(question["query"], corpus, 30)
        bm25_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        hybrid = rrf([dense, lexical])
        fusion_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        candidates = hybrid[:20]
        scores = await rerank(question["query"], [d["text"] for d in candidates])
        reranked = [
            d for _, d in sorted(zip(scores, candidates, strict=True), key=lambda v: v[0], reverse=True)
        ]
        rerank_ms = (time.perf_counter() - start) * 1000
        for mode, ranked, latency in (
            ("dense", dense, dense_ms),
            ("bm25", lexical, bm25_ms),
            ("hybrid", hybrid, dense_ms + bm25_ms + fusion_ms),
            ("rerank", reranked, dense_ms + bm25_ms + fusion_ms + rerank_ms),
        ):
            rows.append(
                {
                    "question_id": question["id"],
                    "mode": mode,
                    **retrieval_metrics([d["id"] for d in ranked], relevant),
                    "latency_ms": latency,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "generation_cost_usd": 0,
                    "cpu_cost_usd": None,
                }
            )
    # Independent rule regression/ablation. Synthetic fixtures are never mixed with real paper measurements.
    base = ExperimentRecord(
        method_name="Synthetic A",
        model_name="SyntheticMoE",
        model_version="v1",
        dataset_name="PIQA",
        dataset_split="validation",
        metric_name="accuracy",
        metric_value="79.2",
        metric_unit="percent",
        metric_direction="higher",
        metric_definition="correct/total",
        average_bits="2.5",
        quantized_components=["expert_weights"],
        evaluation_protocol="synthetic zero-shot",
        calibration_samples=512,
        verification_status="supported",
        field_verification={
            key: "reviewed"
            for key in (
                "model_name",
                "model_version",
                "dataset_name",
                "dataset_split",
                "metric_name",
                "metric_value",
                "metric_unit",
                "metric_direction",
                "metric_definition",
                "average_bits",
                "quantized_components",
                "evaluation_protocol",
                "calibration_samples",
            )
        },
        provenance=Provenance(
            evidence_ids=["synthetic-evidence"], original_value="79.2", row_index=1, column_index=1
        ),
    )
    cases = [
        ("same", {}, "COMPARABLE"),
        ("bits", {"average_bits": "3"}, "PARTIALLY_COMPARABLE"),
        ("metric", {"metric_name": "perplexity"}, "NOT_COMPARABLE"),
        ("calibration", {"calibration_samples": 128}, "PARTIALLY_COMPARABLE"),
        ("missing_version", {"model_version": None}, "INSUFFICIENT_INFORMATION"),
        ("split", {"dataset_split": "test"}, "NOT_COMPARABLE"),
        ("scope", {"quantized_components": ["all_weights"]}, "PARTIALLY_COMPARABLE"),
        ("missing_budget", {"average_bits": None}, "INSUFFICIENT_INFORMATION"),
    ]
    rules = []
    for name, patch, expected in cases:
        other = ExperimentRecord.model_validate({**base.model_dump(), **patch})
        for variant in ("without_comparability", "with_comparability"):
            start = time.perf_counter()
            predicted = "COMPARABLE" if variant == "without_comparability" else compare(base, other)["status"]
            rules.append(
                {
                    "case": name,
                    "variant": variant,
                    "expected": expected,
                    "predicted": predicted,
                    "correct": int(predicted == expected),
                    "latency_ms": (time.perf_counter() - start) * 1000,
                    "data_scope": "synthetic_rule_fixture",
                }
            )
    claims = []
    for name, patch in (
        ("valid", {}),
        ("wrong_value", {"metric_value": "80"}),
        ("wrong_dataset", {"dataset_name": "ARC"}),
        ("wrong_model", {"model_name": "Other"}),
        ("wrong_metric", {"metric_name": "perplexity"}),
        ("invalid_citation", {"evidence_ids": ["invalid"]}),
    ):
        claim = AtomicClaim.model_validate(
            {
                "text": "synthetic test claim",
                "experiment_id": "exp",
                "metric_value": "79.2",
                "metric_unit": "percent",
                "evidence_ids": ["synthetic-evidence"],
                **patch,
            }
        )
        verdict = verify_claim(
            claim,
            {
                "synthetic-evidence": {
                    "paper_id": "synthetic-paper",
                    "text": "Synthetic fixture only",
                    "locator": {
                        "captions": ["SyntheticMoE accuracy (%)"],
                        "cells": [
                            {"row": 0, "col": 1, "end_col": 2, "text": "PIQA", "column_header": True},
                            {"row": 1, "col": 0, "text": "Synthetic A"},
                            {"row": 1, "col": 1, "text": "79.2"},
                        ],
                    },
                }
            },
            {"exp": base},
        )
        claims.append(
            {
                "case": name,
                "expected_support": name == "valid",
                "predicted_support": verdict["status"] == "supported",
                "status": verdict["status"],
                "scope": "synthetic_rule_fixture",
            }
        )
    result = {
        "metadata": {
            "source": annotation["source"],
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "paper_count": 1,
            "human_verified_records": 0,
            "human_verified_questions": 0,
            "questions_executed": len(rows) // 4,
            "missing_anchors": missing,
            "chunks": len(corpus),
            "chunking": "pypdf text, 1800 characters, 200 overlap; distinct from Docling application index",
            "offline_embedding_seconds": offline_seconds,
            "python": platform.python_version(),
            "hardware": platform.platform(),
            "annotation_limitations": annotation["annotation"],
            "run_order": "dense then BM25 then hybrid then rerank per query; cold model loads included",
        },
        "retrieval": rows,
        "comparability_ablation": rules,
        "claim_verification": claims,
        "full_agent_ablation": {
            "status": "not_run",
            "reason": "Small source-anchored pilot only; requires independent human labels and controlled generation runs",
        },
    }
    output = ROOT / "evaluation/results"
    output.mkdir(parents=True, exist_ok=True)
    (output / "pilot.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, values in (("retrieval", rows), ("comparability", rules), ("claims", claims)):
        with (output / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)
    print(
        json.dumps(
            {
                "questions": len(rows) // 4,
                "chunks": len(corpus),
                "missing_anchors": missing,
                "output": str(output),
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
