"""Compute the leaderboard from rankings.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with path.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def percentile(rank: int, n: int) -> float | None:
    """Percentile for rank (0-indexed, 0 = best) within N models. None if N < 2."""
    if n < 2:
        return None
    return (n - 1 - rank) / (n - 1) * 100.0


def compute_leaderboard() -> dict:
    personalities = load_json(ROOT / "personalities.json")["personalities"]
    models = {m["id"]: m for m in load_json(ROOT / "models.json")["models"]}
    rankings = load_json(DATA / "rankings.json")

    per_model: dict[str, dict] = {}
    for mid, m in models.items():
        per_model[mid] = {
            "model_id": mid,
            "display_name": m.get("display_name", mid),
            "provider": m["provider"],
            "percentiles": {},
            "jokes_rated": 0,
            "lol_count": 0,
        }

    for p in personalities:
        pid = p["id"]
        order = rankings["rankings"].get(pid, [])
        lol = set(rankings["lol_flags"].get(pid, []))
        n = len(order)
        for i, mid in enumerate(order):
            if mid not in per_model:
                continue
            pct = percentile(i, n)
            per_model[mid]["percentiles"][pid] = pct
            per_model[mid]["jokes_rated"] += 1
            if mid in lol:
                per_model[mid]["lol_count"] += 1

    rows = []
    for mid, entry in per_model.items():
        pcts = [v for v in entry["percentiles"].values() if v is not None]
        avg = sum(pcts) / len(pcts) if pcts else None
        lol_rate = (entry["lol_count"] / entry["jokes_rated"] * 100.0) if entry["jokes_rated"] else None
        rows.append({
            "model_id": mid,
            "display_name": entry["display_name"],
            "provider": entry["provider"],
            "avg_percentile": avg,
            "lol_rate": lol_rate,
            "jokes_rated": entry["jokes_rated"],
            "lol_count": entry["lol_count"],
            "per_personality": entry["percentiles"],
        })

    rows.sort(key=lambda r: (r["avg_percentile"] is None, -(r["avg_percentile"] or 0)))
    return {"leaderboard": rows}


def regenerate() -> Path:
    out = DATA / "leaderboard.json"
    save_json(out, compute_leaderboard())
    return out


if __name__ == "__main__":
    path = regenerate()
    board = load_json(path)
    print(f"Wrote {path}\n")
    rows = board["leaderboard"]
    if not rows:
        print("(no models)")
    else:
        width = max(len(r["display_name"]) for r in rows)
        print(f"{'Rank':<5} {'Model':<{width}}  {'Avg %ile':>9}  {'LOL':>6}  {'Rated':>6}")
        for i, r in enumerate(rows, 1):
            pct = f"{r['avg_percentile']:.1f}" if r["avg_percentile"] is not None else "  —  "
            lol = f"{r['lol_rate']:.0f}%" if r["lol_rate"] is not None else "  —  "
            print(f"{i:<5} {r['display_name']:<{width}}  {pct:>9}  {lol:>6}  {r['jokes_rated']:>6}")
