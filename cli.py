"""Command-line interface. Live navigation always requires --config."""

import argparse
import logging
from pathlib import Path
import sys

from .config import Config
from .engine import Crawler
from .exporters import export_all
from .sources import FetchError, FixtureSource, SeleniumSource
from .storage import output_lock, read_checkpoint

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_NAMES = ("checkpoint.json", "records.json", "records.xlsx", "report.html", "run_report.json", "scraper.log")
log = logging.getLogger(__name__)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Extract directory records into JSON, Excel and an HTML review report.")
    source = result.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="Use bundled fictional HTML; no browser or network")
    source.add_argument("--config", type=Path, help="Path to a site JSON configuration")
    result.add_argument("--output", type=Path, help="Output directory (default: output/demo or output/run)")
    result.add_argument("--limit", type=int, default=15, help="Maximum detail records, 1–5000 (default: 15)")
    mode = result.add_mutually_exclusive_group()
    mode.add_argument("--resume", action="store_true", help="Reuse successful checkpoint records; retry the rest")
    mode.add_argument("--overwrite", action="store_true", help="Replace this tool's files in the output directory")
    result.add_argument("--headed", action="store_true", help="Show Chrome for a live run")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not 1 <= args.limit <= 5000:
        print("ERROR: --limit must be between 1 and 5000.", file=sys.stderr)
        return 2
    if args.demo and args.headed:
        print("ERROR: --headed applies to --config runs only.", file=sys.stderr)
        return 2
    mode = "demo" if args.demo else "live"
    output = (args.output or Path("output") / ("demo" if args.demo else "run")).resolve()
    try:
        config = Config.load(ROOT / "examples/demo.json" if args.demo else args.config)
        fingerprint = config.fingerprint(mode)
        with output_lock(output):
            existing = [name for name in OUTPUT_NAMES if (output / name).exists()]
            if existing and not (args.resume or args.overwrite):
                raise ValueError("Output already exists. Choose --resume, --overwrite or a new --output directory.")
            previous = read_checkpoint(output / "checkpoint.json", fingerprint) if args.resume else {}
            if any(r.status == "ok" and any(not r.fields.get(key) for key in config.required_fields)
                   for r in previous.values()):
                raise ValueError("Checkpoint has a successful record with missing required fields.")
            if args.overwrite:
                for name in OUTPUT_NAMES:
                    (output / name).unlink(missing_ok=True)
            handlers = [logging.StreamHandler(), logging.FileHandler(output / "scraper.log", encoding="utf-8")]
            root_log = logging.getLogger("webscraper")
            prior_level = root_log.level
            root_log.setLevel(logging.INFO)
            for handler in handlers:
                handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
                root_log.addHandler(handler)
            source = None
            try:
                source = FixtureSource(ROOT / "examples/site") if args.demo else SeleniumSource(config, args.headed)
                options = {"sleep": lambda seconds: None} if args.demo else {}
                crawler = Crawler(config, source, limit=args.limit, checkpoint=output / "checkpoint.json",
                                  fingerprint=fingerprint, previous=previous, mode=mode, **options)
                records, summary = crawler.run()
                export_all(output, records, list(config.fields), summary)
                counts = summary["counts"]
                print(f"Captured {len(records)} records: {counts['ok']} ok, {counts['partial']} partial, {counts['error']} error.")
                print(f"Reused {summary['reused_records']} successful record(s). Report: {output / 'report.html'}")
                for warning in summary["warnings"]:
                    print(f"WARNING: {warning}")
                return 1 if counts["partial"] or counts["error"] else 0
            finally:
                if source:
                    try:
                        source.close()
                    except Exception as exc:
                        log.warning("Could not close browser cleanly: %s", str(exc) or type(exc).__name__)
                for handler in handlers:
                    root_log.removeHandler(handler)
                    handler.close()
                root_log.setLevel(prior_level)
    except KeyboardInterrupt:
        print("Interrupted. Completed records are checkpointed; rerun with --resume.", file=sys.stderr)
        return 130
    except (ValueError, OSError, FetchError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        # Keep the CLI readable for driver startup/export failures; no success exit.
        detail = str(exc).splitlines()[0] if str(exc) else "No additional detail."
        print(f"ERROR: {type(exc).__name__}: {detail}", file=sys.stderr)
        return 2
