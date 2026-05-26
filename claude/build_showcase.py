"""Render a static HTML showcase of the benchmark into docs/index.html (GitHub Pages)."""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).parent
PROJECT = ROOT.parent
DATA = ROOT / "data"
OUT = PROJECT / "docs" / "index.html"

MEDALS = ["🥇", "🥈", "🥉"]
PROVIDER_LABEL = {"anthropic": "Anthropic", "openai": "OpenAI", "google": "Google"}


def load(p: Path) -> dict:
    return json.loads(p.read_text())


def fmt_money(x: float | None) -> str:
    if x is None:
        return "—"
    if x >= 1:
        return f"${x:,.2f}"
    return f"${x:.3f}"


def escape(s: str) -> str:
    return html.escape(s, quote=True)


def build() -> str:
    personalities = load(ROOT / "personalities.json")["personalities"]
    models = {m["id"]: m for m in load(ROOT / "models.json")["models"]}
    rankings = load(DATA / "rankings.json")
    jokes_by_model: dict[str, dict[str, str]] = {}
    for p in (DATA / "jokes").glob("*.json"):
        d = load(p)
        jokes_by_model[d["model_id"]] = d.get("jokes", {})

    # leaderboard rows (reuse scoring logic)
    from scoring import compute_leaderboard

    board = compute_leaderboard()["leaderboard"]
    total_cost = sum((r["cost_usd"] or 0) for r in board)
    total_jokes = sum(1 for m in jokes_by_model for j in jokes_by_model[m].values() if j)

    css = """
    :root { --bg:#fafaf7; --fg:#181818; --muted:#7a7670; --rule:#e4e0d8; --paper:#fff;
            --gold:#c8a93a; --silver:#9a9a9a; --bronze:#a06535;
            --anthropic:#c8782a; --openai:#10a37f; --google:#4285f4;
            --lol:#e64a19; }
    *{box-sizing:border-box} html,body{margin:0;padding:0;background:var(--bg);color:var(--fg);
      font-family:-apple-system,BlinkMacSystemFont,"Inter","Segoe UI",system-ui,sans-serif;
      font-size:16px; line-height:1.55; -webkit-font-smoothing:antialiased}
    a{color:inherit}
    .wrap{max-width:780px; margin:0 auto; padding:64px 24px 96px}
    header h1{font-size:54px; letter-spacing:-0.03em; margin:0 0 8px; font-weight:800}
    header .tag{color:var(--muted); font-size:17px; margin:0 0 24px; max-width:620px}
    header .meta{color:var(--muted); font-size:13px; letter-spacing:0.03em; text-transform:uppercase}
    h2{font-size:22px; font-weight:700; letter-spacing:-0.01em; margin:64px 0 16px}
    section.lead{margin-top:48px}
    table.lb{width:100%; border-collapse:collapse; background:var(--paper); border:1px solid var(--rule); border-radius:10px; overflow:hidden}
    table.lb th, table.lb td{padding:12px 16px; text-align:left; border-bottom:1px solid var(--rule); font-size:14px}
    table.lb tr:last-child td{border-bottom:none}
    table.lb th{color:var(--muted); font-weight:600; font-size:12px; letter-spacing:0.06em; text-transform:uppercase; background:#f3f0e9}
    table.lb td.num{font-variant-numeric:tabular-nums}
    table.lb tr:first-child td .rank{font-weight:700}
    .pill{display:inline-block; padding:2px 8px; border-radius:99px; font-size:11px; font-weight:600; letter-spacing:0.04em}
    .pill.anthropic{background:#fbeede; color:var(--anthropic)}
    .pill.openai{background:#dff5ec; color:var(--openai)}
    .pill.google{background:#e3edfd; color:var(--google)}
    .pers{margin:48px 0 64px; padding-top:24px; border-top:1px solid var(--rule)}
    .pers h3{font-size:28px; margin:0 0 6px; letter-spacing:-0.02em}
    .pers .desc{color:var(--muted); font-size:15px; margin:0 0 24px; max-width:640px}
    .card{background:var(--paper); border:1px solid var(--rule); border-left:4px solid var(--rule);
          border-radius:8px; padding:18px 22px; margin:10px 0; display:grid;
          grid-template-columns:auto 1fr; gap:18px; align-items:start}
    .card.r1{border-left-color:var(--gold)}
    .card.r2{border-left-color:var(--silver)}
    .card.r3{border-left-color:var(--bronze)}
    .rank-cell{display:flex; flex-direction:column; align-items:center; min-width:48px; padding-top:2px}
    .rank-cell .medal{font-size:24px; line-height:1}
    .rank-cell .rank-n{font-size:11px; color:var(--muted); letter-spacing:0.06em; margin-top:4px; font-variant-numeric:tabular-nums}
    .joke{font-family:"Charter","Iowan Old Style","Georgia",serif; font-size:18px; line-height:1.5; color:var(--fg); white-space:pre-wrap}
    .byline{margin-top:10px; font-size:13px; color:var(--muted); display:flex; gap:10px; align-items:center}
    .byline .model{font-weight:600; color:var(--fg)}
    .lol{display:inline-flex; align-items:center; gap:4px; background:#fdecdc; color:var(--lol);
         padding:2px 8px; border-radius:99px; font-size:11px; font-weight:700; letter-spacing:0.04em}
    nav.toc{display:flex; flex-wrap:wrap; gap:6px 10px; margin:8px 0 0; font-size:13px}
    nav.toc a{color:var(--muted); text-decoration:none; border-bottom:1px dotted #ccc}
    nav.toc a:hover{color:var(--fg)}
    footer{margin-top:80px; padding-top:24px; border-top:1px solid var(--rule); color:var(--muted); font-size:13px}
    footer a{color:var(--fg); text-decoration:underline; text-decoration-color:var(--rule)}
    code{font-family:ui-monospace,"SF Mono",Menlo,monospace; background:#efece4; padding:1px 5px; border-radius:4px; font-size:0.92em}
    """

    # leaderboard rows
    lb_rows = []
    for i, r in enumerate(board, 1):
        pct = f"{r['avg_percentile']:.1f}" if r["avg_percentile"] is not None else "—"
        lol = f"{r['lol_rate']:.0f}%" if r["lol_rate"] is not None else "—"
        cost = fmt_money(r["cost_usd"])
        provider = r["provider"]
        lb_rows.append(
            f"<tr><td class='num'><span class='rank'>{i}</span></td>"
            f"<td><strong>{escape(r['display_name'])}</strong>"
            f" <span class='pill {provider}'>{escape(PROVIDER_LABEL.get(provider, provider))}</span></td>"
            f"<td class='num'>{pct}</td>"
            f"<td class='num'>{lol}</td>"
            f"<td class='num'>{cost}</td></tr>"
        )

    # personality sections
    pers_sections = []
    toc = []
    for p in personalities:
        pid = p["id"]
        order = rankings["rankings"].get(pid, [])
        lol_set = set(rankings["lol_flags"].get(pid, []))
        if not order:
            continue
        toc.append(f"<a href='#{escape(pid)}'>{escape(p['name'])}</a>")
        cards = []
        for i, mid in enumerate(order):
            joke = jokes_by_model.get(mid, {}).get(pid, "")
            m = models.get(mid, {"display_name": mid, "provider": ""})
            rank_cls = f"r{i+1}" if i < 3 else ""
            medal = MEDALS[i] if i < len(MEDALS) else "·"
            lol_badge = "<span class='lol'>★ LOL</span>" if mid in lol_set else ""
            provider = m.get("provider", "")
            cards.append(
                f"<div class='card {rank_cls}'>"
                f"<div class='rank-cell'><div class='medal'>{medal}</div>"
                f"<div class='rank-n'>#{i+1}</div></div>"
                f"<div>"
                f"<div class='joke'>{escape(joke)}</div>"
                f"<div class='byline'>"
                f"<span class='model'>{escape(m.get('display_name', mid))}</span>"
                f"<span class='pill {provider}'>{escape(PROVIDER_LABEL.get(provider, provider))}</span>"
                f"{lol_badge}"
                f"</div></div></div>"
            )
        pers_sections.append(
            f"<div class='pers' id='{escape(pid)}'>"
            f"<h3>{escape(p['name'])}</h3>"
            f"<p class='desc'>{escape(p.get('description', ''))}</p>"
            + "".join(cards)
            + "</div>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RoastBench — an LLM benchmark for roast jokes</title>
<style>{css}</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>RoastBench</h1>
  <p class="tag">An LLM benchmark for roast jokes. Each frontier model writes one roast for each of 10 personalities, at maximum reasoning effort. A human rater drags the jokes into a ranked list per personality and flags any that made them laugh.</p>
  <p class="meta">{len(board)} models · {len(personalities)} personalities · {total_jokes} jokes · total cost {fmt_money(total_cost)}</p>
</header>

<section class="lead">
  <h2>Leaderboard</h2>
  <table class="lb">
    <thead><tr><th>#</th><th>Model</th><th>Avg %ile</th><th>LOL rate</th><th>Gen cost</th></tr></thead>
    <tbody>{''.join(lb_rows)}</tbody>
  </table>
</section>

<section>
  <h2>Roasts by personality</h2>
  <nav class="toc">{' · '.join(toc)}</nav>
  {''.join(pers_sections)}
</section>

<footer>
<p><strong>Methodology.</strong> Each model is invoked at its provider's maximum reasoning tier (Anthropic <code>effort:max</code>, OpenAI <code>reasoning:xhigh</code>, Google <code>thinking_level:high</code>), with no tools or web access. The single prompt is: <em>"Write one roast joke about {{name}}. It will be your entry into a competitive roast battle judged by humans."</em> A human rater then drags each joke into a per-personality ranked list (best at top); the headline number is the average percentile across personalities. LOL rate is a separate flag for jokes that made the rater laugh out loud.</p>
<p>Source: <a href="https://github.com/">github.com/…/roast_bench</a></p>
</footer>
</div>
</body>
</html>
"""


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build())
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    main()
