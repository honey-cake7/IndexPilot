"""Export the backend contract for the generated frontend types; no DB connection required."""

import json
from pathlib import Path

from indexpilot.main import create_app


def main():
    output = Path(__file__).resolve().parents[1] / "frontend" / ".openapi.json"
    output.write_text(
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Exported frontend/.openapi.json from the current FastAPI contract.")


if __name__ == "__main__":
    main()
