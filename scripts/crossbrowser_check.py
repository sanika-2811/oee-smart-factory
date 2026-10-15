"""Load every page in Chromium, Firefox and WebKit; fail on console errors, missing live data or horizontal overflow.

    python -m playwright install firefox webkit      # once
    python scripts/crossbrowser_check.py             # needs backend :8000 + frontend :5173
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

APP = "http://127.0.0.1:5173"
ROUTES = ["/overview", "/machines", "/machines/CNC-01", "/alerts", "/maintenance", "/reports", "/control"]


def main() -> int:
    bad = 0
    with sync_playwright() as p:
        for name in ("chromium", "firefox", "webkit"):
            try:
                browser = getattr(p, name).launch()
            except Exception as exc:
                print(f"[{name}] SKIPPED - not installed ({str(exc).splitlines()[0][:80]})")
                continue
            for label, w, h in (("desktop", 1440, 900), ("phone", 390, 844)):
                ctx = browser.new_context(viewport={"width": w, "height": h})
                pg = ctx.new_page()
                errors: list[str] = []
                pg.on("console", lambda m, e=errors: e.append(m.text[:140]) if m.type == "error" else None)
                pg.on("pageerror", lambda x, e=errors: e.append(str(x)[:140]))
                for r in ROUTES:
                    pg.goto(f"{APP}/#{r}")
                    pg.wait_for_timeout(2200)
                    live = pg.locator(".conn.live").count() > 0
                    overflow = pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2")
                    charts = pg.locator("canvas").count()
                    status = "ok" if live and not overflow else "PROBLEM"
                    if status != "ok":
                        bad += 1
                    print(f"[{name}/{label}] {r:18s} live={live} overflowX={overflow} canvases={charts} -> {status}")
                if errors:
                    bad += 1
                    print(f"[{name}/{label}] console errors: {errors[:3]}")
                ctx.close()
            browser.close()
    print("RESULT:", "all clean" if not bad else f"{bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
