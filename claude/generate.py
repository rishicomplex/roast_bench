"""Generate one roast joke per personality for a given model, at max thinking."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
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


def call_anthropic(model_id: str, prompt: str, params: dict) -> str:
    import anthropic

    client = anthropic.Anthropic()
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
    response = client.messages.create(**kwargs)
    return "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()


def call_openai(model_id: str, prompt: str, params: dict) -> str:
    from openai import OpenAI

    client = OpenAI()
    response = client.responses.create(
        model=model_id,
        input=prompt,
        reasoning={"effort": params.get("reasoning_effort", "xhigh")},
        max_output_tokens=params.get("max_output_tokens", 50000),
        # No tools — explicit pure-LM generation
    )
    return response.output_text.strip()


def call_google(model_id: str, prompt: str, params: dict) -> str:
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
            max_output_tokens=params.get("max_output_tokens", 16000),
            # tools=[] (default) — no grounding / Google Search
        ),
    )
    return (response.text or "").strip()


PROVIDERS = {
    "anthropic": call_anthropic,
    "openai": call_openai,
    "google": call_google,
}


def generate_for_model(model: dict, personalities: list[dict]) -> dict:
    provider = model["provider"]
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    caller = PROVIDERS[provider]

    jokes: dict[str, str] = {}
    for p in personalities:
        prompt = build_prompt(p)
        print(f"  [{p['id']}] generating…", file=sys.stderr)
        try:
            joke = caller(model["id"], prompt, model.get("params", {}))
        except Exception as e:
            print(f"  [{p['id']}] ERROR: {e}", file=sys.stderr)
            joke = ""
        jokes[p["id"]] = joke
    return {
        "model_id": model["id"],
        "provider": provider,
        "display_name": model.get("display_name", model["id"]),
        "jokes": jokes,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="Model ID, e.g. claude-opus-4-7")
    ap.add_argument("--provider", required=True, choices=list(PROVIDERS.keys()))
    ap.add_argument("--display", default=None, help="Display name")
    ap.add_argument("--params", default="{}", help="JSON params override")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    personalities = load_json(ROOT / "personalities.json")["personalities"]
    models = load_json(ROOT / "models.json")

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
    if out_path.exists() and not args.overwrite:
        print(f"{out_path} already exists. Use --overwrite to regenerate.", file=sys.stderr)
        return 1

    print(f"Generating jokes for {model['display_name']} ({model['provider']})…", file=sys.stderr)
    result = generate_for_model(model, personalities)
    save_json(out_path, result)

    if existing is None:
        models["models"].append(model)
        save_json(ROOT / "models.json", models)

    print(f"Saved {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
