"""
wiztree-cli-agent
=================

AI 驱动的磁盘清理助手 — 封装 WizTree CLI 工具，
通过 LLM 分析实现安全的人机交互文件清理。

v1.5.0 (2026-06-04)
-------------------
CLI 增强 + 动态路由优化：

* Stage 1 — LLM Router 动态路由（LatencyProbe + WeightedRouter + batch_chat + RequestCoalescer）
* Stage 2 — CLI 脚本化（退出码 + --quiet/--json/--no-color + OutputFormatter）
* Stage 3 — CLI 批量扫描 + 导出（--batch/--batch-file + JSON/CSV 导出）
* Stage 4 — 集成测试 + CHANGELOG + 版本号升级

保留 v1.4.0 全部功能：
* 虚拟滚动 + 内存优化 + 扫描缓存
* 加密凭据存储 + 3 级级联配置
* LLM Router 扩展
* Squarified Treemap + StatusBar
* 6 主题 + 键盘快捷键 + 拖放
* Diff 预览 + 审计日志 + 还原
"""

__version__ = "1.5.0"
