#!/usr/bin/env python3
"""Render an "OpenStack Production Investigation Memo" card (PNG) from a JSON spec.

Usage:
    python3 render_memo.py 01.json 01-memo.png

The spec is a small JSON document (see 01.json). The card is 1080x1350 px
(LinkedIn portrait 4:5), rendered at 2x for sharpness. Text is rendered by a
browser engine, so commands and field names are reproduced exactly.

Requires: playwright (python) with Chromium, IBM Plex Mono / IBM Plex Sans
installed (falls back to DejaVu if absent).
"""
import html
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8">
<style>
  :root {
    --bg: #1b2430; --fg: #e8e6e1; --muted: #9aa3ad; --accent: #e0a458;
    --rule: #2f3a48; --mono: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace;
    --sans: 'IBM Plex Sans', 'DejaVu Sans', sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { width: 1080px; height: 1350px; background: var(--bg); color: var(--fg);
         font-family: var(--sans); padding: 52px 60px 44px 60px; display: flex; flex-direction: column; }
  header { display: flex; justify-content: space-between; align-items: flex-start; }
  header .title { font-size: 21px; letter-spacing: 0.14em; font-weight: 600; color: var(--fg); }
  header .sub { font-size: 17px; color: var(--muted); margin-top: 8px; letter-spacing: 0.02em; }
  header .num { font-family: var(--mono); font-size: 44px; font-weight: 600; color: var(--accent); line-height: 1; }
  hr { border: 0; border-top: 1px solid var(--rule); margin: 22px 0 18px 0; }
  section h2 { font-size: 13px; letter-spacing: 0.18em; font-weight: 600; color: var(--muted); margin-bottom: 9px; }
  .p { font-size: 19px; line-height: 1.35; }
  .cmd { font-family: var(--mono); font-size: 21px; font-weight: 500; padding-right: 24px; }
  .cmdrow { display: flex; justify-content: space-between; align-items: center; }
  .tag { font-family: var(--mono); font-size: 13px; letter-spacing: 0.14em; color: var(--accent);
         border: 1px solid var(--accent); padding: 4px 10px; border-radius: 3px; }
  .mono { font-family: var(--mono); font-size: 18px; line-height: 1.55; white-space: pre-wrap; }
  .muted { color: var(--muted); }
  .accent { color: var(--accent); }
  table.fields { border-collapse: collapse; width: 100%; }
  table.fields td { font-size: 18px; line-height: 1.5; padding: 1px 0; vertical-align: top; }
  table.fields td.k { font-family: var(--mono); width: 335px; font-weight: 500; }
  table.fields td.v { color: var(--fg); }
  table.fields.assume td.k { width: 230px; }
  table.fields.assume td.ne { width: 44px; color: var(--accent); font-family: var(--mono); font-weight: 600; }
  .path { font-family: var(--mono); font-size: 17.5px; line-height: 1.6; }
  .path .arrow { color: var(--accent); }
  footer { margin-top: auto; display: flex; justify-content: space-between; font-size: 14px; color: var(--muted); }
  footer .series { letter-spacing: 0.04em; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; column-gap: 40px; }
</style></head>
<body>
<header>
  <div>
    <div class="title">OPENSTACK PRODUCTION INVESTIGATION MEMO</div>
    <div class="sub">One Command, One Investigation</div>
  </div>
  <div class="num">#{{num}}</div>
</header>
<hr>
<section>
  <h2>PROBLEM</h2>
  <div class="p">{{problem}}</div>
</section>
<hr>
<section>
  <h2>PRIMARY COMMAND</h2>
  <div class="cmdrow"><div class="cmd">{{command}}</div><div class="tag">{{safety}}</div></div>
</section>
<hr>
<section>
  <h2>SOURCE OF TRUTH</h2>
  <div class="p" style="margin-bottom:8px">{{truth}}</div>
  <div class="mono">{{diagram}}</div>
</section>
<hr>
<section>
  <h2>WHAT TO READ</h2>
  <table class="fields">{{fields}}</table>
</section>
<hr>
<section>
  <h2>DO NOT ASSUME</h2>
  <table class="fields assume">{{assume}}</table>
</section>
<hr>
<section>
  <h2>INVESTIGATION PATH</h2>
  <div class="path">{{path}}</div>
</section>
<hr>
<section>
  <h2>NEXT CHECK</h2>
  <div class="mono">{{next}}</div>
  <div class="mono muted" style="margin-top:8px">{{notyet}}</div>
</section>
<footer>
  <div class="series">{{footer_left}}</div>
  <div>{{footer_right}}</div>
</footer>
</body></html>
"""


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def build(spec: dict) -> str:
    fields = "".join(
        f'<tr><td class="k">{esc(k)}</td><td class="v">{esc(v)}</td></tr>'
        for k, v in spec["fields"]
    )
    assume = "".join(
        f'<tr><td class="k" style="font-family:var(--mono);font-weight:500">{esc(k)}</td>'
        f'<td class="ne">≠</td><td class="v">{esc(v)}</td></tr>'
        for k, v in spec["do_not_assume"]
    )
    path = ' <span class="arrow">→</span> '.join(esc(p) for p in spec["path"])
    diagram_lines = []
    for line in spec["diagram"]:
        if line.startswith("~"):
            diagram_lines.append(f'<span class="muted">{esc(line[1:])}</span>')
        else:
            diagram_lines.append(esc(line).replace("→", '<span class="accent">→</span>'))
    out = TEMPLATE
    repl = {
        "num": esc(spec["episode"]),
        "problem": esc(spec["problem"]),
        "command": esc(spec["command"]),
        "safety": esc(spec["safety"]),
        "truth": esc(spec["source_of_truth"]),
        "diagram": "\n".join(diagram_lines),
        "fields": fields,
        "assume": assume,
        "path": path,
        "next": "\n".join(esc(c) for c in spec["next_check"]),
        "notyet": esc(spec.get("not_yet", "")),
        "footer_left": esc(spec.get("footer_left", "One Command, One Investigation")),
        "footer_right": esc(spec.get("footer_right", "")),
    }
    for k, v in repl.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def main() -> None:
    spec = json.loads(Path(sys.argv[1]).read_text())
    out_png = Path(sys.argv[2])
    page_html = build(spec)
    out_png.with_suffix(".html").write_text(page_html)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=2)
        page.set_content(page_html)
        page.wait_for_timeout(300)
        overflow = page.evaluate("document.body.scrollHeight")
        page.screenshot(path=str(out_png), full_page=False)
        browser.close()
    if overflow > 1350:
        print(f"WARNING: content height {overflow}px exceeds 1350px; reduce content or font sizes")
    print(f"wrote {out_png}")


if __name__ == "__main__":
    main()
