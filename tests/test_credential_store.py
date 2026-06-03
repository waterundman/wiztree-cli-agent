"""
CredentialStore 测试 (Stage 1 / v1.2.0)

注意：本测试在所有平台都应通过（使用独立 service_name 隔离真实 keyring，
并对后端失败采取容错）。
"""

import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.credential_store import (  # noqa: E402
    CredentialStore,
    CredentialStoreError,
    _KEYRING_AVAILABLE,
    _index_path,
)


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------
@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    if hasattr(Path, "home"):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # 清掉可能存在的旧索引
    idx = tmp_path / ".wiztree-cli-agent" / ".credential_index.json"
    if idx.exists():
        idx.unlink()
    return tmp_path


@pytest.fixture
def isolated_store(tmp_home):
    """
    一个使用独立 service_name 的 CredentialStore 实例（不污染真实命名空间）。
    """
    service = f"wiztree-cli-agent-test-{uuid.uuid4().hex[:8]}"
    store = CredentialStore(service_name=service)
    yield store
    # 清理所有 provider
    for p in store.list_providers():
        try:
            store.delete_api_key(p)
        except Exception:
            pass


# ----------------------------------------------------------------------
# Test: is_available / import
# ----------------------------------------------------------------------
class TestAvailability:
    def test_keyring_imported(self):
        """keyring 库应该被 import 成功"""
        assert _KEYRING_AVAILABLE is True

    def test_credential_store_can_be_instantiated(self, isolated_store):
        assert isolated_store is not None
        assert isolated_store.service_name.startswith("wiztree-cli-agent-test-")

    def test_backend_name_is_string(self, isolated_store):
        b = isolated_store.backend_name()
        assert isinstance(b, str)
        assert len(b) > 0


# ----------------------------------------------------------------------
# Test: 核心 CRUD
# ----------------------------------------------------------------------
class TestApiKeyCRUD:
    def test_store_and_get_roundtrip(self, isolated_store):
        isolated_store.store_api_key("deepseek", "sk-test-1234")
        assert isolated_store.get_api_key("deepseek") == "sk-test-1234"

    def test_get_nonexistent_returns_none(self, isolated_store):
        assert isolated_store.get_api_key("nonexistent-provider") is None

    def test_delete_removes_key(self, isolated_store):
        isolated_store.store_api_key("openai", "sk-x")
        isolated_store.delete_api_key("openai")
        assert isolated_store.get_api_key("openai") is None

    def test_delete_nonexistent_is_idempotent(self, isolated_store):
        # 不应抛错
        isolated_store.delete_api_key("never-existed")
        assert isolated_store.get_api_key("never-existed") is None

    def test_overwrite_existing_key(self, isolated_store):
        isolated_store.store_api_key("anthropic", "old-key")
        isolated_store.store_api_key("anthropic", "new-key")
        assert isolated_store.get_api_key("anthropic") == "new-key"

    def test_special_characters_in_key(self, isolated_store):
        weird = "sk-+/=_-!@#$%^&*()_+={}[]|:;\"'<>,.?/~`"
        isolated_store.store_api_key("openrouter", weird)
        assert isolated_store.get_api_key("openrouter") == weird


# ----------------------------------------------------------------------
# Test: list_providers
# ----------------------------------------------------------------------
class TestListProviders:
    def test_empty_initially(self, isolated_store):
        assert isolated_store.list_providers() == []

    def test_lists_stored_providers(self, isolated_store):
        isolated_store.store_api_key("a", "ka")
        isolated_store.store_api_key("b", "kb")
        isolated_store.store_api_key("c", "kc")
        providers = isolated_store.list_providers()
        assert sorted(providers) == ["a", "b", "c"]

    def test_delete_updates_list(self, isolated_store):
        isolated_store.store_api_key("a", "ka")
        isolated_store.store_api_key("b", "kb")
        assert len(isolated_store.list_providers()) == 2
        isolated_store.delete_api_key("a")
        assert isolated_store.list_providers() == ["b"]

    def test_list_providers_sorted(self, isolated_store):
        isolated_store.store_api_key("zeta", "z")
        isolated_store.store_api_key("alpha", "a")
        isolated_store.store_api_key("mu", "m")
        assert isolated_store.list_providers() == ["alpha", "mu", "zeta"]


# ----------------------------------------------------------------------
# Test: 输入校验
# ----------------------------------------------------------------------
class TestInputValidation:
    def test_empty_provider_raises(self, isolated_store):
        with pytest.raises(ValueError):
            isolated_store.store_api_key("", "sk-x")
        with pytest.raises(ValueError):
            isolated_store.store_api_key("   ", "sk-x")

    def test_empty_key_raises(self, isolated_store):
        with pytest.raises(ValueError):
            isolated_store.store_api_key("deepseek", "")
        with pytest.raises(ValueError):
            isolated_store.store_api_key("deepseek", "   ")

    def test_get_empty_provider_returns_none(self, isolated_store):
        assert isolated_store.get_api_key("") is None
        assert isolated_store.get_api_key("   ") is None

    def test_delete_empty_provider_is_noop(self, isolated_store):
        # 不应抛错
        isolated_store.delete_api_key("")
        isolated_store.delete_api_key("   ")


# ----------------------------------------------------------------------
# Test: 跨服务命名空间隔离
# ----------------------------------------------------------------------
class TestServiceIsolation:
    def test_different_services_do_not_clash(self, tmp_home):
        s1 = CredentialStore(service_name="wiztree-cli-agent-svc-A")
        s2 = CredentialStore(service_name="wiztree-cli-agent-svc-B")
        try:
            s1.store_api_key("deepseek", "key-A")
            s2.store_api_key("deepseek", "key-B")
            assert s1.get_api_key("deepseek") == "key-A"
            assert s2.get_api_key("deepseek") == "key-B"
        finally:
            for p in s1.list_providers():
                s1.delete_api_key(p)
            for p in s2.list_providers():
                s2.delete_api_key(p)


# ----------------------------------------------------------------------
# Test: 索引文件位置
# ----------------------------------------------------------------------
class TestIndexFile:
    def test_index_uses_home_dir(self, tmp_home):
        store = CredentialStore(service_name="wiztree-cli-agent-idx-test")
        store.store_api_key("p1", "k1")
        idx = _index_path()
        # 索引文件应在 ~/.wiztree-cli-agent/ 下
        assert str(idx).startswith(str(tmp_home))
        assert idx.exists()
        with open(idx, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "p1" in data
        # 清理
        store.delete_api_key("p1")


# ----------------------------------------------------------------------
# Test: 模拟 keyring 不可用
# ----------------------------------------------------------------------
class TestWithoutKeyring:
    def test_construction_fails_without_keyring(self, monkeypatch):
        """模拟 keyring 不可用时，必须抛 CredentialStoreError"""
        from src.utils import credential_store as cs_mod
        monkeypatch.setattr(cs_mod, "_KEYRING_AVAILABLE", False)
        with pytest.raises(CredentialStoreError):
            CredentialStore()

    def test_is_available_reflects_module_state(self, monkeypatch):
        from src.utils import credential_store as cs_mod
        monkeypatch.setattr(cs_mod, "_KEYRING_AVAILABLE", False)
        assert CredentialStore.is_available() is False
