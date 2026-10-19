"""Seven real graph variants on the SAME existing real-paper smoke library.

Run from backend: python ../evaluation/scripts/agent_ablation.py --deepseek
Invokes paid generation APIs. No accuracy is inferred without independent gold answers.
"""

import argparse
import asyncio
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
parser = argparse.ArgumentParser()
parser.add_argument("--deepseek", action="store_true")
parser.add_argument(
    "--question",
    default="Compare the experiments reported for OPT-1.3B and explain how their evaluation conditions limit the comparison.",
)
parser.add_argument("--max-model-calls", type=int, default=30)
args = parser.parse_args()
if args.deepseek:
    os.environ["PM_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]
    os.environ["PM_BASE_URL"] = "https://api.deepseek.com/v1"
    os.environ["PM_CHAT_MODEL"] = "deepseek-chat"
from app.agents.research import AblationOptions, run_agent  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import Session  # noqa: E402
from app.models import Library  # noqa: E402
from app.schemas import ChatInput  # noqa: E402

variants = [
    ("Baseline A: dense", "dense", AblationOptions(False, False, False, False)),
    ("Baseline B: hybrid", "hybrid", AblationOptions(False, False, False, False)),
    ("Baseline C: rerank", "rerank", AblationOptions(False, False, False, False)),
    ("Baseline D: agentic", "hybrid", AblationOptions(True, False, False, False)),
    ("PaperMind A: structured", "hybrid", AblationOptions(True, True, False, False)),
    ("PaperMind B: comparison", "hybrid", AblationOptions(True, True, True, False)),
    ("PaperMind Full", "hybrid", AblationOptions()),
]


async def main():
    if not settings().api_key:
        raise RuntimeError("Configure a real provider before running the agent ablation")
    smoke = json.loads((ROOT / "evaluation/results/live-smoke.json").read_text(encoding="utf8"))
    result = {
        "metadata": {
            "scope": "single real AWQ paper, one query, sequential exploratory run; no human gold quality labels",
            "question": args.question,
            "library_id": smoke["library_id"],
            "model": settings().chat_model,
            "embedding": settings().embedding_model,
            "temperature": settings().temperature,
            "quality_accuracy": None,
            "offline_cost": "Shared existing index; see live-smoke ingestion usage",
            "prices_configured": settings().input_cost_per_million is not None,
        },
        "runs": [],
    }
    output = ROOT / "evaluation/results/agent-ablation.json"
    calls = 0
    async with Session() as db:
        library = await db.get(Library, smoke["library_id"])
        for name, mode, options in variants:
            if calls >= args.max_model_calls:
                result["stopped"] = "model-call budget reached"
                break
            request = ChatInput(library_id=library.id, query=args.question, mode=mode, top_k=4)
            state = await run_agent(db, request, library.owner_id, [], options=options)
            used = len(state.get("usage", {}).get("calls", []))
            calls += used
            row = {
                "variant": name,
                "latency_ms": state["latency_ms"],
                "tool_calls": state.get("tool_count", 0),
                "model_calls": used,
                "input_tokens": state["usage"]["input_tokens"],
                "output_tokens": state["usage"]["output_tokens"],
                "cost_usd": state["usage"]["estimated_cost_usd"],
                "experiments": len(state.get("experiments", [])),
                "comparisons": len(state.get("comparisons", [])),
                "claims": len(state.get("claims", [])),
                "citation_validity": sum(
                    bool(c["evidence_ids"])
                    and all(i in {e["id"] for e in state["evidence"]} for i in c["evidence_ids"])
                    for c in state["claims"]
                )
                / len(state["claims"])
                if state["claims"]
                else None,
                "quality_accuracy": None,
                "answer": state["final_answer"],
                "verification": state["verification"],
                "trace": state["trace"],
                "errors": state["errors"],
            }
            result["runs"].append(row)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    with (output.with_suffix(".csv")).open("w", encoding="utf8", newline="") as f:
        columns = [
            "variant",
            "latency_ms",
            "tool_calls",
            "model_calls",
            "input_tokens",
            "output_tokens",
            "cost_usd",
            "experiments",
            "comparisons",
            "claims",
            "citation_validity",
            "quality_accuracy",
        ]
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["runs"])
    print(
        json.dumps({"variants_executed": len(result["runs"]), "model_calls": calls, "quality_accuracy": None})
    )


if __name__ == "__main__":
    asyncio.run(main())
