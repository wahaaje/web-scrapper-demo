"""Interchangeable HTML sources; importing this module never launches Chrome."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from .config import Config, same_origin


class FetchError(RuntimeError):
    """A page could not be loaded. Non-timeout failures are not retried."""


class PageTimeout(FetchError):
    """A bounded navigation or selector wait timed out."""


@dataclass(frozen=True)
class Page:
    url: str
    html: str


class Source(Protocol):
    def fetch(self, url: str, ready_selector: str) -> Page: ...
    def close(self) -> None: ...


class FixtureSource:
    """Reads bundled HTML mapped to the reserved demo.test domain; no network."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def fetch(self, url: str, ready_selector: str) -> Page:
        if not same_origin(url, "https://demo.test/") or urlsplit(url).query:
            raise FetchError("The demo only supports bundled demo.test pages.")
        path = (self.root / urlsplit(url).path.lstrip("/")).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise FetchError(f"Demo fixture not found: {url}")
        return Page(url, path.read_text(encoding="utf-8"))

    def close(self) -> None:
        pass


class SeleniumSource:
    """Chrome snapshots after an explicit CSS wait, using Selenium Manager."""

    def __init__(self, config: Config, headed: bool = False):
        from selenium import webdriver

        self.config = config
        options = webdriver.ChromeOptions()
        if not headed:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
        self.driver = webdriver.Chrome(options=options)
        try:
            self.driver.set_page_load_timeout(config.timeout)
        except Exception:
            self.driver.quit()
            raise

    def fetch(self, url: str, ready_selector: str) -> Page:
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        try:
            self.driver.get(url)
            if not same_origin(self.driver.current_url, self.config.listing_url):
                raise FetchError("Navigation redirected outside the configured origin.")
            WebDriverWait(self.driver, self.config.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ready_selector))
            )
            return Page(self.driver.current_url, self.driver.page_source)
        except TimeoutException as exc:
            raise PageTimeout("Navigation or the configured CSS wait timed out.") from exc
        except WebDriverException as exc:
            message = str(exc).splitlines()[0][:240] if str(exc) else type(exc).__name__
            raise FetchError(f"Chrome could not load the page: {message}") from exc

    def close(self) -> None:
        self.driver.quit()
