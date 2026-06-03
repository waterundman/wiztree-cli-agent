"""
凭据存储
========

v1.2.0 新增：跨平台安全的 API Key 存储。

跨平台后端（统一通过 `keyring` 库）：
    - Windows: Windows Credential Manager (DPAPI 加密)
    - macOS:   Keychain
    - Linux:   Secret Service (gnome-keyring / kwallet 等)

设计原则：
    - 统一接口：store_api_key / get_api_key / delete_api_key / list_providers
    - 服务名 (service_name) 默认为 "wiztree-cli-agent"，可注入以做测试隔离
    - list_providers 跨后端不可靠（DPAPI 不支持枚举），
      因此用 ~/.wiztree-cli-agent/.credential_index.json 做轻量索引
    - 任何凭据都不写入业务 config.json，sanitize 导出天然安全
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

try:
    import keyring
    import keyring.errors
    _KEYRING_AVAILABLE = True
except ImportError:  # pragma: no cover - import-time guard
    keyring = None  # type: ignore
    _KEYRING_AVAILABLE = False


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 索引文件：用于 list_providers 跨平台
# ---------------------------------------------------------------------------
def _index_path() -> Path:
    return Path.home() / ".wiztree-cli-agent" / ".credential_index.json"


class CredentialStoreError(RuntimeError):
    """凭据存储错误（keyring 不可用 / 后端异常等）"""


class CredentialStore:
    """
    跨平台凭据存储（v1.2.0）

    用法:
        store = CredentialStore()
        store.store_api_key("deepseek", "sk-xxx")
        key = store.get_api_key("deepseek")  # -> "sk-xxx" or None
        store.delete_api_key("deepseek")
        providers = store.list_providers()    # -> ["deepseek", ...]

    Attributes:
        service_name: keyring 服务名（同一 keyring 后端的命名空间）
    """

    DEFAULT_SERVICE = "wiztree-cli-agent"

    def __init__(self, service_name: Optional[str] = None) -> None:
        """
        Args:
            service_name: 自定义服务名（测试时用于隔离）；None 则使用默认值
        """
        self.service_name: str = service_name or self.DEFAULT_SERVICE

        if not _KEYRING_AVAILABLE:
            raise CredentialStoreError(
                "keyring 库未安装。请先运行: pip install keyring>=24.0.0"
            )

        # 获取当前后端（用于诊断）
        try:
            backend = keyring.get_keyring()
            self._backend_name: str = type(backend).__name__
        except Exception as e:  # pragma: no cover
            logger.warning("无法获取 keyring 后端: %s", e)
            self._backend_name = "<unknown>"

    # ------------------------------------------------------------------
    # 核心 API
    # ------------------------------------------------------------------
    def store_api_key(self, provider: str, key: str) -> None:
        """
        加密存储 API Key。

        Args:
            provider: 提供方名称，如 "deepseek" / "openai"
            key:      API Key 明文（写入后端之前内部不持久化）

        Raises:
            CredentialStoreError: 写入后端失败
            ValueError: provider/key 不合法
        """
        provider = (provider or "").strip()
        key = (key or "").strip()
        if not provider:
            raise ValueError("provider 不能为空")
        if not key:
            raise ValueError("key 不能为空")

        try:
            keyring.set_password(self.service_name, provider, key)
        except keyring.errors.PasswordSetError as e:
            raise CredentialStoreError(
                f"无法写入凭据 (provider={provider}): {e}"
            ) from e
        except Exception as e:
            # 部分后端在 no-keyring 守护进程场景下抛错
            raise CredentialStoreError(
                f"keyring 后端异常 ({self._backend_name}): {e}"
            ) from e

        self._add_to_index(provider)

    def get_api_key(self, provider: str) -> Optional[str]:
        """
        读取 API Key（解密后明文返回）。

        Args:
            provider: 提供方名称

        Returns:
            API Key 字符串；若不存在返回 None
        """
        provider = (provider or "").strip()
        if not provider:
            return None
        try:
            value = keyring.get_password(self.service_name, provider)
        except Exception as e:
            logger.warning(
                "keyring 读取失败 (provider=%s, backend=%s): %s",
                provider, self._backend_name, e,
            )
            return None
        if value is None:
            return None
        return value

    def delete_api_key(self, provider: str) -> None:
        """
        删除指定 provider 的 API Key。

        Args:
            provider: 提供方名称
        """
        provider = (provider or "").strip()
        if not provider:
            return
        try:
            keyring.delete_password(self.service_name, provider)
        except keyring.errors.PasswordDeleteError:
            # 不存在时静默忽略（幂等）
            pass
        except Exception as e:
            logger.warning(
                "keyring 删除失败 (provider=%s, backend=%s): %s",
                provider, self._backend_name, e,
            )
        self._remove_from_index(provider)

    def list_providers(self) -> List[str]:
        """
        列出所有已存储的 provider 名称（按字母排序）。

        Returns:
            provider 名称列表

        注意：
            Windows DPAPI 不支持枚举，因此本方法通过
            ~/.wiztree-cli-agent/.credential_index.json 维护索引。
            索引由 store_api_key / delete_api_key 自动维护。
        """
        idx = self._load_index()
        return sorted(idx.keys())

    # ------------------------------------------------------------------
    # 索引维护（仅用于 list_providers 跨平台）
    # ------------------------------------------------------------------
    def _load_index(self) -> Dict[str, str]:
        path = _index_path()
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # 索引仅记录 provider -> 时间戳字符串
                return {str(k): str(v) for k, v in data.items()}
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("凭据索引加载失败: %s", e)
        return {}

    def _save_index(self, data: Dict[str, str]) -> None:
        path = _index_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # 索引文件含 provider 名称（不含 api_key），但仍限制权限
            try:
                os.chmod(path, 0o600)
            except (OSError, AttributeError):
                # Windows 上 os.chmod 部分位会被忽略，不致命
                pass
        except OSError as e:
            logger.warning("凭据索引保存失败: %s", e)

    def _add_to_index(self, provider: str) -> None:
        from datetime import datetime, timezone
        idx = self._load_index()
        idx[provider] = datetime.now(timezone.utc).isoformat()
        self._save_index(idx)

    def _remove_from_index(self, provider: str) -> None:
        idx = self._load_index()
        if provider in idx:
            del idx[provider]
            self._save_index(idx)

    # ------------------------------------------------------------------
    # 诊断
    # ------------------------------------------------------------------
    def backend_name(self) -> str:
        """返回当前 keyring 后端类名（诊断用）"""
        return self._backend_name

    @staticmethod
    def is_available() -> bool:
        """keyring 库是否可用（静态检查）"""
        return _KEYRING_AVAILABLE
