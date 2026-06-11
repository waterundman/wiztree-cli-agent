"""
PromptStore — 用户自定义 Prompt 管理器（v1.2.0 / Stage 2）

设计目标
========

* Prompt 文件以纯文本方式存储到 ``~/.wiztree-cli-agent/prompts/{name}.txt``
* ``name`` 经 ``_safe_name`` 校验，禁止路径分隔符与控制字符
* 当前激活的 Prompt 名称持久化到 ``ConfigLoader``（key = ``llm.active_prompt``）
* 提供 ``list / get / set / delete / get_active / set_active`` 六个方法
* 任何 I/O 错误都抛出 ``PromptStoreError``（子类 ``OSError``），调用方可稳定捕获
* 兼容 Stage 1 的 ``ConfigLoader``：构造时可注入 ``config_loader``，否则使用全局单例

约定
----

* ``name`` 不含 ``.txt`` 后缀（store 内部会加上）
* ``set(name, content)`` 覆盖写；空 ``content`` 也允许（=清空）
* ``delete(name)`` 若不存在抛 ``PromptStoreError``；删除当前 active 时同步清空 active
* ``set_active(name)`` 校验 ``name`` 必须存在于 store，否则抛 ``PromptStoreError``
"""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------
class PromptStoreError(OSError):
    """PromptStore 操作失败时抛出的统一异常"""


# ---------------------------------------------------------------------------
# 路径工具
# ---------------------------------------------------------------------------
DEFAULT_PROMPTS = {
    "default_scan": (
        "analyze_scan",
        "You are a disk cleanup assistant. Analyze these files and identify:\n"
        "1. Temporary files that can be safely deleted\n"
        "2. Cache files no longer needed\n"
        "3. Old log files that can be archived\n"
        "4. Large files that may be forgotten\n\n"
        "Scan Results:\n{scan_results}"
    ),
    "analyze_logs": (
        "log_analysis",
        "You are a log analysis expert. Examine these log files:\n\n"
        "{log_files}\n\n"
        "Recommend which logs can be safely deleted or archived."
    ),
    "deep_cleanup": (
        "deep_analysis",
        "You are a thorough disk cleaner. For each file below, provide:\n"
        "1. Risk level (LOW/MEDIUM/HIGH/CRITICAL)\n"
        "2. Reason for deletion recommendation\n"
        "3. Estimated space savings\n\n"
        "Files:\n{files}"
    ),
}


def _default_prompts_dir() -> Path:
    return Path.home() / ".wiztree-cli-agent" / "prompts"


# name 合法字符：字母/数字/-_./ 1~64 长度
_NAME_RE = re.compile(r"^[A-Za-z0-9._\- ]{1,64}$")


def _safe_name(name: str) -> str:
    if not isinstance(name, str):
        raise PromptStoreError(f"name must be str, got {type(name).__name__}")
    if not name or not _NAME_RE.match(name):
        raise PromptStoreError(
            f"invalid prompt name: {name!r} (allowed: letters/digits/._- and space, 1-64 chars)"
        )
    return name


# ---------------------------------------------------------------------------
# PromptStore
# ---------------------------------------------------------------------------
class PromptStore:
    """
    用户自定义 Prompt 存储（CRUD + active 切换）。

    用法::

        store = PromptStore()
        store.set("default_scan", "Please analyze the following files...")
        store.set_active("default_scan")
        names = store.list()          # ["default_scan"]
        text  = store.get("default_scan")
    """

    ACTIVE_PROMPT_KEY: str = "llm.active_prompt"

    def __init__(
        self,
        prompts_dir: Optional[Path] = None,
        *,
        config_loader: Optional[Any] = None,
    ) -> None:
        """
        Args:
            prompts_dir:     存储目录；None 则使用 ``~/.wiztree-cli-agent/prompts/``
            config_loader:   Stage 1 ConfigLoader 实例（可选）
        """
        self._dir: Path = Path(prompts_dir) if prompts_dir else _default_prompts_dir()
        self._lock = threading.RLock()

        # 延迟解析 ConfigLoader，避免循环 import
        self._config_loader = config_loader
        self._owns_config = config_loader is None

        # 确保目录存在
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise PromptStoreError(f"cannot create prompts dir: {e}") from e

        if prompts_dir is None:
            self._seed_defaults()

    # ------------------------------------------------------------------
    # 内部：ConfigLoader 懒加载
    # ------------------------------------------------------------------
    def _seed_defaults(self) -> None:
        """Seed empty prompts directory with default templates on first run."""
        if not self._dir.is_dir():
            return
        if any(p.is_file() and p.suffix == ".txt" for p in self._dir.iterdir()):
            return
        with self._lock:
            for _key, (name, content) in DEFAULT_PROMPTS.items():
                path = self._dir / f"{name}.txt"
                try:
                    path.write_text(content, encoding="utf-8")
                except OSError as e:
                    logger.warning("seed default prompt %s failed: %s", name, e)
    def _get_config(self) -> Any:
        if self._config_loader is None:
            try:
                from ..utils.config_loader import ConfigLoader
            except ImportError as e:  # pragma: no cover
                raise PromptStoreError(f"ConfigLoader unavailable: {e}") from e
            self._config_loader = ConfigLoader.get_instance()
        return self._config_loader

    def _path_for(self, name: str) -> Path:
        safe = _safe_name(name)
        return self._dir / f"{safe}.txt"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def list(self) -> List[str]:
        """列出全部 prompt 名称（按文件名字典序）"""
        with self._lock:
            if not self._dir.is_dir():
                return []
            names: List[str] = []
            for p in self._dir.iterdir():
                if p.is_file() and p.suffix == ".txt":
                    names.append(p.stem)
            names.sort()
            return names

    def get(self, name: str) -> Optional[str]:
        """读取 prompt 内容；不存在返回 None"""
        path = self._path_for(name)
        if not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            raise PromptStoreError(f"read {name} failed: {e}") from e

    def set(self, name: str, content: str) -> None:
        """写入 prompt（覆盖）。``content`` 必须是 str。"""
        if not isinstance(content, str):
            raise PromptStoreError(
                f"content must be str, got {type(content).__name__}"
            )
        path = self._path_for(name)
        with self._lock:
            try:
                path.write_text(content, encoding="utf-8")
            except OSError as e:
                raise PromptStoreError(f"write {name} failed: {e}") from e

    def delete(self, name: str) -> None:
        """删除 prompt；若不存在抛 ``PromptStoreError``。若删除的是当前 active，同步清空。"""
        path = self._path_for(name)
        with self._lock:
            if not path.is_file():
                raise PromptStoreError(f"prompt not found: {name}")
            try:
                path.unlink()
            except OSError as e:
                raise PromptStoreError(f"delete {name} failed: {e}") from e
            # 若删除了 active，同步清空
            try:
                if self.get_active() == name:
                    self.set_active(None)  # type: ignore[arg-type]
            except PromptStoreError:
                # ConfigLoader 不可用时静默忽略
                logger.debug("failed to clear active after delete of %s", name)

    # ------------------------------------------------------------------
    # Active 切换（持久化到 ConfigLoader）
    # ------------------------------------------------------------------
    def get_active(self) -> Optional[str]:
        """返回当前 active prompt 名称；没有则 None。"""
        try:
            cfg = self._get_config()
            value = cfg.get(self.ACTIVE_PROMPT_KEY, None)
        except Exception as e:  # pragma: no cover
            logger.debug("get_active failed: %s", e)
            return None
        if isinstance(value, str) and value:
            # 防御：active 指向已不存在的 prompt 时，视为 None
            if not self._path_for(value).is_file():
                return None
            return value
        return None

    def set_active(self, name: Optional[str]) -> None:
        """
        设置 active prompt。``None`` 表示清空。

        Raises:
            PromptStoreError: name 非 None 且不存在
        """
        if name is None:
            self._set_active_raw(None)
            return

        _safe_name(name)
        if not self._path_for(name).is_file():
            raise PromptStoreError(f"cannot activate missing prompt: {name}")
        self._set_active_raw(name)

    def _set_active_raw(self, name: Optional[str]) -> None:
        try:
            cfg = self._get_config()
        except Exception as e:  # pragma: no cover
            raise PromptStoreError(f"ConfigLoader unavailable: {e}") from e
        try:
            if name is None:
                # 通过 set("", persist=False) 实际会写入空串——这里改用 reset_path
                # 简单方案：写入一个空字符串，并在 get_active 中已过滤
                cfg.set(self.ACTIVE_PROMPT_KEY, "", persist=True)
            else:
                cfg.set(self.ACTIVE_PROMPT_KEY, name, persist=True)
        except Exception as e:
            raise PromptStoreError(f"set_active({name!r}) failed: {e}") from e

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
    @property
    def prompts_dir(self) -> Path:
        return self._dir

    def get_active_content(self) -> Optional[str]:
        """返回当前 active prompt 的内容（便捷方法）"""
        name = self.get_active()
        if name is None:
            return None
        return self.get(name)


__all__ = [
    "PromptStore",
    "PromptStoreError",
]
