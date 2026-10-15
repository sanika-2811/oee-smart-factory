"""Accessibility audit with axe-core (WCAG 2 A/AA) over every page, dark and light theme, desktop and phone.

    python scripts/a11y_audit.py          # needs backend :8000 + frontend :5173 running
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
AXE = ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"
APP = "http://127.0.0.1:5173"
ROUTES = ["/overview", "/machines", "/machines/CNC-01", "/alerts", "/maintenance", "/reports", "/control"]


def main() -> int:
    total = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("dark", "light"):
            for name, w, h in (("desktop", 1440, 900), ("phone", 390, 844)):
                ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=theme)
                pg = ctx.new_page()
                for r in ROUTES:
                    pg.goto(f"{APP}/#{r}")
                    pg.wait_for_timeout(2500)
                    pg.add_script_tag(path=str(AXE))
                    res = pg.evaluate("axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa']}})")
                    for v in res["violations"]:
                        total += len(v["nodes"])
                        print(f"[{theme}/{name}] {r}: {v['id']} ({v['impact']}) x{len(v['nodes'])} - {v['help']}")
                        for n in v["nodes"][:2]:
                            print("      ", n["target"], "|", (n.get("any") or n.get("all") or n.get("none") or [{}])[0].get("message", "")[:120])
                ctx.close()
        browser.close()
    print("TOTAL violating nodes:", total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
