# WizTree CLI Agent

[![Version](https://img.shields.io/badge/version-1.5.0-blue.svg)](https://github.com/waterundman/wiztree-cli-agent)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-400%2B-passing-green.svg)](#测试)
[![Platform](https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macos-lightgrey.svg)]()

<p align="center">
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <b><a href="README.zh-CN.md">🇨🇳 中文</a></b> &nbsp;|&nbsp;
  <a href="README.fr-FR.md">🇫🇷 Français</a> &nbsp;|&nbsp;
  <a href="README.de-DE.md">🇩🇪 Deutsch</a> &nbsp;|&nbsp;
  <a href="README.ja-JP.md">🇯🇵 日本語</a> &nbsp;|&nbsp;
  <a href="README.ru-RU.md">🇷🇺 Русский</a>
</p>

> **AI 驱动的磁盘清理助手** — 封装 WizTree CLI 工具，集成多 LLM Provider 路由系统，实现智能化的文件分析和安全的人机交互式文件清理。

---

## 目录

- [项目概述](#项目概述)
- [主要功能](#主要功能)
- [截图](#截图)
- [快速开始](#快速开始)
- [下载](#下载)
- [架构设计](#架构设计)
- [LLM Router 路由系统](#llm-router-路由系统)
- [配置指南](#配置指南)
- [测试](#测试)
- [文档索引](#文档索引)
- [常见问题](#常见问题)
- [版本历史](#版本历史)
- [许可证](#许可证)
- [贡献](#贡献)

---

## 项目概述

**WizTree CLI Agent** v1.5.0 是一款开源的 AI 驱动磁盘清理工具，将 WizTree 的高速扫描能力与 LLM 智能分析相结合，提供安全、高效、可视化的文件清理体验。

### 核心理念

```
磁盘扫描 (WizTree CLI) → AI/规则分析 → 安全审核 → 手动确认 → 安全删除
```

### 适用场景

| 场景 | 说明 |
|------|------|
| 🖥️ **个人电脑清理** | 扫描 C 盘 / D 盘，智能识别临时文件、缓存、日志等 |
| 🏢 **企业批量运维** | CLI 脚本化模式，批量扫描多台机器，导出 JSON/CSV 报告 |
| ☁️ **服务器磁盘释放** | 无 GUI 环境使用 CLI 模式，规则引擎无需 API 密钥 |
| 🔒 **安全敏感环境** | 所有删除操作记录 SQLite 审计日志，支持还原 |
| 🧪 **LLM 路由测试** | 内置 6 个 Provider，4 种路由策略，方便对比测试 |

---

## 主要功能

### 🔬 WizTree CLI 集成

- 调用 WizTree CLI 进行高速磁盘扫描，支持 MFT (Master File Table) 直接读取
- 流式 CSV 解析，边扫描边处理结果
- 深度检索功能：按文件名模式、大文件、目录递归搜索
- 扫描缓存机制（1 小时 TTL），避免重复扫描

### 🤖 多 LLM Provider 路由 (LLM Router)

- **6 个内置 Provider**: DeepSeek、OpenAI、Anthropic、OpenRouter、SiliconFlow、Ollama
- **4 种路由策略**: 成本优先、速度优先、故障转移、手动选择
- **断路器模式**: 连续 3 次失败自动断开，60 秒后尝试恢复
- **延迟探测 + 加权路由**: 自动选择响应最快的 Provider
- **请求合并器**: 批量请求合并，降低 API 调用成本
- **延迟初始化**: 无 API 密钥时自动降级到规则引擎

### ⚙️ 规则引擎 (Rule Engine)

- **10 个预定义清理规则**: 临时文件、浏览器缓存、系统日志、回收站、下载文件夹、Windows 更新缓存、.NET 程序集缓存、Thumbs.db、安装包缓存、Docker 构建缓存
- **零依赖**: 无需 API 密钥即可使用
- **LLM 降级方案**: API 不可用时自动切换

### 🛡️ 安全机制

| 机制 | 说明 |
|------|------|
| 🚫 **路径黑名单** | 38 个受保护系统路径（Windows\System32、Program Files 等）|
| 📝 **审计日志** | 所有破坏性操作记录到 SQLite，支持按类型/状态统计 |
| 🔍 **文件验证器** | 删除前检查文件是否存在、是否被锁定、权限校验 |
| 📋 **确认对话框** | 显示文件大小、修改时间、风险等级，用户手动审核后才执行 |
| ♻️ **回收站优先** | 优先使用 send2trash 移至回收站，支持还原 |
| 🔐 **凭据安全存储** | API 密钥通过 OS keyring 存储（Windows DPAPI / macOS Keychain / Linux Secret Service）|

### 🎨 GUI 界面

- **6 种暗色主题**: Steam Dark、Catppuccin Mocha、OLED Black、GitHub Dark、Nord、Dracula
- **Treemap 可视化**: 纯 Python 实现的 Squarified Treemap（Bruls et al. 2000 算法），支持逐级下钻
- **虚拟滚动**: 高性能 Treeview，支持万级文件列表
- **骨架屏加载**: 扫描和分析时的骨架屏占位动画
- **60fps 平滑进度条**: 流畅的扫描进度动画
- **统计信息卡片**: 实时显示文件数量、总大小、扫描时长
- **键盘快捷键**: Ctrl+S 扫描 / Ctrl+R 刷新 / Ctrl+L 清空 / Ctrl+, 设置 / Esc 取消
- **拖放支持**: 拖放文件夹到窗口，自动填入深度检索路径
- **Diff 预览**: 删除前显示文件变更对比
- **模型浏览器**: 浏览 OpenRouter 模型目录
- **提示词编辑器**: 在 GUI 中编辑 LLM 提示词

### ⌨️ CLI 脚本模式

- **交互模式**: 逐步引导的操作界面
- **批量扫描**: `--batch` 参数支持批量扫描多个路径
- **JSON/CSV 导出**: 分析结果导出为结构化数据
- **退出码**: 标准退出码，适合 CI/CD 集成
- **静默模式**: `--quiet` 减少输出，`--json` JSON 格式输出
- **无颜色模式**: `--no-color` 禁用 ANSI 颜色

### ⚡ 性能优化

- **虚拟滚动**: 仅渲染可视区域的行，支持万级文件流畅浏览
- **扫描缓存**: 1 小时 TTL 扫描结果缓存
- **流式 CSV 解析**: 逐行解析，无需等待全量加载
- **`__slots__` 内存优化**: FileInfo 数据类使用 `__slots__` 减少内存占用
- **延迟导入**: 按需加载模块，加速启动

---

## 截图

![WizTree CLI Agent](docs/screenshot.png)

*图注: WizTree CLI Agent 主界面 — 左侧配置面板、右侧结果视图、底部状态栏*

---

## 快速开始

### 环境要求

- **Python**: 3.10 或更高版本
- **操作系统**: Windows 10+ / Linux / macOS
- **WizTree**: 可选但推荐（[官网下载](https://diskanalyzer.com/download)）
- **tkinter**: GUI 模式需要（通常 Python 自带）

### 安装

```bash
# 克隆仓库
git clone https://github.com/waterundman/wiztree-cli-agent.git
cd wiztree-cli-agent

# 安装依赖
pip install -r requirements.txt
```

### 运行

```bash
# CLI 模式（无需 API 密钥，自动使用规则引擎）
python app.py --cli

# CLI 交互模式
python cli.py --interactive

# 扫描并分析
python cli.py --scan "C:\Users" --analyze

# 批量扫描多个路径并导出 JSON
python cli.py --batch "C:\Users,D:\Data" --export-json report.json

# GUI 模式（需要 tkinter）
python app.py
```

### Windows 快捷方式

项目根目录提供了便捷启动脚本：

- `run_cli.bat` — 双击启动 CLI 模式
- `run_gui.bat` — 双击启动 GUI 模式

---

## 下载

### 预编译可执行文件 (Windows)

从 [GitHub Releases](https://github.com/waterundman/wiztree-cli-agent/releases) 页面下载：

| 包类型 | 文件 | 说明 |
|--------|------|------|
| 🖥️ **安装版** | `WizTreeCLIAgent_v1.5.0_Setup.exe` | 自动安装，含开始菜单快捷方式 |
| 📦 **便携版** | `WizTreeCLIAgent_v1.5.0_Portable.zip` | 解压即用，不写注册表 |

> **提示**: 便携版可以放在 U 盘中携带使用。

### 从源码运行

参见上方 [快速开始](#快速开始) 章节。

---

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    WizTree CLI Agent                              │
│                                                                   │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│    │ Scanner  │───▶│ Analyzer │───▶│  Safety  │                  │
│    │ 扫描模块  │    │ 分析模块  │    │ 安全模块  │                  │
│    └────┬─────┘    └────┬─────┘    └────┬─────┘                  │
│         │               │               │                         │
│         ▼        ┌──────┴──────┐        ▼                         │
│    ┌─────────┐  ▼             ▼   ┌─────────┐                    │
│    │WizTree  │ ┌──────────┐ ┌────┐ │Blocklist│                    │
│    │  CLI    │ │ LLMRouter│ │Rule│ │AuditLog │                    │
│    └─────────┘ │ 6 Prov.  │ │Eng.│ │FileValid│                    │
│                └──────────┘ └────┘ │Confirm  │                    │
│                                    └─────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

### 数据流

```
用户输入 (CLI/GUI)
    │
    ▼
Scanner ──▶ WizTree CLI ──▶ CSV 输出 ──▶ FileInfo[]
    │
    ▼
Analyzer ──▶ LLMRouter (API 密钥可用时)
    │            └── LatencyProbe + WeightedRouter + Circuit Breaker
    │         或 RuleEngine (降级方案，无需 API 密钥)
    │
    ▼
Safety ──▶ Blocklist 检查 ──▶ FileValidator ──▶ AuditLogger
    │                                               │
    ▼                                               ▼
用户确认对话框 ──▶ send2trash (软删除) ──▶ 审计记录
```

### 模块说明

#### Scanner 模块 (`src/scanner/`)

| 组件 | 文件 | 说明 |
|------|------|------|
| `ScannerInterface` | `interface.py` | 扫描器抽象基类 |
| `WizTreeScanner` | `wiztree_scanner.py` | WizTree CLI 封装，支持 MFT 扫描、CSV 解析、扫描缓存 |
| `PathValidator` | `path_validator.py` | 路径存在性、权限、系统目录检查 |
| `DeepSearcher` | `deep_search.py` | 递归文件夹扫描、文件名模式搜索、大文件搜索 |
| `ScanProgress` | `scan_progress.py` | 进度回调、取消支持 |
| `ScanOptions` | `options.py` | 最大深度、最小文件大小、排除模式配置 |

#### Analyzer 模块 (`src/analyzer/`)

| 组件 | 文件 | 行数 | 说明 |
|------|------|------|------|
| `LLMAnalyzer` | `llm_analyzer.py` | 596 | LLM 分析器，支持延迟初始化 |
| `LLMRouter` | `llm_router.py` | 1241 | 多 Provider 路由器，v1.5.0 核心 |
| `StreamingJsonParser` | `json_parser.py` | 253 | 流式 JSON 解析器 |
| `RuleEngine` | `rule_engine.py` | 279 | 规则引擎，10 个预定义规则 |
| `ModelCatalog` | `model_catalog.py` | 396 | OpenRouter 模型目录 |
| `PromptStore` | `prompt_store.py` | 244 | 提示词文件管理器 |

#### Safety 模块 (`src/safety/`)

| 组件 | 文件 | 行数 | 说明 |
|------|------|------|------|
| `SafetyInterface` | `interface.py` | 245 | 安全模块抽象基类 |
| `Blocklist` | `blocklist.py` | 226 | 38 个受保护系统路径 |
| `AuditLogger` | `audit_logger.py` | 804 | SQLite 审计日志，支持还原操作 |
| `FileValidator` | `file_validator.py` | 328 | 文件存在性、锁定、权限检查 |
| `ConfirmDialog` | `confirm_dialog.py` | 379 | 用户确认对话框 |
| `ComprehensiveSafetyManager` | `__init__.py` | 292 | 安全管理器组合 |

#### UI 模块 (`src/ui/`)

| 组件 | 文件 | 行数 | 说明 |
|------|------|------|------|
| `MainWindow` | `main_window.py` | 1202 | 主窗口 |
| `SettingsDialog` | `settings_dialog.py` | 300 | 设置对话框 |
| `Keybindings` | `keybindings.py` | 96 | 5 个键盘快捷键 |
| `TreemapView` | `components/treemap_view.py` | 455 | Matplotlib Treemap 组件 |
| `Squarify` | `components/squarify.py` | 320 | 纯 Python Squarified Treemap |
| `DrillDown` | `components/drill_down.py` | 263 | Treemap 逐级下钻控制器 |
| `VirtualTreeview` | `components/virtual_treeview.py` | 177 | 虚拟滚动 Treeview |
| `SkeletonScreen` | `components/skeleton.py` | 197 | 骨架屏加载 |
| `StatusBar` | `components/status_bar.py` | 186 | 底部状态栏 |
| `DiffPreview` | `tabs/diff_preview.py` | 298 | 变更预览 |
| `HistoryTab` | `tabs/history_tab.py` | 566 | 审计历史 + 还原 |
| `ModelsTab` | `tabs/models_tab.py` | 414 | 模型浏览器 |
| `PromptsTab` | `tabs/prompts_tab.py` | 405 | 提示词编辑器 |
| `ModernTheme` | `themes/modern_theme.py` | 451 | 6 主题管理器 |
| `SmoothProgressBar` | `animations/smooth_progress.py` | 84 | 60fps 进度条动画 |

#### 数据模型 (`src/models/`)

| 模型 | 文件 | 说明 |
|------|------|------|
| `FileInfo` | `file_info.py` | 文件信息数据类（`__slots__` 优化）|
| `ScanResult` | `scan_result.py` | 扫描结果数据类 |
| `AnalysisResult` | `analysis_result.py` | 分析结果 + RiskLevel 枚举 |

#### 工具模块 (`src/utils/`)

| 工具 | 文件 | 行数 | 说明 |
|------|------|------|------|
| `ConfigLoader` | `config_loader.py` | 737 | 3 级级联配置加载器 |
| `CredentialStore` | `credential_store.py` | 238 | OS keyring 凭据封装 |

### 功能演进

| 版本 | 功能 |
|------|------|
| **1.0.0** | 核心框架: Scanner + Analyzer + Safety，LLM Router (6 Provider, 4 策略)，RuleEngine (10 规则)，Blocklist (38 路径) |
| **1.1.0** | GUI 现代化: 主题系统、平滑进度条、统计卡片、响应式布局、文件操作表格 |
| **1.2.0** | 安全增强: 凭据存储、6 暗色主题、键盘快捷键、拖放、审计历史+还原、Diff 预览、Squarified Treemap、3 级配置 |
| **1.3.0** | UX 优化: 骨架屏、主题切换回调、ttk 样式集成 |
| **1.4.0** | 性能优化: 虚拟滚动、`__slots__` 内存优化、扫描缓存 (1h TTL)、流式 CSV 解析 |
| **1.5.0** | 路由增强: LatencyProbe、WeightedRouter、batch_chat、RequestCoalescer；CLI 增强: 退出码、--quiet、--json、--batch、JSON/CSV 导出 |

---

## LLM Router 路由系统

### 支持的 Provider

| Provider | 环境变量 | Base URL | 免费模型 | 特色 |
|----------|----------|----------|----------|------|
| **DeepSeek** | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` | deepseek-v4-flash | 国内直连，性价比高，支持推理 |
| **OpenAI** | `OPENAI_API_KEY` | `https://api.openai.com/v1` | 无 | GPT-4o-mini，通用能力强 |
| **Anthropic** | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` | 无 | Claude-3-haiku，安全性高 |
| **OpenRouter** | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | gemini-2.0-flash-exp:free | 聚合 315+ 模型 |
| **SiliconFlow** | `SILICONFLOW_API_KEY` | `https://api.siliconflow.cn/v1` | DeepSeek-V3, Qwen2.5-7B | 国内免费模型 |
| **Ollama** | 无需密钥 | `http://localhost:11434/v1` | llama3.2, qwen2.5 | 本地运行，完全免费 |

### 可用模型及价格

| Provider | 模型 ID | 上下文 | 输入价格 ($/1M tokens) | 输出价格 ($/1M tokens) |
|----------|---------|--------|----------------------|-----------------------|
| DeepSeek | deepseek-v4-flash | 1M | 0.14 | 0.28 |
| DeepSeek | deepseek-v4-pro | 1M | 0.44 | 0.87 |
| OpenAI | gpt-4o-mini | 128K | 0.15 | 0.60 |
| Anthropic | claude-3-haiku | 200K | 0.25 | 1.25 |
| OpenRouter | google/gemini-2.0-flash-exp:free | 1M | 免费 | 免费 |
| SiliconFlow | deepseek-ai/DeepSeek-V3 | 64K | 免费 | 免费 |
| Ollama | llama3.2 | 8K | 免费 (本地) | 免费 (本地) |

### 路由策略

| 策略 | 枚举值 | 行为 | 适用场景 |
|------|--------|------|----------|
| **成本优先** | `COST` | 每请求选择最便宜的模型 | 预算有限，大量分析任务 |
| **速度优先** | `LATENCY` | 选择响应最快的 Provider | 需要快速交互反馈 |
| **故障转移** | `FALLBACK` | 自动切换到下一个可用 Provider | 生产环境，高可用性要求 |
| **手动选择** | `MANUAL` | 仅使用用户指定的 Provider | 测试特定模型 |

### 断路器模式

```
CLOSED (正常)
    │  连续 3 次请求失败
    ▼
OPEN (断开) ── 等待 60 秒 ──▶ HALF_OPEN (半开)
                                    │  测试请求成功
                                    ▼
                               CLOSED (恢复)
```

### 代码示例

```python
from src.analyzer import LLMRouter, RoutingStrategy

# 创建路由器
router = LLMRouter(
    strategy=RoutingStrategy.FALLBACK,
    default_model="deepseek-v4-flash"
)

# 发送聊天请求
response = router.chat(
    messages=[{"role": "user", "content": "分析这些文件哪些可以安全删除"}],
    model="deepseek-v4-flash"
)

# 切换策略
router.set_strategy(RoutingStrategy.COST)    # 成本优先
router.set_strategy(RoutingStrategy.LATENCY) # 速度优先

# 批量聊天
responses = router.batch_chat([
    {"messages": [...], "model": "deepseek-v4-flash"},
    {"messages": [...], "model": "gpt-4o-mini"}
])
```

### OpenRouter Provider 细粒度控制

```json
{
  "model": "deepseek/deepseek-v4-pro",
  "provider": {
    "order": ["DeepSeek", "Together", "Novita"],
    "allow_fallbacks": true
  }
}
```

---

## 配置指南

### API 密钥配置

可通过三种方式配置：

#### 方式一：环境变量（推荐）

```bash
# Windows CMD
set DEEPSEEK_API_KEY=sk-your-key
set OPENAI_API_KEY=sk-your-key
set ANTHROPIC_API_KEY=sk-ant-your-key
set OPENROUTER_API_KEY=sk-your-key
set SILICONFLOW_API_KEY=sk-your-key
```

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY="sk-your-key"
```

```bash
# Linux / macOS
export DEEPSEEK_API_KEY=sk-your-key
```

#### 方式二：安全凭据存储 (v1.2.0+)

GUI → 设置 → 凭据管理 → 添加 API 密钥

或编程方式：

```python
from src.utils.credential_store import CredentialStore

store = CredentialStore()
store.store_api_key("deepseek", "sk-xxx")
```

#### 方式三：配置文件

编辑 `config/llm_config.json` 或 `~/.wiztree-cli-agent/config.json`：

```json
{
  "strategy": "fallback",
  "default_model": "deepseek-v4-flash",
  "timeout": 30,
  "max_retries": 2,
  "providers": [...]
}
```

### 3 级级联配置 (v1.2.0+)

```
1. 内置默认值     (ConfigLoader 硬编码)
2. 用户配置       (~/.wiztree-cli-agent/config.json)
3. 运行时覆盖     (程序运行时的动态修改，不持久化)
```

覆盖优先级: `运行时 > 用户配置 > 内置默认值`

### WizTree 配置

- **默认路径**: `W:\WizTree\WizTree64.exe`
- **自定义路径**: 可在 GUI 设置面板或配置文件中指定

### 无 API 密钥也能用？

**可以！** 系统支持延迟初始化（Lazy Init）：

1. 应用正常启动，Analyzer 进入 lazy 模式
2. LLM 不可用时，自动使用 RuleEngine 的 10 个预定义规则
3. 规则引擎可识别：临时文件、浏览器缓存、系统日志、回收站、下载文件夹、Windows 更新缓存等

---

## 测试

### 运行测试套件

```bash
# 运行所有测试（推荐）
pytest tests/ -v

# 运行特定模块测试
pytest tests/test_scanner.py -v
pytest tests/test_analyzer.py -v
pytest tests/test_safety.py -v
pytest tests/test_router.py -v
pytest tests/test_ui.py -v

# 运行 LLM Router 演示
python tests/demo_router.py

# 运行集成测试
pytest tests/ -v -k "integration"
```

### 测试覆盖

| 测试类别 | 覆盖模块 | 说明 |
|----------|----------|------|
| ✅ **单元测试** | 扫描器、分析器、安全机制、数据模型 | 72+ 核心测试，全部通过 |
| ✅ **集成测试** | LLM Router、模块导入、全流程 | 30+ 集成测试，5 个场景覆盖全部 6 个阶段 |
| ✅ **UI 测试** | MainWindow、FileTable、ResultsView、进度条 | GUI 组件单元测试 |
| ✅ **Router 测试** | 路由策略切换、断路器、故障转移 | 多 Provider 场景模拟 |
| 📊 **总计** | **400+ 测试** | 覆盖核心功能与边缘场景 |

---

## 文档索引

| 文档 | 说明 |
|------|------|
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | 项目架构、模块设计、数据流、目录树 |
| **[API_REFERENCE.md](docs/API_REFERENCE.md)** | 完整模块/类/函数参考 |
| **[CONFIGURATION.md](docs/CONFIGURATION.md)** | LLM Router 配置、Provider 目录、API 密钥、路由策略 |
| **[DEVELOPMENT.md](docs/DEVELOPMENT.md)** | 开发指南、构建、测试、更新日志 |
| **[CHANGELOG.md](docs/CHANGELOG.md)** | 详细版本变更日志 |
| **[INDEX.md](docs/INDEX.md)** | 文档索引页 |

---

## 常见问题

### Q: 没有 API 密钥能使用吗？

**可以！** 应用支持延迟初始化，没有 API 密钥时会自动使用规则引擎（10 个预定义规则）进行分析。所有核心功能（扫描、分析、安全删除）均可正常工作。

### Q: 如何获取 API 密钥？

访问各 Provider 官网注册：

| Provider | 注册地址 | 免费额度 |
|----------|----------|----------|
| DeepSeek | https://platform.deepseek.com | 注册赠 500 万 tokens |
| OpenAI | https://platform.openai.com | 按量付费 |
| OpenRouter | https://openrouter.ai | 免费模型可用 |
| SiliconFlow | https://siliconflow.cn | 免费模型可用 |

### Q: 有哪些免费的模型？

| Provider | 免费模型 | 说明 |
|----------|----------|------|
| OpenRouter | `google/gemini-2.0-flash-exp:free` | Google Gemini 2.0 Flash |
| SiliconFlow | `deepseek-ai/DeepSeek-V3` | DeepSeek V3 |
| SiliconFlow | `Qwen/Qwen2.5-7B-Instruct` | Qwen 2.5 7B |
| Ollama | 全部免费 | 本地运行，需要本地 GPU/CPU |

### Q: 如何切换路由策略？

```python
from src.analyzer import LLMRouter, RoutingStrategy

router = LLMRouter(strategy=RoutingStrategy.COST)  # 成本优先
router.set_strategy(RoutingStrategy.LATENCY)        # 切换到速度优先
router.set_strategy(RoutingStrategy.FALLBACK)       # 切换到故障转移
```

也可在 GUI 的设置面板中直接选择路由策略。

### Q: 如何在 GUI 模式下使用？

```bash
python app.py
```

确保系统已安装 tkinter（Python 标准库通常自带）。如果出现 `ModuleNotFoundError: No module named 'tkinter'`，需要安装 tkinter：

```bash
# Ubuntu / Debian
sudo apt-get install python3-tk

# macOS (homebrew)
brew install python-tk

# Windows
# Python 安装时勾选 "tcl/tk and IDLE"
```

### Q: 删除的文件能恢复吗？

**是的！** 系统默认使用 `send2trash` 将文件移至回收站，而非永久删除。此外，所有删除操作都会记录到 SQLite 审计日志中，可在 GUI 的 "History" 标签页中查看和还原。

### Q: 是否支持中文？

**完全支持！** 应用界面和分析结果均支持中文。LLM 提示词默认使用中文，分析结果以中文呈现。

### Q: 如何构建可执行文件？

```bash
python build.py
```

这会使用 PyInstaller 将应用打包为独立的 `.exe` 文件，位于 `dist/` 目录。

---

## 版本历史

### v1.5.0 (2026-06-04) — CLI 增强 + 动态路由优化

#### 新增
- **LLM Router 动态路由**: LatencyProbe（延迟探测）、WeightedRouter（加权路由）、batch_chat（批量聊天）、RequestCoalescer（请求合并器）
- **CLI 脚本化增强**: 退出码、`--quiet`/`--json`/`--no-color` 参数、`OutputFormatter`
- **CLI 批量扫描 + 导出**: `--batch`/`--batch-file` 参数、JSON/CSV 格式导出

#### 完整变更
参见 [CHANGELOG.md](docs/CHANGELOG.md)

### v1.4.0 — 性能优化

- 虚拟滚动 Treeview，支持万级文件流畅浏览
- FileInfo 使用 `__slots__` 减少 60%+ 内存占用
- 扫描缓存（1 小时 TTL）
- 流式 CSV 解析，逐行处理

### v1.3.0 — UX 优化

- 骨架屏加载动画
- 主题切换回调 + ttk 样式集成

### v1.2.0 — 安全 + 主题 + 交互

- 安全凭据存储 (OS keyring)
- 6 种暗色主题
- 5 个键盘快捷键
- 拖放支持
- 审计历史 + 还原
- Diff 预览
- Squarified Treemap
- 3 级级联配置
- 模型浏览器 + 提示词编辑器

### v1.1.0 — UI 现代化

- 深色/浅色主题切换
- 60fps 平滑进度条
- 统计信息卡片
- 响应式布局
- 文件操作表格
- 批量文件操作

### v1.0.0 — 初始版本

- 模块化架构：Scanner、Analyzer、Safety
- LLM Router 集成（6 个 Provider，4 种策略）
- 规则引擎降级（10 个预定义规则）
- 路径黑名单（38 个系统路径）
- 审计日志（SQLite）
- 68 个单元测试
- 延迟初始化支持

---

## 许可证

本项目使用 **MIT License** 开源。

```
MIT License

Copyright (c) 2026 WizTree CLI Agent

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 贡献

欢迎提交 Issue 和 Pull Request！贡献方式：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 开发指南

```bash
# 安装开发依赖
pip install -r requirements.txt

# 运行测试
pytest tests/ -v

# 构建
python build.py
```

详细开发指南请参考 [DEVELOPMENT.md](docs/DEVELOPMENT.md)。

---

> **WizTree CLI Agent** — 让磁盘清理更智能、更安全、更高效。
>
> 项目主页: [https://github.com/waterundman/wiztree-cli-agent](https://github.com/waterundman/wiztree-cli-agent)
