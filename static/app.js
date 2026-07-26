// Client-side data layer for the hosted rating app (index.html / rate.html).
// Ports the data assembly from server.py and the leaderboard math from
// scoring.py. All static data comes from the repo's committed JSON (served as
// Worker assets); rankings come from /api/rankings (Workers KV).

const SET_LABELS = { original: "Other personalities", human_baseline: "Human baseline" };
const SET_TAGS = {
  original: "Original benchmark set — frontier models only.",
  human_baseline: "10 Comedy Central roast targets (2005–2019); each set includes a Human entry with verified quotes.",
};
const SET_ORDER = ["human_baseline", "original"];

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.json();
}

// Returns {personalities, models, rankings, jokes, sources, totals}
//   models:  model_id -> model dict
//   jokes:   personality_id -> model_id -> joke text
//   sources: personality_id -> model_id -> source dict
//   totals:  model_id -> {cost_usd, input_tokens, output_tokens}
async function loadState() {
  const [pers, modelsFile, rankings] = await Promise.all([
    fetchJSON("/personalities.json"),
    fetchJSON("/models.json"),
    fetchJSON("/api/rankings"),
  ]);
  const models = {};
  for (const m of modelsFile.models) models[m.id] = m;

  const jokes = {}, sources = {}, totals = {};
  await Promise.all(Object.keys(models).map(async (mid) => {
    let d;
    try { d = await fetchJSON(`/data/jokes/${mid}.json`); } catch { return; }
    totals[mid] = d.totals || {};
    for (const [pid, joke] of Object.entries(d.jokes || {})) {
      if (!joke) continue;
      (jokes[pid] = jokes[pid] || {})[mid] = joke;
    }
    for (const [pid, src] of Object.entries(d.sources || {})) {
      if (!src) continue;
      (sources[pid] = sources[pid] || {})[mid] = src;
    }
  }));

  return { personalities: pers.personalities, models, rankings, jokes, sources, totals };
}

function personalitiesBySet(personalities) {
  const out = {};
  for (const p of personalities) (out[p.set || "original"] = out[p.set || "original"] || []).push(p);
  return out;
}

function orderedSets(bySet) {
  const order = SET_ORDER.filter(s => s in bySet);
  for (const s of Object.keys(bySet)) if (!order.includes(s)) order.push(s);
  return order;
}

function percentile(rank, n) {
  if (n < 2) return null;
  return (n - 1 - rank) / (n - 1) * 100.0;
}

// Port of scoring._compute_set — leaderboard rows for one personality set.
function computeSet(setPers, state) {
  const pids = new Set(setPers.map(p => p.id));
  const perModel = {};
  for (const [mid, m] of Object.entries(state.models)) {
    const hasJoke = Object.entries(state.jokes).some(([pid, byModel]) => pids.has(pid) && mid in byModel);
    if (!hasJoke) continue;
    const totals = state.totals[mid] || {};
    perModel[mid] = {
      model_id: mid,
      display_name: m.display_name || mid,
      provider: m.provider,
      percentiles: {},
      jokes_rated: 0,
      lol_count: 0,
      cost_usd: totals.cost_usd ?? null,
      input_tokens: totals.input_tokens ?? null,
      output_tokens: totals.output_tokens ?? null,
    };
  }

  for (const p of setPers) {
    const order = state.rankings.rankings[p.id] || [];
    const lol = new Set(state.rankings.lol_flags[p.id] || []);
    order.forEach((mid, i) => {
      if (!(mid in perModel)) return;
      perModel[mid].percentiles[p.id] = percentile(i, order.length);
      perModel[mid].jokes_rated += 1;
      if (lol.has(mid)) perModel[mid].lol_count += 1;
    });
  }

  const rows = Object.values(perModel).map(e => {
    const pcts = Object.values(e.percentiles).filter(v => v !== null);
    return {
      ...e,
      avg_percentile: pcts.length ? pcts.reduce((a, b) => a + b, 0) / pcts.length : null,
      lol_rate: e.jokes_rated ? e.lol_count / e.jokes_rated * 100.0 : null,
      personalities_in_set: setPers.length,
    };
  });
  rows.sort((a, b) => (a.avg_percentile === null) - (b.avg_percentile === null)
    || (b.avg_percentile || 0) - (a.avg_percentile || 0));
  return rows;
}

// Port of server._next_unranked — next personality (in personalities.json
// order) where this model has a joke but isn't in the ranking yet.
function nextUnranked(state, modelId, skip = null) {
  for (const p of state.personalities) {
    if (p.id === skip) continue;
    if (!(modelId in (state.jokes[p.id] || {}))) continue;
    if (!(state.rankings.rankings[p.id] || []).includes(modelId)) return p.id;
  }
  return null;
}

function unrankedIn(state, modelId, setPers) {
  return setPers.filter(p =>
    modelId in (state.jokes[p.id] || {}) &&
    !(state.rankings.rankings[p.id] || []).includes(modelId)
  ).map(p => p.id);
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
