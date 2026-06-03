"""
ModelCatalog 测试 (v1.2.0 / Stage 2)

覆盖：
- 缓存读写
- 过滤（provider）
- 排序（name / price / context）
- 搜索（大小写不敏感）
- 强制 refresh
- API 失败 → FALLBACK_MODELS 降级
- info() 元信息
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer.model_catalog import (  # noqa: E402
    ModelCatalog,
    ModelInfo,
    FALLBACK_MODELS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_payload(models: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"data": models}


def _model_dict(
    mid: str,
    name: str = None,
    ctx: int = 8000,
    prompt: float = 0.000001,
    completion: float = 0.000002,
) -> Dict[str, Any]:
    return {
        "id": mid,
        "name": name or mid,
        "context_length": ctx,
        "pricing": {"prompt": str(prompt), "completion": str(completion)},
    }


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    """隔离缓存到 tmp_path"""
    cache = tmp_path / "models_cache.json"
    monkeypatch.setattr(
        "src.analyzer.model_catalog._default_cache_path",
        lambda: cache,
    )
    return cache


@pytest.fixture
def fake_openrouter_ok(monkeypatch):
    """成功响应 fixture"""
    payload = _make_payload([
        _model_dict("openai/gpt-4o-mini", "GPT-4o mini", ctx=128_000,
                    prompt=0.00000015, completion=0.0000006),
        _model_dict("openai/gpt-4o", "GPT-4o", ctx=128_000,
                    prompt=0.0000025, completion=0.00001),
        _model_dict("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet", ctx=200_000,
                    prompt=0.000003, completion=0.000015),
        _model_dict("google/gemini-flash", "Gemini Flash", ctx=1_000_000,
                    prompt=0, completion=0),
        _model_dict("deepseek/deepseek-v4-flash", "DeepSeek V4 Flash", ctx=1_000_000,
                    prompt=0.00000014, completion=0.00000028),
    ])

    class _Resp:
        status_code = 200
        def json(self): return payload
        def close(self): pass

    def _fake_get(url, timeout):
        return _Resp()

    import src.analyzer.model_catalog as mc
    # requests 已被 import 过则 monkeypatch；否则注入
    sys.modules.setdefault("requests", type("R", (), {"get": staticmethod(_fake_get)})())
    return payload


# ---------------------------------------------------------------------------
# Test: 缓存
# ---------------------------------------------------------------------------
class TestCache:
    def test_fresh_cache_is_used(self, tmp_cache, fake_openrouter_ok):
        """网络拉取后会写缓存；TTL 内应优先用缓存"""
        cat = ModelCatalog()
        info1 = cat.info()
        assert info1["source"] == "network"
        assert info1["model_count"] >= 5
        assert tmp_cache.is_file()

        # 第二次构造：应从缓存读
        cat2 = ModelCatalog()
        assert cat2.info()["source"] == "cache"

    def test_stale_cache_is_refreshed(self, tmp_cache, fake_openrouter_ok):
        """TTL 之外（mtime 老化）的缓存应当被忽略，重新拉取"""
        # 写一个老化缓存
        tmp_cache.write_text(
            json.dumps(_make_payload([_model_dict("x/y", "Stale")])),
            encoding="utf-8",
        )
        # 把 mtime 调到 13 小时前
        stale_mtime = time.time() - 13 * 3600
        import os
        os.utime(tmp_cache, (stale_mtime, stale_mtime))

        cat = ModelCatalog()
        assert cat.info()["source"] == "network"

    def test_corrupt_cache_falls_back(self, tmp_cache):
        """缓存损坏 → fallback"""
        tmp_cache.write_text("not json {{{", encoding="utf-8")
        # 强制走 fallback（避免在 CI 联网时拉到真数据）
        with patch.object(ModelCatalog, "_fetch_from_network", return_value=False):
            cat = ModelCatalog()
        assert cat.info()["source"] == "fallback"
        assert cat.info()["model_count"] == len(FALLBACK_MODELS)


# ---------------------------------------------------------------------------
# Test: 过滤
# ---------------------------------------------------------------------------
class TestFilter:
    def test_provider_filter(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        openai = cat.list(provider="openai")
        assert all(m.provider == "openai" for m in openai)
        assert any(m.id == "openai/gpt-4o" for m in openai)

        anthropic = cat.list(provider="anthropic")
        assert all(m.provider == "anthropic" for m in anthropic)
        assert len(openai) + len(anthropic) <= cat.info()["model_count"]

    def test_provider_filter_case_insensitive(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        a = cat.list(provider="OpenAI")
        b = cat.list(provider="openai")
        assert [m.id for m in a] == [m.id for m in b]

    def test_all_returns_everything(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        total = cat.info()["model_count"]
        assert len(cat.list(provider="all")) == total
        assert len(cat.list(provider=None)) == total


# ---------------------------------------------------------------------------
# Test: 排序
# ---------------------------------------------------------------------------
class TestSort:
    def test_sort_by_name(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        items = cat.list(sort_by="name")
        names = [m.name.lower() for m in items]
        assert names == sorted(names)

    def test_sort_by_price_ascending(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        items = cat.list(sort_by="price")
        totals = [m.prompt_price + m.completion_price for m in items]
        assert totals == sorted(totals)

    def test_sort_by_context_descending(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        items = cat.list(sort_by="context")
        ctxs = [m.context_length for m in items]
        assert ctxs == sorted(ctxs, reverse=True)

    def test_default_sort_is_name(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        a = cat.list()
        b = cat.list(sort_by="name")
        assert [m.id for m in a] == [m.id for m in b]


# ---------------------------------------------------------------------------
# Test: 搜索
# ---------------------------------------------------------------------------
class TestSearch:
    def test_search_by_id(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        items = cat.list(search="gpt-4o")
        assert items
        assert all("gpt-4o" in m.id.lower() or "gpt-4o" in m.name.lower()
                   for m in items)

    def test_search_case_insensitive(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        a = cat.list(search="GPT")
        b = cat.list(search="gpt")
        assert [m.id for m in a] == [m.id for m in b]

    def test_search_no_match(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        items = cat.list(search="___nothing___")
        assert items == []

    def test_empty_search_returns_all(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        a = cat.list(search="")
        b = cat.list(search=None)
        assert len(a) == len(b)
        assert len(a) == cat.info()["model_count"]


# ---------------------------------------------------------------------------
# Test: refresh
# ---------------------------------------------------------------------------
class TestRefresh:
    def test_refresh_forces_network(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        # 已加载，source=network
        assert cat.info()["source"] == "network"
        # 即使缓存新鲜，refresh 也应重新走网络
        cat.refresh()
        assert cat.info()["source"] == "network"

    def test_refresh_falls_back_on_error(self, tmp_cache):
        cat = ModelCatalog()
        with patch.object(ModelCatalog, "_fetch_from_network", return_value=False):
            cat.refresh()
        assert cat.info()["source"] == "fallback"
        assert cat.info()["model_count"] == len(FALLBACK_MODELS)


# ---------------------------------------------------------------------------
# Test: API 失败降级
# ---------------------------------------------------------------------------
class TestFallback:
    def test_network_failure_uses_fallback(self, tmp_cache):
        """requests 抛异常 → fallback"""
        import src.analyzer.model_catalog as mc
        # Patch the request by ensuring requests.get raises
        class _R:
            @staticmethod
            def get(url, timeout):
                raise ConnectionError("boom")
        sys.modules["requests"] = _R

        cat = ModelCatalog()
        assert cat.info()["source"] == "fallback"
        assert cat.info()["model_count"] == len(FALLBACK_MODELS)
        assert len(cat.info()["providers"]) == len({m.provider for m in FALLBACK_MODELS})

    def test_non_200_status_falls_back(self, tmp_cache):
        class _R:
            @staticmethod
            def get(url, timeout):
                class _Resp:
                    status_code = 503
                    def close(self): pass
                return _Resp()
        sys.modules["requests"] = _R

        cat = ModelCatalog()
        assert cat.info()["source"] == "fallback"

    def test_invalid_json_falls_back(self, tmp_cache):
        class _R:
            @staticmethod
            def get(url, timeout):
                class _Resp:
                    status_code = 200
                    def json(self):
                        raise ValueError("bad json")
                    def close(self): pass
                return _Resp()
        sys.modules["requests"] = _R

        cat = ModelCatalog()
        assert cat.info()["source"] == "fallback"

    def test_fallback_has_at_least_5_models(self):
        assert len(FALLBACK_MODELS) >= 5


# ---------------------------------------------------------------------------
# Test: info
# ---------------------------------------------------------------------------
class TestInfo:
    def test_info_keys(self, tmp_cache, fake_openrouter_ok):
        cat = ModelCatalog()
        info = cat.info()
        for key in (
            "cache_path", "cache_exists", "cache_size_bytes",
            "cache_age_seconds", "ttl_seconds", "model_count",
            "providers", "provider_count", "source",
        ):
            assert key in info, f"missing key: {key}"
        assert info["ttl_seconds"] == 43_200
        assert info["model_count"] > 0
        assert info["provider_count"] == len(info["providers"])

    def test_info_when_cache_missing(self, tmp_path, monkeypatch):
        # 把 cache 路径指向一个空目录
        empty = tmp_path / "no_cache.json"
        monkeypatch.setattr(
            "src.analyzer.model_catalog._default_cache_path",
            lambda: empty,
        )
        with patch.object(ModelCatalog, "_fetch_from_network", return_value=False):
            cat = ModelCatalog()
        info = cat.info()
        assert info["cache_exists"] is False
        assert info["cache_size_bytes"] == 0
        assert info["cache_age_seconds"] < 0


# ---------------------------------------------------------------------------
# Test: ModelInfo 不可变
# ---------------------------------------------------------------------------
class TestModelInfo:
    def test_immutable(self):
        m = ModelInfo(
            id="x", name="X", provider="p",
            context_length=1, prompt_price=0.0, completion_price=0.0,
        )
        with pytest.raises(Exception):  # FrozenInstanceError 或 AttributeError
            m.id = "y"

    def test_to_dict(self):
        m = ModelInfo(
            id="x", name="X", provider="p",
            context_length=1, prompt_price=0.5, completion_price=1.5,
        )
        d = m.to_dict()
        assert d == {
            "id": "x", "name": "X", "provider": "p",
            "context_length": 1, "prompt_price": 0.5, "completion_price": 1.5,
        }
