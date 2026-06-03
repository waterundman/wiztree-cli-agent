# WizTree CLI Agent — Architecture

## Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    WizTree CLI Agent                          │
│                                                              │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│    │ Scanner  │───▶│ Analyzer │───▶│  Safety  │             │
│    │ 扫描模块  │    │ 分析模块  │    │ 安全模块  │             │
│    └────┬─────┘    └────┬─────┘    └────┬─────┘             │
│         │               │               │                    │
│         ▼        ┌──────┴──────┐        ▼                    │
│    ┌─────────┐  ▼             ▼   ┌─────────┐              │
│    │WizTree  │ ┌──────────┐ ┌────┐ │Blocklist│              │
│    │  CLI    │ │ LLMRouter│ │Rule│ │AuditLog │              │
│    └─────────┘ │ 6 Prov.  │ │Eng.│ │FileValid│              │
│                └──────────┘ └────┘ │Confirm  │              │
│                                    └─────────┘              │
└──────────────────────────────────────────────────────────────┘
```

## Core Modules

### 1. Scanner (`src/scanner/`)

| File | Description |
|------|-------------|
| `interface.py` | `ScannerInterface` — abstract base class |
| `wiztree_scanner.py` | `WizTreeScanner` — WizTree CLI wrapper (MFT scan, CSV parse, scan cache) |
| `path_validator.py` | `PathValidator` — path existence, permissions, system directory checks |
| `scan_progress.py` | `ScanProgress` — progress callback, cancellation support |
| `deep_search.py` | `DeepSearcher` — recursive folder scan, pattern search, large file search |
| `options.py` | `ScanOptions` — max depth, min size, exclude patterns |

### 2. Analyzer (`src/analyzer/`)

| File | Description |
|------|-------------|
| `interface.py` | `AnalyzerInterface` — abstract base class |
| `llm_analyzer.py` | `LLMAnalyzer` — LLM-based analysis with lazy init (596 lines) |
| `llm_router.py` | `LLMRouter` — multi-Provider router v1.5.0 (1241 lines) |
| `json_parser.py` | `StreamingJsonParser` — streaming JSON parser (253 lines) |
| `rule_engine.py` | `RuleEngine` — 10 predefined rules as LLM fallback (279 lines) |
| `model_catalog.py` | `ModelCatalog` — OpenRouter model catalog (396 lines) |
| `prompt_store.py` | `PromptStore` — prompt file manager (244 lines) |

### 3. Safety (`src/safety/`)

| File | Description |
|------|-------------|
| `interface.py` | `SafetyInterface` — abstract base (245 lines) |
| `blocklist.py` | 38 protected system paths (226 lines) |
| `audit_logger.py` | SQLite audit log with restore capability (804 lines) |
| `file_validator.py` | File existence, lock, permission checks (328 lines) |
| `confirm_dialog.py` | User confirmation dialog (379 lines) |
| `__init__.py` | `ComprehensiveSafetyManager` (292 lines) |

### 4. UI (`src/ui/`)

| File | Description |
|------|-------------|
| `main_window.py` | Main GUI window (1202 lines) |
| `settings_dialog.py` | Settings dialog (300 lines) |
| `keybindings.py` | 5 keyboard shortcuts (96 lines) |
| `config_panel.py` | Configuration panel (16 lines) |
| `results_view.py` | Results view (17 lines) |
| `file_table.py` | File operation table (21 lines) |
| **Components** | |
| `components/treemap_view.py` | Matplotlib treemap widget (455 lines) |
| `components/squarify.py` | Pure-Python squarified treemap (320 lines) |
| `components/drill_down.py` | Treemap drill-down controller (263 lines) |
| `components/virtual_treeview.py` | Virtual scrolling Treeview (177 lines) |
| `components/skeleton.py` | Skeleton loading screen (197 lines) |
| `components/status_bar.py` | Bottom status bar (186 lines) |
| **Tabs** | |
| `tabs/diff_preview.py` | Before/after diff preview (298 lines) |
| `tabs/history_tab.py` | Audit history + restore (566 lines) |
| `tabs/models_tab.py` | Model browser (414 lines) |
| `tabs/prompts_tab.py` | Prompt editor (405 lines) |
| **Themes** | |
| `themes/modern_theme.py` | 6-theme manager (451 lines) |
| **Animations** | |
| `animations/smooth_progress.py` | 60fps progress bar + spinner (84 lines) |

### 5. Models (`src/models/`)

| File | Description |
|------|-------------|
| `file_info.py` | `FileInfo` dataclass with `__slots__` (52 lines) |
| `scan_result.py` | `ScanResult` dataclass (55 lines) |
| `analysis_result.py` | `AnalysisResult`, `RiskLevel` enum (76 lines) |

### 6. Utils (`src/utils/`)

| File | Description |
|------|-------------|
| `config_loader.py` | 3-tier cascading config loader (737 lines) |
| `credential_store.py` | OS keyring credential wrapper (238 lines) |

## Entry Points

| File | Description |
|------|-------------|
| `app.py` | GUI application entry (140 lines) |
| `cli.py` | CLI entry — interactive, batch, scriptable mode (403 lines) |
| `build.py` | PyInstaller build script (210 lines) |

## Data Flow

```
User Input (CLI/GUI)
    │
    ▼
Scanner ──▶ WizTree CLI ──▶ CSV output ──▶ FileInfo[]
    │
    ▼
Analyzer ──▶ LLMRouter (if API key available)
    │            └── LatencyProbe + WeightedRouter + Circuit Breaker
    │         OR RuleEngine (fallback, no API key needed)
    │
    ▼
Safety ──▶ Blocklist check ──▶ FileValidator ──▶ AuditLogger
    │                                                    │
    ▼                                                    ▼
User Confirm Dialog ──▶ send2trash (soft delete) ──▶ Audit Record
```

## Directory Tree

```
wiztree-cli-agent/
├── app.py                          # GUI entry
├── cli.py                          # CLI entry (scriptable, batch)
├── build.py                        # PyInstaller builder
├── audit.db                        # SQLite audit log (runtime)
├── requirements.txt                # Python dependencies
├── WizTreeCLIAgent.spec            # PyInstaller spec
├── run_cli.bat                     # CLI launcher
├── run_gui.bat                     # GUI launcher
├── config/
│   └── llm_config.json             # LLM Router config
├── docs/                           # ← consolidated documentation
├── src/
│   ├── __init__.py                 # Package, __version__ = "1.5.0"
│   ├── scanner/                    # 6 files
│   ├── analyzer/                   # 7 files
│   ├── safety/                     # 6 files
│   ├── ui/                         # 16 files (components/ tabs/ themes/ animations/)
│   ├── models/                     # 3 files
│   └── utils/                      # 2 files
└── tests/                          # ~30 test files
```

## Key Features by Version

| Version | Features |
|---------|----------|
| 1.0.0 | Core: Scanner + Analyzer + Safety, LLM Router (6 providers, 4 strategies), RuleEngine (10 rules), Blocklist (38 paths) |
| 1.1.0 | UI: Theme system, smooth progress bar, stats cards, responsive layout, file table |
| 1.2.0 | Security: Credential store, 6 dark themes, keyboard shortcuts, drag-drop, audit history+restore, diff preview, squarified treemap, 3-tier config, models/prompts tabs |
| 1.3.0 | UX: Skeleton screen, theme switching callbacks, ttk style integration |
| 1.4.0 | Performance: Virtual scrolling, `__slots__` memory optimization, scan cache (1h TTL), CSV streaming parser |
| 1.5.0 | Routing: LatencyProbe, WeightedRouter, batch_chat, RequestCoalescer; CLI: --quiet/--json/--no-color, exit codes, --batch, JSON/CSV export |

## File Inventory

| Category | Count |
|----------|-------|
| Source files (.py) | ~35 |
| Test files | ~30 |
| Config files | 2 |
| Documentation | 5 (consolidated) |
| Batch files | 2 |
| **Total** | **~75** |

## Dependencies

```
customtkinter>=5.2.0   # GUI framework
openai>=1.0.0          # LLM API client
send2trash>=1.8.0      # Safe delete (recycle bin)
matplotlib>=3.7.0      # Visualization
squarify>=0.4.3        # Treemap (legacy; bundled pure-Python impl used)
keyring>=24.0.0        # OS credential storage
requests>=2.28.0       # HTTP client
tkinterdnd2>=0.4.2     # Drag & drop (graceful fallback)
pytest>=7.4.0          # Testing
pytest-cov>=4.0.0      # Coverage
```
