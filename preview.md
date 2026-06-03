# WizTree CLI Agent — 项目预览

> 生成时间：2026-06-03  
> 版本：v1.3.0  
> 用途：为 deep-research 技能提供项目上下文

---

## 1. 项目概述

| 属性 | 值 |
|------|-----|
| **名称** | WizTree CLI Agent |
| **版本** | v1.3.0 (2026-06-03) |
| **描述** | AI 驱动的磁盘清理助手，封装 WizTree CLI 工具，通过 LLM 分析实现安全的人机交互文件清理 |
| **许可证** | MIT |
| **Python** | 3.10+ |
| **平台** | Windows (主)、macOS/Linux (部分支持) |

### 核心价值

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

### 模块依赖关系

```
app.py / cli.py
    ├── src.scanner (WizTree CLI 封装)
    ├── src.analyzer (LLM Router + 规则引擎)
    ├── src.safety (黑名单 + 审计 + 验证)
    ├── src.ui (customtkinter GUI)
    ├── src.models (FileInfo, ScanResult, etc.)
    └── src.utils (配置加载、凭据存储)
```

---

## 3. 核心组件

### 3.1 Scanner 模块 (`src/scanner/`)

| 组件 | 职责 |
|------|------|
| `WizTreeScanner` | WizTree CLI 封装，MFT 快速扫描 |
| `DeepSearcher` | 文件夹深度递归检索 |
| `PathValidator` | 路径合法性验证 |
| `ScanProgress` | 扫描进度状态机 |
| `ScanOptions` | 扫描参数配置 |

### 3.2 Analyzer 模块 (`src/analyzer/`)

| 组件 | 职责 |
|------|------|
| `LLMRouter` | 多 Provider 路由器（6 Provider × 4 策略） |
| `LLMAnalyzer` | LLM 分析器（延迟初始化） |
| `RuleEngine` | 10 条规则引擎（无 API 降级方案） |
| `StreamingJsonParser` | 流式 JSON 解析器 |
| `ModelCatalog` | 模型目录浏览 |
| `PromptStore` | Prompt 持久化编辑 |

**路由策略**：`cost`（成本优先）/ `latency`（速度优先）/ `fallback`（故障转移）/ `manual`（手动）

**支持 Provider**：DeepSeek / OpenAI / Anthropic / OpenRouter / SiliconFlow / Ollama

### 3.3 Safety 模块 (`src/safety/`)

| 组件 | 职责 |
|------|------|
| `Blocklist` | 38 条系统路径黑名单 |
| `AuditLogger` | SQLite 审计日志 + 恢复 |
| `FileValidator` | 文件存在性/锁定/权限检查 |
| `ConfirmDialog` | 二次确认对话框 |
| `ComprehensiveSafetyManager` | 统一安全门控 |

### 3.4 UI 模块 (`src/ui/`)

| 组件 | 职责 |
|------|------|
| `MainWindow` | 主窗口框架 |
| `ConfigPanel` | 扫描/LLM 配置面板 |
| `ResultsView` | 扫描结果展示 |
| `FileTable` | 文件操作表（勾选/风险筛选） |
| `TreemapView` | Squarified Treemap 可视化 |
| `ModernTheme` | 6 暗色主题管理 |
| `SkeletonWidget` | 骨架屏加载动画 |
| `StatusBar` | 状态栏（扫描/分析/就绪/错误） |

### 3.5 Models 模块 (`src/models/`)

- `FileInfo` — 文件元数据（路径/大小/类型/修改时间）
- `ScanResult` — 扫描结果集合
- `AnalysisResult` — 分析结果（建议删除列表）
- `ValidationResult` — 验证结果枚举

---

## 4. 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| **语言** | Python | 3.10+ |
| **GUI** | customtkinter | ≥5.2.0 |
| **LLM** | openai | ≥1.0.0 |
| **安全删除** | send2trash | ≥1.8.0 |
| **可视化** | matplotlib | ≥3.7.0 |
| **Treemap** | 纯 Python 实现 (Bruls 2000) | 内置 |
| **凭据** | keyring | ≥24.0.0 |
| **拖放** | tkinterdnd2 | ≥0.4.2 |
| **HTTP** | requests | ≥2.28.0 |
| **持久化** | sqlite3 | 内置 |
| **测试** | pytest + pytest-cov | ≥7.4.0 |

---

## 5. 测试覆盖情况

### 汇总（v1.3.0）

| 类别 | 数量 | 状态 |
|------|------|------|
| 单元测试 | 336+ | ✅ PASS |
| 集成测试 (v1.2.0) | 30 | ✅ PASS |
| 集成测试 (v1.3.0) | 19 | ✅ PASS |
| 跳过 | 116 | ⚠️ 环境依赖 |
| **总计** | **400 passed** | ✅ |

### 测试文件清单

| 文件 | 覆盖模块 |
|------|----------|
| `test_scanner.py` | Scanner 路径验证、扫描接口 |
| `test_analyzer.py` | JSON 解析、规则引擎 |
| `test_safety.py` | 黑名单、文件验证、安全管理器 |
| `test_deep_search.py` | 深度检索、模式搜索 |
| `test_models.py` | 数据模型 |
| `test_router.py` | LLM Router 路由策略 |
| `test_ui.py` | UI 组件 |
| `test_squarify.py` | Treemap 算法 |
| `test_skeleton.py` | 骨架屏组件 |
| `test_integration_v120.py` | v1.2.0 端到端集成 |
| `test_integration_v130.py` | v1.3.0 骨架屏+主题集成 |

---

## 6. 版本历史

| 版本 | 日期 | 核心变更 |
|------|------|----------|
| **v1.0.0** | 2026-05-31 | 初始版本：WizTree CLI 封装、LLM Router（6 Provider）、规则引擎、安全机制、Treemap |
| **v1.1.0** | 2026-06-01 | UI 现代化：深色/浅色主题、60fps 进度条、统计卡片、文件操作表 |
| **v1.2.0** | 2026-06-XX | 安全+交互：加密凭据存储、6 暗色主题、键盘快捷键、拖放、审计恢复、Diff 预览、纯 Python Squarify |
| **v1.3.0** | 2026-06-03 | 骨架屏+主题优化：SkeletonWidget、主题切换回调、ttk 样式集成 |

---

## 7. 关键设计决策

### 7.1 延迟初始化 (Lazy Init)

- **问题**：GUI 启动时 API 密钥可能未配置
- **方案**：`LLMAnalyzer` 延迟创建 LLM 客户端，首次调用时初始化
- **降级**：无 API 密钥时自动切换到 `RuleEngine`（10 条规则）

### 7.2 多 Provider 路由

- **问题**：单一 Provider 不可靠，成本/速度难兼顾
- **方案**：`LLMRouter` 统一抽象，支持 4 种策略
- **收益**：故障自动转移、成本优化、本地 Ollama 支持

### 7.3 安全门控 (Human-in-the-Loop)

- **问题**：AI 建议可能误删关键文件
- **方案**：所有删除操作必须经过用户二次确认
- **保障**：黑名单（38 路径）+ 文件验证 + 审计日志 + 回收站优先

### 7.4 纯 Python Treemap

- **问题**：第三方 `squarify` 包有依赖冲突
- **方案**：实现 Bruls et al. (2000) Algorithm 4
- **收益**：零外部依赖、主题感知、支持钻取交互

### 7.5 3 级级联配置

- **层级**：内置默认 → 用户文件 (`~/.wiztree-cli-agent/config.json`) → 内存覆盖
- **迁移**：v1.1.0 配置自动迁移到新路径
- **安全**：导出时递归剥离 API 密钥

### 7.6 骨架屏加载

- **问题**：扫描/分析期间界面空白
- **方案**：`SkeletonWidget` 脉冲动画（~30fps），主题感知颜色
- **集成**：MainWindow / ModelsTab / PromptsTab 统一生命周期

---

## 附录：项目结构

```
wiztree-cli-agent/
├── app.py                          # GUI 入口
├── cli.py                          # CLI 入口
├── build.py                        # 打包脚本
├── requirements.txt                # 依赖清单
├── config/                         # 配置目录
│   └── llm_config.json             # LLM 配置（已迁移）
├── docs/                           # 文档
│   ├── CHANGELOG.md                # 更新日志
│   ├── TEST_REPORT.md              # 测试报告
│   └── ...
├── src/                            # 源码
│   ├── __init__.py                 # 版本号 v1.3.0
│   ├── scanner/                    # 扫描模块
│   ├── analyzer/                   # 分析模块（含 LLM Router）
│   ├── safety/                     # 安全模块
│   ├── ui/                         # GUI 模块
│   ├── models/                     # 数据模型
│   └── utils/                      # 工具函数
└── tests/                          # 测试（31 文件）
    ├── test_integration_v120.py
    ├── test_integration_v130.py
    └── ...
```

---

*本文档由 opencode 自动生成，供 deep-research 技能使用。*
