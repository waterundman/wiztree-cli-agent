import csv
from pathlib import Path

from ..models import ScanResult

CSV_HEADERS = [
    "path",
    "name",
    "size",
    "size_human_readable",
    "modified_time",
    "created_time",
    "is_directory",
    "extension",
    "depth",
]


def export_csv(result: ScanResult, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for file_info in result.files:
            writer.writerow(
                {
                    "path": str(file_info.path),
                    "name": file_info.name,
                    "size": file_info.size,
                    "size_human_readable": file_info.size_human_readable,
                    "modified_time": file_info.modified_time.isoformat(),
                    "created_time": (
                        file_info.created_time.isoformat()
                        if file_info.created_time
                        else ""
                    ),
                    "is_directory": file_info.is_directory,
                    "extension": file_info.extension or "",
                    "depth": file_info.depth,
                }
            )
