"""Phase 16 Verification Suite: FastAPI Production Server, SSE Streaming & REST API.

Tests:
  16.1: GET /api/health returns 200, database connected, total_wells == 200, total_inspections >= 39000.
  16.2: GET /api/users returns operator list with user_id, user_name, role, team_name, initials, color_hue.
  16.3: GET /api/wells and GET /api/wells/WELL-0001 return well summaries and full 360-degree dossier.
  16.4: POST /api/chat with Q1 returns StatusCardSpec with is_producing == False.
  16.5: POST /api/chat with Q2 returns TableSpec with 4 rows for Northeast Block 8.
  16.6: POST /api/chat with Q3 returns LineChartSpec with 13 points and threshold line.
  16.7: POST /api/chat with Q7 returns MapSpec with 4 pins (WELL-0151, WELL-0165, WELL-0175, WELL-0186).
  16.8: POST /api/chat with Q8 returns HeatmapSpec with grand_total == 141 and 4 area rows.
  16.9: POST /api/chat/stream emits SSE events with metadata, progress, and envelope chunks.
  16.10: POST /api/feedback/reset executes in < 50ms; GET /api/evaluation/report returns 18/18 PASS.
"""

import json
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.db.connection import get_db_connection
from backend.feedback.override_engine import reset_runtime_state


@pytest.fixture(autouse=True)
def clean_state():
    con = get_db_connection()
    reset_runtime_state(con)
    yield
    reset_runtime_state(con)


@pytest.fixture
def client():
    return TestClient(app)


def test_16_1_health_check(client):
    """Checkpoint 16.1: Health endpoint returns healthy and connected database."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["total_wells"] == 200
    assert data["total_inspections"] >= 39000
    assert "version" in data


def test_16_2_users_endpoint(client):
    """Checkpoint 16.2: Users endpoint returns all operator profiles with metadata."""
    resp = client.get("/api/users")
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) >= 14

    user_names = [u["user_name"] for u in users]
    assert "Michael Turner" in user_names
    assert "Jessica Reed" in user_names
    assert "Tyler Hughes" in user_names
    assert "Laura Simmons" in user_names

    mt = next(u for u in users if u["user_name"] == "Michael Turner")
    assert mt["user_id"] == "U-201"
    assert mt["team_name"] == "Northeast Production"
    assert mt["initials"] == "MT"
    assert mt["color_hue"] > 0


def test_16_3_wells_list_and_dossier(client):
    """Checkpoint 16.3: Wells endpoints list fleet wells and retrieve single 360-degree dossier."""
    resp_list = client.get("/api/wells?limit=10")
    assert resp_list.status_code == 200
    wells = resp_list.json()
    assert len(wells) == 10
    assert wells[0]["asset_id"] == "WELL-0001"
    assert "well_name" in wells[0]
    assert "area_name" in wells[0]

    resp_dossier = client.get("/api/wells/WELL-0001")
    assert resp_dossier.status_code == 200
    dossier_data = resp_dossier.json()
    assert dossier_data["status"] == "success"
    assert dossier_data["asset_id"] == "WELL-0001"
    dossier = dossier_data["dossier"]
    assert "status" in dossier
    assert "recent_inspections" in dossier
    assert "recent_repairs" in dossier


def test_16_4_chat_q1_status_card(client):
    """Checkpoint 16.4: Q1 via POST /api/chat returns status_card visual payload."""
    payload = {
        "message": "Is WELL-0001 producing oil right now? Explain how you know.",
        "user_name": "Michael Turner",
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "markdown_answer" in data
    assert "NOT producing" in data["markdown_answer"]
    assert data["visual_payload"]["visual_type"] == "status_card"
    card = data["visual_payload"]
    assert card["asset_id"] == "WELL-0001"
    assert card["is_producing"] is False
    assert len(data["citations"]) >= 1


def test_16_5_chat_q2_table(client):
    """Checkpoint 16.5: Q2 via POST /api/chat returns table visual payload with 4 rows."""
    payload = {
        "message": "Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.",
        "user_name": "Michael Turner",
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["visual_payload"]["visual_type"] == "table"
    table = data["visual_payload"]
    assert len(table["rows"]) == 4
    well_ids = [r["asset_id"] for r in table["rows"]]
    assert set(well_ids) == {"WELL-0164", "WELL-0170", "WELL-0172", "WELL-0175"}


def test_16_6_chat_q3_line_chart(client):
    """Checkpoint 16.6: Q3 via POST /api/chat returns line_chart visual payload."""
    payload = {
        "message": "Show the weekly wellhead and ambient temperatures for WELL-0001 over the last 13 weeks. On which dates was it not producing oil?",
        "user_name": "Michael Turner",
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["visual_payload"]["visual_type"] == "line_chart"
    chart = data["visual_payload"]
    assert len(chart["data_points"]) == 13
    assert chart["threshold_line"]["value"] == 15.0
    assert "2026-10-08" in chart["non_producing_markers"]
    assert "2026-10-15" in chart["non_producing_markers"]


def test_16_7_chat_q7_map(client):
    """Checkpoint 16.7: Q7 via POST /api/chat returns map visual payload with 4 pins."""
    payload = {
        "message": "Show on a map every well in Northeast Block 8 with a real spill in the last 90 days.",
        "user_name": "Michael Turner",
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["visual_payload"]["visual_type"] == "map"
    map_spec = data["visual_payload"]
    assert len(map_spec["pins"]) == 4
    pin_wells = [p["asset_id"] for p in map_spec["pins"]]
    assert set(pin_wells) == {"WELL-0151", "WELL-0165", "WELL-0175", "WELL-0186"}


def test_16_8_chat_q8_heatmap(client):
    """Checkpoint 16.8: Q8 via POST /api/chat returns heatmap visual payload summing to 141."""
    payload = {
        "message": "Produce a monthly heatmap of spill counts by area for 2026.",
        "user_name": "Michael Turner",
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["visual_payload"]["visual_type"] == "heatmap"
    hm = data["visual_payload"]
    assert hm["grand_total"] == 141
    assert hm["row_totals"] == [35, 43, 37, 26]
    assert len(data["override_badges"]) >= 1


def test_16_9_chat_stream_sse(client):
    """Checkpoint 16.9: POST /api/chat/stream emits Server-Sent Events with metadata, progress, and envelope."""
    payload = {
        "message": "Is WELL-0001 producing oil right now? Explain how you know.",
        "user_name": "Michael Turner",
    }
    events_found = []
    envelope_data = None

    with client.stream("POST", "/api/chat/stream", json=payload) as response:
        assert response.status_code == 200
        current_event = None
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("event: "):
                current_event = line.replace("event: ", "").strip()
                events_found.append(current_event)
            elif line.startswith("data: ") and current_event == "envelope":
                envelope_json_str = line.replace("data: ", "").strip()
                envelope_data = json.loads(envelope_json_str)

    assert "metadata" in events_found
    assert "progress" in events_found
    assert "envelope" in events_found
    assert "done" in events_found
    assert envelope_data is not None
    assert envelope_data["visual_payload"]["visual_type"] == "status_card"


def test_16_10_reset_and_evaluation_report(client):
    """Checkpoint 16.10: Reset endpoint runs in < 50ms and evaluation report returns 18/18 PASS."""
    # 1. Test reset
    resp_reset = client.post("/api/feedback/reset")
    assert resp_reset.status_code == 200
    data_reset = resp_reset.json()
    assert data_reset["status"] == "success"
    assert data_reset["duration_ms"] < 50.0

    # 2. Test evaluation report
    resp_eval = client.get("/api/evaluation/report")
    assert resp_eval.status_code == 200
    eval_data = resp_eval.json()
    assert eval_data["summary"]["total_scenarios"] == 18
    assert eval_data["summary"]["passed_scenarios"] == 18
    assert eval_data["summary"]["parity_percentage"] == 100.0
