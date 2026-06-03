# WizTree CLI Agent — API Reference

## `src.analyzer`

### `LLMRouter`

Multi-Provider LLM router with smart routing, circuit breaker, and dynamic routing.

```python
from src.analyzer import LLMRouter, RoutingStrategy

router = LLMRouter(
    strategy=RoutingStrategy.FALLBACK,  # COST | LATENCY | FALLBACK | MANUAL
    default_model="deepseek-v4-flash"
)
```

**Key Methods**:
| Method | Description |
|--------|-------------|
| `chat(messages, model, **kwargs)` | Send chat completion request |
| `chat_stream(messages, model, **kwargs)` | Stream chat completion |
| `batch_chat(requests, max_workers)` | Parallel batch requests |
| `set_strategy(strategy)` | Switch routing strategy at runtime |
| `get_provider_status()` | Get status of all providers |
| `get_available_models()` | List available models |
| `clear_cache()` | Clear scan cache |

**v1.5.0 Additions**:
- `LatencyProbe` — real-time latency measurement with sliding window
- `WeightedRouter` — weighted score = latency + success_rate + cost
- `RequestCoalescer` — deduplicates identical in-flight requests
- Circuit Breaker: CLOSED → OPEN (3 failures) → HALF_OPEN (60s recovery)

### `LLMAnalyzer`

```python
from src.analyzer import LLMAnalyzer

analyzer = LLMAnalyzer(router=llm_router)
result = analyzer.analyze(file_infos)  # Lazy init: auto-degrade to RuleEngine
```

### `RuleEngine`

10 predefined cleanup rules, no API key needed.

| Rule | Category |
|------|----------|
| Temporary files | `*.tmp`, `~$*` |
| Cache files | Browser caches, `__pycache__`, `.cache` |
| Log files | `*.log` |
| Installers | `*.msi`, `*.exe` (non-system) |
| Media files | Large media files |
| Documents | Recycle/docs |
| ... | 4 more rules |

### `StreamingJsonParser`

```python
from src.analyzer import StreamingJsonParser
parser = StreamingJsonParser()
chunk = parser.feed(chunk_text)  # incremental parse
```

---

## `src.scanner`

### `WizTreeScanner`

```
WizTreeScanner(wiztree_path="W:\\WizTree\\WizTree64.exe")
```

| Method | Description |
|--------|-------------|
| `scan(path, options)` | Scan directory or drive |
| `scan_batch(paths)` | Scan multiple directories, merge results |
| `scan_with_cache(path, options)` | Transparent cache layer (1h TTL) |
| `clear_cache()` | Clear scan cache |
| `_parse_csv_streaming()` | CSV streaming parser (generator) |

### `DeepSearcher`

```python
from src.scanner import DeepSearcher
searcher = DeepSearcher()
results = searcher.search(pattern="*.log", root_dir="C:\\Users")
```

### `PathValidator`

```python
PathValidator.validate_path("C:\\path")      # → (is_valid, error_msg)
PathValidator.is_system_directory("C:\\Windows\\System32")  # → True
```

### `ScanOptions`

```python
ScanOptions(
    max_depth=10,
    min_size_bytes=1024,
    exclude_patterns=["*.sys", "*.dll"]
)
```

---

## `src.safety`

### `ComprehensiveSafetyManager`

```python
from src.safety import ComprehensiveSafetyManager
manager = ComprehensiveSafetyManager()
result = manager.validate_deletion(file_infos)
```

### `Blocklist`

38 protected system paths. Methods: `is_blocked(path)`, `add_path(path)`, `remove_path(path)`.

### `AuditLogger`

SQLite audit log with restore capability.

| Method | Description |
|--------|-------------|
| `log(action_type, target_path, status, metadata, user)` | Write audit record |
| `restore(action_id)` | Reverse file_delete or file_move |
| `list_recent(limit, action_type)` | Read recent records |
| `get_stats()` | Total / by_type / by_status / recent_24h |
| `record_trash(original_path, deleted_path, size)` | Register soft-delete |
| `list_trash(original_path, limit)` | List soft-delete entries |

### `FileValidator`

```python
FileValidator.validate("C:\\path\\file.txt")
# → (is_valid, error_msg, warnings)
```

---

## `src.models`

### `FileInfo`

```python
@dataclass(slots=True)
class FileInfo:
    path: str
    size: int
    modified: datetime
    is_directory: bool = False
    # ~30% memory reduction vs __dict__
```

### `ScanResult`

```python
@dataclass
class ScanResult:
    files: list[FileInfo]
    total_size: int
    scan_time: float
    file_count: int
```

### `AnalysisResult`

```python
@dataclass
class AnalysisResult:
    recommendations: list[DeletionRecommendation]
    total_savings: int
    risk_level: RiskLevel  # LOW | MEDIUM | HIGH | CRITICAL
```

---

## `src.ui`

### `MainWindow`

Main GUI window (1202 lines). Integrates all components:
- Config panel (left)
- Tab view with 5 tabs (Scan Results, AI Analysis, File Actions, History, Models, Prompts)
- Status bar (bottom)
- Skeleton screens, treemap visualization

### `ModernTheme`

```python
ModernTheme.apply("Catppuccin Mocha")  # 6 themes
ModernTheme.list_themes()
ModernTheme.get_current()
ModernTheme.on_theme_change(callback)  # register callbacks
```

### `KeyBindings`

```python
KeyBindings.bind_all(window)
# Ctrl+S (scan), Ctrl+R (refresh), Ctrl+L (clear),
# Ctrl+, (settings), Esc (cancel)
```

### UI Components

| Component | Description |
|-----------|-------------|
| `TreemapView` | Matplotlib treemap with drill-down |
| `Squarify` | Pure-Python squarified treemap (Bruls et al. 2000) |
| `DrillDownController` | Drill-down on treemap blocks |
| `VirtualTreeview` | Virtualized Treeview for 10000+ rows |
| `SkeletonWidget` | Pulsing grey placeholder rectangles |
| `StatusBar` | Bottom status bar with scan statistics |
| `SmoothProgressBar` | 60fps smooth progress animation |

---

## `src.utils`

### `ConfigLoader`

3-tier cascading config: `override > user (~/.wiztree-cli-agent/config.json) > builtin`

```python
ConfigLoader(auto_migrate=True)
ConfigLoader.export(sanitize=True)  # strips API keys
```

### `CredentialStore`

```python
CredentialStore.store_api_key("deepseek", "sk-xxx")
CredentialStore.get_api_key("deepseek")
CredentialStore.delete_api_key("deepseek")
```

Uses OS keyring: Windows Credential Manager / DPAPI, macOS Keychain, Linux Secret Service.

---

## CLI Reference

```
python cli.py [options]

Options:
  --interactive        Interactive CLI mode
  --scan PATH          Scan directory/file
  --analyze            Analyze scan results
  --batch DIR [DIR..]  Batch scan multiple directories
  --batch-file FILE    Read directory list from file
  --json               Output results as JSON
  --csv PATH           Export results to CSV
  --quiet              Suppress info/progress output
  --no-color           Disable ANSI colors
  --help               Show help

Exit Codes:
  0  EXIT_SUCCESS
  1  EXIT_ERROR
  2  EXIT_WARNING
```
