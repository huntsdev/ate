"""Run with uv from apps/api; no database, provider, or real credentials needed."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))
from sentinelforge.core.config import Settings  # noqa: E402
from sentinelforge.main import create_app  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
schema = create_app(Settings(postgres_password="synthetic-schema-only-password")).openapi()
serialized = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
target = Path(__file__).resolve().parents[1] / "packages/contracts/openapi.json"
if args.check:
    if not target.exists() or target.read_text(encoding="utf-8") != serialized:
        raise SystemExit("OpenAPI contract is stale; regenerate it before committing.")
    print("OpenAPI contract matches FastAPI.")
else:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialized, encoding="utf-8", newline="\n")
    print("Exported packages/contracts/openapi.json")
