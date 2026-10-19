"""Re-run deterministic alignment over saved model extractions, retaining the raw smoke result.

Does not invent new extractions, mutate the saved smoke response, or claim human verification.
Run from backend with its Python; SQL corrections use the public revision API for actual users.
"""

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sqlalchemy import select  # noqa: E402

from app.core.db import Session  # noqa: E402
from app.experiments import align_record  # noqa: E402
from app.ingestion.pipeline import evidence_dict  # noqa: E402
from app.models import Evidence  # noqa: E402
from app.schemas import ExperimentRecord  # noqa: E402


async def main():
    source = ROOT / "evaluation/results/live-smoke.json"
    smoke = json.loads(source.read_text(encoding="utf8"))
    async with Session() as db:
        rows = (await db.scalars(select(Evidence).where(Evidence.paper_id == smoke["paper_id"]))).all()
    evidence = {e.id: evidence_dict(e) for e in rows}
    records = []
    for item in smoke["experiments"]:
        record = ExperimentRecord.model_validate(item["record"])
        record.warnings = []
        aligned = align_record(record, evidence)
        records.append(aligned.model_dump(mode="json"))
    result = {
        "source_result": "live-smoke.json",
        "operation": "deterministic re-alignment of real model output against Docling table cells",
        "status_counts": dict(Counter(r["verification_status"] for r in records)),
        "human_verified": False,
        "records": records,
    }
    output = ROOT / "evaluation/results/realignment.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print(result["status_counts"])


if __name__ == "__main__":
    asyncio.run(main())
