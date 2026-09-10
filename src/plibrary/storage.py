from __future__ import annotations

import csv
from pathlib import Path
from threading import Lock

from .models import MeasurementResult


class ResultStore:
    HEADERS = ["측정일시", "공급처", "도서명", "소요시간(초)", "상태", "비고"]

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or (Path.home() / "Documents" / "PLibrary")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.base_dir / "measurements.csv"
        self._lock = Lock()

    def append(self, result: MeasurementResult) -> Path:
        with self._lock:
            new_file = not self.csv_path.exists()
            with self.csv_path.open("a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                if new_file:
                    writer.writerow(self.HEADERS)
                writer.writerow([
                    result.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                    result.provider,
                    result.book_title,
                    f"{result.elapsed_seconds:.3f}",
                    result.status,
                    result.note,
                ])
        return self.csv_path
