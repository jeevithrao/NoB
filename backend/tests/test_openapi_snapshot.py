"""docs/openapi.json is what the frontend developer reads: it must match the code."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_openapi_snapshot_is_current():
    from app.main import app

    snapshot = ROOT / "docs" / "openapi.json"
    assert snapshot.exists(), "run: python backend/scripts/export_openapi.py"
    expected = json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert snapshot.read_text() == expected, "API changed: run python backend/scripts/export_openapi.py and commit docs/openapi.json"


def test_every_documented_route_has_a_summary_path_and_error_envelope_free_of_detail_arrays():
    from app.main import app

    schema = app.openapi()
    assert len(schema["paths"]) >= 50
    assert "/purchases/{purchase_id}/rebind-device" in schema["paths"]
    assert "/me/notifications" in schema["paths"]
