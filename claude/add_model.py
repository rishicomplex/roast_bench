"""End-to-end: generate jokes for a new model, then launch the rating UI."""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from generate import JOKES_DIR, PROVIDERS, generate_for_model, load_json, save_json  # noqa: E402
from scoring import regenerate  # noqa: E402
from server import app  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="Model ID, e.g. claude-opus-4-7")
    ap.add_argument("--provider", required=True, choices=list(PROVIDERS.keys()))
    ap.add_argument("--display", default=None, help="Display name")
    ap.add_argument("--params", default="{}", help="JSON params override")
    ap.add_argument("--skip-generate", action="store_true", help="Reuse existing jokes file")
    ap.add_argument("--overwrite", action="store_true", help="Regenerate even if jokes file exists")
    ap.add_argument("--workers", type=int, default=5, help="Parallel API calls")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()

    personalities = load_json(ROOT / "personalities.json")["personalities"]
    models_doc = load_json(ROOT / "models.json")

    existing = next((m for m in models_doc["models"] if m["id"] == args.id), None)
    model = existing or {
        "id": args.id,
        "provider": args.provider,
        "display_name": args.display or args.id,
        "params": {},
    }
    if args.display:
        model = {**model, "display_name": args.display}
    if args.params:
        model = {**model, "params": {**model.get("params", {}), **json.loads(args.params)}}

    out_path = JOKES_DIR / f"{args.id}.json"
    if not args.skip_generate and (not out_path.exists() or args.overwrite):
        print(f"→ Generating jokes for {model['display_name']} ({model['provider']})…", file=sys.stderr)
        result = generate_for_model(model, personalities, max_workers=args.workers)
        save_json(out_path, result)
        print(f"✓ Saved {out_path}", file=sys.stderr)
    elif out_path.exists():
        print(f"✓ Reusing existing jokes at {out_path}", file=sys.stderr)
    else:
        print(f"✗ No jokes file and --skip-generate set; nothing to do.", file=sys.stderr)
        return 1

    if existing is None:
        models_doc["models"].append(model)
        save_json(ROOT / "models.json", models_doc)
        print(f"✓ Registered {args.id} in models.json", file=sys.stderr)

    regenerate()

    url = f"http://{args.host}:{args.port}/rate/{args.id}"
    print(f"→ Opening {url}", file=sys.stderr)
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
