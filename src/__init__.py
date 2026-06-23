"""
wiztree-cli-agent
=================

AI 驱动的磁盘清理助手 — 封装 WizTree CLI 工具，
通过 LLM 分析实现安全的人机交互文件清理。

v2.1.0 (2026-06-23)
-------------------
模块拆分 + Bug 修复版本：

* 修复 app.py run_cli() 中 status 变量未初始化问题（添加 try/except）
* 修复 cli.py 中 WizTreeAgentApp 未导入问题
* 重命名 file_validator.FileInfo → ValidationFileInfo（消除命名冲突）
* 拆分 llm_router.py（1378 行）为 5 个模块：
  - circuit_breaker.py: CircuitBreaker
  - latency_probe.py: LatencyProbe, LatencySample
  - request_coalescer.py: RequestCoalescer
  - batch.py: BatchRequest, BatchResult, batch_chat
  - llm_router.py: LLMRouter, WeightedRouter（核心路由逻辑）
* 版本号统一为 2.1.0

保留 v1.8.0 全部功能：
* 稳定化 + 测试版本
* 修复风险等级显示（添加 CRITICAL 等级检查）
* 消除 72 处 except Exception: pass（添加日志）
* 添加线程安全：_safe_call 添加 winfo_exists() 检查
* 新增 53 个测试用例
"""

__version__ = "2.1.0"
