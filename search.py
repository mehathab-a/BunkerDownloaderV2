"""CLI entrypoint for the provider-based search returner."""

from __future__ import annotations

import json
from argparse import ArgumentParser, Namespace

from src.search.preview import render_html, write_urls
from src.search.search_returner import SearchRequest, parse_provider_params, search, search_all


def parse_args() -> Namespace:
    """Parse CLI arguments into a Namespace."""
    parser = ArgumentParser(description="Search Bunkr-adjacent and similar providers.")
    parser.add_argument(
        "--provider",
        type=str,
        required=True,
        help="Provider name (e.g. balbums, turbo, gelbooru, e621, unsplash) or 'all'.",
    )
    parser.add_argument("--query", type=str, required=True, help="Search query text.")
    parser.add_argument("--page", type=int, default=1, help="Page number (default: 1).")
    parser.add_argument("--page-size", type=int, default=20, help="Page size (default: 20).")
    parser.add_argument("--sort", type=str, default=None, help="Provider sort value.")
    parser.add_argument(
        "--exact-mode",
        type=str,
        default="none",
        choices=("none", "phrase", "token_all", "token_exact"),
        help="Post-filter mode for exact result matching.",
    )
    parser.add_argument(
        "--exact-field",
        action="append",
        default=None,
        help="Field considered for exact match (repeatable, default: title,tags).",
    )
    parser.add_argument(
        "--provider-param",
        action="append",
        default=None,
        help="Provider specific KEY=VALUE passthrough parameter (repeatable).",
    )
    parser.add_argument(
        "--html",
        type=str,
        default=None,
        metavar="PATH",
        help="Write a viewable HTML preview gallery of the results to PATH.",
    )
    parser.add_argument(
        "--urls-out",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Write one album/result URL per line to PATH (URLs.txt format) "
            "for batch downloading after review."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the JSON dump on stdout (useful with --html/--urls-out).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable the in-memory search response cache.",
    )
    parser.add_argument(
        "--providers",
        type=str,
        default=None,
        metavar="LIST",
        help="Comma-separated provider subset when --provider all (default: all Tier A+B).",
    )
    return parser.parse_args()


def build_request(parsed: Namespace) -> SearchRequest:
    """Build a SearchRequest from parsed CLI arguments."""
    exact_fields = tuple(parsed.exact_field or ("title", "tags"))
    provider_params = parse_provider_params(parsed.provider_param)
    providers_filter = None
    if parsed.providers:
        providers_filter = tuple(
            name.strip().lower()
            for name in parsed.providers.split(",")
            if name.strip()
        )
    return SearchRequest(
        provider=parsed.provider.lower().strip(),
        query=parsed.query.strip(),
        page=max(parsed.page, 1),
        page_size=max(parsed.page_size, 1),
        sort=parsed.sort,
        exact_mode=parsed.exact_mode,
        exact_fields=exact_fields,
        provider_params=provider_params,
        use_cache=not parsed.no_cache,
        providers_filter=providers_filter,
    )


def main() -> None:
    """Run the search command and optionally emit preview/URL artifacts."""
    parsed = parse_args()
    request = build_request(parsed)
    payload = search_all(request) if request.provider == "all" else search(request)

    if not parsed.quiet:
        print(json.dumps(payload, indent=2, ensure_ascii=True))

    if parsed.html:
        count = render_html(payload, parsed.html, query=request.query)
        print(f"[preview] Wrote {count} result(s) to {parsed.html}")

    if parsed.urls_out:
        count = write_urls(payload, parsed.urls_out)
        print(f"[urls] Wrote {count} URL(s) to {parsed.urls_out}")


if __name__ == "__main__":
    main()
