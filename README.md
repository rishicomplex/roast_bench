# RoastBench

A benchmark for how well frontier LLMs write roast jokes. Each model writes one roast per personality at maximum reasoning effort; I rank the jokes by hand and flag any that made me laugh out loud.

Two sets of personalities:

- **Set A — vs. human comedians.** LLMs go up against some of my favorite roast jokes from real Comedy Central roasts. Showcases performance against an expert human baseline.
- **Set B — held-out personalities.** 10 figures I find interesting who have never been the subject of a public roast, so the models can't lean on memorized material.

→ All jokes + the per-personality breakdown at **[rishimehta.xyz/roast_bench](https://rishimehta.xyz/roast_bench/)**.

**Avg %ile** — for each personality I order all models from best to worst. Each model's rank is converted to a percentile (top = 100, bottom = 0, linear). The displayed number is the mean of that model's percentiles across the set's personalities. **LOL rate** — fraction of the model's jokes (in this set) I flagged as making me laugh out loud during rating.

## vs. human comedians

<!-- leaderboard:human_baseline:start -->
| # | Model | Avg %ile | LOL rate |
|---:|---|---:|---:|
| 1 | Human comedians | 100.0 | 100% |
| 2 | Claude Fable 5 | 56.0 | 10% |
| 3 | Claude Opus 4.8 | 50.0 | 0% |
| 4 | Gemini 3.1 Pro | 42.0 | 0% |
| 5 | Claude Opus 4.7 | 28.0 | 0% |
| 6 | GPT-5.5 | 24.0 | 0% |
<!-- leaderboard:human_baseline:end -->

## 10 additional personalities

<!-- leaderboard:original:start -->
| # | Model | Avg %ile | LOL rate |
|---:|---|---:|---:|
| 1 | Claude Fable 5 | 75.0 | 0% |
| 2 | Claude Opus 4.8 | 62.5 | 10% |
| 3 | Gemini 3.1 Pro | 45.0 | 0% |
| 4 | GPT-5.5 | 35.0 | 0% |
| 5 | Claude Opus 4.7 | 32.5 | 10% |
<!-- leaderboard:original:end -->

## Add a model

```bash
python add_model.py --id <model-id> --provider {anthropic,openai,google}
```

Generates 10 jokes at the provider's top reasoning tier, opens the Flask rating UI at `localhost:5000` to drag the new jokes into the per-personality rankings, then regenerates `data/leaderboard.json`. Run `python build_showcase.py` to refresh the public site and this README.
