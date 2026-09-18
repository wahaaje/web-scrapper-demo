"""Bounded sequential crawling with injectable sources, time and checkpoints."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Callable

from .config import Config, normalize_url, same_origin
from .extraction import Record, parse_detail, parse_listing
from .sources import FetchError, Page, PageTimeout, Source
from .storage import save_checkpoint

log = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Crawler:
    def __init__(self, config: Config, source: Source, *, limit: int,
                 checkpoint: Path, fingerprint: str, previous: dict[str, Record] | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], str] = utc_now, mode: str = "live"):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5000:
            raise ValueError("Record limit must be between 1 and 5000.")
        self.config, self.source, self.limit = config, source, limit
        self.checkpoint, self.fingerprint = checkpoint, fingerprint
        self.previous = previous or {}
        self.sleep, self.clock, self.mode = sleep, clock, mode
        self.request_count = 0
        self.listing_pages = 0
        self.warnings: list[str] = []
        self.stop_reason = "end_of_listing"

    def fetch(self, url: str, selector: str) -> tuple[Page, int]:
        for attempt in range(1, self.config.retries + 2):
            if self.request_count:
                self.sleep(self.config.request_delay * (2 ** (attempt - 1)))
            self.request_count += 1
            try:
                page = self.source.fetch(url, selector)
                if not same_origin(page.url, self.config.listing_url):
                    raise FetchError("Navigation ended outside the configured origin.")
                return page, attempt
            except PageTimeout:
                if attempt > self.config.retries:
                    raise
                log.warning("Timeout; retry %s/%s: %s", attempt, self.config.retries, url)
        raise AssertionError("Unreachable retry state")

    def discover(self) -> list[str]:
        url = self.config.listing_url
        visited: set[str] = set()
        seen: set[str] = set()
        urls: list[str] = []
        while url:
            if url in visited:
                raise FetchError("Pagination loop detected. Review next_selector.")
            page, _ = self.fetch(url, self.config.listing_ready)
            final_url = normalize_url(page.url, url)
            if final_url in visited:
                raise FetchError("Pagination redirected to a page already visited.")
            visited.update((url, final_url))
            self.listing_pages += 1
            links, next_url = parse_listing(page.html, page.url, self.config)
            for target in links:
                if target not in seen:
                    seen.add(target)
                    urls.append(target)
                if len(urls) >= self.limit:
                    self.stop_reason = "record_limit"
                    self.warnings.append("Record limit reached; more records may exist.")
                    return urls
            if next_url and self.listing_pages >= self.config.max_listing_pages:
                self.stop_reason = "listing_page_limit"
                self.warnings.append("Listing page limit reached; more records may exist.")
                break
            url = next_url
        return urls

    def run(self) -> tuple[list[Record], dict]:
        started_at = self.clock()
        urls = self.discover()
        records: list[Record] = []
        # Preserve earlier checkpoint entries, including those outside this run's sample.
        durable = dict(self.previous)
        reused = 0
        for url in urls:
            previous = self.previous.get(url)
            if previous and previous.status == "ok":
                record = previous
                reused += 1
            else:
                before = self.request_count
                try:
                    page, attempts = self.fetch(url, self.config.detail_ready)
                    record = parse_detail(page.html, url, page.url, self.config, self.clock(), attempts)
                except FetchError as exc:
                    record = Record(url, "", self.clock(), attempts=self.request_count - before,
                                    issues=[str(exc)])
            records.append(record)
            durable[url] = record
            save_checkpoint(self.checkpoint, self.fingerprint, list(durable.values()))
            log.info("%s/%s %s: %s", len(records), len(urls), record.status, url)
        summary = {
            "schema_version": 1, "mode": self.mode, "started_at": started_at,
            "finished_at": self.clock(), "listing_url": self.config.listing_url,
            "record_limit": self.limit, "listing_pages": self.listing_pages,
            "page_attempts": self.request_count, "records": len(records),
            "reused_records": reused, "attempted_records": len(records) - reused,
            "counts": {status: sum(r.status == status for r in records)
                       for status in ("ok", "partial", "error")},
            "stop_reason": self.stop_reason, "warnings": self.warnings,
        }
        return records, summary
