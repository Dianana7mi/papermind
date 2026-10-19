"""Exercise the RUNNING local server's real SSE/model/file path against the existing AWQ smoke library.
The local JWT is generated in process memory and never written to results.
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import httpx  # noqa: E402

from app.core.security import token_for  # noqa: E402

smoke = json.loads((ROOT / "evaluation/results/live-smoke.json").read_text(encoding="utf8"))
with sqlite3.connect(ROOT / "backend/data/papermind.db") as db:
    owner = db.execute("SELECT owner_id FROM libraries WHERE id=?", (smoke["library_id"],)).fetchone()[0]
with httpx.Client(
    base_url="http://127.0.0.1:8000", headers={"Authorization": "Bearer " + token_for(owner)}, timeout=240
) as client:
    client.get("/health/ready").raise_for_status()
    events = []
    with client.stream(
        "POST",
        "/api/v1/research/chat/stream",
        json={
            "library_id": smoke["library_id"],
            "query": "What does AWQ use to identify salient weight channels?",
            "mode": "hybrid",
            "top_k": 4,
        },
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    done = next(e for e in events if "answer" in e)
    assert done["trace_id"] and done["citations"]
    done["http_citations"] = [
        {
            "paper_id": c["paper_id"],
            "status": client.get(f"/api/v1/papers/{c['paper_id']}/file").status_code,
            "page": c["page"],
        }
        for c in done["citations"]
    ]
    done["sse_status_events"] = len([e for e in events if "node" in e])
    (ROOT / "evaluation/results/api-live-smoke.json").write_text(
        json.dumps(done, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(
        json.dumps(
            {
                "sse": "PASS",
                "citations": len(done["citations"]),
                "claims": len(done["verification"]),
                "trace_id_present": bool(done["trace_id"]),
            }
        )
    )
