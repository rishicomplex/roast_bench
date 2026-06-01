"""Render a static HTML showcase of the benchmark into docs/index.html (GitHub Pages)."""
from __future__ import annotations

import html
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "index.html"
README = ROOT / "README.md"

MEDALS = ["🥇", "🥈", "🥉"]
PROVIDER_LABEL = {"anthropic": "Anthropic", "openai": "OpenAI", "google": "Google", "human": "Human"}
SET_LABELS = {
    "human_baseline": "Set A · vs. human comedians",
    "original": "Set B · held-out personalities",
}
SET_TAGS = {
    "human_baseline": "LLMs go up against some of my favorite roast jokes — verified quotes from real Comedy Central roasts (2005–2019).",
    "original": "10 personalities I find interesting who have never been the subject of a public roast, so the models can't fall back on memorized material; frontier LLMs only.",
}
SET_ORDER = ["human_baseline", "original"]

COL_TIPS = {
    "avg": (
        "For each personality I rank all models from best to worst. Each model's rank is "
        "converted to a percentile (top=100, bottom=0, linear). The displayed number is the "
        "mean of that model's percentiles across this set's personalities."
    ),
    "lol": (
        "Fraction of the model's jokes (in this set) that I flagged as making me laugh out "
        "loud during rating."
    ),
    "cost": (
        "Total USD spent generating this model's jokes for this set (input + output tokens × "
        "provider rate, including reasoning tokens)."
    ),
}


def info(key: str) -> str:
    """Render a tap/hover-friendly info trigger for a column header."""
    return (
        f"<button type='button' class='info' aria-label='What does this column mean?' "
        f'data-tip="{escape(COL_TIPS[key])}">ⓘ</button>'
    )


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


def discover_repo_url() -> str | None:
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]
    return url.removesuffix(".git") or None


def build() -> str:
    personalities = load(ROOT / "personalities.json")["personalities"]
    models = {m["id"]: m for m in load(ROOT / "models.json")["models"]}
    rankings = load(DATA / "rankings.json")
    jokes_by_model: dict[str, dict[str, str]] = {}
    sources_by_model: dict[str, dict[str, dict]] = {}
    for p in sorted((DATA / "jokes").glob("*.json")):
        d = load(p)
        jokes_by_model[d["model_id"]] = d.get("jokes", {})
        sources_by_model[d["model_id"]] = d.get("sources", {})

    pers_by_set: dict[str, list[dict]] = {}
    for p in personalities:
        pers_by_set.setdefault(p.get("set", "original"), []).append(p)
    set_order = [s for s in SET_ORDER if s in pers_by_set]
    for s in pers_by_set:
        if s not in set_order:
            set_order.append(s)

    # leaderboard rows (reuse scoring logic)
    from scoring import compute_leaderboard

    boards = compute_leaderboard()["sets"]
    all_rows = [r for rows in boards.values() for r in rows]
    total_cost = sum((r["cost_usd"] or 0) for r in all_rows)
    total_jokes = sum(1 for m in jokes_by_model for j in jokes_by_model[m].values() if j)
    total_models = len({r["model_id"] for r in all_rows})

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
    .pill.human{background:#eee7da; color:#5e4a1f}
    th .th-label{vertical-align:middle}
    .info{display:inline-flex; align-items:center; justify-content:center; width:22px; height:22px;
          margin-left:2px; padding:0; border:none; background:none; color:#b8b3aa; cursor:pointer;
          font:inherit; font-size:13px; line-height:1; vertical-align:middle; border-radius:50%;
          text-transform:none; letter-spacing:0; user-select:none; -webkit-tap-highlight-color:transparent;
          transition:color .12s ease, background .12s ease}
    .info:hover, .info:focus-visible, .info.active{color:var(--fg); outline:none}
    .info.active{background:#ece8df}
    .tip-bubble{position:fixed; left:0; top:0; z-index:60; max-width:min(280px, calc(100vw - 24px));
          background:#181818; color:#fafaf7; font-size:13px; line-height:1.45; font-weight:400;
          letter-spacing:0; text-transform:none; padding:10px 13px; border-radius:9px;
          box-shadow:0 8px 28px rgba(0,0,0,0.22); opacity:0; transform:translateY(-4px);
          transition:opacity .13s ease, transform .13s ease; pointer-events:none}
    .tip-bubble.show{opacity:1; transform:translateY(0)}
    .tip-arrow{position:absolute; width:10px; height:10px; background:#181818; transform:rotate(45deg)}
    .tip-arrow.up{top:-5px}
    .tip-arrow.down{bottom:-5px}
    .repo-link{display:inline-flex; align-items:center; gap:6px; padding:6px 12px; border:1px solid var(--rule);
               border-radius:6px; font-size:13px; font-weight:500; color:var(--fg); text-decoration:none;
               background:var(--paper)}
    .repo-link:hover{border-color:var(--muted)}
    header .title-row{display:flex; align-items:baseline; justify-content:space-between; gap:16px; flex-wrap:wrap}
    header .title-row h1{margin:0}
    .set-tag{color:var(--muted); font-size:14px; margin:0 0 20px; max-width:640px}
    .source{margin-top:8px; font-size:13px; color:var(--muted)}
    .source strong{color:var(--fg)}
    .source .unverified{background:#f5e8c8; color:#8a6a14; padding:1px 6px; border-radius:3px;
                        font-size:10px; margin-left:6px; letter-spacing:0.03em; text-transform:uppercase}
    .tabs{display:flex; gap:4px; border-bottom:1px solid var(--rule); margin:32px 0 24px; position:sticky; top:0;
          background:var(--bg); z-index:5; padding-top:4px}
    .tab{background:none; border:none; padding:14px 18px; cursor:pointer; font:inherit; font-weight:600;
         font-size:15px; color:var(--muted); border-bottom:2px solid transparent; margin-bottom:-1px;
         letter-spacing:-0.005em}
    .tab:hover{color:var(--fg)}
    .tab.active{color:var(--fg); border-bottom-color:var(--fg)}
    .tab-panel{display:none}
    .tab-panel.active{display:block}
    section.lead h2{margin-top:0}
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

    def render_card(i: int, mid: str, pid: str, lol_set: set[str]) -> str:
        joke = jokes_by_model.get(mid, {}).get(pid, "")
        m = models.get(mid, {"display_name": mid, "provider": ""})
        rank_cls = f"r{i+1}" if i < 3 else ""
        medal = MEDALS[i] if i < len(MEDALS) else "·"
        lol_badge = "<span class='lol'>★ LOL</span>" if mid in lol_set else ""
        provider = m.get("provider", "")
        src = sources_by_model.get(mid, {}).get(pid)
        source_block = ""
        if src:
            unv = "" if src.get("verified") else "<span class='unverified'>unverified</span>"
            roast = f" at the {escape(src['roast'])}" if src.get("roast") else ""
            source_block = (
                f"<div class='source'>— <strong>{escape(src.get('roaster',''))}</strong>{roast}{unv}</div>"
            )
        return (
            f"<div class='card {rank_cls}'>"
            f"<div class='rank-cell'><div class='medal'>{medal}</div>"
            f"<div class='rank-n'>#{i+1}</div></div>"
            f"<div>"
            f"<div class='joke'>{escape(joke)}</div>"
            f"{source_block}"
            f"<div class='byline'>"
            f"<span class='model'>{escape(m.get('display_name', mid))}</span>"
            f"<span class='pill {provider}'>{escape(PROVIDER_LABEL.get(provider, provider))}</span>"
            f"{lol_badge}"
            f"</div></div></div>"
        )

    # Per-set leaderboard tables + personality sections
    set_sections = []
    for set_name in set_order:
        rows = boards.get(set_name, [])
        if not rows and not pers_by_set.get(set_name):
            continue
        lb_rows = []
        for i, r in enumerate(rows, 1):
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
        lb_table = (
            "<table class='lb'>"
            "<thead><tr>"
            "<th>#</th>"
            "<th>Model</th>"
            f"<th><span class='th-label'>Avg %ile</span>{info('avg')}</th>"
            f"<th><span class='th-label'>LOL rate</span>{info('lol')}</th>"
            f"<th><span class='th-label'>Gen cost</span>{info('cost')}</th>"
            "</tr></thead>"
            f"<tbody>{''.join(lb_rows)}</tbody></table>"
        )

        pers_sections = []
        toc = []
        for p in pers_by_set.get(set_name, []):
            pid = p["id"]
            order = rankings["rankings"].get(pid, [])
            lol_set = set(rankings["lol_flags"].get(pid, []))
            if not order:
                continue
            toc.append(f"<a href='#{escape(pid)}'>{escape(p['name'])}</a>")
            cards = [render_card(i, mid, pid, lol_set) for i, mid in enumerate(order)]
            pers_sections.append(
                f"<div class='pers' id='{escape(pid)}'>"
                f"<h3>{escape(p['name'])}</h3>"
                f"<p class='desc'>{escape(p.get('description', ''))}</p>"
                + "".join(cards)
                + "</div>"
            )

        set_sections.append(
            f"<div class='tab-panel' id='set-{escape(set_name)}'>"
            f"<section class='lead'>"
            f"<p class='set-tag'>{escape(SET_TAGS.get(set_name, ''))}</p>"
            f"{lb_table}"
            f"<h2>Roasts by personality</h2>"
            f"<nav class='toc'>{' · '.join(toc)}</nav>"
            f"{''.join(pers_sections)}"
            f"</section>"
            f"</div>"
        )

    tab_buttons = "".join(
        f'<button class="tab" data-target="set-{escape(s)}" role="tab">{escape(SET_LABELS.get(s, s))}</button>'
        for s in set_order
    )
    repo_url = discover_repo_url()
    source_link = (
        f'Source: <a href="{escape(repo_url)}">{escape(repo_url.replace("https://", ""))}</a>'
        if repo_url else 'Source on GitHub (link not yet configured)'
    )
    repo_button = (
        f'<a class="repo-link" href="{escape(repo_url)}" target="_blank" rel="noopener">'
        f'<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">'
        f'<path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 '
        f'0-.19-.01-.82-.01-1.49-2 .37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 '
        f'1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 '
        f'0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.42 7.42 0 0 1 2-.27c.68 0 1.36.09 '
        f'2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 '
        f'3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>'
        f'</svg> View on GitHub</a>'
        if repo_url else ''
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
  <div class="title-row">
    <h1>RoastBench</h1>
    {repo_button}
  </div>
  <p class="tag">A benchmark for how well frontier LLMs write roast jokes. Each model writes one roast per personality at maximum reasoning effort; I rank the jokes by hand and flag any that made me laugh out loud.</p>
  <p class="meta">{total_models} models · {len(personalities)} personalities · {total_jokes} jokes · total LLM cost {fmt_money(total_cost)}</p>
</header>

<nav class="tabs" role="tablist">
{tab_buttons}
</nav>

{''.join(set_sections)}

<footer>
<p><strong>Methodology.</strong> Each LLM is invoked at its provider's maximum reasoning tier (Anthropic <code>effort:max</code>, OpenAI <code>reasoning:xhigh</code>, Google <code>thinking_level:high</code>), with no tools or web access. The single prompt is: <em>"Write one roast joke about {{name}}. It will be your entry into a competitive roast battle judged by humans."</em> A human rater drags each joke into a per-personality ranked list (best at top); the headline number is the average percentile across personalities. LOL rate is a separate flag for jokes that made the rater laugh out loud.</p>
<p>The <strong>Human baseline</strong> set is seeded with quotes from real Comedy Central roasts (2005–2019). Each card credits the original comedian and event; jokes labelled "unverified" are paraphrases that need a verbatim transcript.</p>
<p>{source_link}</p>
</footer>
</div>
<script>
(function() {{
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.tab-panel');
  function activate(id) {{
    tabs.forEach(t => t.classList.toggle('active', t.dataset.target === id));
    panels.forEach(p => p.classList.toggle('active', p.id === id));
  }}
  tabs.forEach(t => t.addEventListener('click', () => {{
    activate(t.dataset.target);
    history.replaceState(null, '', '#' + t.dataset.target);
  }}));
  const initial = (location.hash || '').replace('#', '') || (tabs[0] && tabs[0].dataset.target);
  activate(initial);
}})();

// Tap/hover info tooltips (works on touch devices, unlike native title=)
(function() {{
  const triggers = document.querySelectorAll('.info');
  if (!triggers.length) return;
  const canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  const bubble = document.createElement('div');
  bubble.className = 'tip-bubble';
  bubble.setAttribute('role', 'tooltip');
  const arrow = document.createElement('span');
  arrow.className = 'tip-arrow';
  const text = document.createElement('span');
  bubble.append(arrow, text);
  document.body.appendChild(bubble);
  let current = null;

  function place(el) {{
    const pad = 12;
    const r = el.getBoundingClientRect();
    const bw = bubble.offsetWidth, bh = bubble.offsetHeight;
    const cx = r.left + r.width / 2;
    let left = Math.max(pad, Math.min(cx - bw / 2, window.innerWidth - bw - pad));
    let top = r.bottom + 9, below = true;
    if (top + bh > window.innerHeight - pad && r.top - bh - 9 > pad) {{
      top = r.top - bh - 9; below = false;
    }}
    bubble.style.left = left + 'px';
    bubble.style.top = top + 'px';
    let ax = Math.max(9, Math.min(cx - left - 5, bw - 19));
    arrow.style.left = ax + 'px';
    arrow.classList.toggle('up', below);
    arrow.classList.toggle('down', !below);
  }}
  function show(el) {{
    text.textContent = el.getAttribute('data-tip') || '';
    current = el;
    el.classList.add('active');
    bubble.classList.add('show');
    place(el);
  }}
  function hide() {{
    if (current) current.classList.remove('active');
    current = null;
    bubble.classList.remove('show');
  }}
  function toggle(el) {{ current === el ? hide() : (hide(), show(el)); }}

  triggers.forEach(el => {{
    el.addEventListener('click', e => {{ e.stopPropagation(); toggle(el); }});
    if (canHover) {{
      el.addEventListener('mouseenter', () => show(el));
      el.addEventListener('mouseleave', hide);
    }}
  }});
  document.addEventListener('click', hide);
  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') hide(); }});
  window.addEventListener('resize', hide);
  window.addEventListener('scroll', hide, true);
}})();
</script>
</body>
</html>
"""


def _markdown_table(rows: list[dict]) -> str:
    if not rows:
        return "_(no ratings yet)_"
    lines = ["| # | Model | Avg %ile | LOL rate |", "|---:|---|---:|---:|"]
    for i, r in enumerate(rows, 1):
        pct = f"{r['avg_percentile']:.1f}" if r["avg_percentile"] is not None else "—"
        lol = f"{r['lol_rate']:.0f}%" if r["lol_rate"] is not None else "—"
        lines.append(f"| {i} | {r['display_name']} | {pct} | {lol} |")
    return "\n".join(lines)


def _replace_marker(text: str, marker: str, body: str) -> tuple[str, bool]:
    start = f"<!-- {marker}:start -->"
    end = f"<!-- {marker}:end -->"
    if start not in text or end not in text:
        return text, False
    before, _, rest = text.partition(start)
    _, _, after = rest.partition(end)
    new = f"{before}{start}\n{body}\n{end}{after}"
    return new, new != text


def update_readme() -> bool:
    if not README.exists():
        return False
    text = README.read_text()
    from scoring import compute_leaderboard
    sets = compute_leaderboard()["sets"]
    changed = False
    for marker, set_name in [("leaderboard:human_baseline", "human_baseline"),
                              ("leaderboard:original", "original")]:
        text, did = _replace_marker(text, marker, _markdown_table(sets.get(set_name, [])))
        changed = changed or did
    # Back-compat: if there's still a plain "leaderboard" block, fill it with human_baseline.
    text, did = _replace_marker(text, "leaderboard", _markdown_table(sets.get("human_baseline", [])))
    changed = changed or did
    if changed:
        README.write_text(text)
    return changed


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build())
    print(f"Wrote {OUT}")
    if update_readme():
        print(f"Updated {README}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    main()
