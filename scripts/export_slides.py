#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export a slideshow that a course platform renders as per-page images
(typical URL pattern: https://<host>/doc/<objectId>/thumb/<N>.png)
into a single PDF and/or PPTX file.

Works standalone - no agent framework required.

Usage:
    # From a full image URL (recommended - just copy one image link from DevTools):
    python export_slides.py "https://smartcourse-d.hust.edu.cn/doc/1c/<hash>/thumb/1.png"

    # Or from objectId + host:
    python export_slides.py 911f063fa250bae64bc37222cbed0b4f --host smartcourse-d.hust.edu.cn

    # Common options:
    -o / --output   output base name (default: "slides"; extension added automatically)
    -d / --dir      output directory (default: ./slides_export)
    --pdf-only      skip PPTX generation
    --no-pdf        skip PDF generation
    --limit N       only download the first N pages (debug / preview)
    --retries N     consecutive 404s before stopping page probing (default: 3)

Dependencies:
    pip install pillow img2pdf python-pptx

Notes:
    * Most platforms behind this pattern require a browser-like Referer /
      User-Agent header; sensible defaults are sent automatically.
    * Page count is auto-detected: pages are numbered 1..N and the script
      stops after N consecutive misses (default 3).
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

DEFAULT_HOST = "smartcourse-d.hust.edu.cn"
DEFAULT_REFERER = "https://smartcourse.hust.edu.cn/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Referer": DEFAULT_REFERER,
}

# --------------------------------------------------------------------------
# URL parsing
# --------------------------------------------------------------------------

def parse_target(target: str, host_override: str | None = None) -> tuple[str, str]:
    """Return (page_url_template, label) from a thumb URL or a bare objectId.

    page_url_template contains {n} where the 1-based page number goes.

    IMPORTANT: everything before `thumb/` is kept verbatim - platforms often
    include a routing/sharding path segment (e.g. /doc/<prefix>/<id>/) that
    is required; dropping it causes HTTP 500.
    """
    if target.lower().startswith("http"):
        m = re.match(r"^(https?://.+/)thumb/\d+\.png.*$", target)
        if not m:
            sys.exit(
                "ERROR: URL does not match the expected pattern\n"
                "  .../<anything>/thumb/<N>.png\n"
                "Copy the link of one slide image from your browser DevTools."
            )
        template = m.group(1) + "thumb/{n}.png"
        hexes = re.findall(r"([0-9a-fA-F]{16,40})", template)
        label = hexes[-1][:12] if hexes else "slides"
        return template, label

    # bare objectId -> needs --host and assumes the /doc/<id>/ layout
    if not re.fullmatch(r"[0-9a-fA-F]{16,40}", target.strip()):
        sys.exit(
            f"ERROR: '{target}' is neither a thumb URL nor a valid objectId."
        )
    host = host_override or DEFAULT_HOST
    template = f"https://{host}/doc/{target.strip()}/thumb/{{n}}.png"
    return template, target.strip()[:12]


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------

def fetch(url: str, timeout: int = 30, cookie: str | None = None) -> bytes:
    headers = dict(HEADERS)
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_with_retry(
    url: str,
    cookie: str | None = None,
    attempts: int = 5,
) -> bytes:
    """Retry transient server errors (5xx) with backoff.

    Some platforms intermittently answer 500 while their page-image cache
    is cold; the same URL usually succeeds seconds-to-minutes later.
    """
    delay = 2.0
    for i in range(attempts):
        try:
            return fetch(url, cookie=cookie)
        except HTTPError as exc:
            if exc.code == 404:
                raise  # definitive: page does not exist
            if i == attempts - 1:
                raise
            print(f"    transient HTTP {exc.code}, retrying in {delay:.0f}s ...")
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise RuntimeError("unreachable")


def download_pages(
    template: str,
    out_dir: Path,
    limit: int | None = None,
    max_misses: int = 3,
    cookie: str | None = None,
) -> list[Path]:
    """Download pages 1..N until `max_misses` consecutive 404s."""
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    misses = 0
    n = 1
    while True:
        if limit and n > limit:
            print(f"[limit] stopping at page limit {limit}")
            break
        path = out_dir / f"{n}.png"
        try:
            data = fetch_with_retry(template.format(n=n), cookie=cookie)
            if not data:
                raise ValueError("empty body")
            path.write_bytes(data)
            saved.append(path)
            misses = 0
            print(f"  page {n}: ok ({len(data) // 1024} KB)")
        except HTTPError as exc:
            if exc.code != 404:
                sys.exit(
                    f"ERROR: page {n} kept returning HTTP {exc.code} after "
                    "repeated retries.\n"
                    "The platform's image cache is probably cold for this deck.\n"
                    "Fix: open the course page in your browser (let the slides "
                    "load), then run this command again - already-downloaded "
                    "pages are kept."
                )
            misses += 1
            if path.exists():
                path.unlink()
            if saved and misses >= max_misses:
                print(f"  page {n}: 404 x{misses} -> stop, total {len(saved)} pages")
                break
            if not saved and misses >= max_misses:
                sys.exit(
                    "ERROR: the very first page returned 404.\n"
                    "The objectId looks invalid, or the resource needs a login "
                    "cookie (try --cookie 'NAME=VALUE; ...')."
                )
            print(f"  page {n}: 404 ({misses}/{max_misses})")
        except (URLError, ValueError, OSError) as exc:
            if not saved:
                sys.exit(
                    "ERROR: the very first page failed to download.\n"
                    f"Last error: {exc}\n"
                    "Check that the URL is correct and reachable; some servers "
                    "also require login cookies (--cookie 'NAME=VALUE; ...')."
                )
            print(f"  page {n}: network error ({exc})")
        n += 1
        time.sleep(0.15)  # be gentle to the server
    if not saved:
        sys.exit("ERROR: no pages downloaded.")
    return saved


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def make_pdf(pages: list[Path], out_path: Path) -> None:
    import img2pdf  # deferred so --no-pdf works without the dep

    with open(out_path, "wb") as fh:
        fh.write(img2pdf.convert([str(p) for p in pages]))
    print(f"PDF  written: {out_path}")


def make_pptx(pages: list[Path], out_path: Path) -> None:
    from PIL import Image
    from pptx import Presentation
    from pptx.util import Emu

    w_px, h_px = Image.open(pages[0]).size
    prs = Presentation()
    prs.slide_width = Emu(9144000)  # 10 inches
    prs.slide_height = Emu(int(9144000 * h_px / w_px))
    blank = prs.slide_layouts[6]
    for p in pages:
        slide = prs.slides.add_slide(blank)
        slide.shapes.add_picture(str(p), 0, 0, width=prs.slide_width, height=prs.slide_height)
    prs.save(str(out_path))
    print(f"PPTX written: {out_path}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Export a per-page-image slideshow into PDF and PPTX."
    )
    ap.add_argument("target", help="a thumb image URL or a bare objectId")
    ap.add_argument("--host", default=None, help=f"host when passing a bare objectId (default: {DEFAULT_HOST})")
    ap.add_argument("-o", "--output", default="slides", help="output base name (default: slides)")
    ap.add_argument("-d", "--dir", default="slides_export", help="output directory (default: ./slides_export)")
    ap.add_argument("--pdf-only", action="store_true", help="only generate the PDF")
    ap.add_argument("--no-pdf", action="store_true", help="skip PDF generation")
    ap.add_argument("--limit", type=int, default=None, help="download at most N pages")
    ap.add_argument("--retries", type=int, default=3, help="consecutive 404s before stopping (default: 3)")
    ap.add_argument("--cookie", default=None, help="extra Cookie header if the platform requires login")
    args = ap.parse_args()

    template, label = parse_target(args.target, args.host)
    base = Path(args.dir) / args.output
    img_dir = base.with_suffix("")  # e.g. out/第二章_药物的跨膜转运/
    print(f"Target template: {template}")
    print(f"Saving images to: {img_dir}")

    pages = download_pages(template, img_dir, limit=args.limit, max_misses=args.retries, cookie=args.cookie)

    if not args.no_pdf:
        make_pdf(pages, base.with_suffix(".pdf"))
    if not args.pdf_only:
        try:
            make_pptx(pages, base.with_suffix(".pptx"))
        except ImportError as exc:
            print(f"[warn] PPTX skipped (missing dependency: {exc.name}); "
                  "pip install pillow python-pptx to enable.")
    print(f"Done. {len(pages)} pages exported.")


if __name__ == "__main__":
    main()
