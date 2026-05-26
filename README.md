# RoastBench

An LLM benchmark for roast jokes. Each frontier model writes one roast for each of 10 personalities at maximum reasoning effort; a human rater drags new jokes into a per-personality ranked list and flags any that made them laugh out loud. The headline number is average percentile across personalities; LOL rate is a separate column.

See the [showcase page](https://rishicomplex.github.io/roast_bench/) for the current leaderboard and all 30 jokes.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # then fill in your keys
```

You need keys for whichever providers you want to test: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`.

## Adding a model

```bash
python add_model.py --id claude-opus-4-7 --provider anthropic --display "Claude Opus 4.7"
```

This generates 10 jokes (one per personality) at maximum reasoning effort, then launches the Flask rating UI at `http://localhost:5000`. Drag the new model's jokes into the ranked list for each personality. The leaderboard regenerates automatically.

Pre-configured frontier models live in [`models.json`](models.json):

| Provider | Model | Effort flag |
|---|---|---|
| Anthropic | `claude-opus-4-7` | `output_config.effort: max` |
| OpenAI | `gpt-5.5` | `reasoning.effort: xhigh` |
| Google | `gemini-3.1-pro-preview` | `thinking_level: high` |

All calls pass no tools and no web access. Token budget capped at 64k combined (thinking + output).

## Rebuilding the showcase

After rating, regenerate the static page used by GitHub Pages:

```bash
python build_showcase.py
```

This writes `docs/index.html`.

## Scoring

Each personality has a per-model ranking (best at top). A model's score on a personality is its percentile within that ranking (top = 100, bottom = 0). The headline number is the average percentile across personalities. LOL rate is the fraction of the model's jokes the rater flagged.

## Layout

```
personalities.json     # the 10 roast targets
models.json            # registered models + per-provider params + prices
generate.py            # provider API wrappers, max thinking, parallel
scoring.py             # percentile + LOL rate + leaderboard regen
server.py              # Flask rating UI
add_model.py           # generate → rate → regen pipeline
build_showcase.py      # static HTML for docs/index.html
data/
  jokes/<model>.json   # generated jokes per model
  rankings.json        # per-personality ranking + LOL flags
  leaderboard.json     # derived
docs/index.html        # GitHub Pages output
```
