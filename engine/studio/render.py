"""STATION 2 — Studio: render the on-brand social image.

Reads:  status == drafted   (uses hook, body)
Writes: image_path          (status unchanged; brand_qc advances it next)

Flow:
  1. On first run, download Fraunces + Inter WOFF2 from Google Fonts, base64-encode
     them, and cache the resulting @font-face CSS in renders/fonts/fonts.css.
     Subsequent runs load from cache — fully offline after first use.
  2. Render post.html.j2 with Jinja2, inline brand.css + @font-face into <style>.
  3. Inject a direct font-family override so headless Chromium can't fall back
     past the embedded fonts (CSS variable resolution is bypassed).
  4. Screenshot via Playwright at 1080x1350 @2x device scale.
"""

import base64
import os
import re
import tempfile
import urllib.request
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from db import get_post, update_post

REPO_ROOT     = Path(__file__).resolve().parents[2]
TEMPLATE_DIR  = REPO_ROOT / "templates" / "social"
TEMPLATE_FILE = "post.html.j2"
CSS_PATH      = REPO_ROOT / "client-data" / "lumen-skin" / "brand.css"
RENDERS_DIR   = REPO_ROOT / "renders"
FONTS_DIR     = RENDERS_DIR / "fonts"   # gitignored via renders/

GF_API_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Playfair+Display:wght@600"
    "&family=Work+Sans:wght@400"
    "&display=swap"
)
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Hardcoded override — applied after all other styles so headless Chromium
# paints the correct typefaces regardless of CSS variable resolution.
FONT_OVERRIDE = (
    "<style>"
    ".hook,.brand{font-family:'Playfair Display',Georgia,serif!important;}"
    ".post,.body{font-family:'Work Sans','Inter',system-ui,sans-serif!important;}"
    "</style>"
)


def _ensure_fonts() -> str:
    """Download Fraunces + Inter WOFF2 once; return @font-face CSS with base64 data URIs.

    Base64 embedding avoids all file:// cross-origin restrictions in headless Chromium.
    Cached at renders/fonts/fonts.css — reused on every subsequent render.
    """
    css_cache = FONTS_DIR / "fonts.css"
    if css_cache.exists():
        return css_cache.read_text()

    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    print("  [studio.render] downloading fonts (first run only)…")

    req = urllib.request.Request(GF_API_URL, headers={"User-Agent": CHROME_UA})
    with urllib.request.urlopen(req) as r:
        gf_css = r.read().decode()

    def _embed(m: re.Match) -> str:
        url = m.group(1).strip("'\"")
        fname = url.split("/")[-1].split("?")[0] + ".woff2"
        local = FONTS_DIR / fname
        if not local.exists():
            with urllib.request.urlopen(url) as r:
                local.write_bytes(r.read())
        data = base64.b64encode(local.read_bytes()).decode()
        return f"url('data:font/woff2;base64,{data}')"

    embedded_css = re.sub(r"url\(([^)]+)\)", _embed, gf_css)
    css_cache.write_text(embedded_css)
    return embedded_css


def run(post_id: str, auto_approve: bool = False) -> None:
    post = get_post(post_id)
    RENDERS_DIR.mkdir(exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    html = env.get_template(TEMPLATE_FILE).render(
        hook=post["hook"] or "",
        body=post["body"] or "",
    )

    # Inline @font-face (base64) + brand CSS variables in place of the <link> tag
    font_css  = _ensure_fonts()
    brand_css = CSS_PATH.read_text()
    html = re.sub(
        r"<link[^>]*brand\.css[^>]*/>",
        f"<style>\n{font_css}\n{brand_css}\n</style>",
        html,
    )

    # Append font override before </head> — bypasses CSS variable fallback issues
    html = html.replace("</head>", f"{FONT_OVERRIDE}\n</head>")

    image_path = str(RENDERS_DIR / f"{post_id}.png")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html)
        tmp_html = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1080, "height": 1350},
                device_scale_factor=2,
            )
            page.goto(f"file://{tmp_html}")
            page.wait_for_load_state("networkidle")
            page.evaluate("document.fonts.ready")
            page.screenshot(path=image_path, full_page=False, scale="device")
            browser.close()
    finally:
        os.unlink(tmp_html)

    update_post(post_id, image_path=image_path)
    print(f"  [studio.render] saved → {image_path}")
