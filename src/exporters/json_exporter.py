import json
from datetime import datetime
from pathlib import Path

from ..models import ScanResult


def _serialize_value(obj):
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def export_json(result: ScanResult, output: Path) -> None:
    metadata = {
        "target_path": str(result.target_path),
        "scan_time": result.scan_time.isoformat(),
        "duration_seconds": result.duration_seconds,
    }

    files = [
        {
            "path": str(f.path),
            "name": f.name,
            "size": f.size,
            "size_human_readable": f.size_human_readable,
            "modified_time": f.modified_time.isoformat(),
            "created_time": f.created_time.isoformat() if f.created_time else None,
            "is_directory": f.is_directory,
            "extension": f.extension,
            "depth": f.depth,
        }
        for f in result.files
    ]

    summary = {
        "total_files": result.total_files,
        "total_directories": result.total_directories,
        "total_size": result.total_size,
        "total_size_human_readable": result.total_size_human_readable,
        "average_file_size": result.average_file_size,
    }

    report = {"metadata": metadata, "files": files, "summary": summary}

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=_serialize_value)
