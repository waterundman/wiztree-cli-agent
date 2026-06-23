<p align="center">
  <img src="docs/logo.png" alt="WizTree CLI Agent" width="120"/>
</p>

<h1 align="center">WizTree CLI Agent</h1>

<p align="center">
  <strong>AI-Powered Disk Cleanup Assistant</strong>
  <br />
  Intelligent file analysis · Multi-LLM routing · Human-in-the-loop safety
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/version-2.1.0-blue.svg" alt="Version 2.1.0"/></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+"/></a>
  <a href="#"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"/></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-666%20passed-green.svg" alt="Tests 666 passed"/></a>
  <a href="#"><img src="https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macos-lightgrey.svg" alt="Platform"/></a>
</p>

<p align="center">
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.zh-CN.md">🇨🇳 中文</a> &nbsp;|&nbsp;
  <a href="README.fr-FR.md">🇫🇷 Français</a> &nbsp;|&nbsp;
  <a href="README.de-DE.md">🇩🇪 Deutsch</a> &nbsp;|&nbsp;
  <a href="README.ja-JP.md">🇯🇵 日本語</a> &nbsp;|&nbsp;
  <a href="README.ru-RU.md">🇷🇺 Русский</a>
</p>

---

## Project Overview

**WizTree CLI Agent** is an AI-driven disk cleanup assistant that wraps the lightning-fast [WizTree CLI](https://www.diskanalyzer.com/) scanner with a **multi-LLM Provider routing system** for intelligent file analysis and safe human-in-the-loop file cleanup.

Instead of blindly deleting files based on simple rules, it leverages Large Language Models to understand *what* each file is, *why* it exists, and *whether* it can be safely removed — all while keeping you in control with a confirmation gate, path blocklist, and full audit trail.

No API key? No problem. The built-in **RuleEngine** with 10 predefined cleanup rules works offline, and the **lazy initialization** pattern means the app runs even when no LLM provider is configured.

---

## What's New in v2.1.0

### GUI Now Supports LLM Analysis
The GUI now uses **LLM-first analysis** with automatic RuleEngine fallback. Select a model from the dropdown, and the AI Analysis tab shows streaming LLM results in real-time. No API key? It transparently falls back to the built-in RuleEngine.

### Architecture Overhaul
- **MainWindow** refactored from 1765 lines to 762 lines (↓57%) via MVC-style controller extraction
- **ScanController** — manages WizTree scanner lifecycle and streaming
- **AnalysisController** — manages LLM/RuleEngine analysis with streaming callbacks
- **FileOperationController** — manages file deletion, restore, and audit logging
- **llm_router.py** split from 1378 lines into 4 focused modules: `circuit_breaker.py`, `latency_probe.py`, `request_coalescer.py`, `batch.py`

### Bug Fixes
- Fixed `NameError` in `app.py` when LLM router is not configured
- Fixed missing `WizTreeAgentApp` import in `cli.py`
- Unified `FileInfo` naming conflict between `models` and `safety` modules
- Version numbers aligned to 2.1.0 across all files

---

## Key Features

### 🔬 WizTree CLI Integration
- MFT (Master File Table) accelerated scan via WizTree — scan an entire drive in seconds
- CSV output parsing with streaming parser for minimal memory footprint
- Configurable scan options: depth limits, min file size, exclude patterns
- Scan cache with 1-hour TTL to avoid redundant rescans
- Deep recursive folder search with pattern matching and large file discovery

### 🤖 Intelligent LLM Router
- **6 providers**: DeepSeek, OpenAI, Anthropic, OpenRouter, SiliconFlow, Ollama
- **4 routing strategies**: cost-first, latency-first, fallback, manual
- **Circuit Breaker** pattern: CLOSED → OPEN (after 3 failures) → HALF_OPEN (after 60s recovery)
- **LatencyProbe**: background thread that continuously pings providers to track real-time latency
- **WeightedRouter**: dynamic weight-based routing scoring latency, success rate, and cost
- **RequestCoalescer**: deduplicates identical concurrent requests into a single API call
- **batch_chat**: parallel multi-request execution with configurable worker count

### ⚙️ RuleEngine Fallback
- 10 predefined rules covering temp files, cache, logs, downloads, installers, archives, and more
- Works entirely offline — no API key required
- Risk-level scoring (LOW / MEDIUM / HIGH / CRITICAL) with confidence and size thresholds
- Extensible: add custom rules at runtime

### 🛡️ Multi-Layer Safety
- **Blocklist**: 38 protected system paths (Windows System32, Program Files, etc.) with wildcard and regex matching
- **AuditLogger**: all destructive operations recorded in SQLite with full context (path, size, timestamp, action type)
- **Restore capability**: revert `file_delete` and `file_move` operations from the History tab
- **FileValidator**: checks existence, lock status, permissions before any operation
- **ConfirmDialog**: always requires manual user confirmation before deletion
- **Recycle bin**: uses `send2trash` to move files to the system recycle bin instead of permanent deletion

### 🎨 Modern GUI
- **6 dark themes**: Steam Dark, Catppuccin Mocha, OLED Black, GitHub Dark, Nord, Dracula — switchable at runtime
- **Squarified Treemap**: visualize disk usage with pure-Python Bruls et al. (2000) algorithm
- **Drill-down navigation**: click treemap cells to navigate into subdirectories
- **Skeleton screen**: loading placeholder for perceived performance
- **SmoothProgressBar**: 60fps progress animation with spinner indicator
- **Keyboard shortcuts**: Ctrl+S (scan), Ctrl+R (refresh), Ctrl+L (clear), Ctrl+, (settings), Esc (cancel)
- **Drag & drop**: drop folders/files onto the window via `tkinterdnd2` (graceful fallback if unavailable)
- **Model & Prompt tabs**: browse the model catalog and edit system prompts without leaving the GUI
- **Diff preview**: inspect file details (size, mtime, path) before confirming destructive actions

### 🖥️ CLI & Scriptability
- **Interactive mode**: shell-like REPL with `scan`, `analyze`, `show`, `validate`, `exit` commands
- **Batch scan**: scan multiple directories in one pass with `--batch DIR1 DIR2`
- **Quiet mode**: `--quiet` / `-q` suppresses all non-result output for scripting
- **JSON output**: `--json` outputs results as structured JSON for programmatic consumption
- **Exit codes**: `0` success, `1` error, `2` warning (e.g., when high-risk files are found)

### ⚡ Performance
- **Virtual scrolling**: `VirtualTreeview` only renders visible rows for huge file lists
- **`__slots__` memory optimization**: `FileInfo` uses `__slots__` to reduce memory overhead per file
- **Scan cache**: cached results expire after 1 hour; repeated scans of the same directory return instantly
- **Streaming CSV parser**: processes WizTree CSV output line-by-line without loading the entire file into memory

---

## Architecture (v2.1.0)

```
┌──────────────────────────────────────────────────────────────────┐
│                      WizTree CLI Agent                           │
│                                                                  │
│    ┌──────────┐     ┌──────────┐     ┌──────────┐              │
│    │ Scanner  │────▶│ Analyzer │────▶│  Safety  │              │
│    └────┬─────┘     └────┬─────┘     └────┬─────┘              │
│         │                │                 │                     │
│         ▼         ┌──────┴──────┐         ▼                     │
│    ┌─────────┐   ▼             ▼    ┌──────────┐               │
│    │WizTree  │ ┌──────────┐ ┌──────┐ │Blocklist │               │
│    │  CLI    │ │ LLMRouter │ │Rule  │ │AuditLog  │               │
│    └─────────┘ │CircuitBrk │ │Engine│ │FileValid │               │
│                │LatencyPrb │ │10 rls│ │Confirm   │               │
│                │ReqCoalesc │ └──────┘ └──────────┘               │
│                │Weighted   │                                     │
│                └──────────┘                                     │
│                                                                  │
│    ┌─────────────────────────────────────────────┐              │
│    │              UI Layer (v2.1.0)               │              │
│    │  MainWindow (762 lines)                      │              │
│    │    ├── ScanController (331 lines)            │              │
│    │    ├── AnalysisController (163 lines)        │              │
│    │    └── FileOperationController (92 lines)    │              │
│    └─────────────────────────────────────────────┘              │
└──────────────────────────────────────────────────────────────────┘
```

### Module Overview

| Module | Directory | Description |
|--------|-----------|-------------|
| **Scanner** | `src/scanner/` | WizTree CLI wrapper, path validation, deep search, scan progress, scan cache, streaming scanner |
| **Analyzer** | `src/analyzer/` | LLM Router (6 providers, 4 strategies), Circuit Breaker, Latency Probe, Request Coalescer, Batch, RuleEngine (10 rules), Streaming JSON parser, model catalog, prompt store |
| **Safety** | `src/safety/` | Blocklist (38 paths), SQLite audit log with restore, file validator (ValidationFileInfo), confirmation dialog |
| **UI** | `src/ui/` | MainWindow + 3 controllers, treemap, virtual treeview, skeleton screen, 6 themes, keyboard shortcuts, drag & drop, smooth progress bar, diff preview, history tab, model/prompt browsers |
| **Models** | `src/models/` | `FileInfo`, `ScanResult`, `AnalysisResult` / `RiskLevel` dataclasses |
| **Utils** | `src/utils/` | 3-tier cascading config loader, OS keyring credential store |

---

## Quick Start

### Prerequisites

- Python 3.10 or later
- [WizTree](https://www.diskanalyzer.com/download) CLI (the `WizTree64.exe` or `WizTree` binary)

### Installation

```bash
git clone https://github.com/waterundman/wiztree-cli-agent.git
cd wiztree-cli-agent
pip install -r requirements.txt
```

### Usage

```bash
# GUI mode (requires tkinter)
python app.py

# CLI mode — module check
python app.py --cli

# Scan a directory and analyze results
python cli.py --scan "C:\Users" --analyze

# Interactive CLI shell
python cli.py --interactive

# Batch scan multiple directories
python cli.py --batch "C:\Users\Downloads" "D:\Temp" --analyze --json

# Quiet batch scan with JSON output (for scripting)
python cli.py --batch-file dirs.txt --analyze --json --quiet
```

### Build Standalone Executable

```bash
python build.py
```

This produces a portable `.exe` in the `dist/` directory using PyInstaller. No Python installation needed on the target machine.

---

## Download

Pre-built binaries are available on the [Releases](https://github.com/waterundman/wiztree-cli-agent/releases) page:

| Package | Description |
|---------|-------------|
| `WizTreeCLIAgent-v2.1.0-win64.zip` | Windows 64-bit portable executable |

---

## LLM Router

### Supported Providers

| Provider | Environment Variable | Base URL | Free Models | Tags |
|----------|-------------------|----------|-------------|------|
| **DeepSeek** | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` | `deepseek-v4-flash` | cost, thinking, china |
| **OpenAI** | `OPENAI_API_KEY` | `https://api.openai.com/v1` | — | general, vision |
| **Anthropic** | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` | — | core, reasoning |
| **OpenRouter** | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | `gemini-2.0-flash-exp:free` | aggregator, fallback |
| **SiliconFlow** | `SILICONFLOW_API_KEY` | `https://api.siliconflow.cn/v1` | `DeepSeek-V3`, `Qwen2.5-7B` | free, china, fallback |
| **Ollama** | — (local) | `http://localhost:11434/v1` | `llama3.2`, `qwen2.5` | local, free, fallback |

### Circuit Breaker

```
CLOSED (normal operation)
    │  3 consecutive failures
    ▼
OPEN (rejects all requests)
    │  60 seconds timeout
    ▼
HALF_OPEN (allows one test request)
    │  success → CLOSED  │  failure → OPEN
```

### Code Example

```python
from src.analyzer import LLMRouter, RoutingStrategy, WeightedRouter, batch_chat, BatchRequest

# Basic router with fallback strategy
router = LLMRouter(
    strategy=RoutingStrategy.FALLBACK,
    default_model="deepseek-v4-flash"
)

# Chat
response = router.chat(
    messages=[{"role": "user", "content": "Suggest files to clean in C:\\Users"}],
    model="deepseek-v4-flash"
)

# Advanced: WeightedRouter with latency probe
wrouter = WeightedRouter(
    strategy=RoutingStrategy.COST,
    enable_probe=True,
    weights={"latency": 0.4, "success": 0.3, "cost": 0.3}
)

# Batch parallel requests
results = batch_chat(wrouter, [
    BatchRequest(messages=[{"role": "user", "content": msg}])
    for msg in ["Analyze Downloads", "Analyze Temp"]
], max_workers=2)
```

---

## Configuration

### API Keys

Set environment variables or use the built-in secure credential store (OS keyring):

```bash
# Windows
set DEEPSEEK_API_KEY=sk-your-key-here

# Linux / macOS
export DEEPSEEK_API_KEY=sk-your-key-here
```

**No API key needed?** The application auto-detects missing keys and gracefully degrades to the RuleEngine — no configuration required.

### Secure Credential Storage

API keys can be stored via the OS credential manager using `keyring`:

- **Windows**: Windows Credential Manager (DPAPI encrypted)
- **macOS**: macOS Keychain
- **Linux**: Secret Service (libsecret)

```python
from src.utils.credential_store import CredentialStore
CredentialStore.store_api_key("deepseek", "sk-xxx")
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src -v
```

### Test Statistics (v2.1.0)

| Metric | Count |
|--------|-------|
| Test files | ~48 |
| Total test cases | 666 passed |
| Integration scenarios | 19+ |
| UI tests | Theme switching, skeleton, keybindings, treemap, diff preview, history, controllers |

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| **2.1.0** | 2026-06-23 | **GUI LLM analysis integration**, MainWindow controller extraction (1765→762 lines), llm_router.py module split (1378→973 lines), 6 bug fixes, 666 tests |
| **2.0.0** | 2026-06-13 | Stability: SQLite WAL mode, CircuitBreaker thread safety, memory leak fix, subprocess cleanup, exception handling, cache atomic write |
| **1.9.0** | 2026-06-12 | Streaming scanner, memory optimization, batch navigation, batch cache |
| **1.8.0** | 2026-06-11 | Code quality: 72 `except Exception: pass` eliminated, 53 new tests |
| **1.5.0** | 2026-06-04 | LatencyProbe, WeightedRouter, batch_chat, RequestCoalescer, CLI enhancements |
| **1.4.0** | 2026-06-03 | Virtual scrolling, `__slots__` memory optimization, scan cache |
| **1.3.0** | 2026-06-02 | Skeleton screen, theme switching callbacks |
| **1.2.0** | 2026-06-01 | Secure credential store, 6 dark themes, keyboard shortcuts, drag & drop, audit history, treemap |
| **1.1.0** | 2026-06-01 | Modern theme system, smooth progress bar, stats cards |
| **1.0.0** | 2026-05-31 | Core scanner + analyzer + safety, LLM Router, RuleEngine |

---

## License

**MIT License** — Copyright (c) 2026 WizTree CLI Agent

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

<p align="center">
  <sub>Built with ❤️ using Python, customtkinter, and LLMs.</sub>
</p>
