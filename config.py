"""Validated site configuration and URL scope."""

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import soupsieve


def normalize_url(href: str, base: str) -> str | None:
    """Resolve HTTP(S) links, remove fragments, preserve meaningful query strings."""
    if not isinstance(href, str) or not href.strip() or href.strip().startswith("#"):
        return None
    try:
        parts = urlsplit(urljoin(base, href.strip()))
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        port = parts.port
        host = parts.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        if port and (parts.scheme, port) not in {("http", 80), ("https", 443)}:
            host += f":{port}"
        return urlunsplit((parts.scheme, host, parts.path or "/", parts.query, ""))
    except ValueError:
        return None


def same_origin(url: str, base: str) -> bool:
    first, second = normalize_url(url, base), normalize_url(base, base)
    return bool(first and second and urlsplit(first)[:2] == urlsplit(second)[:2])


@dataclass(frozen=True)
class Config:
    listing_url: str
    link_selector: str
    fields: dict[str, str]
    required_fields: tuple[str, ...] = ("name",)
    next_selector: str | None = None
    listing_ready: str = "body"
    detail_ready: str = "body"
    block_selector: str = ".data-block"
    block_label: str = ".block-label"
    block_value: str = ".block-value"
    request_delay: float = 1.5
    timeout: float = 20
    retries: int = 1
    max_listing_pages: int = 10

    @classmethod
    def load(cls, path: Path) -> "Config":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a JSON object.")
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
        for name in ("listing_url", "link_selector", "fields"):
            if name not in data:
                raise ValueError(f"Missing configuration key: {name}")
        values = dict(data)
        url = normalize_url(values["listing_url"], "")
        if not url:
            raise ValueError("listing_url must be an absolute HTTP(S) URL without credentials.")
        values["listing_url"] = url
        fields = values["fields"]
        reserved = {"requested_url", "source_url", "scraped_at", "status", "attempts", "issues"}
        if not isinstance(fields, dict) or not fields:
            raise ValueError("fields must be a nonempty object of field names and CSS selectors.")
        for key in fields:
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", key) or key in reserved:
                raise ValueError(f"Invalid or reserved field name: {key}")
        required = values.get("required_fields", ["name"])
        if not isinstance(required, (list, tuple)) or not required:
            raise ValueError("required_fields must be a nonempty list.")
        if any(not isinstance(key, str) or key not in fields for key in required):
            raise ValueError("Every required field must exist in fields.")
        if len(set(required)) != len(required):
            raise ValueError("required_fields contains duplicates.")
        values["required_fields"] = tuple(required)
        config = cls(**values)
        selectors = {key: getattr(config, key) for key in (
            "link_selector", "listing_ready", "detail_ready", "block_selector",
            "block_label", "block_value"
        )}
        if config.next_selector is not None:
            selectors["next_selector"] = config.next_selector
        selectors.update({f"fields.{key}": value for key, value in fields.items()})
        for key, selector in selectors.items():
            if not isinstance(selector, str) or not selector.strip():
                raise ValueError(f"{key} must be a nonempty CSS selector.")
            try:
                soupsieve.compile(selector)
            except soupsieve.SelectorSyntaxError as exc:
                raise ValueError(f"Invalid CSS selector in {key}: {selector}") from exc
        for key, low, high in (("request_delay", 1, 120), ("timeout", 1, 300),
                               ("retries", 0, 3), ("max_listing_pages", 1, 500)):
            value = getattr(config, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{key} must be a number.")
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{key} must be between {low} and {high}.")
            if key in {"retries", "max_listing_pages"} and not isinstance(value, int):
                raise ValueError(f"{key} must be a whole number.")
        return config

    def fingerprint(self, mode: str) -> str:
        payload = json.dumps({"config": asdict(self), "mode": mode}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()
