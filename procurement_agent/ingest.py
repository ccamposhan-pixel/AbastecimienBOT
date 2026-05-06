from __future__ import annotations

import csv
from pathlib import Path

from .models import RawTable


def discover_csv_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(path for path in input_path.rglob("*.csv") if path.is_file())


def read_csv(path: Path) -> RawTable:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except csv.Error:
        dialect = csv.excel

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, dialect=dialect)
        rows = [dict(row) for row in reader]

    return RawTable(source_file=str(path), rows=rows)


def load_tables(input_path: str | Path) -> list[RawTable]:
    root = Path(input_path)
    files = discover_csv_files(root)
    return [read_csv(path) for path in files]
