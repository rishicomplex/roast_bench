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
| 2 | Claude Opus 5.5 | 69.1 | 0% |
| 3 | GPT-6 Astra | 59.1 | 0% |
| 4 | Claude Fable 5.1 | 58.2 | 0% |
| 5 | Claude Opus 5 | 56.4 | 20% |
| 6 | Claude Fable 5 | 52.7 | 10% |
| 7 | Claude Opus 4.8 | 49.1 | 0% |
| 8 | Gemini 3.1 Pro | 39.1 | 0% |
| 9 | GPT-5.6 Sol | 34.5 | 0% |
| 10 | Kimi K3 | 30.9 | 0% |
| 11 | Claude Opus 4.7 | 28.2 | 0% |
| 12 | GPT-5.5 | 22.7 | 0% |
<!-- leaderboard:human_baseline:end -->

## 10 additional personalities

<!-- leaderboard:original:start -->
| # | Model | Avg %ile | LOL rate |
|---:|---|---:|---:|
| 1 | Claude Opus 5.5 | 81.0 | 0% |
| 2 | Claude Fable 5 | 63.0 | 0% |
| 3 | Claude Fable 5.1 | 60.0 | 0% |
| 4 | Claude Opus 4.8 | 54.0 | 10% |
| 5 | GPT-5.6 Sol | 54.0 | 10% |
| 6 | Claude Opus 5 | 48.0 | 0% |
| 7 | Gemini 3.1 Pro | 43.0 | 0% |
| 8 | GPT-6 Astra | 39.0 | 0% |
| 9 | Kimi K3 | 37.0 | 0% |
| 10 | GPT-5.5 | 36.0 | 0% |
| 11 | Claude Opus 4.7 | 35.0 | 10% |
<!-- leaderboard:original:end -->

## Add a model

```bash
python add_model.py --id <model-id> --provider {anthropic,openai,google,moonshot}
```

Generates 10 jokes at the provider's top reasoning tier, opens the Flask rating UI at `localhost:5000` to drag the new jokes into the per-personality rankings, then regenerates `data/leaderboard.json`. Run `python build_showcase.py` to refresh the public site and this README.

## Hosted rating app (rate from anywhere)

The rating UI is also hosted privately at **https://roast-bench.rishimehta.workers.dev** (Google sign-in, allowlist), so a new model can be generated + rated end-to-end from the Claude app without a laptop. Same setup as the `korean` project:

- `src/index.js` — Cloudflare Worker: auth gate + static assets + a tiny rankings API.
- `index.html` / `rate.html` + `static/app.js` — client-side port of the Flask templates (leaderboard math from `scoring.py` included); they read the committed JSON (`models.json`, `personalities.json`, `data/jokes/*.json`) as assets.
- Rankings are the one mutable piece: stored in Workers KV (seeded from `data/rankings.json` on first use).

### Remote flow

1. Generate jokes for a new model: `python generate.py --id <model-id> --provider <provider>` (registers it in `models.json`, no UI). Commit, push.
2. Deploy: push to `main` auto-deploys if the Cloudflare GitHub build integration is connected (dashboard → Workers → `roast-bench` → Settings → Build); otherwise `npm run deploy`.
3. Rate on the phone at the URL above.
4. `scripts/pull_rankings.sh` — pulls KV rankings back into `data/rankings.json`, regenerates the leaderboard + showcase. Commit the result.

Note: after rating on the hosted app, KV is the source of truth for rankings until `pull_rankings.sh` lands them in the repo — don't rate locally and remotely at the same time. To push repo rankings back up to KV (e.g. after rating in the local Flask app): `npx wrangler kv key put rankings --binding RANKINGS --remote --path data/rankings.json`.

### Remote (cloud) session environment — one-time setup

So the whole loop runs from a phone, the claude.ai Code environment for this repo needs:

- **Environment variables** (`KEY=value`, no quotes): `ROAST_ANTHROPIC_API_KEY` (plus `OPENAI_API_KEY` / `GEMINI_API_KEY` / `MOONSHOT_API_KEY` when generating for those providers), and `CLOUDFLARE_API_TOKEN` — a token with *Account → Workers KV Storage → Read* so `pull_rankings.sh` can fetch ratings without wrangler login.

  The Anthropic key uses the `ROAST_` prefix because the cloud session reserves `ANTHROPIC_API_KEY` for the harness's own auth and its UI won't accept that name. `generate.py` reads either. Locally (`.env`), plain `ANTHROPIC_API_KEY` still works.
- **Network access = Custom**, "include default list" checked, allowed domains: `api.anthropic.com`, `api.openai.com`, `generativelanguage.googleapis.com`, `api.moonshot.ai`, `api.cloudflare.com`. A provider missing from this list fails as `APIConnectionError` at the proxy, which looks like an outage rather than a config gap — add the domain before blaming the provider.
- **Setup script**: `pip install -r requirements.txt`.

Deploys need no credentials remotely — pushing to `main` triggers the Cloudflare GitHub build.

One-time pieces already done: KV namespace, `TOKEN_SECRET` secret, worker deploy. The Google OAuth client is shared with `korean`; the workers.dev origin must be in its authorized JavaScript origins.
