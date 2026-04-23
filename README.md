# Web Scraper — Selenium + Python + Excel

Automated web scraping solution that extracts structured contact and metadata
records from public websites and exports them into a clean, filterable Excel file.

Built with **Python**, **Selenium**, and **openpyxl**.

---

## Features

- Visits multiple detail pages automatically from a listing/index page
- Identifies and extracts separate visible data blocks per page
- Handles repeated section titles correctly (deduplicates with `_2`, `_3` suffixes)
- Preserves exact displayed values with no transformation
- Exports to a formatted `.xlsx` file with:
  - Auto-filter dropdowns on all columns
  - Frozen header row
  - Color-coded scrape status (green = ok, red = error)
  - Auto-fitted column widths
- Sample mode: scrape 10-20 records first for client verification before full run
- Full logging to console and `scraper.log`

---

## Output Preview

| Name | Phone | Email | Address | Category | Scrape Status |
|------|-------|-------|---------|----------|---------------|
| ABC Law Firm | +1-555-0101 | abc@law.com | 12 Main St | Legal | ✅ ok |
| XYZ Clinic | +1-555-0202 | xyz@clinic.com | 8 Park Ave | Medical | ✅ ok |

---

## Requirements

```
Python 3.10+
selenium
openpyxl
webdriver-manager
```

Install all dependencies:

```bash
pip install selenium openpyxl webdriver-manager
```

Google Chrome must be installed on your machine. ChromeDriver is downloaded
automatically by `webdriver-manager`.

---

## Usage

### 1. Configure

Open `scraper.py` and set these values at the top:

```python
LISTING_URL    = "https://example.com/directory"   # The index/listing page
BASE_URL       = "https://example.com"              # Base domain for relative links
LINK_SELECTOR  = "a.record-link"                   # CSS selector for detail-page links
SAMPLE_MODE    = True                               # True = sample, False = full scrape
SAMPLE_LIMIT   = 15                                 # Records to scrape in sample mode
OUTPUT_FILE    = "scraped_data.xlsx"                # Output file name
```

Then adjust the CSS selectors inside `scrape_detail_page()` to match the
target site's HTML structure.

### 2. Run sample (10-20 records)

```bash
python scraper.py
```

With `SAMPLE_MODE = True` this scrapes the first 15 records and saves
`scraped_data.xlsx` for review.

### 3. Run full scrape

Set `SAMPLE_MODE = False` in the config, then run again:

```bash
python scraper.py
```

---

## Project Structure

```
web-scraper-demo/
├── scraper.py        # Main scraper (fully commented)
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

---

## How It Works

```
Listing Page
     │
     ├── collect_detail_urls()   →  gathers all detail-page links
     │
     ├── scrape_detail_page()    →  visits each page, extracts fields
     │       └── extract_data_blocks()  →  handles repeated section titles
     │
     └── export_to_excel()       →  writes formatted .xlsx output
```

---

## Adapting to a New Site

Only three things need to change per project:

1. `LISTING_URL` and `LINK_SELECTOR` — point to the correct index page and links
2. CSS selectors inside `scrape_detail_page()` — match the target site's HTML
3. Fields in the `Record` dataclass — add/rename columns as needed

Everything else (deduplication, Excel export, logging, error handling) works
as-is for any site.

---

## Author

**Raja Wahaj** — Data Engineer and Analyst  
Upwork: [Wahaj](https://www.upwork.com/freelancers/wahaj)  
GitHub: [wahaaje](https://github.com/wahaaje)
