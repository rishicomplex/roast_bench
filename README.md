# RoastBench

A two-part comparison. The **first table** pits frontier LLMs against some of my favorite roast jokes from human comedians (verified quotes from real Comedy Central roasts). The **second table** is a separate set of 10 additional personalities where the LLMs are scored only against each other. For every personality, each model writes one roast at maximum reasoning effort; I rank the jokes by hand and flag any that made me laugh.

→ All jokes + the per-personality breakdown at **[rishimehta.xyz/roast_bench](https://rishimehta.xyz/roast_bench/)**.

## vs. human comedians

<!-- leaderboard:human_baseline:start -->
| # | Model | Avg %ile | LOL rate |
|---:|---|---:|---:|
| 1 | Human (Comedy Central) | 100.0 | 100% |
| 2 | Gemini 3.1 Pro | 43.3 | 0% |
| 3 | Claude Opus 4.7 | 33.3 | 0% |
| 4 | GPT-5.5 | 23.3 | 0% |
<!-- leaderboard:human_baseline:end -->

## 10 additional personalities

<!-- leaderboard:original:start -->
| # | Model | Avg %ile | LOL rate |
|---:|---|---:|---:|
| 1 | Gemini 3.1 Pro | 55.0 | 0% |
| 2 | Claude Opus 4.7 | 50.0 | 10% |
| 3 | GPT-5.5 | 45.0 | 0% |
<!-- leaderboard:original:end -->

## Add a model

```bash
python add_model.py --id <model-id> --provider {anthropic,openai,google}
```

Generates 10 jokes at the provider's top reasoning tier, opens the Flask rating UI at `localhost:5000` to drag the new jokes into the per-personality rankings, then regenerates `data/leaderboard.json`. Run `python build_showcase.py` to refresh the public site and this README.
