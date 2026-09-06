"""Module that provides tools to manage the downloading of individual files from Bunkr.

It supports retry mechanisms, progress tracking, and error handling for a robust
download experience.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from pathlib import Path
from typing import TYPE_CHECKING

from src.config import DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT, DOWNLOAD_HEADERS
from src.crawlers.crawler_utils import refresh_item_download_link
from src.enums import CompletedReason, FailedReason, SkippedReason
from src.misc.bunkr_utils import subdomain_is_offline
from src.misc.file_utils import (
    matches_ignore_list,
    matches_include_list,
    truncate_filename,
    write_on_session_log,
)
from src.models import DownloadConfig, DownloadInfo, RetryConfig, SessionInfo

from .download_utils import (
    detect_range_support,
    save_file_with_resume,
    save_file_with_chunks,
    should_use_parallel_download,
)

if TYPE_CHECKING:
    from src.managers.live_manager import LiveManager

_BACKOFF_FACTOR = 1.5


class MediaDownloader:
    """Manage the downloading of individual files from Bunkr URLs."""

    def __init__(
        self,
        session_info: SessionInfo,
        download_info: DownloadInfo,
        live_manager: LiveManager,
        retry_config: RetryConfig,
    ) -> None:
        """Initialize the MediaDownloader instance."""
        self.session_info = session_info
        self.download_info = download_info
        self.live_manager = live_manager
        self.retry_config = retry_config

    def attempt_download(self, final_path: str) -> bool:
        """Attempt to download the file, using parallel chunks when supported.

        For sufficiently large files, uses parallel byte-range requests when the server
        supports them. Each chunk is saved to a separate ``.partN`` file to support
        resuming. Falls back to a single-connection download when chunking is not
        applicable. Both download strategies use the same outer retry budget and
        exponential backoff.

        Returns:
            True if the download failed, False if it succeeded.

        """
        num_connections = getattr(self.session_info.args, "connections", 1)
        rate_limiter = self.session_info.rate_limiter
        request_timeout = self._request_timeout()

        for attempt in range(self.retry_config.retries):
            supports_range, content_length = detect_range_support(
                self.download_info.download_link,
                DOWNLOAD_HEADERS,
                request_timeout,
            )

            if should_use_parallel_download(
                content_length,
                num_connections,
                supports_range=supports_range,
            ):
                # .partN files are preserved on failure so a future attempt
                # resumes instead of restarting.
                failed = save_file_with_chunks(
                    self.download_info.download_link,
                    final_path,
                    self.download_info.task,
                    self.live_manager,
                    DownloadConfig(
                        content_length=content_length,
                        num_connections=num_connections,
                        headers=DOWNLOAD_HEADERS,
                        request_timeout=request_timeout,
                        rate_limiter=rate_limiter,
                    ),
                )
            else:
                failed = save_file_with_resume(
                    self.download_info.download_link,
                    final_path,
                    self.download_info.task,
                    self.live_manager,
                    headers=DOWNLOAD_HEADERS,
                    request_timeout=request_timeout,
                    rate_limiter=rate_limiter,
                )

            if not failed:
                return False

            # A failed attempt is often an expired/rotated signed URL. Re-resolving the
            # item page mints a fresh link before the next attempt.
            if self._refresh_download_link():
                self.live_manager.update_log(
                    event="Refreshed media URL",
                    details=(
                        f"Obtained a fresh signed URL for "
                        f"{self.download_info.filename} before retrying."
                    ),
                )

            if not self._retry_with_backoff(attempt, event="Retrying download"):
                break

        return True

    def _request_timeout(self) -> tuple[float, float]:
        """Return (connect_timeout, read_timeout) from CLI or defaults."""
        args = self.session_info.args
        connect_timeout = float(
            getattr(args, "connect_timeout", DEFAULT_CONNECT_TIMEOUT)
            or DEFAULT_CONNECT_TIMEOUT
        )
        read_timeout = float(
            getattr(args, "read_timeout", DEFAULT_READ_TIMEOUT)
            or DEFAULT_READ_TIMEOUT
        )
        return (connect_timeout, read_timeout)

    def _refresh_download_link(self) -> bool:
        """Refresh the signed media URL from the source item page."""
        try:
            refreshed_link = asyncio.run(refresh_item_download_link(self.download_info.item_url))
        except RuntimeError:
            return False

        if refreshed_link and refreshed_link != self.download_info.download_link:
            self.download_info.download_link = refreshed_link
            return True

        return False

    def download(self) -> bool:
        """Handle the download process.

        Returns:
            True if the item ultimately failed (and no one else will retry it), False if
            it succeeded, was skipped, or will be retried later by an external caller.

        """
        is_final_attempt = not self.retry_config.has_external_retry
        is_offline = subdomain_is_offline(
            self.download_info.download_link,
            self.session_info.bunkr_status,
        )
        should_skip_offline = (
            is_offline
            and is_final_attempt
            and not self.session_info.args.disable_server_check
        )
        if should_skip_offline:
            self.live_manager.update_log(
                event="Non-operational subdomain",
                details=f"The subdomain for {self.download_info.filename} is offline. "
                "Check the log file.",
            )
            self._finalize_download(SkippedReason.DOMAIN_OFFLINE)
            return False

        # Skip download if the file exists or is blacklisted
        formatted_filename = truncate_filename(self.download_info.filename)
        final_path = Path(self.session_info.download_path) / formatted_filename
        if self._skip_file_download(final_path):
            return False

        # Attempt to download the file with retries
        failed_download = self.attempt_download(final_path)

        # Handle failed download after retries
        if failed_download:
            return self._handle_failed_download(is_final_attempt=is_final_attempt)

        self._apply_item_mtime(final_path)
        self.live_manager.update_summary(CompletedReason.DOWNLOAD_SUCCESS)
        return False

    # Private methods
    def _skip_file_download(self, final_path: str) -> bool:
        """Determine whether a file should be skipped during download.

        If any of these conditions are met, the download is skipped:
            - The file already exists at the specified path.
            - The file's name matches any pattern in the ignore list.
            - The file's name does not match any pattern in the include list.
        """
        def log_and_skip_event(reason: str) -> bool:
            """Log the skip reason and updates the task before."""
            self.live_manager.update_log(event="Skipped download", details=reason)
            self.live_manager.update_task(
                self.download_info.task,
                completed=100,
                visible=False,
            )
            return True

        ignore_list = getattr(self.session_info.args, "ignore", [])
        include_list = getattr(self.session_info.args, "include", [])

        # Check if the file already exists
        if Path(final_path).exists():
            self.live_manager.update_summary(SkippedReason.ALREADY_DOWNLOADED)
            return log_and_skip_event(
                f"{self.download_info.filename} has already been downloaded.",
            )

        # Check if the file is in the ignore list
        if matches_ignore_list(self.download_info.filename, ignore_list):
            self.live_manager.update_summary(SkippedReason.IGNORE_LIST)
            return log_and_skip_event(
                f"{self.download_info.filename} matches the ignore list.",
            )

        # Check if the file is not in the include list
        if matches_include_list(self.download_info.filename, include_list):
            self.live_manager.update_summary(SkippedReason.INCLUDE_LIST)
            return log_and_skip_event(
                f"No included words found for {self.download_info.filename}.",
            )

        # Check if the subdomain is marked as offline
        if (
            subdomain_is_offline(
                self.download_info.download_link,
                self.session_info.bunkr_status,
            )
            and not self.session_info.args.disable_server_check
        ):
            self._finalize_download(SkippedReason.DOMAIN_OFFLINE)
            return log_and_skip_event(
                f"The subdomain for {self.download_info.download_link} has been "
                "previously marked as offline.",
            )

        # If none of the skip conditions are met, do not skip
        return False

    def _retry_with_backoff(self, attempt: int, *, event: str) -> bool:
        """Log error, apply backoff, and return True if should retry."""
        self.live_manager.update_log(
            event=event,
            details=f"{event} for {self.download_info.filename} "
            f"({attempt + 1}/{self.retry_config.retries})...",
        )

        if attempt < self.retry_config.retries - 1:
            delay = _BACKOFF_FACTOR ** (attempt + 1) + random.uniform(1, 2)  # noqa: S311
            time.sleep(delay)
            return True

        return False

    def _handle_failed_download(self, *, is_final_attempt: bool) -> bool:
        """Handle a failed download after all retry attempts.

        Always returns True (failed). When this is not the final attempt, only a log
        line is emitted -- the caller (AlbumDownloader) already has everything it needs
        to retry the item itself. The session log is only written on the final attempt,
        since that is the only point at which the outcome is permanent.
        """
        if not is_final_attempt:
            self.live_manager.update_log(
                event="Exceeded retry attempts",
                details=f"Max retries reached for {self.download_info.filename}. "
                "It will be retried one more time after all other tasks.",
            )
            # Hide stalled rows until retries to avoid cluttering the UI during large
            # albums. Rows reappear automatically when retries make progress.
            self.live_manager.update_task(
                self.download_info.task,
                completed=None,
                visible=False,
            )
            return True

        self.live_manager.update_log(
            event="Download failed",
            details=f"Failed to download {self.download_info.filename}. "
            "Check the log file.",
        )
        self._finalize_download(FailedReason.MAX_RETRIES_REACHED)
        return True

    def _apply_item_mtime(self, final_path: Path) -> None:
        """Set the downloaded file's modified time to the item's source date.

        Best-effort only: if no date could be extracted from the item page
        (self.download_info.item_date is None) or the OS call fails, the file simply
        keeps its normal (download-time) mtime.
        """
        item_date = self.download_info.item_date
        if item_date is None:
            return

        try:
            timestamp = item_date.timestamp()
            os.utime(final_path, (timestamp, timestamp))

        except (OSError, OverflowError, ValueError):
            pass

    def _finalize_download(
        self,
        reason: FailedReason | SkippedReason,
        *,
        completed: int | None = 100,
    ) -> None:
        outcome = reason.__class__.__name__.replace("Reason", "")
        write_on_session_log(self.download_info, reason=reason, outcome=outcome)
        self.live_manager.update_task(
            self.download_info.task,
            completed=completed,
            visible=False,
        )
        self.live_manager.update_summary(reason)
