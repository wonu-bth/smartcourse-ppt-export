---
name: smartcourse-ppt-export
description: Export course-platform slideshows that are rendered as per-page images (URL pattern https://<host>/doc/<objectId>/thumb/<N>.png, e.g. HUST smartcourse / Chaoxing-style platforms) into a single PDF and PPTX file. Use when the user cannot download an embedded course PPT and wants the slides extracted, or asks to batch-download numbered page images and combine them.
---

# Smartcourse PPT Export

## When to use

- A course page embeds a PPT/slideshow that has no download button.
- DevTools (Network tab, filter: Img) shows the slides load as `1.png`, `2.png`, ... from a URL like `https://<host>/doc/<objectId>/thumb/1.png`.
- The user wants a combined PDF or PPTX of all pages.

## Quick start

Have the user provide **one** of the following (anything works):

1. The full URL of one slide image (easiest: DevTools → Network → right-click the `1.png` request → Copy → Copy link address).
2. Just the objectId (the hex string between `/doc/` and `/thumb/`).

Then run:

```bash
pip install pillow img2pdf python-pptx   # once

python scripts/export_slides.py "https://smartcourse-d.hust.edu.cn/doc/<objectId>/thumb/1.png" -o "课件名"
# or
python scripts/export_slides.py <objectId> --host smartcourse-d.hust.edu.cn -o "课件名"
```

The script automatically:

- probes pages 1..N (stops after 3 consecutive misses),
- downloads every page into `<输出目录>/<课件名>/`,
- assembles `课件名.pdf` and `课件名.pptx` (slides sized to the image aspect ratio).

## Agent workflow (interactive retrieval)

If the user cannot find the URL themselves, guide them through DevTools:

1. Open the course page, let the PPT load (or flip through a few pages to trigger lazy-loading).
2. F12 → Network tab → filter by **Img** → refresh the page.
3. Locate `1.png` in the request list → right-click → **Copy → Copy link address**.
4. Feed that URL to the script.

Do NOT transcribe URLs from screenshots - a single wrong hex character in the
objectId yields HTTP 500. Always have the user copy-paste the exact link
(right-click copy, or "Copy as cURL" and extract the URL).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| HTTP 500 on requests | Almost always a malformed path: the segment(s) between `/doc/` and `thumb/` must be kept VERBATIM (platforms use a routing/sharding prefix, e.g. `/doc/8d/<objectId>/thumb/1.png` - dropping `8d/` gives 500, not 404). Always have the user copy-paste the exact URL; never rebuild it by hand. The script still retries 5xx a few times in case of genuine transient errors. |
| HTTP 403 / login page returned | The resource needs the user's session. Ask the user to "Copy as cURL" from DevTools and pass its `Cookie` header via `--cookie 'NAME=VALUE; ...'` (never commit real cookies). |
| Stops at page 1 with 404 | objectId invalid - have the user re-copy the exact link. |
| PPTX step warns about missing deps | `pip install pillow python-pptx`. |

## Notes

- Keep the ENTIRE path before `thumb/` intact; the two-character prefix after
  `/doc/` is mandatory on some deployments even though it looks redundant.

- Output is image-based (that is how the platform serves it); text is not editable.
- For personal study use only - respect the course platform's terms and the lecturer's copyright.
