# WizTree CLI Agent — 项目上下文与预览

> **版本**: v1.5.0 | **最后更新**: 2026-06-04 | **许可证**: MIT

---

## 1. 项目描述

WizTree CLI Agent 是一个 AI 驱动的磁盘清理助手，通过封装 WizTree CLI 工具并集成多 LLM Provider 路由系统，实现智能化的文件分析和安全的人机交互式文件清理。

**核心价值**:
- **零门槛**：无 API 密钥时自动降级到规则引擎（10 条预定义规则）
- **安全第一**：38 条路径黑名单 + 审计日志 + 二次确认 + 回收站优先
- **多 LLM 支持**：6 个 Provider、4 种路由策略、故障转移

---

## 2. 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        app.py / cli.py                       │
│                      (入口层：GUI / CLI)                      │
├─────────────────────────────────────────────────────────────┤
│                            src/                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ scanner/ │  │ analyzer/│  │  safety/ │  │   ui/    │    │
│  │ 扫描模块 │  │ 分析模块 │  │ 安全模块 │  │ 界面模块 │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │              │              │              │          │
│  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐    │
│  │ models/  │  │  utils/  │  │          │  │          │    │
│  │ 数据模型 │  │ 工具函数 │  │          │  │          │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 模块关系

```
┌─────────────────────────────────────────────────────────────────┐
│                    WizTree CLI Agent                             │
│                         │                                       │
│    ┌────────────────────┼────────────────────┐                  │
│    │                    │                    │                  │
│    ▼                    ▼                    ▼                  │
│ ┌──────────┐      ┌──────────┐        ┌──────────┐             │
│ │ Scanner  │      │ Analyzer │        │  Safety  │             │
│ └────┬─────┘      └────┬─────┘        └────┬─────┘             │
│      │           ┌─────┴─────┐              │                   │
│      │           │           │              │                   │
│      ▼           ▼           ▼              ▼                   │
│ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐             │
│ │WizTree  │ │ LLMRouter│ │RuleEngine│ │Blocklist│             │
│ │  CLI    │ │ 路由器   │ │ 规则引擎│ │ 黑名单  │             │
│ └─────────┘ └────┬─────┘ └──────────┘ └─────────┘             │
│                  │                                              │
│           ┌──────┴──────┐                                      │
│           │             │                                      │
│           ▼             ▼                                      │
│     ┌──────────┐  ┌──────────┐                                │
│     │ Provider │  │ Circuit  │                                │
│     │  提供商  │  │ Breaker  │                                │
│     └──────────┘  │ 断路器   │                                │
│                   └──────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 领域术语

| 术语 | 定义 |
|------|------|
| **LLMRouter** | 统一大模型 API 网关层，负责多 Provider 路由、故障转移和成本优化 |
| **RuleEngine** | 规则引擎，提供 10 个预定义清理规则，作为 LLM 不可用时的降级方案 |
| **Blocklist** | 路径黑名单，包含 38 个受保护的系统路径 |
| **AuditLogger** | 审计日志记录器，使用 SQLite 记录所有破坏性操作 |
| **RoutingStrategy** | 路由策略枚举：COST / LATENCY / FALLBACK / MANUAL |
| **断路器模式** | Circuit Breaker，CLOSED→OPEN→HALF_OPEN 状态转换 |
| **延迟初始化** | Lazy Init，无 API 密钥时自动降级到规则引擎 |

---

## 4. 核心组件

### 4.1 Scanner (`src/scanner/`)

| 组件 | 职责 |
|------|------|
| `WizTreeScanner` | WizTree CLI 封装，MFT 快速扫描，CSV 解析，扫描缓存 (1h TTL) |
| `DeepSearcher` | 文件夹深度递归检索，模式搜索，大文件搜索 |
| `PathValidator` | 路径合法性验证，系统目录检测 |
| `ScanProgress` | 扫描进度状态机，取消支持 |
| `ScanOptions` | 扫描参数 (最大深度/最小大小/排除模式) |

### 4.2 Analyzer (`src/analyzer/`)

| 组件 | 职责 |
|------|------|
| `LLMRouter` | 6 Provider × 4 策略路由器，延迟探测，加权路由，断路器 |
| `LLMAnalyzer` | LLM 分析器，延迟初始化 |
| `RuleEngine` | 10 条规则引擎（无 API 降级） |
| `StreamingJsonParser` | 流式 JSON 解析器 |
| `ModelCatalog` | 模型目录（OpenRouter 315+ 模型） |
| `PromptStore` | Prompt 持久化编辑 |

### 4.3 Safety (`src/safety/`)

| 组件 | 职责 |
|------|------|
| `Blocklist` | 38 条系统路径黑名单 |
| `AuditLogger` | SQLite 审计日志 + 文件恢复 |
| `FileValidator` | 文件存在性/锁定/权限检查 |
| `ConfirmDialog` | 二次确认对话框 |
| `ComprehensiveSafetyManager` | 统一安全门控 |

### 4.4 UI (`src/ui/`)

| 组件 | 职责 |
|------|------|
| `MainWindow` | 主窗口（1200+ 行） |
| `ModernTheme` | 6 暗色主题管理 + 动态切换 |
| `TreemapView` | Squarified Treemap 可视化 |
| `SkeletonWidget` | 骨架屏加载动画 (~30fps) |
| `StatusBar` | 状态栏（扫描/分析/就绪/错误） |
| `VirtualTreeview` | 虚拟滚动 Treeview (10000+ 行) |
| `SmoothProgressBar` | 60fps 平滑进度条 |

### 4.5 Models (`src/models/`)

`FileInfo` → `ScanResult` → `AnalysisResult` → `DeletionRecommendation` / `RiskLevel`

---

## 5. 技术栈

| 类别 | 技术 |
|------|------|
| **语言** | Python 3.10+ |
| **GUI** | customtkinter ≥ 5.2.0 |
| **LLM** | openai ≥ 1.0.0 |
| **安全删除** | send2trash ≥ 1.8.0 |
| **可视化** | matplotlib ≥ 3.7.0 |
| **Treemap** | 纯 Python (Bruls et al. 2000) |
| **凭据** | keyring ≥ 24.0.0 |
| **HTTP** | requests ≥ 2.28.0 |
| **测试** | pytest + pytest-cov |

---

## 6. 关键设计决策

### 6.1 延迟初始化
无 API 密钥时应用正常启动，自动使用 RuleEngine 的 10 个预定义规则。

### 6.2 多 Provider 路由
单一 Provider 不可靠 → LLMRouter 统一抽象，4 种策略，故障自动转移。

### 6.3 安全门控
所有删除操作需用户二次确认，黑名单 + 文件验证 + 审计日志 + 回收站优先。

### 6.4 纯 Python Treemap
实现 Bruls et al. (2000) Algorithm 4，零外部依赖，主题感知。

### 6.5 3 级级联配置
内置默认 → `~/.wiztree-cli-agent/config.json` → 内存覆盖，安全导出。

---

## 7. 版本历史

| 版本 | 日期 | 核心变更 |
|------|------|----------|
| v1.0.0 | 2026-05-31 | 初始：WizTree CLI 封装、6 Provider LLM Router、规则引擎、安全机制 |
| v1.1.0 | 2026-06-01 | UI 现代化：主题系统、60fps 进度条、统计卡片 |
| v1.2.0 | 2026-06-XX | 安全+交互：加密凭据、6 主题、快捷键、拖放、审计恢复、Diff 预览 |
| v1.3.0 | 2026-06-03 | 骨架屏+主题优化：SkeletonWidget、ttk 样式 |
| v1.4.0 | 2026-06-03 | 性能：虚拟滚动、内存优化 (slots)、扫描缓存、CSV 流式解析 |
| v1.5.0 | 2026-06-04 | 路由：LatencyProbe、WeightedRouter、batch_chat；CLI 脚本化、批量导出 |

---

## 8. 测试覆盖

| 类别 | 数量 | 状态 |
|------|------|------|
| 单元测试 | 336+ | ✅ |
| 集成测试 (v1.2.0) | 30 | ✅ |
| 集成测试 (v1.3.0) | 19 | ✅ |
| 集成测试 (v1.5.0) | 18 | ✅ |
| 性能基准 | 6 | ✅ |
| **总计** | **452+ passed** | ✅ |

---

## 9. 项目结构

```
wiztree-cli-agent/
├── app.py / cli.py            # 入口
├── build.py                   # 打包脚本
├── requirements.txt           # 依赖
├── config/                    # 配置
│   └── llm_config.json        # LLM 配置
├── docs/                      # 文档
├── src/                       # 源码
│   ├── scanner/               # 扫描模块
│   ├── analyzer/              # 分析模块 (LLM Router)
│   ├── safety/                # 安全模块
│   ├── ui/                    # GUI 模块
│   ├── models/                # 数据模型
│   └── utils/                 # 工具函数
├── tests/                     # 测试 (30+ 文件)
└── dist/                      # 构建产物
```

---

*本文档由项目代码分析自动生成。*
