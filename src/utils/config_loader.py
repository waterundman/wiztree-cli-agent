"""
配置加载器
===========

v1.2.0 重构：三级级联配置层
- Level 1: built-in defaults (程序内建默认)
- Level 2: ~/.wiztree-cli-agent/config.json (用户配置文件)
- Level 3: in-memory overrides (CLI/GUI 运行时覆盖)

v1.1.0 兼容：保留 load_llm_config / create_router_from_config / get_default_router /
create_custom_router 四个函数（v1.1.0 已通过其测试），同时新增 ConfigLoader 类。

API Key 加密：API Key 不再存放于 JSON 中，而是经由 CredentialStore
(keyring / Windows DPAPI / macOS Keychain / Linux Secret Service) 存储。
因此 export(sanitize=True) 永远不导出 api_key。
"""

import copy
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..analyzer.llm_router import (
    LLMRouter,
    RoutingStrategy,
    ProviderConfig,
    ModelConfig,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# v1.1.0 兼容函数（不要破坏既有 import / 测试）
# ---------------------------------------------------------------------------

def load_llm_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载 LLM 配置文件（v1.1.0 接口）

    Args:
        config_path: 配置文件路径，None 则使用默认路径 config/llm_config.json

    Returns:
        Dict: 配置字典

    Raises:
        FileNotFoundError: 配置文件不存在
    """
    if config_path is None:
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "llm_config.json"
        )

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_router_from_config(config_path: Optional[str] = None) -> LLMRouter:
    """
    从配置文件创建 LLM 路由器（v1.1.0 接口）

    Args:
        config_path: 配置文件路径

    Returns:
        LLMRouter: 路由器实例
    """
    config = load_llm_config(config_path)

    # 解析路由策略
    strategy_str = config.get("strategy", "fallback")
    strategy = RoutingStrategy(strategy_str)

    # 解析 Provider
    providers = []
    for provider_config in config.get("providers", []):
        # 解析模型
        models = []
        for model_config in provider_config.get("models", []):
            model = ModelConfig(
                id=model_config["id"],
                aliases=model_config.get("aliases", []),
                context_window=model_config.get("context_window", 4096),
                max_output=model_config.get("max_output", 4096),
                cost_input=model_config.get("cost_input", 0),
                cost_output=model_config.get("cost_output", 0),
                features=model_config.get("features", {}),
            )
            models.append(model)

        # 创建 Provider 配置
        provider = ProviderConfig(
            name=provider_config["name"],
            base_url=provider_config["base_url"],
            api_key_env=provider_config.get("api_key_env", ""),
            api_key=provider_config.get("api_key"),
            compatibility=provider_config.get("compatibility", ["openai"]),
            models=models,
            priority=provider_config.get("priority", 1),
            tags=provider_config.get("tags", []),
            timeout=provider_config.get("timeout", 30),
            max_retries=provider_config.get("max_retries", 2),
        )
        providers.append(provider)

    # 创建路由器
    router = LLMRouter(
        strategy=strategy,
        providers=providers,
        default_model=config.get("default_model"),
        timeout=config.get("timeout", 30),
        max_retries=config.get("max_retries", 2),
    )

    return router


def get_default_router() -> LLMRouter:
    """
    获取默认路由器（v1.1.0 接口）

    Returns:
        LLMRouter: 路由器实例
    """
    try:
        return create_router_from_config()
    except FileNotFoundError:
        # 配置文件不存在，使用默认配置
        return LLMRouter(
            strategy=RoutingStrategy.FALLBACK,
            default_model="deepseek-v4-flash",
        )


def create_custom_router(
    strategy: str = "fallback",
    providers: Optional[list] = None,
    default_model: str = "deepseek-v4-flash",
) -> LLMRouter:
    """
    创建自定义路由器（v1.1.0 接口）

    Args:
        strategy: 路由策略 (cost, latency, fallback, manual)
        providers: Provider 配置列表
        default_model: 默认模型

    Returns:
        LLMRouter: 路由器实例
    """
    routing_strategy = RoutingStrategy(strategy)

    if providers is None:
        return LLMRouter(
            strategy=routing_strategy,
            default_model=default_model,
        )

    # 转换 Provider 配置
    provider_configs = []
    for p in providers:
        models = []
        for m in p.get("models", []):
            model = ModelConfig(
                id=m["id"],
                aliases=m.get("aliases", []),
                context_window=m.get("context_window", 4096),
                max_output=m.get("max_output", 4096),
                cost_input=m.get("cost_input", 0),
                cost_output=m.get("cost_output", 0),
                features=m.get("features", {}),
            )
            models.append(model)

        provider = ProviderConfig(
            name=p["name"],
            base_url=p["base_url"],
            api_key_env=p.get("api_key_env", ""),
            api_key=p.get("api_key"),
            compatibility=p.get("compatibility", ["openai"]),
            models=models,
            priority=p.get("priority", 1),
            tags=p.get("tags", []),
            timeout=p.get("timeout", 30),
            max_retries=p.get("max_retries", 2),
        )
        provider_configs.append(provider)

    return LLMRouter(
        strategy=routing_strategy,
        providers=provider_configs,
        default_model=default_model,
    )


# ---------------------------------------------------------------------------
# v1.2.0 新增：ConfigLoader
# ---------------------------------------------------------------------------

# 内建默认值（v1.1.0 config/llm_config.json 兼容结构）
BUILTIN_DEFAULTS: Dict[str, Any] = {
    "llm": {
        "strategy": "fallback",
        "default_model": "deepseek-v4-flash",
        "default_provider": "deepseek",
        "timeout": 30,
        "max_retries": 2,
        "providers": [
            {
                "name": "deepseek",
                "base_url": "https://api.deepseek.com",
                "api_key_env": "DEEPSEEK_API_KEY",
                "compatibility": ["openai", "anthropic"],
                "priority": 1,
                "tags": ["cost", "thinking", "china"],
                "models": [
                    {
                        "id": "deepseek-v4-flash",
                        "aliases": ["deepseek-chat"],
                        "context_window": 1000000,
                        "max_output": 8192,
                        "cost_input": 0.14,
                        "cost_output": 0.28,
                        "features": {"streaming": True, "thinking": True, "tool_calls": True},
                    },
                    {
                        "id": "deepseek-v4-pro",
                        "aliases": ["deepseek-reasoner"],
                        "context_window": 1000000,
                        "max_output": 8192,
                        "cost_input": 0.44,
                        "cost_output": 0.87,
                        "features": {"streaming": True, "thinking": True, "tool_calls": True},
                    },
                ],
            },
            {
                "name": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "compatibility": ["openai"],
                "priority": 2,
                "tags": ["general", "vision"],
                "models": [
                    {
                        "id": "gpt-4o-mini",
                        "context_window": 128000,
                        "max_output": 16384,
                        "cost_input": 0.15,
                        "cost_output": 0.60,
                        "features": {"streaming": True, "tool_calls": True, "vision": True},
                    },
                    {
                        "id": "gpt-4o",
                        "context_window": 128000,
                        "max_output": 16384,
                        "cost_input": 2.50,
                        "cost_output": 10.00,
                        "features": {"streaming": True, "tool_calls": True, "vision": True},
                    },
                ],
            },
            {
                "name": "anthropic",
                "base_url": "https://api.anthropic.com/v1",
                "api_key_env": "ANTHROPIC_API_KEY",
                "compatibility": ["anthropic", "openai"],
                "priority": 3,
                "tags": ["core", "reasoning"],
                "models": [
                    {
                        "id": "claude-3-haiku-20240307",
                        "aliases": ["claude-haiku"],
                        "context_window": 200000,
                        "max_output": 4096,
                        "cost_input": 0.25,
                        "cost_output": 1.25,
                        "features": {"streaming": True, "tool_calls": True},
                    },
                    {
                        "id": "claude-3-5-sonnet-20241022",
                        "aliases": ["claude-sonnet"],
                        "context_window": 200000,
                        "max_output": 8192,
                        "cost_input": 3.00,
                        "cost_output": 15.00,
                        "features": {"streaming": True, "tool_calls": True, "vision": True},
                    },
                ],
            },
            {
                "name": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
                "compatibility": ["openai"],
                "priority": 4,
                "tags": ["aggregator", "fallback"],
                "models": [
                    {
                        "id": "deepseek/deepseek-v4-flash",
                        "context_window": 1000000,
                        "max_output": 8192,
                        "cost_input": 0.14,
                        "cost_output": 0.28,
                        "features": {"streaming": True, "thinking": True},
                    },
                    {
                        "id": "google/gemini-2.0-flash-exp:free",
                        "aliases": ["gemini-flash-free"],
                        "context_window": 1000000,
                        "max_output": 8192,
                        "cost_input": 0,
                        "cost_output": 0,
                        "features": {"streaming": True},
                    },
                ],
            },
            {
                "name": "siliconflow",
                "base_url": "https://api.siliconflow.cn/v1",
                "api_key_env": "SILICONFLOW_API_KEY",
                "compatibility": ["openai"],
                "priority": 5,
                "tags": ["free", "china", "fallback"],
                "models": [
                    {
                        "id": "deepseek-ai/DeepSeek-V3",
                        "aliases": ["deepseek-v3-sf"],
                        "context_window": 65536,
                        "max_output": 8192,
                        "cost_input": 0.0,
                        "cost_output": 0.0,
                        "features": {"streaming": True},
                    },
                    {
                        "id": "Qwen/Qwen2.5-7B-Instruct",
                        "aliases": ["qwen-2.5-7b"],
                        "context_window": 32768,
                        "max_output": 8192,
                        "cost_input": 0.0,
                        "cost_output": 0.0,
                        "features": {"streaming": True},
                    },
                ],
            },
            {
                "name": "ollama",
                "base_url": "http://localhost:11434/v1",
                "api_key_env": "NO_AUTH",
                "api_key": "ollama",
                "compatibility": ["openai"],
                "priority": 10,
                "tags": ["local", "free", "fallback"],
                "models": [
                    {
                        "id": "llama3.2",
                        "context_window": 8192,
                        "max_output": 4096,
                        "cost_input": 0,
                        "cost_output": 0,
                        "features": {"streaming": True},
                    },
                    {
                        "id": "qwen2.5",
                        "context_window": 32768,
                        "max_output": 8192,
                        "cost_input": 0,
                        "cost_output": 0,
                        "features": {"streaming": True},
                    },
                ],
            },
        ],
    },
    "ui": {
        "theme": "blue",  # blue / green / dark-blue / dark-green / light / system
        "appearance_mode": "system",  # system / light / dark
        "language": "en",
    },
    "scan": {
        "default_path": "",
        "follow_symlinks": False,
        "include_hidden": False,
        "min_file_size": 0,
        "default_top_n": 50,
        "auto_refresh": True,
    },
    "safety": {
        "confirm_delete": True,
        "send2trash": True,
        "backup_before_delete": False,
    },
}

# API Key 字段名（脱敏时排除）
_API_KEY_KEYS = {"api_key", "apiKey", "apikey"}


def _default_config_dir() -> Path:
    """返回用户配置目录 ~/.wiztree-cli-agent"""
    return Path.home() / ".wiztree-cli-agent"


def _default_config_path() -> Path:
    """返回用户配置文件路径 ~/.wiztree-cli-agent/config.json"""
    return _default_config_dir() / "config.json"


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """
    深度合并字典：overlay 覆盖 base，但保留 base 中独有的键。
    """
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _strip_api_keys(data: Any) -> Any:
    """递归移除 api_key 字段（脱敏）"""
    if isinstance(data, dict):
        return {
            k: _strip_api_keys(v)
            for k, v in data.items()
            if k not in _API_KEY_KEYS
        }
    if isinstance(data, list):
        return [_strip_api_keys(v) for v in data]
    return data


_MISSING = object()


def _get_by_path(data: Dict[str, Any], dotted_key: str) -> Any:
    """支持 a.b.c 形式按键取值；未命中返回 _MISSING 哨兵"""
    parts = dotted_key.split(".")
    cur: Any = data
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return _MISSING
    return cur


def _set_by_path(data: Dict[str, Any], dotted_key: str, value: Any) -> None:
    """支持 a.b.c 形式按键赋值（中间 dict 不存在则创建）"""
    parts = dotted_key.split(".")
    cur = data
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _has_path(data: Dict[str, Any], dotted_key: str) -> bool:
    """判断点分键是否存在于 data 中"""
    parts = dotted_key.split(".")
    cur: Any = data
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return False
    return True


class ConfigLoader:
    """
    三级级联配置加载器（v1.2.0）

    解析顺序（高优先级覆盖低优先级）：
        1. _overrides   - 内存覆盖（CLI flag / GUI 设置）
        2. _user_config - ~/.wiztree-cli-agent/config.json
        3. BUILTIN_DEFAULTS - 程序内建默认

    设计目标：
        - get/set/reset API 与 dict 类似
        - JSON 导入/导出（导出时默认脱敏）
        - v1.1.0 config/llm_config.json 自动迁移到新位置（首次实例化时）
    """

    _instance: Optional["ConfigLoader"] = None
    _instance_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Singleton 入口（可选；测试时可显式禁用）
    # ------------------------------------------------------------------
    @classmethod
    def get_instance(cls) -> "ConfigLoader":
        """获取全局唯一 ConfigLoader 实例"""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置全局单例（主要用于测试）"""
        with cls._instance_lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # 构造
    # ------------------------------------------------------------------
    def __init__(
        self,
        config_path: Optional[Path] = None,
        *,
        auto_migrate: bool = True,
    ) -> None:
        """
        Args:
            config_path: 用户配置文件路径；None 则使用 ~/.wiztree-cli-agent/config.json
            auto_migrate: 首次启动时是否将 v1.1.0 config/llm_config.json 自动迁移到新位置
        """
        self._config_path: Path = Path(config_path) if config_path else _default_config_path()
        self._user_config: Dict[str, Any] = {}
        self._overrides: Dict[str, Any] = {}

        # 1. 确保配置目录存在
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("无法创建配置目录 %s: %s", self._config_path.parent, e)

        # 2. 加载用户配置（如果存在）
        self._load_user_config()

        # 3. v1.1.0 自动迁移
        if auto_migrate and not self._user_config:
            migrated = self._try_migrate_v110()
            if migrated:
                logger.info("已自动迁移 v1.1.0 配置到 %s", self._config_path)

    # ------------------------------------------------------------------
    # 内部：加载用户配置
    # ------------------------------------------------------------------
    def _load_user_config(self) -> None:
        if not self._config_path.exists():
            return
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._user_config = data
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("无法加载用户配置 %s: %s", self._config_path, e)
            self._user_config = {}

    def _save_user_config(self) -> None:
        """将 _user_config 落盘"""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._user_config, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error("无法保存用户配置 %s: %s", self._config_path, e)
            raise

    # ------------------------------------------------------------------
    # 内部：v1.1.0 自动迁移
    # ------------------------------------------------------------------
    def _try_migrate_v110(self) -> bool:
        """
        尝试从 v1.1.0 config/llm_config.json 迁移到新位置。

        Returns:
            True 如果成功迁移；否则 False
        """
        legacy = (
            Path(__file__).parent.parent.parent / "config" / "llm_config.json"
        )
        if not legacy.exists():
            return False

        try:
            with open(legacy, "r", encoding="utf-8") as f:
                legacy_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("v1.1.0 配置读取失败: %s", e)
            return False

        if not isinstance(legacy_data, dict):
            return False

        # v1.1.0 顶层就是 llm 配置；包一层以适配 v1.2.0 结构
        self._user_config = {"llm": legacy_data}
        try:
            self._save_user_config()
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Public API：get / set / reset
    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        """
        三级级联取值。

        Args:
            key: 支持点分路径，如 "llm.strategy" 或 "ui.theme"
            default: 未找到时返回的默认值

        Returns:
            解析后的值；若都不存在返回 default
        """
        # 优先级：override > user > default
        v = _get_by_path(self._overrides, key)
        if v is not _MISSING:
            return v
        v = _get_by_path(self._user_config, key)
        if v is not _MISSING:
            return v
        v = _get_by_path(BUILTIN_DEFAULTS, key)
        if v is not _MISSING:
            return v
        return default

    def set(self, key: str, value: Any, *, persist: bool = True) -> None:
        """
        设置配置项。

        Args:
            key: 点分路径
            value: 值
            persist: 是否同时写入用户配置文件（默认 True）
        """
        _set_by_path(self._overrides, key, value)
        if persist:
            # 同步到 user 层（让 set 即是显式覆盖）并落盘
            _set_by_path(self._user_config, key, value)
            self._save_user_config()

    def reset(self) -> None:
        """重置：清空内存覆盖，并重新从磁盘加载用户配置"""
        self._overrides = {}
        self._load_user_config()

    def reset_to_defaults(self) -> None:
        """重置为内建默认值（不影响磁盘上的用户配置）"""
        self._overrides = {}
        self._user_config = {}

    # ------------------------------------------------------------------
    # Public API：导入/导出
    # ------------------------------------------------------------------
    def export(self, path: str, sanitize: bool = True) -> None:
        """
        导出当前合并后的配置到 JSON 文件。

        Args:
            path: 目标路径
            sanitize: True 时移除 api_key 字段（默认）
        """
        merged = self._merged_view()
        if sanitize:
            merged = _strip_api_keys(merged)

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

    def import_from(self, path: str, *, persist: bool = True) -> None:
        """
        从 JSON 文件导入配置，合并到用户层。

        Args:
            path: 源路径
            persist: 是否立即落盘
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Imported config must be a JSON object, got {type(data)}")

        # 防御：导入文件中如果含 api_key 字段，丢弃（安全）
        sanitized = _strip_api_keys(data)
        self._user_config = _deep_merge(self._user_config, sanitized)
        if persist:
            self._save_user_config()

    # ------------------------------------------------------------------
    # 视图 / 辅助
    # ------------------------------------------------------------------
    def _merged_view(self) -> Dict[str, Any]:
        """返回三级合并后的视图（override > user > default）"""
        merged = _deep_merge(BUILTIN_DEFAULTS, self._user_config)
        merged = _deep_merge(merged, self._overrides)
        return merged

    def snapshot(self) -> Dict[str, Any]:
        """返回当前生效配置的一份深拷贝（不修改内部状态）"""
        return copy.deepcopy(self._merged_view())

    def config_path(self) -> Path:
        """返回用户配置文件路径"""
        return self._config_path

    @staticmethod
    def _flatten_keys(data: Dict[str, Any], prefix: str = "") -> set:
        """递归展开 dict 的点分键名集合"""
        keys: set = set()
        for k, v in data.items():
            full = f"{prefix}.{k}" if prefix else k
            keys.add(full)
            if isinstance(v, dict):
                keys |= ConfigLoader._flatten_keys(v, full)
        return keys


# ---------------------------------------------------------------------------
# 模块级便利函数
# ---------------------------------------------------------------------------
def get_config_loader() -> ConfigLoader:
    """获取全局 ConfigLoader 单例"""
    return ConfigLoader.get_instance()
