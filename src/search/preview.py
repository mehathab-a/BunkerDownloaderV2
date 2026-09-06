"""Render search results into a viewable HTML gallery and a URL list.

The preview mirrors the "view before you download" workflow of index sites: each result
is shown as a thumbnail card (title, file count, source link) so a user can visually
confirm which albums to retrieve before feeding them to the downloader.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def collect_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten items from a single-provider or aggregated ('all') payload."""
    if "items" in payload:
        return list(payload.get("items", []))

    items: list[dict[str, Any]] = []
    for provider_result in payload.get("results", []):
        items.extend(provider_result.get("items", []))
    return items


def _card_html(index: int, item: dict[str, Any]) -> str:
    """Render one result card."""
    title = html.escape(str(item.get("title") or "(untitled)"))
    url = html.escape(str(item.get("url") or ""))
    thumb = html.escape(str(item.get("thumbnail_url") or ""))
    provider = html.escape(str(item.get("provider") or ""))
    host = html.escape(str(item.get("host") or ""))
    file_count = item.get("file_count")
    if file_count is None:
        file_count = (item.get("provider_fields") or {}).get("file_count")
    media_type = html.escape(str(item.get("media_type") or ""))

    meta_bits = [bit for bit in (
        f"{file_count} files" if file_count is not None else "",
        media_type,
        provider or host,
    ) if bit]
    meta = html.escape(" • ".join(meta_bits))

    thumb_html = (
        f'<img loading="lazy" src="{thumb}" alt="" '
        f'onerror="this.style.display=\'none\'">'
        if thumb
        else '<div class="noimg">no preview</div>'
    )

    return f"""
    <a class="card" href="{url}" target="_blank" rel="noopener noreferrer">
      <div class="thumb">{thumb_html}<span class="idx">#{index}</span></div>
      <div class="body">
        <div class="title">{title}</div>
        <div class="meta">{meta}</div>
        <div class="url">{url}</div>
      </div>
    </a>"""


def render_html(payload: dict[str, Any], out_path: str, *, query: str) -> int:
    """Write an HTML preview gallery. Returns the number of rendered items."""
    items = collect_items(payload)
    cards = "\n".join(
        _card_html(index, item) for index, item in enumerate(items, start=1)
    )
    safe_query = html.escape(query)

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Preview: {safe_query}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font-family: system-ui, sans-serif; margin: 0; background:#0e0f13; color:#e6e6e6; }}
  header {{ padding: 18px 24px; border-bottom: 1px solid #23252d; position: sticky; top:0; background:#0e0f13; }}
  header h1 {{ font-size: 16px; margin: 0; font-weight: 600; }}
  header p {{ margin: 6px 0 0; font-size: 12px; color:#9aa0aa; }}
  .grid {{ display:grid; gap:16px; padding:24px;
           grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }}
  .card {{ background:#161821; border:1px solid #23252d; border-radius:12px;
           overflow:hidden; text-decoration:none; color:inherit; transition:border-color .15s; }}
  .card:hover {{ border-color:#4c8bf5; }}
  .thumb {{ position:relative; aspect-ratio:4/3; background:#0b0c10; overflow:hidden; }}
  .thumb img {{ width:100%; height:100%; object-fit:cover; }}
  .noimg {{ display:flex; align-items:center; justify-content:center; height:100%;
            color:#5b616e; font-size:12px; }}
  .idx {{ position:absolute; top:8px; left:8px; background:rgba(0,0,0,.6);
          padding:2px 8px; border-radius:20px; font-size:11px; }}
  .body {{ padding:12px; }}
  .title {{ font-size:13px; font-weight:600; line-height:1.35;
            display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
  .meta {{ margin-top:6px; font-size:11px; color:#9aa0aa; }}
  .url {{ margin-top:6px; font-size:10px; color:#5b616e; word-break:break-all; }}
</style>
</head>
<body>
<header>
  <h1>Preview for &ldquo;{safe_query}&rdquo;</h1>
  <p>{len(items)} result(s). Click a card to open the source album. Only download content you own or have rights to.</p>
</header>
<div class="grid">
{cards}
</div>
</body>
</html>
"""
    Path(out_path).write_text(document, encoding="utf-8")
    return len(items)


def write_urls(payload: dict[str, Any], out_path: str) -> int:
    """Write one album URL per line. Returns the number of URLs written."""
    items = collect_items(payload)
    urls = [str(item.get("url")) for item in items if item.get("url")]
    Path(out_path).write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    return len(urls)
