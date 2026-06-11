"""
wiztree-cli-agent
=================

AI 驱动的磁盘清理助手 — 封装 WizTree CLI 工具，
通过 LLM 分析实现安全的人机交互文件清理。

v1.8.0 (2026-06-11)
-------------------
稳定化 + 测试版本：

* 修复风险等级显示（添加 CRITICAL 等级检查）
* 修复风险筛选下拉（添加 Critical 选项）
* 消除 72 处 except Exception: pass（添加日志）
* 修复 16 处 except ImportError（添加日志）
* 添加线程安全：_safe_call 添加 winfo_exists() 检查
* 新增 53 个测试用例

保留 v1.7.3 全部功能：
* 文件管理增强 + UI 修复
* CLI 增强 + 动态路由优化
* 虚拟滚动 + 内存优化 + 扫描缓存
* 加密凭据存储 + 3 级级联配置
* LLM Router 扩展
* Squarified Treemap + StatusBar
* 6 主题 + 键盘快捷键 + 拖放
* Diff 预览 + 审计日志 + 还原
"""

__version__ = "1.8.0"
