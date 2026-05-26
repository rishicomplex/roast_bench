"""Flask app for rating jokes and viewing the leaderboard."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

from scoring import compute_leaderboard, regenerate

ROOT = Path(__file__).parent
DATA = ROOT / "data"
JOKES_DIR = DATA / "jokes"

app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))


def _load(p: Path) -> dict:
    with p.open() as f:
        return json.load(f)


def _save(p: Path, d: dict) -> None:
    with p.open("w") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")


def get_personalities() -> list[dict]:
    return _load(ROOT / "personalities.json")["personalities"]


def get_models() -> dict[str, dict]:
    return {m["id"]: m for m in _load(ROOT / "models.json")["models"]}


def get_rankings() -> dict:
    return _load(DATA / "rankings.json")


def save_rankings(r: dict) -> None:
    _save(DATA / "rankings.json", r)


def get_jokes() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = defaultdict(dict)
    if not JOKES_DIR.exists():
        return out
    for path in sorted(JOKES_DIR.glob("*.json")):
        d = _load(path)
        mid = d["model_id"]
        for pid, joke in d.get("jokes", {}).items():
            if joke:
                out[pid][mid] = joke
    return out


def _next_unranked(pers: list[dict], rankings: dict, model_id: str, skip: str | None = None) -> str | None:
    for p in pers:
        if p["id"] == skip:
            continue
        if model_id not in rankings["rankings"].get(p["id"], []):
            return p["id"]
    return None


@app.route("/")
def index():
    board = compute_leaderboard()["leaderboard"]
    pers = get_personalities()
    rankings = get_rankings()
    models = get_models()
    jokes = get_jokes()

    # progress per model
    progress = {}
    for mid in models:
        unranked = []
        has_joke = []
        for p in pers:
            if mid in jokes.get(p["id"], {}):
                has_joke.append(p["id"])
                if mid not in rankings["rankings"].get(p["id"], []):
                    unranked.append(p["id"])
        progress[mid] = {
            "unranked": unranked,
            "has_joke": has_joke,
            "next": unranked[0] if unranked else None,
        }

    return render_template(
        "index.html",
        board=board,
        models=models,
        personalities=pers,
        rankings=rankings,
        progress=progress,
    )


@app.route("/rate/<model_id>")
def rate_model(model_id):
    pers = get_personalities()
    rankings = get_rankings()
    nxt = _next_unranked(pers, rankings, model_id)
    if nxt is None:
        return redirect(url_for("index"))
    return redirect(url_for("rate_personality", model_id=model_id, personality_id=nxt))


@app.route("/rate/<model_id>/<personality_id>", methods=["GET", "POST"])
def rate_personality(model_id, personality_id):
    pers = get_personalities()
    by_pid = {p["id"]: p for p in pers}
    if personality_id not in by_pid:
        return ("Unknown personality", 404)

    rankings = get_rankings()
    models = get_models()
    jokes_for_p = get_jokes().get(personality_id, {})

    if request.method == "POST":
        body = request.get_json(force=True)
        order = [m for m in body.get("order", []) if m in jokes_for_p]
        lol = [m for m in body.get("lol", []) if m in jokes_for_p]
        rankings["rankings"][personality_id] = order
        rankings["lol_flags"][personality_id] = lol
        save_rankings(rankings)
        regenerate()
        nxt = _next_unranked(pers, rankings, model_id, skip=personality_id)
        if nxt:
            return jsonify({"next": url_for("rate_personality", model_id=model_id, personality_id=nxt)})
        return jsonify({"next": url_for("index")})

    current = list(rankings["rankings"].get(personality_id, []))
    lol_set = set(rankings["lol_flags"].get(personality_id, []))
    if model_id in jokes_for_p and model_id not in current:
        current.insert(0, model_id)
    cards = [
        {
            "model_id": mid,
            "display_name": models.get(mid, {}).get("display_name", mid),
            "joke": jokes_for_p[mid],
            "is_new": mid == model_id,
            "lol": mid in lol_set,
        }
        for mid in current
        if mid in jokes_for_p
    ]

    pers_progress = [
        {
            "personality": p,
            "rated": model_id in rankings["rankings"].get(p["id"], []),
            "is_current": p["id"] == personality_id,
            "has_joke": model_id in get_jokes().get(p["id"], {}),
        }
        for p in pers
    ]
    completed = sum(1 for x in pers_progress if x["rated"])

    return render_template(
        "rate.html",
        personality=by_pid[personality_id],
        cards=cards,
        model_id=model_id,
        model_display=models.get(model_id, {}).get("display_name", model_id),
        completed=completed,
        total=len(pers),
        pers_progress=pers_progress,
    )


@app.route("/personality/<personality_id>")
def rerank_personality(personality_id):
    """Re-rank a personality without anchoring on a specific 'new' model."""
    pers = get_personalities()
    by_pid = {p["id"]: p for p in pers}
    if personality_id not in by_pid:
        return ("Unknown personality", 404)

    rankings = get_rankings()
    models = get_models()
    jokes_for_p = get_jokes().get(personality_id, {})
    current = list(rankings["rankings"].get(personality_id, []))
    for mid in jokes_for_p:
        if mid not in current:
            current.append(mid)
    lol_set = set(rankings["lol_flags"].get(personality_id, []))
    cards = [
        {
            "model_id": mid,
            "display_name": models.get(mid, {}).get("display_name", mid),
            "joke": jokes_for_p[mid],
            "is_new": False,
            "lol": mid in lol_set,
        }
        for mid in current
        if mid in jokes_for_p
    ]

    return render_template(
        "rate.html",
        personality=by_pid[personality_id],
        cards=cards,
        model_id="",
        model_display="(re-rank)",
        completed=0,
        total=len(pers),
        pers_progress=[],
        rerank_only=True,
    )


@app.route("/personality/<personality_id>", methods=["POST"])
def save_rerank(personality_id):
    body = request.get_json(force=True)
    rankings = get_rankings()
    jokes_for_p = get_jokes().get(personality_id, {})
    rankings["rankings"][personality_id] = [m for m in body.get("order", []) if m in jokes_for_p]
    rankings["lol_flags"][personality_id] = [m for m in body.get("lol", []) if m in jokes_for_p]
    save_rankings(rankings)
    regenerate()
    return jsonify({"next": url_for("index")})


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
