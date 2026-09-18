"""Atomic checkpoints and a per-output-directory process lock."""

from contextlib import contextmanager
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile

from .extraction import Record


def atomic_text(path: Path, content: str) -> None:
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def save_checkpoint(path: Path, fingerprint: str, records: list[Record]) -> None:
    atomic_text(path, json.dumps({"version": 1, "fingerprint": fingerprint,
                                 "records": [asdict(r) for r in records]}, indent=2, ensure_ascii=False))


def read_checkpoint(path: Path, fingerprint: str) -> dict[str, Record]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unsupported checkpoint version.")
    if data.get("fingerprint") != fingerprint:
        raise ValueError("Checkpoint configuration differs. Use a new output directory.")
    if not isinstance(data.get("records"), list):
        raise ValueError("Checkpoint records must be a list.")
    records = {}
    for item in data["records"]:
        try:
            record = Record(**item)
        except (TypeError, KeyError) as exc:
            raise ValueError("Checkpoint contains an invalid record.") from exc
        if (record.status not in {"ok", "partial", "error"}
                or not isinstance(record.requested_url, str)
                or not isinstance(record.source_url, str)
                or not isinstance(record.scraped_at, str)
                or isinstance(record.attempts, bool)
                or not isinstance(record.attempts, int) or record.attempts < 1
                or not isinstance(record.fields, dict)
                or any(not isinstance(k, str) or not isinstance(v, str) for k, v in record.fields.items())
                or not isinstance(record.blocks, list)
                or any(not isinstance(block, dict) or set(block) != {"label", "value"}
                       or any(not isinstance(v, str) for v in block.values()) for block in record.blocks)
                or not isinstance(record.issues, list)
                or any(not isinstance(issue, str) for issue in record.issues)
                or (record.status == "ok" and record.issues)):
            raise ValueError("Checkpoint contains an invalid record.")
        if record.requested_url in records:
            raise ValueError("Checkpoint contains duplicate requested URLs.")
        records[record.requested_url] = record
    return records


@contextmanager
def output_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ".run.lock"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError("This output directory is locked. See docs/operations.md.") from exc
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)
