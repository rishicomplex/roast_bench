"""Compute leaderboards from rankings.json, partitioned by personality set."""
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


def _load_totals(model_id: str) -> dict:
    p = DATA / "jokes" / f"{model_id}.json"
    if not p.exists():
        return {}
    return load_json(p).get("totals", {})


def _load_jokes_for_model(model_id: str) -> dict[str, str]:
    p = DATA / "jokes" / f"{model_id}.json"
    if not p.exists():
        return {}
    return {pid: j for pid, j in load_json(p).get("jokes", {}).items() if j}


def _personalities_by_set() -> dict[str, list[dict]]:
    pers = load_json(ROOT / "personalities.json")["personalities"]
    out: dict[str, list[dict]] = {}
    for p in pers:
        out.setdefault(p.get("set", "original"), []).append(p)
    return out


def _compute_set(set_name: str, personalities: list[dict], models: dict[str, dict], rankings: dict) -> list[dict]:
    """Compute leaderboard rows for one set, including only models that have at least one joke in this set."""
    pids = {p["id"] for p in personalities}
    per_model: dict[str, dict] = {}
    for mid, m in models.items():
        jokes_in_set = {pid for pid in _load_jokes_for_model(mid) if pid in pids}
        if not jokes_in_set:
            continue
        totals = _load_totals(mid)
        per_model[mid] = {
            "model_id": mid,
            "display_name": m.get("display_name", mid),
            "provider": m["provider"],
            "percentiles": {},
            "jokes_rated": 0,
            "lol_count": 0,
            # Token / cost totals only make sense for the original benchmark — humans have none.
            "cost_usd": totals.get("cost_usd"),
            "input_tokens": totals.get("input_tokens"),
            "output_tokens": totals.get("output_tokens"),
        }

    for p in personalities:
        pid = p["id"]
        order = rankings["rankings"].get(pid, [])
        lol = set(rankings["lol_flags"].get(pid, []))
        n = len(order)
        for i, mid in enumerate(order):
            if mid not in per_model:
                continue
            per_model[mid]["percentiles"][pid] = percentile(i, n)
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
            "set": set_name,
            "avg_percentile": avg,
            "lol_rate": lol_rate,
            "jokes_rated": entry["jokes_rated"],
            "personalities_in_set": len(personalities),
            "lol_count": entry["lol_count"],
            "cost_usd": entry["cost_usd"],
            "input_tokens": entry["input_tokens"],
            "output_tokens": entry["output_tokens"],
            "per_personality": entry["percentiles"],
        })

    rows.sort(key=lambda r: (r["avg_percentile"] is None, -(r["avg_percentile"] or 0)))
    return rows


def compute_leaderboard() -> dict:
    """Returns {"sets": {set_name: [rows]}, "leaderboard": [rows]} where `leaderboard` is the original set (back-compat)."""
    by_set = _personalities_by_set()
    models = {m["id"]: m for m in load_json(ROOT / "models.json")["models"]}
    rankings = load_json(DATA / "rankings.json")

    sets: dict[str, list[dict]] = {}
    for set_name, persons in by_set.items():
        sets[set_name] = _compute_set(set_name, persons, models, rankings)

    return {
        "sets": sets,
        # Back-compat: existing callers read top-level "leaderboard" — keep pointing at the original set.
        "leaderboard": sets.get("original", []),
    }


def regenerate() -> Path:
    out = DATA / "leaderboard.json"
    save_json(out, compute_leaderboard())
    return out


if __name__ == "__main__":
    path = regenerate()
    board = load_json(path)
    print(f"Wrote {path}\n")
    for set_name, rows in board["sets"].items():
        print(f"━━ {set_name} ━━")
        if not rows:
            print("(no models)\n")
            continue
        width = max(len(r["display_name"]) for r in rows)
        print(f"{'Rank':<5} {'Model':<{width}}  {'Avg %ile':>9}  {'LOL':>6}  {'Rated':>6}")
        for i, r in enumerate(rows, 1):
            pct = f"{r['avg_percentile']:.1f}" if r["avg_percentile"] is not None else "  —  "
            lol = f"{r['lol_rate']:.0f}%" if r["lol_rate"] is not None else "  —  "
            print(f"{i:<5} {r['display_name']:<{width}}  {pct:>9}  {lol:>6}  {r['jokes_rated']:>6}")
        print()
