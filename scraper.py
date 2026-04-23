"""
scraper.py
==========
Automated web scraper using Selenium + openpyxl.

PURPOSE
-------
Visits a listing/index page, collects all detail-page URLs,
then scrapes structured contact and metadata records from each page.
Exports results to a clean, filterable Excel file.

REQUIREMENTS
------------
    pip install selenium openpyxl webdriver-manager

USAGE
-----
    1. Set BASE_URL and LISTING_URL below.
    2. Adjust the CSS selectors in the extraction functions to match
       the target site's HTML structure.
    3. Run:  python scraper.py
    4. Output:  scraped_data.xlsx  (in the same directory)

CONFIGURATION
-------------
To run a sample (10-20 records) before the full scrape, set:
    SAMPLE_MODE = True
To run the full scrape:
    SAMPLE_MODE = False
"""

import time
import logging
from dataclasses import dataclass, fields
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# CONFIGURATION — edit these before running
# ---------------------------------------------------------------------------

# The page that lists all the records (index/listing page).
LISTING_URL = "https://example.com/directory"

# Base domain, used to resolve relative href links found on the listing page.
BASE_URL = "https://example.com"

# CSS selector that matches each detail-page link on the listing page.
# Example: "a.record-link", "table.results td a", ".entry-title a"
LINK_SELECTOR = "a.record-link"

# Whether to scrape only the first SAMPLE_LIMIT records.
SAMPLE_MODE = True
SAMPLE_LIMIT = 15

# Seconds to wait between page requests (be polite to the server).
REQUEST_DELAY = 1.5

# Max seconds to wait for a page element to appear before timing out.
PAGE_LOAD_TIMEOUT = 10

# Output file path.
OUTPUT_FILE = "scraped_data.xlsx"

# ---------------------------------------------------------------------------
# LOGGING — writes to console and to scraper.log
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DATA MODEL
# ---------------------------------------------------------------------------

@dataclass
class Record:
    """
    One row in the final Excel output.

    Add or rename fields to match the columns you need.
    Each field name becomes a column header in the spreadsheet.
    """
    page_url: str = ""          # Source URL (always populated for traceability)
    name: str = ""              # Primary name / title of the record
    phone: str = ""             # Contact phone number
    email: str = ""             # Contact email address
    address: str = ""           # Physical or mailing address
    category: str = ""          # Category / type label
    section_a_title: str = ""   # First data block label (deduplicated)
    section_a_value: str = ""   # First data block value
    section_b_title: str = ""   # Second data block label
    section_b_value: str = ""   # Second data block value
    notes: str = ""             # Any additional visible text / notes
    scrape_status: str = ""     # "ok" or error message — useful for QA


# ---------------------------------------------------------------------------
# BROWSER SETUP
# ---------------------------------------------------------------------------

def build_driver() -> webdriver.Chrome:
    """
    Creates a headless Chrome WebDriver.

    webdriver-manager automatically downloads the correct ChromeDriver
    version for the installed Chrome, so no manual driver setup is needed.
    """
    options = Options()
    options.add_argument("--headless")          # Run without opening a window
    options.add_argument("--no-sandbox")        # Required in some Linux envs
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # Mimic a real browser to reduce bot-detection blocks
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


# ---------------------------------------------------------------------------
# STEP 1 — COLLECT DETAIL-PAGE URLS FROM THE LISTING PAGE
# ---------------------------------------------------------------------------

def collect_detail_urls(driver: webdriver.Chrome) -> list[str]:
    """
    Loads the listing/index page and extracts all detail-page href values.

    Handles:
    - Relative URLs (e.g. /records/123) → prefixed with BASE_URL
    - Duplicate links → deduplicated while preserving order
    - Sample mode → returns only the first SAMPLE_LIMIT URLs

    Args:
        driver: Active Selenium WebDriver instance.

    Returns:
        List of absolute URLs to visit.
    """
    log.info(f"Loading listing page: {LISTING_URL}")
    driver.get(LISTING_URL)

    # Wait until at least one matching link is present on the page
    try:
        WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, LINK_SELECTOR))
        )
    except TimeoutException:
        log.error(f"Timed out waiting for links with selector: '{LINK_SELECTOR}'")
        return []

    link_elements = driver.find_elements(By.CSS_SELECTOR, LINK_SELECTOR)
    log.info(f"Found {len(link_elements)} link elements on listing page")

    seen = set()
    urls = []

    for el in link_elements:
        href = el.get_attribute("href") or ""

        # Convert relative URLs to absolute
        if href.startswith("/"):
            href = BASE_URL.rstrip("/") + href

        # Skip empty, anchor-only, or already-seen links
        if not href or href.startswith("#") or href in seen:
            continue

        seen.add(href)
        urls.append(href)

    if SAMPLE_MODE:
        log.info(f"SAMPLE MODE — limiting to {SAMPLE_LIMIT} records")
        urls = urls[:SAMPLE_LIMIT]

    log.info(f"Will scrape {len(urls)} detail pages")
    return urls


# ---------------------------------------------------------------------------
# STEP 2 — SCRAPE ONE DETAIL PAGE
# ---------------------------------------------------------------------------

def safe_text(driver: webdriver.Chrome, selector: str) -> str:
    """
    Helper: returns stripped inner text of the first matching element,
    or an empty string if the element does not exist.

    Args:
        driver:   Active WebDriver.
        selector: CSS selector string.

    Returns:
        Cleaned text content, or "".
    """
    try:
        el = driver.find_element(By.CSS_SELECTOR, selector)
        return el.text.strip()
    except NoSuchElementException:
        return ""


def extract_data_blocks(driver: webdriver.Chrome) -> dict[str, str]:
    """
    Extracts repeated label/value pairs from a page, handling duplicate
    section titles by appending a numeric suffix (_2, _3, ...).

    This function assumes each data block is structured as:
        <div class="data-block">
            <span class="block-label">Title</span>
            <span class="block-value">Value</span>
        </div>

    *** ADJUST THE SELECTORS BELOW to match the target site. ***

    Args:
        driver: Active WebDriver.

    Returns:
        Dict mapping deduplicated label strings to their values.
        Example: {"Category": "Law Firm", "Category_2": "Notary"}
    """
    blocks = {}
    label_count: dict[str, int] = {}  # Track how many times each label appears

    block_elements = driver.find_elements(By.CSS_SELECTOR, "div.data-block")

    for block in block_elements:
        try:
            label = block.find_element(By.CSS_SELECTOR, ".block-label").text.strip()
            value = block.find_element(By.CSS_SELECTOR, ".block-value").text.strip()
        except NoSuchElementException:
            continue  # Skip malformed blocks silently

        if not label:
            continue

        # Deduplicate: if "Category" seen before, store as "Category_2", etc.
        label_count[label] = label_count.get(label, 0) + 1
        key = label if label_count[label] == 1 else f"{label}_{label_count[label]}"

        blocks[key] = value

    return blocks


def scrape_detail_page(driver: webdriver.Chrome, url: str) -> Record:
    """
    Visits a single detail page and extracts all fields into a Record.

    *** ADJUST THE CSS SELECTORS BELOW to match the target site. ***

    Args:
        driver: Active WebDriver.
        url:    Full URL of the detail page.

    Returns:
        Populated Record dataclass instance.
    """
    record = Record(page_url=url)

    try:
        driver.get(url)

        # Wait for the main content container to load
        WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.main-content"))
        )

        # --- Extract individual fields ---
        # Adjust each selector to match the real site's HTML.

        record.name     = safe_text(driver, "h1.record-name")
        record.phone    = safe_text(driver, "span.phone-number")
        record.email    = safe_text(driver, "a.email-link")
        record.address  = safe_text(driver, "div.address-block")
        record.category = safe_text(driver, "span.category-tag")
        record.notes    = safe_text(driver, "div.notes-section")

        # --- Extract repeated label/value blocks ---
        blocks = extract_data_blocks(driver)

        # Map the first two blocks into fixed columns.
        # You can expand this if there are more blocks.
        block_items = list(blocks.items())
        if len(block_items) >= 1:
            record.section_a_title, record.section_a_value = block_items[0]
        if len(block_items) >= 2:
            record.section_b_title, record.section_b_value = block_items[1]

        record.scrape_status = "ok"
        log.info(f"  Scraped: {record.name or url}")

    except TimeoutException:
        record.scrape_status = "timeout — page did not load"
        log.warning(f"  Timeout on: {url}")

    except Exception as exc:
        record.scrape_status = f"error: {exc}"
        log.error(f"  Failed on {url}: {exc}")

    return record


# ---------------------------------------------------------------------------
# STEP 3 — EXPORT TO EXCEL
# ---------------------------------------------------------------------------

# Header background color (dark teal) and text color (white)
HEADER_FILL  = PatternFill("solid", start_color="1F4E79", end_color="1F4E79")
HEADER_FONT  = Font(name="Arial", bold=True, color="FFFFFF", size=11)
BODY_FONT    = Font(name="Arial", size=10)
ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=False)
ALIGN_LEFT   = Alignment(horizontal="left",   vertical="center", wrap_text=True)

# Thin border for all cells
_thin = Side(style="thin", color="BFBFBF")
CELL_BORDER  = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)

# Status-color fills for the scrape_status column
STATUS_OK_FILL    = PatternFill("solid", start_color="C6EFCE", end_color="C6EFCE")  # green
STATUS_ERR_FILL   = PatternFill("solid", start_color="FFC7CE", end_color="FFC7CE")  # red


def export_to_excel(records: list[Record], filepath: str) -> None:
    """
    Writes a list of Record objects to a formatted, filterable Excel file.

    Features:
    - Bold colored header row
    - Auto-filter on all columns (click the dropdown arrows to filter)
    - Frozen top row so headers stay visible while scrolling
    - Status column color-coded green/red
    - Auto-fitted column widths

    Args:
        records:  List of scraped Record instances.
        filepath: Output .xlsx file path.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Scraped Data"

    # --- Build header row from dataclass field names ---
    # Convert snake_case field names to "Title Case" for readability
    column_names = [f.name.replace("_", " ").title() for f in fields(Record)]
    ws.append(column_names)

    # Style the header row
    for col_idx, _ in enumerate(column_names, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font      = HEADER_FONT
        cell.fill      = HEADER_FILL
        cell.alignment = ALIGN_CENTER
        cell.border    = CELL_BORDER

    # --- Write data rows ---
    for row_idx, record in enumerate(records, start=2):
        row_values = [getattr(record, f.name) for f in fields(Record)]
        ws.append(row_values)

        for col_idx, value in enumerate(row_values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font      = BODY_FONT
            cell.alignment = ALIGN_LEFT
            cell.border    = CELL_BORDER

        # Color-code the scrape_status column (last column)
        status_cell = ws.cell(row=row_idx, column=len(column_names))
        if record.scrape_status == "ok":
            status_cell.fill = STATUS_OK_FILL
        else:
            status_cell.fill = STATUS_ERR_FILL

    # --- Auto-filter on all columns ---
    # This adds the dropdown arrows Excel users expect for filtering
    ws.auto_filter.ref = ws.dimensions

    # --- Freeze the top row ---
    ws.freeze_panes = "A2"

    # --- Auto-fit column widths ---
    # openpyxl doesn't measure text width natively, so we estimate
    # based on the longest value in each column (capped at 60 chars).
    for col_idx, col_name in enumerate(column_names, start=1):
        col_letter = get_column_letter(col_idx)
        max_len = len(col_name)  # Start with header width as minimum

        for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
            for cell in row:
                cell_len = len(str(cell.value)) if cell.value else 0
                if cell_len > max_len:
                    max_len = cell_len

        # Cap at 60 to prevent absurdly wide columns
        ws.column_dimensions[col_letter].width = min(max_len + 4, 60)

    # Row height for header
    ws.row_dimensions[1].height = 20

    wb.save(filepath)
    log.info(f"Excel file saved: {filepath}  ({len(records)} rows)")


# ---------------------------------------------------------------------------
# MAIN — orchestrates the full scrape
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Entry point. Runs the full pipeline:
        1. Launch browser
        2. Collect detail-page URLs from the listing page
        3. Visit each page and extract data
        4. Export results to Excel
        5. Quit browser
    """
    log.info("=" * 60)
    log.info("Scraper starting")
    log.info(f"Target listing: {LISTING_URL}")
    log.info(f"Sample mode:    {SAMPLE_MODE} (limit={SAMPLE_LIMIT})")
    log.info("=" * 60)

    driver = build_driver()

    try:
        # Step 1 — get all URLs
        urls = collect_detail_urls(driver)

        if not urls:
            log.error("No URLs found. Check LISTING_URL and LINK_SELECTOR.")
            return

        # Step 2 — scrape each detail page
        records: list[Record] = []
        for i, url in enumerate(urls, start=1):
            log.info(f"[{i}/{len(urls)}] {url}")
            record = scrape_detail_page(driver, url)
            records.append(record)

            # Polite delay between requests
            time.sleep(REQUEST_DELAY)

        # Step 3 — export
        export_to_excel(records, OUTPUT_FILE)

        # Summary
        ok_count  = sum(1 for r in records if r.scrape_status == "ok")
        err_count = len(records) - ok_count
        log.info(f"Done. {ok_count} ok, {err_count} errors. Output: {OUTPUT_FILE}")

    finally:
        driver.quit()
        log.info("Browser closed.")


if __name__ == "__main__":
    main()
