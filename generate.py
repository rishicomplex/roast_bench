"""Generate one roast joke per personality for a given model, at max thinking."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

ROOT = Path(__file__).parent
DATA = ROOT / "data"
JOKES_DIR = DATA / "jokes"

ROAST_PROMPT = "Write one roast joke about {name}. It will be your entry into a competitive roast battle judged by humans."


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def build_prompt(personality: dict) -> str:
    return ROAST_PROMPT.format(name=personality["name"])


# NOTE: All three calls pass NO tools — no web search, no code interp, no grounding.
# Each provider defaults to no tools when the tools/tool list is omitted.


def _cost(usage: dict, prices: dict) -> float:
    """Cost in USD. `prices` has 'input' and 'output' in $/M tokens. Thinking counts as output."""
    return (usage.get("input", 0) / 1e6) * prices.get("input", 0) + (usage.get("output", 0) / 1e6) * prices.get("output", 0)


def call_anthropic(model_id: str, prompt: str, params: dict) -> tuple[str, dict]:
    import anthropic

    # Claude Code cloud sessions reserve ANTHROPIC_API_KEY (it's the harness's own
    # credential), so its env-var UI won't let you set it. Accept an alias.
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ROAST_ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    kwargs: dict = {
        "model": model_id,
        "max_tokens": params.get("max_tokens", 64000),
        "messages": [{"role": "user", "content": prompt}],
    }
    # Opus 4.7+ uses output_config.effort ("low"|"medium"|"high"|"xhigh"|"max")
    # with adaptive thinking. Older models used thinking={type:enabled,budget_tokens:N}.
    if "effort" in params:
        kwargs["output_config"] = {"effort": params["effort"]}
        kwargs["thinking"] = {"type": "adaptive"}
    elif "thinking_budget" in params:
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": params["thinking_budget"]}
    # Streaming required when max-effort thinking can exceed 10 min.
    with client.messages.stream(**kwargs) as stream:
        response = stream.get_final_message()
    text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()
    u = response.usage
    usage = {
        "input": getattr(u, "input_tokens", 0),
        "output": getattr(u, "output_tokens", 0),  # includes thinking tokens
        "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
    }
    return text, usage


def call_openai(model_id: str, prompt: str, params: dict) -> tuple[str, dict]:
    from openai import OpenAI

    client = OpenAI()
    response = client.responses.create(
        model=model_id,
        input=prompt,
        reasoning={"effort": params.get("reasoning_effort", "xhigh")},
        max_output_tokens=params.get("max_output_tokens", 64000),
        # No tools — explicit pure-LM generation
    )
    u = response.usage
    reasoning_toks = 0
    details = getattr(u, "output_tokens_details", None)
    if details is not None:
        reasoning_toks = getattr(details, "reasoning_tokens", 0) or 0
    usage = {
        "input": getattr(u, "input_tokens", 0),
        "output": getattr(u, "output_tokens", 0),  # includes reasoning tokens
        "reasoning": reasoning_toks,
    }
    return response.output_text.strip(), usage


def call_google(model_id: str, prompt: str, params: dict) -> tuple[str, dict]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"])
    # Gemini 3.x uses thinking_level enum ("low"|"medium"|"high"); 2.x used thinking_budget int.
    thinking_cfg: dict = {}
    if "thinking_level" in params:
        thinking_cfg["thinking_level"] = params["thinking_level"]
    elif "thinking_budget" in params:
        thinking_cfg["thinking_budget"] = params["thinking_budget"]
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(**thinking_cfg) if thinking_cfg else None,
            max_output_tokens=params.get("max_output_tokens", 64000),
            # tools=[] (default) — no grounding / Google Search
        ),
    )
    m = getattr(response, "usage_metadata", None)
    usage = {
        "input": getattr(m, "prompt_token_count", 0) or 0,
        "output": (getattr(m, "candidates_token_count", 0) or 0) + (getattr(m, "thoughts_token_count", 0) or 0),
        "thoughts": getattr(m, "thoughts_token_count", 0) or 0,
    }
    return (response.text or "").strip(), usage


PROVIDERS = {
    "anthropic": call_anthropic,
    "openai": call_openai,
    "google": call_google,
}


def generate_for_model(model: dict, personalities: list[dict], max_workers: int = 5) -> dict:
    provider = model["provider"]
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    caller = PROVIDERS[provider]
    prices = model.get("prices_per_mtok", {})
    params = model.get("params", {})

    def _one(p: dict) -> tuple[str, str, dict, float]:
        try:
            joke, usage = caller(model["id"], build_prompt(p), params)
            cost = _cost(usage, prices) if prices else 0.0
        except Exception as e:
            return p["id"], "", {"error": str(e)}, 0.0
        return p["id"], joke, usage, cost

    results: dict[str, tuple[str, dict, float]] = {}
    total = len(personalities)
    print(f"  Dispatching {total} calls with {max_workers} workers…", file=sys.stderr, flush=True)
    t0 = time.monotonic()
    running_cost = 0.0
    ok = 0
    failed = 0
    starts: dict[str, float] = {}

    def _wrapped(p: dict):
        starts[p["id"]] = time.monotonic()
        print(f"  ▶ [{p['id']}] started", file=sys.stderr, flush=True)
        return _one(p)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_wrapped, p): p for p in personalities}
        for i, fut in enumerate(as_completed(futures), 1):
            pid, joke, usage, cost = fut.result()
            dt = time.monotonic() - starts.get(pid, t0)
            elapsed = time.monotonic() - t0
            if "error" in usage:
                failed += 1
                print(
                    f"  ✗ [{i}/{total}] [{pid}] FAILED after {dt:.1f}s — {usage['error'][:120]}",
                    file=sys.stderr, flush=True,
                )
            else:
                ok += 1
                running_cost += cost
                print(
                    f"  ✓ [{i}/{total}] [{pid}] {dt:.1f}s · in={usage.get('input',0)} out={usage.get('output',0)} cost=${cost:.4f} "
                    f"(elapsed {elapsed:.0f}s · running ${running_cost:.4f} · ok {ok} fail {failed})",
                    file=sys.stderr, flush=True,
                )
            results[pid] = (joke, usage, cost)

    jokes = {p["id"]: results[p["id"]][0] for p in personalities}
    usages = {p["id"]: results[p["id"]][1] for p in personalities}
    costs = {p["id"]: results[p["id"]][2] for p in personalities}
    total_in = sum(u.get("input", 0) for u in usages.values())
    total_out = sum(u.get("output", 0) for u in usages.values())
    total_cost = sum(costs.values())
    elapsed = time.monotonic() - t0
    print(
        f"  TOTAL: {ok} ok, {failed} failed · {elapsed:.0f}s wall · in={total_in} out={total_out} cost=${total_cost:.4f}",
        file=sys.stderr, flush=True,
    )
    return {
        "model_id": model["id"],
        "provider": provider,
        "display_name": model.get("display_name", model["id"]),
        "jokes": jokes,
        "usage": usages,
        "cost_usd": costs,
        "totals": {"input_tokens": total_in, "output_tokens": total_out, "cost_usd": total_cost},
    }


def _merge_results(existing: dict, new: dict) -> dict:
    """Merge a fresh generate_for_model() result into an existing jokes file."""
    if not existing:
        return new
    out = {**existing, "model_id": new["model_id"], "provider": new["provider"], "display_name": new["display_name"]}
    out["jokes"] = {**existing.get("jokes", {}), **new["jokes"]}
    out["usage"] = {**existing.get("usage", {}), **new["usage"]}
    out["cost_usd"] = {**existing.get("cost_usd", {}), **new["cost_usd"]}
    # Recompute totals across all jokes.
    in_tok = sum(u.get("input", 0) for u in out["usage"].values())
    out_tok = sum(u.get("output", 0) for u in out["usage"].values())
    cost = sum(out["cost_usd"].values())
    out["totals"] = {"input_tokens": in_tok, "output_tokens": out_tok, "cost_usd": cost}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="Model ID, e.g. claude-opus-4-7")
    ap.add_argument("--provider", required=True, choices=list(PROVIDERS.keys()))
    ap.add_argument("--display", default=None, help="Display name")
    ap.add_argument("--params", default="{}", help="JSON params override")
    ap.add_argument("--overwrite", action="store_true", help="Regenerate all personalities, replacing existing jokes")
    ap.add_argument("--fill", action="store_true", help="Only generate for personalities not yet in the jokes file")
    ap.add_argument("--set", dest="set_filter", default=None, help="Only generate for personalities in this set (e.g. human_baseline)")
    ap.add_argument("--workers", type=int, default=5, help="Parallel API calls")
    args = ap.parse_args()

    personalities = load_json(ROOT / "personalities.json")["personalities"]
    models = load_json(ROOT / "models.json")

    if args.set_filter:
        personalities = [p for p in personalities if p.get("set", "original") == args.set_filter]
        if not personalities:
            print(f"No personalities matched --set {args.set_filter!r}", file=sys.stderr)
            return 1

    existing = next((m for m in models["models"] if m["id"] == args.id), None)
    model = existing or {
        "id": args.id,
        "provider": args.provider,
        "display_name": args.display or args.id,
        "params": {},
    }
    if args.params:
        model = {**model, "params": {**model.get("params", {}), **json.loads(args.params)}}
    if args.display:
        model = {**model, "display_name": args.display}

    out_path = JOKES_DIR / f"{args.id}.json"
    existing_data: dict = {}
    if out_path.exists():
        existing_data = load_json(out_path)
        if not args.overwrite and not args.fill:
            print(f"{out_path} already exists. Use --overwrite to regenerate all, or --fill to add only missing personalities.", file=sys.stderr)
            return 1

    if args.fill and existing_data:
        have = {pid for pid, j in existing_data.get("jokes", {}).items() if j}
        missing = [p for p in personalities if p["id"] not in have]
        if not missing:
            print(f"Nothing to fill — all {len(personalities)} personalities already have jokes.", file=sys.stderr)
            return 0
        print(f"Filling {len(missing)} missing personalities (of {len(personalities)}) for {model['display_name']}…", file=sys.stderr)
        result = generate_for_model(model, missing, max_workers=args.workers)
        result = _merge_results(existing_data, result)
    else:
        print(f"Generating jokes for {model['display_name']} ({model['provider']})…", file=sys.stderr)
        result = generate_for_model(model, personalities, max_workers=args.workers)

    save_json(out_path, result)

    if existing is None:
        models["models"].append(model)
        save_json(ROOT / "models.json", models)

    print(f"Saved {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
