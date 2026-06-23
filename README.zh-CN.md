# WizTree CLI Agent

[![Version](https://img.shields.io/badge/version-2.1.0-blue.svg)](https://github.com/waterundman/wiztree-cli-agent)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-666%20passed-green.svg)](#测试)
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

## v2.1.0 更新内容

### GUI 接入 LLM 分析
GUI 现在支持 **LLM 优先分析**，自动降级到规则引擎。从下拉菜单选择模型后，AI 分析标签页实时显示 LLM 流式分析结果。无 API 密钥时自动使用内置规则引擎，用户无感知。

### 架构重构
- **MainWindow** 从 1765 行精简到 762 行 (↓57%)，采用 MVC 控制器模式
- **ScanController** — 管理 WizTree 扫描器生命周期和流式扫描
- **AnalysisController** — 管理 LLM/规则引擎分析，支持流式回调
- **FileOperationController** — 管理文件删除、恢复和审计日志
- **llm_router.py** 从 1378 行拆分为 4 个独立模块：`circuit_breaker.py`、`latency_probe.py`、`request_coalescer.py`、`batch.py`

### Bug 修复
- 修复 `app.py` 中 LLM 路由器未配置时的 `NameError`
- 修复 `cli.py` 中缺失的 `WizTreeAgentApp` 导入
- 统一 `models` 和 `safety` 模块的 `FileInfo` 命名冲突
- 版本号统一为 2.1.0

---

## 主要功能

### 🔬 WizTree CLI 集成
- MFT 直接读取，秒级扫描整盘
- 流式 CSV 解析，最小内存占用
- 扫描缓存（1 小时 TTL），避免重复扫描
- 深度检索：按文件名模式、大文件、目录递归搜索

### 🤖 多 LLM Provider 路由
- **6 个内置 Provider**: DeepSeek、OpenAI、Anthropic、OpenRouter、SiliconFlow、Ollama
- **4 种路由策略**: 成本优先、速度优先、故障转移、手动选择
- **断路器模式**: 连续 3 次失败自动断开，60 秒后尝试恢复
- **延迟探测 + 加权路由**: 自动选择响应最快的 Provider
- **请求合并器**: 批量请求合并，降低 API 调用成本

### ⚙️ 规则引擎降级
- 10 个预定义清理规则，覆盖临时文件、缓存、日志等
- 零依赖，无需 API 密钥即可使用
- API 不可用时自动切换

### 🛡️ 安全机制
- **路径黑名单**: 38 个受保护系统路径
- **审计日志**: SQLite 记录所有破坏性操作，支持还原
- **文件验证**: 删除前检查存在性、锁定状态、权限
- **确认对话框**: 用户手动审核后才执行删除
- **回收站优先**: 使用 send2trash 软删除

### 🎨 GUI 界面
- **6 种暗色主题**: Steam Dark、Catppuccin Mocha、OLED Black、GitHub Dark、Nord、Dracula
- **Squarified Treemap**: 磁盘使用可视化，支持逐级下钻
- **虚拟滚动**: 万级文件列表流畅浏览
- **骨架屏加载**: 扫描和分析时的占位动画
- **60fps 平滑进度条**: 流畅的扫描进度动画
- **键盘快捷键**: Ctrl+S 扫描 / Ctrl+R 刷新 / Ctrl+L 清空 / Esc 取消
- **拖放支持**: 拖放文件夹到窗口
- **Diff 预览**: 删除前显示文件变更对比

### 🖥️ CLI 脚本模式
- **批量扫描**: `--batch` 参数支持多路径扫描
- **JSON/CSV 导出**: 结构化数据输出
- **退出码**: 标准退出码，适合 CI/CD 集成
- **静默模式**: `--quiet` 减少输出

---

## 架构设计 (v2.1.0)

```
┌─────────────────────────────────────────────────────────────────┐
│                    WizTree CLI Agent                              │
│                                                                   │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│    │ Scanner  │───▶│ Analyzer │───▶│  Safety  │                  │
│    └────┬─────┘    └────┬─────┘    └────┬─────┘                  │
│         │               │               │                         │
│         ▼        ┌──────┴──────┐        ▼                         │
│    ┌─────────┐  ▼             ▼   ┌─────────┐                    │
│    │WizTree  │ ┌──────────┐ ┌────┐ │Blocklist│                    │
│    │  CLI    │ │ LLMRouter│ │Rule│ │AuditLog │                    │
│    └─────────┘ │CircuitBrk│ │Eng.│ │FileValid│                    │
│                │LatencyPrb│ └────┘ │Confirm  │                    │
│                │ReqCoalesc│        └─────────┘                    │
│                └──────────┘                                      │
│                                                                   │
│    ┌────────────────────────────────────────┐                    │
│    │           UI (v2.1.0 MVC)              │                    │
│    │  MainWindow (762行)                    │                    │
│    │    ├── ScanController (331行)          │                    │
│    │    ├── AnalysisController (163行)      │                    │
│    │    └── FileOperationController (92行)  │                    │
│    └────────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

### 模块说明

| 模块 | 目录 | 说明 |
|------|------|------|
| **Scanner** | `src/scanner/` | WizTree CLI 封装、路径验证、深度搜索、扫描缓存、流式扫描器 |
| **Analyzer** | `src/analyzer/` | LLM Router (6 Provider, 4 策略)、断路器、延迟探测、请求合并器、批量请求、规则引擎、流式 JSON 解析器、模型目录、提示词管理 |
| **Safety** | `src/safety/` | 路径黑名单 (38 路径)、SQLite 审计日志、文件验证器 (ValidationFileInfo)、确认对话框 |
| **UI** | `src/ui/` | MainWindow + 3 控制器、Treemap、虚拟滚动、骨架屏、6 主题、快捷键、拖放、进度条、Diff 预览、历史标签页 |
| **Models** | `src/models/` | `FileInfo`、`ScanResult`、`AnalysisResult` / `RiskLevel` 数据类 |
| **Utils** | `src/utils/` | 3 级级联配置加载器、OS keyring 凭据存储 |

---

## 快速开始

### 环境要求

- **Python**: 3.10 或更高版本
- **操作系统**: Windows 10+ / Linux / macOS
- **WizTree**: 可选但推荐（[官网下载](https://diskanalyzer.com/download)）

### 安装

```bash
git clone https://github.com/waterundman/wiztree-cli-agent.git
cd wiztree-cli-agent
pip install -r requirements.txt
```

### 运行

```bash
# GUI 模式（需要 tkinter）
python app.py

# CLI 模式
python app.py --cli

# 扫描并分析
python cli.py --scan "C:\Users" --analyze

# 交互模式
python cli.py --interactive

# 批量扫描
python cli.py --batch "C:\Users\Downloads" "D:\Temp" --analyze --json
```

### 构建可执行文件

```bash
python build.py
```

---

## 下载

从 [GitHub Releases](https://github.com/waterundman/wiztree-cli-agent/releases) 页面下载预编译版本：

| 包类型 | 说明 |
|--------|------|
| `WizTreeCLIAgent-v2.1.0-win64.zip` | Windows 64 位便携版 |

---

## LLM Router 路由系统

### 支持的 Provider

| Provider | 环境变量 | 免费模型 | 特色 |
|----------|----------|----------|------|
| **DeepSeek** | `DEEPSEEK_API_KEY` | deepseek-v4-flash | 国内直连，性价比高 |
| **OpenAI** | `OPENAI_API_KEY` | 无 | GPT-4o-mini，通用能力强 |
| **Anthropic** | `ANTHROPIC_API_KEY` | 无 | Claude-3-haiku，安全性高 |
| **OpenRouter** | `OPENROUTER_API_KEY` | gemini-2.0-flash-exp:free | 聚合 315+ 模型 |
| **SiliconFlow** | `SILICONFLOW_API_KEY` | DeepSeek-V3, Qwen2.5-7B | 国内免费模型 |
| **Ollama** | 无需密钥 | llama3.2, qwen2.5 | 本地运行，完全免费 |

### 路由策略

| 策略 | 行为 | 适用场景 |
|------|------|----------|
| **成本优先** | 选择最便宜的模型 | 预算有限 |
| **速度优先** | 选择响应最快的 Provider | 需要快速反馈 |
| **故障转移** | 自动切换到下一个可用 Provider | 高可用性要求 |
| **手动选择** | 仅使用指定的 Provider | 测试特定模型 |

### 断路器模式

```
CLOSED (正常)
    │  连续 3 次失败
    ▼
OPEN (断开) ── 等待 60 秒 ──▶ HALF_OPEN (半开)
                                    │  测试成功
                                    ▼
                               CLOSED (恢复)
```

### 代码示例

```python
from src.analyzer import LLMRouter, RoutingStrategy, WeightedRouter, batch_chat, BatchRequest

# 基础路由器
router = LLMRouter(
    strategy=RoutingStrategy.FALLBACK,
    default_model="deepseek-v4-flash"
)

# 发送请求
response = router.chat(
    messages=[{"role": "user", "content": "分析这些文件哪些可以安全删除"}],
    model="deepseek-v4-flash"
)

# 加权路由器
wrouter = WeightedRouter(
    strategy=RoutingStrategy.COST,
    enable_probe=True,
    weights={"latency": 0.4, "success": 0.3, "cost": 0.3}
)

# 批量请求
results = batch_chat(wrouter, [
    BatchRequest(messages=[{"role": "user", "content": msg}])
    for msg in ["Analyze Downloads", "Analyze Temp"]
], max_workers=2)
```

---

## 配置指南

### API 密钥

```bash
# Windows CMD
set DEEPSEEK_API_KEY=sk-your-key

# Linux / macOS
export DEEPSEEK_API_KEY=sk-your-key
```

**无 API 密钥也能用！** 系统自动降级到规则引擎，所有核心功能正常工作。

### 安全凭据存储

API 密钥通过 OS keyring 存储（Windows DPAPI / macOS Keychain / Linux Secret Service）：

```python
from src.utils.credential_store import CredentialStore
CredentialStore.store_api_key("deepseek", "sk-xxx")
```

---

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行覆盖率报告
pytest tests/ --cov=src -v
```

### 测试统计 (v2.1.0)

| 指标 | 数量 |
|------|------|
| 测试文件 | ~48 |
| 测试用例 | 666 passed |
| 集成测试 | 19+ 场景 |
| UI 测试 | 主题切换、骨架屏、快捷键、Treemap、Diff 预览、控制器 |

---

## 版本历史

| 版本 | 日期 | 亮点 |
|------|------|------|
| **2.1.0** | 2026-06-23 | **GUI LLM 分析集成**、MainWindow 控制器拆分 (1765→762 行)、llm_router 模块拆分 (1378→973 行)、6 个 Bug 修复、666 测试 |
| **2.0.0** | 2026-06-13 | 稳定性：SQLite WAL 模式、CircuitBreaker 线程安全、内存泄漏修复、子进程清理 |
| **1.9.0** | 2026-06-12 | 流式扫描器、内存优化、批次导航、批次缓存 |
| **1.8.0** | 2026-06-11 | 代码质量：消除 72 处 `except Exception: pass`，新增 53 个测试 |
| **1.5.0** | 2026-06-04 | LatencyProbe、WeightedRouter、batch_chat、CLI 增强 |
| **1.4.0** | 2026-06-03 | 虚拟滚动、`__slots__` 内存优化、扫描缓存 |
| **1.3.0** | 2026-06-02 | 骨架屏、主题切换回调 |
| **1.2.0** | 2026-06-01 | 安全凭据存储、6 暗色主题、快捷键、拖放、审计历史、Treemap |
| **1.1.0** | 2026-06-01 | 主题系统、平滑进度条、统计卡片 |
| **1.0.0** | 2026-05-31 | 核心框架：Scanner + Analyzer + Safety、LLM Router、RuleEngine |

---

## 许可证

本项目使用 **MIT License** 开源。

---

## 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

> **WizTree CLI Agent** — 让磁盘清理更智能、更安全、更高效。
>
> 项目主页: [https://github.com/waterundman/wiztree-cli-agent](https://github.com/waterundman/wiztree-cli-agent)
