"""
PromptStore 测试 (v1.2.0 / Stage 2)

覆盖：
- CRUD（list / get / set / delete）
- active 切换（get_active / set_active）
- 异常路径（invalid name / missing prompt）
- 删除当前 active 后自动清空 active
- 持久化到 ConfigLoader
"""

import sys
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterator

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer.prompt_store import (  # noqa: E402
    PromptStore,
    PromptStoreError,
    _safe_name,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_prompts_dir() -> Iterator[Path]:
    d = Path(tempfile.mkdtemp(prefix="prompts_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def isolated_config(tmp_path, monkeypatch) -> Iterator[Any]:
    """隔离 ConfigLoader 单例到 tmp_path"""
    from src.utils import ConfigLoader
    monkeypatch.setenv("HOME", str(tmp_path))
    if hasattr(Path, "home"):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
    ConfigLoader.reset_instance()
    yield ConfigLoader.get_instance()
    ConfigLoader.reset_instance()


@pytest.fixture
def store(tmp_prompts_dir, isolated_config) -> PromptStore:
    return PromptStore(prompts_dir=tmp_prompts_dir, config_loader=isolated_config)


# ---------------------------------------------------------------------------
# Test: name 校验
# ---------------------------------------------------------------------------
class TestSafeName:
    def test_accepts_normal(self):
        assert _safe_name("default_scan") == "default_scan"
        assert _safe_name("My Prompt-1.0") == "My Prompt-1.0"
        assert _safe_name("a") == "a"
        assert _safe_name("A" * 64) == "A" * 64

    def test_rejects_empty(self):
        with pytest.raises(PromptStoreError):
            _safe_name("")

    def test_rejects_too_long(self):
        with pytest.raises(PromptStoreError):
            _safe_name("a" * 65)

    def test_rejects_path_separator(self):
        with pytest.raises(PromptStoreError):
            _safe_name("../etc/passwd")
        with pytest.raises(PromptStoreError):
            _safe_name("a/b")
        with pytest.raises(PromptStoreError):
            _safe_name("a\\b")

    def test_rejects_non_string(self):
        with pytest.raises(PromptStoreError):
            _safe_name(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test: CRUD
# ---------------------------------------------------------------------------
class TestCRUD:
    def test_initial_list_is_empty(self, store):
        assert store.list() == []

    def test_set_and_get(self, store):
        store.set("foo", "hello world")
        assert store.get("foo") == "hello world"

    def test_set_overwrites(self, store):
        store.set("foo", "v1")
        store.set("foo", "v2")
        assert store.get("foo") == "v2"

    def test_set_empty_content_allowed(self, store):
        store.set("foo", "")
        assert store.get("foo") == ""

    def test_get_missing_returns_none(self, store):
        assert store.get("nope") is None

    def test_set_rejects_non_string_content(self, store):
        with pytest.raises(PromptStoreError):
            store.set("foo", 123)  # type: ignore[arg-type]

    def test_set_rejects_invalid_name(self, store):
        with pytest.raises(PromptStoreError):
            store.set("../bad", "x")

    def test_list_returns_sorted(self, store):
        for n in ("c", "a", "b"):
            store.set(n, f"content-{n}")
        assert store.list() == ["a", "b", "c"]

    def test_delete(self, store):
        store.set("foo", "x")
        store.delete("foo")
        assert store.get("foo") is None
        assert "foo" not in store.list()

    def test_delete_missing_raises(self, store):
        with pytest.raises(PromptStoreError):
            store.delete("nope")

    def test_delete_invalid_name_raises(self, store):
        with pytest.raises(PromptStoreError):
            store.delete("../bad")

    def test_files_persist_on_disk(self, tmp_prompts_dir, isolated_config):
        s1 = PromptStore(prompts_dir=tmp_prompts_dir, config_loader=isolated_config)
        s1.set("foo", "bar")
        # 新实例读取同一目录
        s2 = PromptStore(prompts_dir=tmp_prompts_dir, config_loader=isolated_config)
        assert s2.get("foo") == "bar"
        assert s2.list() == ["foo"]


# ---------------------------------------------------------------------------
# Test: active
# ---------------------------------------------------------------------------
class TestActive:
    def test_initial_active_is_none(self, store):
        assert store.get_active() is None

    def test_set_and_get_active(self, store):
        store.set("a", "x")
        store.set_active("a")
        assert store.get_active() == "a"

    def test_set_active_none_clears(self, store):
        store.set("a", "x")
        store.set_active("a")
        store.set_active(None)
        assert store.get_active() is None

    def test_set_active_missing_raises(self, store):
        with pytest.raises(PromptStoreError):
            store.set_active("does_not_exist")

    def test_set_active_invalid_name_raises(self, store):
        with pytest.raises(PromptStoreError):
            store.set_active("../bad")

    def test_delete_active_clears_active(self, store):
        store.set("a", "x")
        store.set_active("a")
        store.delete("a")
        assert store.get_active() is None

    def test_delete_non_active_keeps_active(self, store):
        store.set("a", "x")
        store.set("b", "y")
        store.set_active("a")
        store.delete("b")
        assert store.get_active() == "a"

    def test_get_active_content(self, store):
        store.set("a", "hello")
        store.set_active("a")
        assert store.get_active_content() == "hello"

    def test_get_active_content_when_none(self, store):
        assert store.get_active_content() is None

    def test_active_persists_in_config(self, store, isolated_config):
        store.set("a", "x")
        store.set_active("a")
        assert isolated_config.get("llm.active_prompt") == "a"

    def test_active_clear_persists(self, store, isolated_config):
        store.set("a", "x")
        store.set_active("a")
        store.set_active(None)
        # ConfigLoader 中存的是空串，但 get_active() 应返回 None
        assert store.get_active() is None


# ---------------------------------------------------------------------------
# Test: active 指向已不存在的文件
# ---------------------------------------------------------------------------
class TestActiveDangling:
    def test_dangling_active_returns_none(self, tmp_prompts_dir, isolated_config):
        s = PromptStore(prompts_dir=tmp_prompts_dir, config_loader=isolated_config)
        s.set("a", "x")
        s.set_active("a")
        # 手工把文件删了，但 ConfigLoader 里还有记录
        (tmp_prompts_dir / "a.txt").unlink()
        assert s.get_active() is None


# ---------------------------------------------------------------------------
# Test: 目录自动创建
# ---------------------------------------------------------------------------
class TestDirCreation:
    def test_creates_missing_dir(self, tmp_path):
        d = tmp_path / "new_dir" / "prompts"
        s = PromptStore(prompts_dir=d)
        assert d.is_dir()
        s.set("x", "y")
        assert (d / "x.txt").is_file()
