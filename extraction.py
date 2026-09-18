"""Pure parsing functions shared by the demo and browser adapters."""

from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from .config import Config, normalize_url, same_origin


@dataclass
class Record:
    requested_url: str
    source_url: str
    scraped_at: str
    fields: dict[str, str] = field(default_factory=dict)
    blocks: list[dict[str, str]] = field(default_factory=list)
    status: str = "error"
    attempts: int = 1
    issues: list[str] = field(default_factory=list)


def text_at(node, selector: str) -> str:
    found = node.select_one(selector)
    # Normalize whitespace only; do not infer, validate or rewrite field values.
    return " ".join(found.stripped_strings) if found else ""


def parse_listing(html: str, url: str, config: Config) -> tuple[list[str], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    elements = soup.select(config.link_selector)
    if not elements:
        raise ValueError(f"No detail links match {config.link_selector!r} at {url}")
    urls = []
    for element in elements:
        target = normalize_url(element.get("href", ""), url)
        if target and same_origin(target, config.listing_url) and target not in urls:
            urls.append(target)
    if not urls:
        raise ValueError(f"No in-scope HTTP(S) detail links found at {url}")
    next_url = None
    next_element = soup.select_one(config.next_selector) if config.next_selector else None
    if next_element and next_element.get("aria-disabled") != "true":
        next_url = normalize_url(next_element.get("href", ""), url)
        if not next_url or not same_origin(next_url, config.listing_url):
            raise ValueError("The next-page link is missing a valid in-scope href.")
    return urls, next_url


def parse_detail(html: str, requested_url: str, source_url: str,
                 config: Config, scraped_at: str, attempts: int = 1) -> Record:
    soup = BeautifulSoup(html, "html.parser")
    record = Record(requested_url, source_url, scraped_at, attempts=attempts)
    record.fields = {name: text_at(soup, selector) for name, selector in config.fields.items()}
    for number, block in enumerate(soup.select(config.block_selector), start=1):
        label = text_at(block, config.block_label)
        value = text_at(block, config.block_value)
        record.blocks.append({"label": label, "value": value})
        if not label or not value:
            record.issues.append(f"Block {number} has an empty label or value.")
    for name in config.required_fields:
        if not record.fields[name]:
            record.issues.append(f"Required field is empty: {name}")
    record.status = "partial" if record.issues else "ok"
    return record
