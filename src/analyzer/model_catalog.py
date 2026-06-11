"""
ModelCatalog — OpenRouter 模型目录浏览器（v1.2.0 / Stage 2）

设计目标
========

* 从 OpenRouter 公开 API ``https://openrouter.ai/api/v1/models`` 拉取全部模型
* 拉取结果以 JSON 形式缓存到 ``~/.wiztree-cli-agent/models_cache.json``
* 默认 TTL 12 小时（43200 秒），过期或缺失时自动重新拉取
* API 不可用时（网络失败 / 超时 / 解析错误）回退到 ``FALLBACK_MODELS``
  （>= 5 个常见模型，离线可用）
* 支持按 provider 过滤、按 name/price/context 排序、模糊搜索
* 缓存元信息（时间、大小、provider 数）通过 ``info()`` 暴露
* 兼容 Stage 1 的 ``ConfigLoader``：构造时可注入 ``config_loader``，否则使用全局单例

约定
----

* ``ModelInfo`` 是不可变 dataclass，所有字段都是基本类型，UI 层可直接使用
* ``list()`` 的结果 *总是* 经过过滤+排序+搜索的浅拷贝（不会泄漏内部状态）
* 网络/磁盘 I/O 失败一律降级为 ``FALLBACK_MODELS``，不抛异常
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据类（必须先定义，供 FALLBACK_MODELS 引用）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ModelInfo:
    """单个模型的信息（不可变，便于 UI 直接绑定）"""

    id: str
    name: str
    provider: str
    context_length: int
    prompt_price: float       # USD per 1M tokens
    completion_price: float   # USD per 1M tokens

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 兜底模型列表：API 不可用时的最小可用集（>= 5 个）
# ---------------------------------------------------------------------------
FALLBACK_MODELS: List[ModelInfo] = [
    ModelInfo(
        id="deepseek/deepseek-v4-flash",
        name="DeepSeek V4 Flash",
        provider="openrouter",
        context_length=1_000_000,
        prompt_price=0.14,
        completion_price=0.28,
    ),
    ModelInfo(
        id="google/gemini-2.0-flash-exp:free",
        name="Gemini 2.0 Flash (free)",
        provider="openrouter",
        context_length=1_000_000,
        prompt_price=0.0,
        completion_price=0.0,
    ),
    ModelInfo(
        id="anthropic/claude-3.5-sonnet",
        name="Claude 3.5 Sonnet",
        provider="openrouter",
        context_length=200_000,
        prompt_price=3.00,
        completion_price=15.00,
    ),
    ModelInfo(
        id="openai/gpt-4o-mini",
        name="GPT-4o mini",
        provider="openrouter",
        context_length=128_000,
        prompt_price=0.15,
        completion_price=0.60,
    ),
    ModelInfo(
        id="meta-llama/llama-3.1-70b-instruct",
        name="Llama 3.1 70B Instruct",
        provider="openrouter",
        context_length=131_072,
        prompt_price=0.35,
        completion_price=0.40,
    ),
    ModelInfo(
        id="qwen/qwen-2.5-72b-instruct",
        name="Qwen 2.5 72B Instruct",
        provider="openrouter",
        context_length=131_072,
        prompt_price=0.40,
        completion_price=0.40,
    ),
]


# ---------------------------------------------------------------------------
# 路径工具
# ---------------------------------------------------------------------------
def _default_cache_dir() -> Path:
    return Path.home() / ".wiztree-cli-agent"


def _default_cache_path() -> Path:
    return _default_cache_dir() / "models_cache.json"


# ---------------------------------------------------------------------------
# OpenRouter 解析
# ---------------------------------------------------------------------------
def _parse_openrouter_payload(payload: Any) -> List[ModelInfo]:
    """
    OpenRouter ``/api/v1/models`` 返回 ``{"data": [...]}``，每项形如::

        {
            "id": "openai/gpt-4o-mini",
            "name": "OpenAI: GPT-4o mini",
            "context_length": 128000,
            "pricing": {"prompt": "0.00000015", "completion": "0.00000060"},
            "top_provider": {...}
        }

    ``pricing.prompt`` 的单位是 USD per token；我们换算成 USD per 1M tokens。
    """
    if not isinstance(payload, dict):
        raise ValueError("OpenRouter payload root is not an object")
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("OpenRouter payload missing 'data' list")

    out: List[ModelInfo] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id:
            continue
        # provider 取 id 中 '/' 前缀；fallback 到 "openrouter"
        if "/" in model_id:
            provider = model_id.split("/", 1)[0]
        else:
            provider = "openrouter"

        name = item.get("name") or model_id

        ctx = item.get("context_length") or 0
        try:
            context_length = int(ctx)
        except (TypeError, ValueError):
            context_length = 0

        pricing = item.get("pricing") or {}
        try:
            prompt_price = float(pricing.get("prompt", 0.0)) * 1_000_000
        except (TypeError, ValueError):
            prompt_price = 0.0
        try:
            completion_price = float(pricing.get("completion", 0.0)) * 1_000_000
        except (TypeError, ValueError):
            completion_price = 0.0

        out.append(
            ModelInfo(
                id=model_id,
                name=str(name),
                provider=str(provider),
                context_length=context_length,
                prompt_price=round(prompt_price, 4),
                completion_price=round(completion_price, 4),
            )
        )
    return out


# ---------------------------------------------------------------------------
# ModelCatalog
# ---------------------------------------------------------------------------
class ModelCatalog:
    """
    模型目录管理器（OpenRouter 缓存 + 离线降级）。

    用法::

        catalog = ModelCatalog()
        models  = catalog.list(provider="openai", sort_by="price", search="gpt")
        catalog.refresh()           # 强制拉新
        meta    = catalog.info()     # 缓存元信息
    """

    CACHE_TTL_SECONDS: int = 43_200  # 12 小时
    OPENROUTER_URL: str = "https://openrouter.ai/api/v1/models"
    REQUEST_TIMEOUT: float = 10.0

    def __init__(
        self,
        cache_path: Optional[Path] = None,
        *,
        config_loader: Optional[Any] = None,
    ) -> None:
        """
        Args:
            cache_path:     缓存文件路径；None 则使用 ``~/.wiztree-cli-agent/models_cache.json``
            config_loader:  Stage 1 ConfigLoader 实例（可选，仅用于 future 扩展）
        """
        self._cache_path: Path = Path(cache_path) if cache_path else _default_cache_path()
        self._config_loader = config_loader  # 当前未使用；保留以便后续注入
        self._models: List[ModelInfo] = []
        self._source: str = "empty"  # empty | cache | network | fallback

        # 首次构造时尝试加载（懒加载策略——不阻塞 import）
        # 但保证 list() 在没有缓存时也能返回 FALLBACK_MODELS。
        self._ensure_loaded()

    # ------------------------------------------------------------------
    # 内部：加载策略
    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> None:
        """缓存有效则直接复用；否则尝试网络拉取；都失败则用 fallback。"""
        if self._load_from_cache_if_fresh():
            return
        if self._fetch_from_network():
            return
        self._use_fallback()

    def _load_from_cache_if_fresh(self) -> bool:
        """尝试读取缓存，且 mtime 在 TTL 之内。"""
        try:
            if not self._cache_path.is_file():
                return False
            mtime = self._cache_path.stat().st_mtime
            if time.time() - mtime > self.CACHE_TTL_SECONDS:
                return False
            with open(self._cache_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            models = _parse_openrouter_payload(payload)
            if not models:
                return False
            self._models = models
            self._source = "cache"
            return True
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.debug("load_from_cache failed: %s", e)
            return False

    def _fetch_from_network(self) -> bool:
        """向 OpenRouter 发起 GET 请求；成功则写入缓存。"""
        try:
            import requests  # 延迟 import 以减少强依赖
        except ImportError:
            logger.debug("requests not available, skip network fetch")
            return False
        try:
            resp = requests.get(self.OPENROUTER_URL, timeout=self.REQUEST_TIMEOUT)
        except Exception as e:  # requests.RequestException + 其他网络错误
            logger.info("OpenRouter fetch failed: %s", e)
            return False
        try:
            if resp.status_code != 200:
                logger.info("OpenRouter returned HTTP %s", resp.status_code)
                return False
            try:
                payload = resp.json()
            except ValueError as e:
                logger.info("OpenRouter JSON decode failed: %s", e)
                return False
            models = _parse_openrouter_payload(payload)
            if not models:
                return False
            self._models = models
            self._source = "network"
            # 落盘缓存（best-effort）
            self._write_cache(payload)
            return True
        finally:
            try:
                resp.close()
            except Exception:  # pragma: no cover
                logger.debug("Failed to close HTTP response", exc_info=True)

    def _write_cache(self, payload: Any) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError as e:  # pragma: no cover - 写失败不影响内存结果
            logger.warning("write cache failed: %s", e)

    def _use_fallback(self) -> None:
        self._models = list(FALLBACK_MODELS)
        self._source = "fallback"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """强制重新拉取（忽略缓存 TTL）。网络失败仍走 fallback。"""
        if not self._fetch_from_network():
            self._use_fallback()

    def list(
        self,
        provider: Optional[str] = None,
        sort_by: str = "name",
        search: Optional[str] = None,
    ) -> List[ModelInfo]:
        """
        返回过滤 + 排序 + 搜索后的模型列表（浅拷贝）。

        Args:
            provider: 按 provider 过滤；``None`` 或 ``"all"`` 不过滤
            sort_by:  ``"name"`` / ``"price"`` / ``"context"``
            search:   模糊匹配（不区分大小写），匹配 ``id`` 或 ``name``
        """
        # 1. 过滤
        items: Sequence[ModelInfo] = self._models
        if provider and provider.lower() != "all":
            p = provider.lower()
            items = [m for m in items if m.provider.lower() == p]

        # 2. 搜索
        if search:
            needle = search.strip().lower()
            if needle:
                items = [
                    m for m in items
                    if needle in m.id.lower() or needle in m.name.lower()
                ]

        # 3. 排序（稳定排序避免抖动）
        if sort_by == "price":
            items = sorted(
                items,
                key=lambda m: (m.prompt_price + m.completion_price, m.name),
            )
        elif sort_by == "context":
            items = sorted(items, key=lambda m: (-m.context_length, m.name))
        else:
            # 默认 name
            items = sorted(items, key=lambda m: m.name.lower())

        return list(items)

    def info(self) -> Dict[str, Any]:
        """返回当前缓存元信息（不会触发网络请求）"""
        try:
            if self._cache_path.is_file():
                stat = self._cache_path.stat()
                size = stat.st_size
                mtime = stat.st_mtime
                age = max(0.0, time.time() - mtime)
            else:
                size = 0
                mtime = 0.0
                age = -1.0
        except OSError:
            size = 0
            mtime = 0.0
            age = -1.0

        providers = sorted({m.provider for m in self._models})
        return {
            "cache_path": str(self._cache_path),
            "cache_exists": self._cache_path.is_file(),
            "cache_size_bytes": size,
            "cache_mtime": mtime,
            "cache_age_seconds": age,
            "ttl_seconds": self.CACHE_TTL_SECONDS,
            "model_count": len(self._models),
            "providers": providers,
            "provider_count": len(providers),
            "source": self._source,
        }

    @property
    def cache_path(self) -> Path:
        return self._cache_path


__all__ = [
    "ModelInfo",
    "ModelCatalog",
    "FALLBACK_MODELS",
]
