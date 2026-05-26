# RoastBench

Each frontier model writes one roast joke for each of 10 personalities at maximum reasoning effort. I rank the jokes per personality and flag any that made me laugh out loud. The headline score is average percentile across personalities; LOL rate is a separate column.

→ All 30 jokes at **[rishimehta.xyz/roast_bench](https://rishimehta.xyz/roast_bench/)**.

## Leaderboard

<!-- leaderboard:start -->
| # | Model | Avg %ile | LOL rate |
|---:|---|---:|---:|
| 1 | Gemini 3.1 Pro | 55.0 | 0% |
| 2 | Claude Opus 4.7 | 50.0 | 10% |
| 3 | GPT-5.5 | 45.0 | 0% |
<!-- leaderboard:end -->

## Add a model

```bash
python add_model.py --id <model-id> --provider {anthropic,openai,google}
```

Generates 10 jokes at the provider's top reasoning tier, opens the Flask rating UI at `localhost:5000` to drag the new jokes into the per-personality rankings, then regenerates `data/leaderboard.json`. Run `python build_showcase.py` to refresh the public site and this README.
