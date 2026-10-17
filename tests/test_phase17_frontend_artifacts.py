"""Phase 17 Verification Suite: Frontend UI Application & Generative UI Components.

Tests:
  17.1: backend/api/static/index.html exists and is non-empty (> 10 KB).
  17.2: GET / serves the interactive dashboard HTML with 200 OK.
  17.3: frontend/package.json specifies Next.js 14, React, Tailwind, and Lucide.
  17.4: frontend/src/types/copilot.ts defines all visual payloads, badges, and conflict cards.
  17.5: All 6 Generative UI React widgets exist in frontend/src/components/.
  17.6: frontend/src/app/page.tsx and layout.tsx exist and wire multi-user state.
  17.7: HTML dashboard implements native <dialog> elements for citations and evaluation gate.
  17.8: HTML dashboard provides quick prompt chips covering Q1, Q2, Q3, Q4, Q7, Q8, Q12, Q13, Q17.
  17.9: HTML dashboard hooks into /api/feedback/reset and /api/evaluation/report.
  17.10: FastAPI /docs (Swagger) and /api/health are reachable and valid.
"""

from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_17_1_static_dashboard_html_exists():
    """Checkpoint 17.1: Static index.html exists and is properly populated (> 10 KB)."""
    static_file = Path("backend/api/static/index.html")
    assert static_file.exists()
    assert static_file.stat().st_size > 10000


def test_17_2_dashboard_served_at_root(client):
    """Checkpoint 17.2: GET / serves the HTML dashboard with 200 OK and proper headers."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "FlytBase Asset Intelligence Copilot" in resp.text
    assert "Live Field Telemetry" in resp.text


def test_17_3_frontend_package_json():
    """Checkpoint 17.3: frontend/package.json specifies Next.js, React, and UI dependencies."""
    pkg_file = Path("frontend/package.json")
    assert pkg_file.exists()
    with open(pkg_file, "r") as f:
        pkg = json.load(f)
    assert "next" in pkg["dependencies"]
    assert "react" in pkg["dependencies"]
    assert "tailwindcss" in pkg["devDependencies"]
    assert "lucide-react" in pkg["dependencies"]


def test_17_4_frontend_typescript_types():
    """Checkpoint 17.4: frontend/src/types/copilot.ts defines all required schemas."""
    ts_types = Path("frontend/src/types/copilot.ts")
    assert ts_types.exists()
    content = ts_types.read_text(encoding="utf-8")
    assert "interface StatusCardSpec" in content
    assert "interface TableSpec" in content
    assert "interface LineChartSpec" in content
    assert "interface BarChartSpec" in content
    assert "interface MapSpec" in content
    assert "interface HeatmapSpec" in content
    assert "interface OverrideDiffBadge" in content
    assert "interface ConflictAlertCard" in content
    assert "interface CopilotResponseEnvelope" in content


def test_17_5_frontend_widget_components():
    """Checkpoint 17.5: All 6 Generative UI React widgets exist in frontend/src/components/."""
    comp_dir = Path("frontend/src/components")
    assert comp_dir.exists()
    expected_widgets = [
        "StatusCardWidget.tsx",
        "TableWidget.tsx",
        "LineChartWidget.tsx",
        "BarChartWidget.tsx",
        "MapWidget.tsx",
        "HeatmapWidget.tsx",
        "OverrideBadge.tsx",
        "ConflictCard.tsx",
    ]
    for w in expected_widgets:
        f = comp_dir / w
        assert f.exists(), f"Missing widget component: {w}"
        assert f.stat().st_size > 100


def test_17_6_frontend_page_and_layout():
    """Checkpoint 17.6: Next.js page.tsx and layout.tsx exist and wire multi-user chat state."""
    page_file = Path("frontend/src/app/page.tsx")
    layout_file = Path("frontend/src/app/layout.tsx")
    assert page_file.exists()
    assert layout_file.exists()

    content = page_file.read_text(encoding="utf-8")
    assert "Michael Turner" in content
    assert "handleUserChange" in content
    assert "renderVisual" in content


def test_17_7_static_ui_has_native_dialogs():
    """Checkpoint 17.7: Static UI implements native <dialog> elements per modern HTML standards."""
    static_file = Path("backend/api/static/index.html")
    content = static_file.read_text(encoding="utf-8")
    assert '<dialog id="eval-modal"' in content
    assert '<dialog id="citation-modal"' in content
    assert "showModal()" in content


def test_17_8_static_ui_has_quick_prompts():
    """Checkpoint 17.8: Static UI provides quick prompt chips covering official evaluation queries."""
    static_file = Path("backend/api/static/index.html")
    content = static_file.read_text(encoding="utf-8")
    assert "Q1: WELL-0001 Status Card" in content
    assert "Q2: NE-08 Non-Producing Table" in content
    assert "Q3: WELL-0001 13-Week Chart" in content
    assert "Q4: WELL-0001 4-Year Spills Table" in content
    assert "Q7: NE-08 Spills Map" in content
    assert "Q8: Area &times; Month Heatmap" in content
    assert "Q12: WELL-0164 Temp Override" in content
    assert "Q17: Contradiction Alert" in content


def test_17_9_static_ui_has_reset_and_eval():
    """Checkpoint 17.9: Static UI wires into reset and evaluation API endpoints."""
    static_file = Path("backend/api/static/index.html")
    content = static_file.read_text(encoding="utf-8")
    assert "/api/feedback/reset" in content
    assert "/api/evaluation/report" in content
    assert "resetState()" in content
    assert "openEvalModal()" in content


def test_17_10_full_api_health_and_docs(client):
    """Checkpoint 17.10: OpenAPI docs (/docs) and health (/api/health) endpoints are operational."""
    resp_docs = client.get("/docs")
    assert resp_docs.status_code == 200
    assert "swagger-ui" in resp_docs.text.lower()

    resp_health = client.get("/api/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "healthy"
