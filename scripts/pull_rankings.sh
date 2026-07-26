#!/usr/bin/env bash
# Pull rankings from the hosted app (Workers KV) back into the repo, then
# regenerate the leaderboard and public showcase. Run after rating jokes at
# https://roast-bench.rishimehta.workers.dev, then commit the result.
#
# Auth, in order of preference:
#   - CLOUDFLARE_API_TOKEN set (works in Claude Code remote sessions; token
#     needs Account > Workers KV Storage > Read) -> plain REST call.
#   - Otherwise wrangler's local OAuth login (works on the Mac).
set -euo pipefail
cd "$(dirname "$0")/.."

ACCOUNT_ID="f0a77ffe094ecbfd2865ebc4867fbead"
NAMESPACE_ID="dd0e8bc706874e8baa615c1f267f90ed"   # binding RANKINGS, see wrangler.jsonc
TMP="$(mktemp)"

if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
  curl -sf "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/storage/kv/namespaces/${NAMESPACE_ID}/values/rankings" \
    -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" > "$TMP"
else
  npx wrangler kv key get rankings --binding RANKINGS --remote > "$TMP"
fi

# Reformat to match the repo's JSON style (indent 2, unicode, trailing newline).
KV_FILE="$TMP" python3 - <<'EOF'
import json, os
with open(os.environ["KV_FILE"]) as f:
    d = json.load(f)
assert set(d) >= {"rankings", "lol_flags"}, f"unexpected KV payload: {list(d)}"
with open("data/rankings.json", "w") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write("\n")
EOF
rm -f "$TMP"

python3 scoring.py
python3 build_showcase.py
echo "Pulled KV rankings -> data/rankings.json; leaderboard + showcase regenerated."
