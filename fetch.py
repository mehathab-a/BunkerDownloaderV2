"""Unified multi-host fetch CLI.

Resolves album/file URLs from PixelDrain, GoFile, Cyberdrop, and Saint, then downloads
them with the shared chunked/resume transfer engine.

Bunkr URLs should still use downloader.py / main.py (they have a richer album pipeline).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from src.config import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_CONNECTIONS,
    DEFAULT_READ_TIMEOUT,
    DOWNLOAD_HEADERS,
    MAX_RETRIES,
    apply_config_file_defaults,
)
from src.downloaders.download_utils import (
    detect_range_support,
    save_file_with_chunks,
    save_file_with_resume,
    should_use_parallel_download,
)
from src.enums import CompletedReason, FailedReason, SkippedReason
from src.hosts import resolve_url, supported_hosts
from src.hosts.base import ResolvedItem
from src.managers.live_manager import initialize_managers
from src.managers.rate_limiter import RateLimiter
from src.misc.file_utils import create_download_directory, truncate_filename
from src.misc.general_utils import check_python_version, clear_terminal
from src.models import DownloadConfig


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the multi-host fetcher."""
    parser = argparse.ArgumentParser(
        description=(
            "Download from PixelDrain / GoFile / Cyberdrop / Saint URLs. "
            f"Supported: {', '.join(supported_hosts())}."
        ),
    )
    parser.add_argument("url", type=str, help="Album or file URL to resolve and download.")
    parser.add_argument("--custom-path", type=str, default=None)
    parser.add_argument("--no-download-folder", action="store_true", default=None)
    parser.add_argument("--disable-ui", action="store_true", default=None)
    parser.add_argument("--disable-disk-check", action="store_true", default=None)
    parser.add_argument("--connections", type=int, default=None)
    parser.add_argument("--max-retries", type=int, default=None)
    parser.add_argument("--rate-limit", type=float, default=None, metavar="KB/S")
    parser.add_argument("--connect-timeout", type=float, default=None)
    parser.add_argument("--read-timeout", type=float, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Resolve and list items without downloading.",
    )
    parser.add_argument("--config", type=str, default=None, metavar="PATH")
    args = parser.parse_args()
    return apply_config_file_defaults(args)


def _timeouts(args: argparse.Namespace) -> tuple[float, float]:
    connect = float(getattr(args, "connect_timeout", None) or DEFAULT_CONNECT_TIMEOUT)
    read = float(getattr(args, "read_timeout", None) or DEFAULT_READ_TIMEOUT)
    return connect, read


def _download_one(
    item: ResolvedItem,
    download_path: Path,
    live_manager,
    args: argparse.Namespace,
    rate_limiter: RateLimiter | None,
) -> bool:
    """Download one resolved item. Returns True on permanent failure."""
    filename = truncate_filename(item.filename)
    final_path = download_path / filename
    task = live_manager.add_task()

    if final_path.exists():
        live_manager.update_log(
            event="Skipped download",
            details=f"{filename} has already been downloaded.",
        )
        live_manager.update_task(task, completed=100, visible=False)
        live_manager.update_summary(SkippedReason.ALREADY_DOWNLOADED)
        return False

    headers = {**DOWNLOAD_HEADERS, **(item.headers or {})}
    request_timeout = _timeouts(args)
    num_connections = int(getattr(args, "connections", None) or DEFAULT_CONNECTIONS)
    max_retries = int(getattr(args, "max_retries", None) or MAX_RETRIES)

    for attempt in range(max_retries):
        supports_range, content_length = detect_range_support(
            item.download_url,
            headers,
            request_timeout,
        )
        if content_length <= 0 and item.size > 0:
            content_length = item.size

        if should_use_parallel_download(
            content_length,
            num_connections,
            supports_range=supports_range,
        ):
            failed = save_file_with_chunks(
                item.download_url,
                str(final_path),
                task,
                live_manager,
                DownloadConfig(
                    content_length=content_length,
                    num_connections=num_connections,
                    headers=headers,
                    request_timeout=request_timeout,
                    rate_limiter=rate_limiter,
                ),
            )
        else:
            failed = save_file_with_resume(
                item.download_url,
                str(final_path),
                task,
                live_manager,
                headers=headers,
                request_timeout=request_timeout,
                rate_limiter=rate_limiter,
            )

        if not failed:
            live_manager.update_summary(CompletedReason.DOWNLOAD_SUCCESS)
            live_manager.update_task(task, completed=100, visible=False)
            return False

        live_manager.update_log(
            event="Retrying download",
            details=f"Retry {attempt + 1}/{max_retries} for {filename}",
        )

    live_manager.update_log(
        event="Download failed",
        details=f"Failed to download {filename}.",
    )
    live_manager.update_summary(FailedReason.MAX_RETRIES_REACHED)
    live_manager.update_task(task, completed=100, visible=False)
    return True


def main() -> None:
    """Resolve and download a multi-host URL."""
    clear_terminal()
    check_python_version()
    args = parse_args()
    console = Console()

    try:
        host_name, items = resolve_url(args.url)
    except ValueError as err:
        console.print(f"[red]{err}[/red]")
        sys.exit(2)

    if not items:
        console.print(f"[yellow]No downloadable items resolved from {args.url}[/yellow]")
        sys.exit(1)

    if args.dry_run:
        console.print(f"[cyan]Host:[/cyan] {host_name}  [cyan]Items:[/cyan] {len(items)}")
        for index, item in enumerate(items, start=1):
            size = f"{item.size} B" if item.size > 0 else "unknown"
            console.print(f"  {index}. {item.filename}  ({size})")
            console.print(f"     {item.download_url}")
        return

    download_path = Path(
        create_download_directory(
            directory_name=None,
            custom_path=args.custom_path,
            no_download_folder=bool(args.no_download_folder),
        ),
    )
    rate_limiter = RateLimiter(
        args.rate_limit * 1024 if getattr(args, "rate_limit", None) else None,
    )
    live_manager = initialize_managers(disable_ui=bool(args.disable_ui))

    failed = 0
    with live_manager.live:
        live_manager.add_overall_task(host_name, num_tasks=len(items))
        live_manager.update_log(
            event="Resolved host",
            details=f"{host_name}: {len(items)} item(s) from {args.url}",
        )
        for item in items:
            if _download_one(item, download_path, live_manager, args, rate_limiter):
                failed += 1
        live_manager.stop()

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
