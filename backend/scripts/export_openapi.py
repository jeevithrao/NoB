"""Write the API's OpenAPI document to docs/openapi.json.

    python scripts/export_openapi.py          # regenerate
    python scripts/export_openapi.py --check  # exit 1 if the file is out of date (used by a test)

Import it into Postman/Insomnia, or generate a typed client from it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))  # so `import app` works when run as a script
TARGET = ROOT / "docs" / "openapi.json"


def render() -> str:
    from app.main import app

    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        return 0 if TARGET.exists() and TARGET.read_text() == text else 1
    TARGET.write_text(text)
    print(f"wrote {TARGET} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
