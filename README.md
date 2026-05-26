# RoastBench

An LLM benchmark for roast jokes. Each model writes one roast for each of 10 personalities; a human rater drags new jokes into a ranked list per personality and flags any that made them laugh out loud. Models are scored by average percentile across personalities plus a separate LOL rate.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r claude/requirements.txt

export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...
export GEMINI_API_KEY=...
```

## Adding a model

```bash
python claude/add_model.py --id claude-opus-4-7 --provider anthropic --display "Claude Opus 4.7"
```

This generates 10 jokes (one per personality) with maximal thinking enabled, then launches the rating UI at `http://localhost:5000`. After you've placed the new model's jokes for all 10 personalities, the leaderboard is regenerated automatically.

## Scoring

For each personality the user maintains an ordered ranking of models (best first). A model's score on a personality is its percentile within that personality (top model = 100, bottom = 0). The headline number is the average percentile across all personalities. LOL rate (fraction of the model's jokes flagged) is reported as a separate column.

## Layout

```
claude/
  personalities.json     # the 10 roast targets
  models.json            # registered models
  generate.py            # provider API wrappers, max thinking
  scoring.py             # percentile + LOL rate + leaderboard regen
  server.py              # Flask rating UI
  add_model.py           # generate → rate → regen pipeline
  data/
    jokes/<model>.json   # generated jokes per model
    rankings.json        # per-personality ranking + LOL flags
    leaderboard.json     # derived
```
