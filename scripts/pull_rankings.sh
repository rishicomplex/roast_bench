#!/usr/bin/env bash
# Pull rankings from the hosted app (Workers KV) back into the repo, then
# regenerate the leaderboard and public showcase. Run after rating jokes at
# https://roast-bench.rishimehta.workers.dev, then commit the result.
set -euo pipefail
cd "$(dirname "$0")/.."

npx wrangler kv key get rankings --binding RANKINGS --remote > /tmp/roast_rankings_kv.json

# Reformat to match the repo's JSON style (indent 2, unicode, trailing newline).
python3 - <<'EOF'
import json
with open("/tmp/roast_rankings_kv.json") as f:
    d = json.load(f)
assert set(d) >= {"rankings", "lol_flags"}, f"unexpected KV payload: {list(d)}"
with open("data/rankings.json", "w") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write("\n")
EOF

python3 scoring.py
python3 build_showcase.py
echo "Pulled KV rankings -> data/rankings.json; leaderboard + showcase regenerated."
