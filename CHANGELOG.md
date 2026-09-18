# Changelog

## 2.0.0 — 2026-09-18

### Added

- A runnable local fixture demo with two listing pages and three fictional organizations.
- Validated JSON configuration and a command-line interface for sample/live runs.
- Pagination, same-origin link selection, duplicate URL handling and crawl limits.
- Required-field validation and structured `ok`, `partial` and `error` results.
- Per-record atomic checkpoints, config-aware resume and an output-directory lock.
- Full JSON export, a separate Excel data-block sheet and a searchable offline HTML report.
- Behavioral tests, GitHub Actions workflow and configuration/operations documentation.

### Changed

- Moved browser loading, parsing, run control and exports into separate modules.
- Preserved all repeated data blocks instead of retaining only two sections.
- Kept extracted text literal in Excel and escaped it in HTML.
- Replaced an additional driver-manager package with Selenium's built-in manager.
- Removed a hardcoded browser-identification override and unconditional sandbox-disabling options.
- Replaced placeholder usage instructions with a reproducible demo and explicit live-site limitations.

### Migration

- Root `scraper.py` remains the entry point, now with `--demo` or `--config` required.
- Configuration constants in the old script move to JSON; existing custom selectors must be copied into that file.
- Output is now a directory with separate dataset, report, checkpoint and log files.
- Section labels remain unchanged in a list/long-form sheet, so consumers of old `section_a_*` / `section_b_*` columns must update.
