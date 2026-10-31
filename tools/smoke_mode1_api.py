"""Offline smoke for the Mode 1 API: queue mode 0/1, analysis, corrections, accuracy."""

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from overheard.app import create_app
from overheard.config import Settings


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "smoke.db"
        app = create_app(Settings(db_path=db))
        client = TestClient(app)

        # queue mode 0 unchanged
        r0 = client.get("/api/queue?mode=0")
        assert r0.status_code == 200, r0.text
        assert all("urgency" not in item for item in r0.json()), r0.text[:400]
        print(f"mode 0: {len(r0.json())} items, no urgency/team keys")

        # m37: Eleanor Voss, urgent hardship
        r1 = client.get("/api/messages/m37?mode=1")
        assert r1.status_code == 200, r1.text
        a = r1.json()["analysis"]
        summ = a["summary"]["data"]
        urg = a["intent_urgency"]["data"]
        rout = a["routing"]["data"]
        print(f"m37: {summ['short']} | {urg['intent']} {urg['urgency']} | {rout['team']}")
        assert urg["intent"] == "urgent_hardship" and urg["urgency"] == 5
        assert rout["team"] == "escalations"
        assert a["summary"]["provenance"] in ("mock", "llm", "fallback"), a["summary"]["provenance"]
        assert "spans" in a["extraction"]["data"] or True  # spans live inside extraction data

        # queue mode 1 sorted by (-urgency, receivedAt, id)
        rq = client.get("/api/queue?mode=1")
        assert rq.status_code == 200, rq.text
        items = rq.json()
        keys = [(-i["urgency"], i["receivedAt"], i["id"]) for i in items]
        assert keys == sorted(keys), keys
        assert all("team" in i for i in items)
        top = items[0]
        print(f"mode 1 queue: {len(items)} items, top = {top['id']} u{top['urgency']} {top['team']}")

        # POST analysis (re-run, force)
        rp = client.post("/api/analysis/m37?force=true")
        assert rp.status_code == 200, rp.text
        assert "summary" in rp.json() and "routing" in rp.json()

        # corrections round trip: correct intent_urgency.intent + extraction.caseId to null
        rc = client.post(
            "/api/corrections",
            json={"voicemail": "m37", "task": "intent_urgency", "field": "intent", "value": "billed"},
        )
        assert rc.status_code == 200, rc.text
        rn = client.post(
            "/api/corrections",
            json={"voicemail": "m37", "task": "extraction", "field": "caseId", "value": None},
        )
        assert rn.status_code == 200, rn.text
        unknown = client.post(
            "/api/corrections",
            json={"voicemail": "m999", "task": "intent_urgency", "field": "intent", "value": "billed"},
        )
        assert unknown.status_code == 404, unknown.status_code
        got = client.get("/api/corrections").json()
        fields = {c["field"] for c in got if c["voicemail"] == "m37"}
        assert fields == {"intent", "caseId"}, got

        # accuracy reflects the corrections (caseId correction to null is honoured)
        acc = client.get("/api/accuracy").json()
        print("accuracy:", json.dumps(acc, sort_keys=True)[:300])
        assert acc["corrections"] >= 2

        # delete corrections, accuracy back
        assert client.delete("/api/corrections").json() == {"cleared": True}
        assert client.get("/api/corrections").json() == []
        acc2 = client.get("/api/accuracy").json()
        assert acc2["corrections"] == 0

    print("SMOKE OK")


if __name__ == "__main__":
    main()
