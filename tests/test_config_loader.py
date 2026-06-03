"""
ConfigLoader 测试 (Stage 1 / v1.2.0)
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 让 tests/ 顶层可以 import src.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import ConfigLoader, BUILTIN_DEFAULTS  # noqa: E402
from src.utils.config_loader import (  # noqa: E402
    _default_config_path,
    _strip_api_keys,
    _deep_merge,
    _has_path,
    _get_by_path,
    _set_by_path,
)


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------
@pytest.fixture
def tmp_config_home(tmp_path, monkeypatch):
    """将 HOME 指向临时目录，隔离用户配置文件"""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Windows 下 HOME 可能不生效，强制覆盖
    if hasattr(Path, "home"):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def loader(tmp_config_home):
    """提供一个全新的 ConfigLoader 实例（隔离单例）"""
    ConfigLoader.reset_instance()
    cfg = ConfigLoader(auto_migrate=False)
    yield cfg
    ConfigLoader.reset_instance()


# ----------------------------------------------------------------------
# Test: _default_config_path
# ----------------------------------------------------------------------
class TestDefaultConfigPath:
    def test_default_path_points_to_home(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        p = _default_config_path()
        assert p == tmp_path / ".wiztree-cli-agent" / "config.json"
        assert "wiztree-cli-agent" in str(p)


# ----------------------------------------------------------------------
# Test: utility helpers
# ----------------------------------------------------------------------
class TestHelpers:
    def test_strip_api_keys_removes_top_level(self):
        data = {"api_key": "secret", "name": "deepseek", "nested": {"apiKey": "x"}}
        out = _strip_api_keys(data)
        assert "api_key" not in out
        assert "apiKey" not in out["nested"]
        assert out["name"] == "deepseek"

    def test_strip_api_keys_handles_list(self):
        data = [{"api_key": "x", "name": "a"}, {"api_key": "y", "name": "b"}]
        out = _strip_api_keys(data)
        assert all("api_key" not in d for d in out)
        assert [d["name"] for d in out] == ["a", "b"]

    def test_deep_merge_preserves_unique_keys(self):
        a = {"x": 1, "nested": {"a": 1, "b": 2}}
        b = {"y": 2, "nested": {"b": 99, "c": 3}}
        out = _deep_merge(a, b)
        assert out == {"x": 1, "y": 2, "nested": {"a": 1, "b": 99, "c": 3}}

    def test_deep_merge_does_not_mutate_inputs(self):
        a = {"nested": {"a": 1}}
        b = {"nested": {"b": 2}}
        _deep_merge(a, b)
        assert a == {"nested": {"a": 1}}
        assert b == {"nested": {"b": 2}}

    def test_get_set_by_path_basic(self):
        d: dict = {}
        _set_by_path(d, "a.b.c", 42)
        assert d == {"a": {"b": {"c": 42}}}
        assert _get_by_path(d, "a.b.c") == 42

    def test_has_path(self):
        d = {"a": {"b": 1}}
        assert _has_path(d, "a.b") is True
        assert _has_path(d, "a.c") is False
        assert _has_path(d, "x") is False


# ----------------------------------------------------------------------
# Test: ConfigLoader — 三级级联
# ----------------------------------------------------------------------
class TestCascadeResolution:
    def test_get_returns_builtin_default(self, loader):
        """L3 builtin 必须能取到"""
        assert loader.get("llm.strategy") == "fallback"
        assert loader.get("ui.theme") == "blue"
        assert loader.get("scan.default_top_n") == 50

    def test_get_returns_default_for_missing_key(self, loader):
        assert loader.get("nonexistent.key", "fallback") == "fallback"
        assert loader.get("nonexistent.key") is None

    def test_user_config_overrides_default(self, tmp_config_home):
        """L2 用户配置覆盖 L3"""
        # 写入用户配置
        cfg_dir = tmp_config_home / ".wiztree-cli-agent"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.json").write_text(
            json.dumps({"llm": {"strategy": "cost"}, "ui": {"theme": "green"}}),
            encoding="utf-8",
        )
        ConfigLoader.reset_instance()
        loader = ConfigLoader(auto_migrate=False)
        assert loader.get("llm.strategy") == "cost"
        assert loader.get("ui.theme") == "green"
        # 未覆盖的 key 仍走 builtin
        assert loader.get("llm.default_model") == "deepseek-v4-flash"

    def test_override_beats_user_beats_default(self, tmp_config_home):
        """L1 in-memory override 覆盖 L2/L3"""
        cfg_dir = tmp_config_home / ".wiztree-cli-agent"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.json").write_text(
            json.dumps({"llm": {"strategy": "cost"}}),
            encoding="utf-8",
        )
        ConfigLoader.reset_instance()
        loader = ConfigLoader(auto_migrate=False)
        # 用户配置 -> cost
        assert loader.get("llm.strategy") == "cost"
        # 显式 override
        loader._overrides = {"llm": {"strategy": "latency"}}
        assert loader.get("llm.strategy") == "latency"

    def test_nested_key_lookup(self, loader):
        """深层 key 必须能穿透"""
        providers = loader.get("llm.providers")
        assert isinstance(providers, list)
        assert any(p["name"] == "deepseek" for p in providers)


# ----------------------------------------------------------------------
# Test: set / persist / reset
# ----------------------------------------------------------------------
class TestSetPersistReset:
    def test_set_persists_to_disk(self, tmp_config_home, loader):
        loader.set("ui.theme", "dark-blue")
        # 重新实例化，必须能从磁盘读到
        ConfigLoader.reset_instance()
        loader2 = ConfigLoader(auto_migrate=False)
        assert loader2.get("ui.theme") == "dark-blue"

    def test_set_with_persist_false_does_not_touch_disk(self, tmp_config_home, loader):
        loader.set("ui.theme", "system", persist=False)
        # 重新实例化应读不到（因为没落盘），但当前实例可读到（in-memory override）
        assert loader.get("ui.theme") == "system"
        ConfigLoader.reset_instance()
        loader2 = ConfigLoader(auto_migrate=False)
        # 仍然应为 builtin blue
        assert loader2.get("ui.theme") == "blue"

    def test_reset_clears_overrides_and_reloads(self, tmp_config_home):
        cfg_dir = tmp_config_home / ".wiztree-cli-agent"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.json").write_text(
            json.dumps({"ui": {"theme": "green"}}),
            encoding="utf-8",
        )
        ConfigLoader.reset_instance()
        loader = ConfigLoader(auto_migrate=False)
        assert loader.get("ui.theme") == "green"
        # 修改并落盘
        loader.set("ui.theme", "dark-blue")
        # 重新走一遍 reset（清空 override，重新读盘）
        loader.reset()
        assert loader.get("ui.theme") == "dark-blue"  # 磁盘上的值
        # 强制写新值
        loader.set("ui.theme", "light")
        loader.reset()
        assert loader.get("ui.theme") == "light"

    def test_reset_to_defaults_clears_user_config(self, tmp_config_home, loader):
        loader.set("ui.theme", "system")
        loader.reset_to_defaults()
        # override 与 user 都清空 -> 回到 builtin
        assert loader.get("ui.theme") == "blue"


# ----------------------------------------------------------------------
# Test: export / import
# ----------------------------------------------------------------------
class TestExportImport:
    def test_export_writes_json(self, tmp_config_home, loader, tmp_path):
        out = tmp_path / "export.json"
        loader.export(str(out), sanitize=True)
        assert out.exists()
        with open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 必须包含 builtin keys
        assert "llm" in data
        assert "ui" in data

    def test_export_sanitize_strips_api_key(self, tmp_config_home, loader, tmp_path):
        out = tmp_path / "sanitized.json"
        # 在 builtin 里塞一个 api_key 模拟
        loader._overrides = {
            "llm": {
                "providers": [
                    {"name": "deepseek", "api_key": "sk-supersecret", "base_url": "x"}
                ]
            }
        }
        loader.export(str(out), sanitize=True)
        with open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        # api_key 必须被剥掉
        for prov in data["llm"]["providers"]:
            assert "api_key" not in prov

    def test_export_no_sanitize_keeps_api_key(self, tmp_config_home, loader, tmp_path):
        out = tmp_path / "raw.json"
        loader._overrides = {
            "llm": {
                "providers": [
                    {"name": "deepseek", "api_key": "sk-supersecret"}
                ]
            }
        }
        loader.export(str(out), sanitize=False)
        with open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["llm"]["providers"][0]["api_key"] == "sk-supersecret"

    def test_import_merges_into_user_config(self, tmp_config_home, loader, tmp_path):
        src = tmp_path / "import.json"
        src.write_text(
            json.dumps({"llm": {"strategy": "latency"}, "ui": {"theme": "green"}}),
            encoding="utf-8",
        )
        loader.import_from(str(src))
        # merged into user
        assert loader.get("llm.strategy") == "latency"
        assert loader.get("ui.theme") == "green"
        # 未指定 key 仍走 builtin
        assert loader.get("llm.default_model") == "deepseek-v4-flash"

    def test_import_strips_api_key(self, tmp_config_home, loader, tmp_path):
        src = tmp_path / "evil.json"
        src.write_text(
            json.dumps({"llm": {"api_key": "stolen"}}),
            encoding="utf-8",
        )
        loader.import_from(str(src))
        # 不应保留 api_key
        snap = loader.snapshot()
        assert "api_key" not in snap.get("llm", {})

    def test_import_rejects_non_dict(self, tmp_config_home, loader, tmp_path):
        src = tmp_path / "bad.json"
        src.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
        with pytest.raises(ValueError):
            loader.import_from(str(src))


# ----------------------------------------------------------------------
# Test: v1.1.0 兼容性 + 自动迁移
# ----------------------------------------------------------------------
class TestV110Migration:
    def test_legacy_config_migrates_to_new_location(self, tmp_config_home):
        """
        在项目 config/llm_config.json 存在且新位置为空时，
        应自动复制到 ~/.wiztree-cli-agent/config.json
        """
        # 构造一个 v1.1.0 legacy 文件
        legacy = Path(__file__).parent.parent / "config" / "llm_config.json"
        assert legacy.exists(), "v1.1.0 config file must exist for migration test"

        ConfigLoader.reset_instance()
        loader = ConfigLoader(auto_migrate=True)
        # 新位置应已创建
        new_path = tmp_config_home / ".wiztree-cli-agent" / "config.json"
        assert new_path.exists()
        # 加载后能看到 legacy 中的内容
        with open(new_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "llm" in data
        assert data["llm"]["strategy"] in ("fallback", "cost", "latency", "manual")

    def test_no_migration_when_user_config_exists(self, tmp_config_home):
        """新位置已有配置时，不应覆盖"""
        cfg_dir = tmp_config_home / ".wiztree-cli-agent"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.json").write_text(
            json.dumps({"ui": {"theme": "system"}}),
            encoding="utf-8",
        )
        ConfigLoader.reset_instance()
        loader = ConfigLoader(auto_migrate=True)
        # theme 应保留为 system（迁移未触发）
        assert loader.get("ui.theme") == "system"

    def test_legacy_load_llm_config_still_works(self):
        """v1.1.0 函数 load_llm_config 不能被破坏"""
        from src.utils import load_llm_config
        legacy = Path(__file__).parent.parent / "config" / "llm_config.json"
        if legacy.exists():
            data = load_llm_config()
            assert "providers" in data

    def test_get_default_router_still_works(self):
        """v1.1.0 get_default_router 不能被破坏"""
        from src.utils import get_default_router
        from src.analyzer import LLMRouter, RoutingStrategy
        router = get_default_router()
        assert isinstance(router, LLMRouter)
        assert isinstance(router.strategy, RoutingStrategy)
        assert len(router.providers) > 0


# ----------------------------------------------------------------------
# Test: snapshot
# ----------------------------------------------------------------------
class TestSnapshot:
    def test_snapshot_returns_deepcopy(self, loader):
        s1 = loader.snapshot()
        s1["llm"]["strategy"] = "MUTATED"
        # 不应影响 loader
        assert loader.get("llm.strategy") != "MUTATED"

    def test_snapshot_contains_builtin_keys(self, loader):
        snap = loader.snapshot()
        for top in ("llm", "ui", "scan", "safety"):
            assert top in snap, f"snapshot must contain '{top}'"
