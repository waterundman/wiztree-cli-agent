# 项目上下文 (Project Context)

> **项目名称**: WizTree CLI Agent
> **版本**: v1.2.0
> **最后更新**: 2026-06-03

---

## 1. 项目描述

WizTree CLI Agent 是一个 AI 驱动的磁盘清理助手，通过封装 WizTree CLI 工具并集成多 LLM Provider 路由系统，实现智能化的文件分析和安全的人机交互式文件清理。

---

## 2. 领域术语表

### 核心组件

| 术语 | 定义 |
|------|------|
| **WizTree CLI Agent** | 项目主应用，整合扫描、分析、安全三大模块的磁盘清理工具 |
| **LLMRouter** | 统一的大模型 API 网关层，负责多 Provider 路由、故障转移和成本优化 |
| **RuleEngine** | 规则引擎，提供 10 个预定义清理规则，作为 LLM 不可用时的降级方案 |
| **Scanner** | 扫描器模块，封装 WizTree CLI 进行快速磁盘扫描，支持 MFT 扫描加速 |
| **Analyzer** | 分析器模块，包含 LLMAnalyzer 和 RuleEngine，负责文件清理建议生成 |
| **Orchestrator** | 动态工作流编排器，协调 Scanner → Analyzer → Safety 的执行流程 |

### 安全机制

| 术语 | 定义 |
|------|------|
| **Safety** | 安全模块，包含黑名单保护、审计日志、文件验证和确认对话框 |
| **Blocklist** | 路径黑名单，包含 38 个受保护的系统路径 |
| **AuditLogger** | 审计日志记录器，使用 SQLite 记录所有破坏性操作 |
| **ConfirmDialog** | 确认对话框，用户手动审核后才执行删除操作 |

### 路由与策略

| 术语 | 定义 |
|------|------|
| **RoutingStrategy** | 路由策略枚举：COST（成本优先）、LATENCY（速度优先）、FALLBACK（故障转移）、MANUAL（手动选择）|
| **Provider** | LLM 服务提供商，如 DeepSeek、OpenAI、Anthropic 等 |
| **断路器模式** | Circuit Breaker 模式，防止持续调用失败的 Provider，支持 CLOSED→OPEN→HALF_OPEN 状态转换 |
| **延迟初始化** | Lazy Init 模式，无 API 密钥时应用仍可运行，自动降级到规则引擎 |

### UI 与可视化

| 术语 | 定义 |
|------|------|
| **骨架屏** | Skeleton Screen，加载时显示占位 UI，提升感知性能 |
| **主题系统** | 支持 6 种深色主题（Steam Dark/Catppuccin Mocha/OLED Black 等），支持动态切换 |
| **TreemapView** | 文件大小分布可视化，使用 Squarified Treemap 算法 |
| **SmoothProgressBar** | 60fps 平滑进度条动画组件 |

---

## 3. 术语关系

```
┌─────────────────────────────────────────────────────────────────┐
│                    WizTree CLI Agent                             │
│                         │                                       │
│    ┌────────────────────┼────────────────────┐                  │
│    │                    │                    │                  │
│    ▼                    ▼                    ▼                  │
│ ┌──────────┐      ┌──────────┐        ┌──────────┐             │
│ │ Scanner  │      │ Analyzer │        │  Safety  │             │
│ │ 扫描模块 │      │ 分析模块 │        │ 安全模块 │             │
│ └────┬─────┘      └────┬─────┘        └────┬─────┘             │
│      │                 │                    │                   │
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

### 关系说明

1. **WizTree CLI Agent** 包含三大核心模块：**Scanner**、**Analyzer**、**Safety**
2. **Analyzer** 依赖 **LLMRouter** 进行 LLM 调用，**RuleEngine** 作为降级方案
3. **LLMRouter** 管理多个 **Provider**，使用 **断路器模式** 保护系统稳定性
4. **Safety** 模块通过 **Blocklist** 和 **AuditLogger** 确保操作安全
5. **延迟初始化** 使应用在无 API 密钥时仍可运行，自动降级到 **RuleEngine**

---

## 4. 示例对话

### 场景：用户询问项目架构

```
用户: 这个项目的 LLMRouter 是如何工作的？

助手: LLMRouter 是统一的大模型 API 网关层，主要功能包括：

1. **多 Provider 路由**：支持 6 个 Provider（DeepSeek/OpenAI/Anthropic/OpenRouter/SiliconFlow/Ollama）
2. **4 种路由策略**：
   - COST：成本优先，选择最便宜的模型
   - LATENCY：速度优先，选择响应最快的
   - FALLBACK：故障转移，自动切换可用 Provider
   - MANUAL：手动指定 Provider
3. **断路器保护**：连续失败 3 次后自动断开，60 秒后尝试恢复

核心代码位于 `src/analyzer/llm_router.py:97`
```

### 场景：用户询问降级机制

```
用户: 如果没有 API 密钥，系统还能工作吗？

助手: 可以。系统支持延迟初始化（Lazy Init）：

1. **无 API 密钥时**：应用正常启动，Analyzer 进入 lazy 模式
2. **自动降级**：LLM 不可用时，自动使用 RuleEngine 的 10 个预定义规则
3. **功能完整**：规则引擎可识别临时文件、缓存、日志、安装包等

初始化逻辑位于 `src/analyzer/llm_analyzer.py:61-99`
```

### 场景：用户询问安全机制

```
用户: 如何防止误删重要文件？

助手: 系统有多层安全保护：

1. **Blocklist**：38 个受保护的系统路径（如 Windows\System32）
2. **风险等级**：每个文件标注 LOW/MEDIUM/HIGH/CRITICAL
3. **ConfirmDialog**：删除前必须手动确认
4. **AuditLogger**：所有操作记录到 SQLite，支持恢复
5. **Diff Preview**：删除前显示文件详情和警告
```

---

## 5. 关键配置

| 配置项 | 位置 | 说明 |
|--------|------|------|
| LLM Router 配置 | `config/llm_config.json` | Provider 和模型配置 |
| 应用配置 | `~/.wiztree-cli-agent/config.json` | 用户级配置 |
| API 密钥 | 环境变量 | `DEEPSEEK_API_KEY`、`OPENAI_API_KEY` 等 |

---

## 6. 快速参考

### 常用命令

```bash
# CLI 模式
python app.py --cli

# 扫描并分析
python cli.py --scan "C:\Users" --analyze

# GUI 模式
python app.py
```

### 核心类

| 类 | 文件 | 用途 |
|----|------|------|
| `LLMRouter` | `src/analyzer/llm_router.py` | 多 Provider 路由 |
| `LLMAnalyzer` | `src/analyzer/llm_analyzer.py` | LLM 文件分析 |
| `RuleEngine` | `src/analyzer/rule_engine.py` | 规则引擎 |
| `WizTreeScanner` | `src/scanner/` | 磁盘扫描 |
| `ComprehensiveSafetyManager` | `src/safety/` | 安全管理 |

---

*此文档由项目代码自动分析生成，用于帮助开发者快速理解项目上下文。*
