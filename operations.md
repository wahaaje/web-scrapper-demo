# Running and recovering jobs

## First run

Run the fixture demo, then configure a small live sample. Inspect its JSON, Excel workbook and HTML report before expanding the record limit. Check the target site's access rules and robots policy; this tool does not fetch or enforce robots.txt automatically. It has no login or CAPTCHA workflow.

```bash
python scraper.py --config config.local.json --limit 5 --output output/site-sample
```

Use `--headed` for a visible browser when a wait selector needs inspection. Selenium Manager resolves driver setup; installation or driver download problems are runtime errors, not successful empty runs.

## Resume an interrupted run

Keep the same configuration and output path:

```bash
python scraper.py --config config.local.json --limit 200 --output output/site-sample --resume
```

Resume re-reads the listing, reuses checkpoint records with `status=ok`, and retries partial/error records. It does **not** refresh a previously successful record. You may change the CLI record limit; changing anything in the JSON configuration or switching between demo/live modes invalidates the checkpoint fingerprint. Use a new output directory for a different configuration.

The checkpoint is updated after every completed detail record. Interrupting the current record can cause that one URL to be fetched again. Interrupting before the first completed record may leave no checkpoint; rerun into a new output directory or deliberately replace the incomplete run with `--overwrite`.

## Fresh data

Choose a new path to keep the previous run:

```bash
python scraper.py --config config.local.json --limit 200 --output output/site-refresh
```

Or explicitly replace this tool's output files:

```bash
python scraper.py --config config.local.json --limit 200 --output output/site-sample --overwrite
```

`--overwrite` replaces only the six documented output files; unrelated files remain. It discards that run's prior checkpoint and exports, so use a new output path when you need history.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Every selected record is `ok`; inspect run warnings for sampling limits |
| `1` | Final exports were produced, but at least one record is partial or failed |
| `2` | Configuration, discovery, driver, filesystem or export failure |
| `130` | Keyboard interruption; completed records remain checkpointed |

`run_report.json` provides machine-readable counts, stop reason and warnings. A record cap is a successful bounded sample, not proof of complete site coverage.

## Troubleshooting

| Symptom | Action |
|---|---|
| Output already exists | Select `--resume`, a new output directory or a deliberate `--overwrite` |
| Checkpoint configuration differs | Restore the original config or use a new output directory |
| No detail links match | Inspect `link_selector`, the loaded page and `listing_ready` |
| Required fields are empty | Inspect selectors and choose a reliable `detail_ready` marker |
| Pagination loop / invalid next link | Check `next_selector`; it must target a real next-page anchor |
| Chrome startup failure | Confirm Chrome setup, driver access and the Selenium Manager guidance |
| Workbook cannot be replaced | Close the file in Excel, then rerun with `--resume` |
| Output is locked | Wait for the other run. If the process was terminated forcibly, confirm it is no longer running before removing `.run.lock` from that output directory |

Do not edit checkpoint status values to make incomplete records appear successful. Fix selectors or page access and run a new sample.

## Scheduling

The repository runs on demand. It does not install a scheduler or continue while a local laptop is off. A server/CI scheduler can invoke the CLI, but should use separate output directories for refreshes, retain exit-code monitoring and avoid overlapping runs. Scheduling an external scrape is a separate deployment decision.

## Verification performed for this upgrade

- Python 3.12.14, Linux; direct package versions recorded in `requirements.txt`.
- 36 unit/integration tests passed, including a mocked Selenium adapter.
- The offline demo generated 3 records, 10 data blocks and matching JSON/Excel/HTML exports.
- An immediate resume reused all three records while still re-reading the two listing pages.
- Workbook round-trip checks covered literal formula-like strings, leading-zero phone values and complete data-block counts.
- HTML parsing checks covered escaping and expected report content. A visual browser preview could not be completed in the preparation environment because local-file navigation was blocked.

These checks do not establish performance on a live external site. The GitHub Actions workflow is supplied for verification after upload; a successful hosted CI run must be confirmed in the repository.
