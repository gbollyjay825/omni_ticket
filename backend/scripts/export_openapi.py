from pathlib import Path
import json
import sys

from app.main import create_app


def main() -> None:
    default_output = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "openapi.json"
    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else default_output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
