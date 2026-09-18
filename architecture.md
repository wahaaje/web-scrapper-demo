# Architecture and engineering decisions

## Boundaries

| Component | Responsibility |
|---|---|
| `scraper.py` | Stable command-line entry point |
| `webscraper/cli.py` | Arguments, output lifecycle, logging and exit codes |
| `webscraper/config.py` | Configuration validation, fingerprinting and URL normalization |
| `webscraper/sources.py` | Local fixture adapter and Selenium Chrome adapter |
| `webscraper/extraction.py` | Pure listing and detail HTML parsing |
| `webscraper/engine.py` | Sequential discovery, limits, retries and per-record checkpoints |
| `webscraper/storage.py` | Atomic file replacement, checkpoint loading and output lock |
| `webscraper/exporters.py` | JSON, Excel and escaped HTML presentation |
| `webscraper/report.html` | Self-contained HTML report template |

## Why these choices

**A reproducible fixture demo.** Third-party markup can change or become unavailable. Five small local HTML files exercise two-page discovery, duplicate links, repeated labels and a missing optional field. The demo has no browser or network dependency after packages are installed.

**Browser acquisition, pure parsing.** Selenium waits for a configured element and returns an HTML snapshot. Beautiful Soup parses it using the same functions as the fixture demo. Tests can target data behavior without an external website or Chrome. This is deliberately not a computed-visibility extractor: hidden HTML can still match a selector.

**Explicit quality states.** `ok` means configured required fields are nonempty and matched data blocks have both a label and value. It does not mean that phone numbers, addresses or business claims have been independently verified. `partial` retains imperfect extracted data; `error` retains the failed URL and explanation.

**Ordered data blocks.** A page may contain three labels named `Service` and another literally named `Service_2`. An ordered list preserves labels and every value without key collisions. Excel represents these in a separate long-form sheet keyed by requested URL and block position.

**Recovery at a record boundary.** A checkpoint is written after each completed detail record, including partial/error results. Atomic replacement reduces the chance of a truncated state file. An output-directory lock prevents two cooperating scraper processes from writing the same run simultaneously.

**Configuration-bound resume.** A SHA-256 fingerprint covers the full configuration and source mode. Resume re-discovers listing pages, skips previously successful detail URLs and retries incomplete ones. It retains older checkpoint entries outside the current sample, while final exports contain only URLs selected in the current run. Old successful records keep their original extraction timestamps.

**Bounded sequential work.** Record and listing-page caps constrain the run. Every navigation after the first is paced; timeout retries use increasing delays. Non-timeout browser errors are recorded without retry. Sequential execution is easier to inspect and recover, at the cost of throughput.

**Portable review and machine-readable delivery.** JSON retains the complete extracted data. Excel provides frozen headers, filters, readable widths and status colors. HTML supports offline search and status filtering. Each final file is replaced atomically, but the set of files is not a transaction; an export failure can leave a mixture of older/newer final files. The checkpoint supports recovery.

## Boundaries to be aware of

- The URL scope limits links the crawler enqueues. Chrome can follow an HTTP redirect before the adapter checks its final URL. This is not a network sandbox.
- A detail URL is the unit of deduplication. Two different URLs resolving to the same business can still produce two records.
- The parser does not support DOM click sequences, scroll-to-load listings, shadow roots or iframes without additional adapter code.
- A timeout can mean slow content, a wrong selector or a blocked page. The adapter does not infer HTTP status codes from WebDriver or bypass access controls.
- Discovery happens before detail extraction. A discovery failure stops the run with an error; it does not silently export a supposedly complete directory.
- Checkpoints are local trusted state, not a database, distributed queue or freshness cache. Delete/rebuild an output deliberately when refreshed data is required.
- At most 5000 detail URLs are selected per run. All selected records are held in memory; this is intended for bounded jobs, not web-scale crawling.

## References

- [Selenium explicit waits](https://www.selenium.dev/documentation/webdriver/waits/)
- [Selenium Manager](https://www.selenium.dev/documentation/selenium_manager/)
- [Beautiful Soup documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
