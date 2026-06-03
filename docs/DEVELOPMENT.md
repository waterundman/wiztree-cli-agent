# WizTree CLI Agent — Development Guide

## Environment Setup

```bash
# Python 3.10+ required
pip install -r requirements.txt
```

Dependencies:
- `customtkinter>=5.2.0` — GUI framework
- `openai>=1.0.0` — LLM API client
- `send2trash>=1.8.0` — Safe delete
- `matplotlib>=3.7.0` — Visualization
- `keyring>=24.0.0` — OS credential storage
- `requests>=2.28.0` — HTTP client
- `tkinterdnd2>=0.4.2` — Drag & drop (optional, graceful fallback)
- `pytest>=7.4.0` / `pytest-cov>=4.0.0` — Testing

## Running

```bash
# CLI mode
python app.py --cli
python cli.py --interactive
python cli.py --scan "C:\Users" --analyze
python cli.py --batch "D:\Temp" "C:\Users\Downloads" --json
python cli.py --batch-file dirs.txt --csv output.csv

# GUI mode
python app.py
```

## Testing

```bash
pytest tests/ -v                                # All tests
pytest tests/test_scanner.py -v                 # Single module
pytest tests/ -v --cov=src                      # With coverage
python tests/demo_router.py                     # LLM Router demo
```

### Test Files

Unit tests in `tests/`:
- `test_scanner.py` — Scanner module
- `test_analyzer.py` — Analyzer module
- `test_safety.py` — Safety module
- `test_deep_search.py` — Deep search
- `test_models.py` — Data models
- `test_ui.py` — UI components
- `test_router.py` — LLM Router

Integration tests:
- `test_integration_v120.py` — v1.2.0 (30 tests, 5 scenarios)
- `test_integration_v130.py` — v1.3.0 (19 tests, 5 scenarios)
- `test_integration_v150.py` — v1.5.0 (18 tests, 5 scenarios)

Performance benchmarks:
- `test_performance.py` — VirtualTreeview, memory, cache, streaming (6 tests)

### Test Results (cumulative)

| Version | New Tests | Cumulative |
|---------|-----------|------------|
| v1.0.0 | 68 | 68 |
| v1.1.0 | 87 | 136 |
| v1.2.0 | 279 | 366 passed, 116 skipped |
| v1.3.0 | 19 | 400 passed |
| v1.4.0 | 6 | 434 passed |
| v1.5.0 | 18 | 452+ passed |

## Building with PyInstaller

```bash
python build.py
```

Outputs in `dist/`:
| File | Size | Description |
|------|------|-------------|
| `WizTreeCLIAgent.exe` | ~48 MB | Single executable |
| `WizTreeCLIAgent_Portable.zip` | ~48 MB | Portable package |
| `install.bat` | 510 B | Installer |

## Version History

### v1.5.0 (2026-06-04)
- **LLM Router**: LatencyProbe, WeightedRouter, batch_chat, RequestCoalescer
- **CLI Scriptable**: Exit codes, --quiet/--json/--no-color, OutputFormatter
- **Batch Scanning**: --batch, --batch-file, JSON/CSV exporters
- **Tests**: 18 new integration tests

### v1.4.0 (2026-06-03)
- Virtual scrolling (VirtualTreeview, 10000+ rows)
- Memory optimization (FileInfo `__slots__`, ~30% reduction)
- Scan cache (SHA-256 key, 1h TTL)
- CSV streaming parser (generator-based)
- 6 performance benchmarks

### v1.3.0 (2026-06-03)
- Skeleton screens (scan + AI loading states)
- Theme switching callbacks, ttk style integration
- 19 new integration tests

### v1.2.0 (2026-06-XX)
- Secure credential storage (OS keyring)
- 6 dark themes, keyboard shortcuts, drag & drop
- Audit history + restore, diff preview
- Pure-Python squarified treemap
- 3-tier cascading config
- 30 integration tests, 366 total passed

### v1.1.0 (2026-06-01)
- Modern theme system (dark/light toggle)
- Smooth progress bar (60fps), spinner loading
- Statistics cards, responsive layout
- File action table, AI result copy
- 87 UI tests

### v1.0.0 (2026-05-31)
- Initial release
- WizTree CLI wrapper, LLM Router (6 providers, 4 strategies)
- RuleEngine (10 rules), Blocklist (38 paths)
- SQLite audit log, treemap visualization
- 49 unit tests

## Coding Conventions

- **Type hints**: Required for all public APIs
- **Imports**: Standard → Third-party → Local (grouped)
- **Naming**: snake_case for functions/vars, PascalCase for classes
- **Docstrings**: Google style (`"""Summary\n\nArgs:\nReturns:\n"""`)
- **Error handling**: Custom exceptions with clear messages
- **Testing**: pytest with descriptive test names

## Architecture Guidelines

- `Scanner → Analyzer → Safety` pipeline (orchestrated by Orchestrator)
- All modules depend on interfaces (in `interface.py`) not concrete classes
- LLM Router supports lazy init: no API key → auto-degrade to RuleEngine
- All destructive operations pass through Safety module
- Audit trail for every delete/move/restore operation
