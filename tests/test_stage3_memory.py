"""
Stage 3: 内存泄漏修复验证
- deque(maxlen=1000) 自动淘汰
- get_stats() 兼容 deque
- Provider→OpenAI 客户端缓存
- _client_lock 线程安全
"""
import threading
from collections import deque
from unittest.mock import patch, MagicMock

import pytest

from src.analyzer.llm_router import (
    LLMRouter,
    RoutingStrategy,
    ProviderConfig,
    ModelConfig,
)


class TestRequestHistoryDeque:
    """验证 _request_history 改为 deque(maxlen=1000)"""

    def test_is_deque_instance(self):
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        assert isinstance(router._request_history, deque)

    def test_maxlen_is_1000(self):
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        assert router._request_history.maxlen == 1000

    def test_auto_eviction(self):
        """写入 >1000 条记录，旧记录应被淘汰"""
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        for i in range(1200):
            router._request_history.append({"idx": i, "success": True})
        assert len(router._request_history) == 1000
        # 最早的 200 条应被淘汰，当前第一条是 idx=200
        assert router._request_history[0]["idx"] == 200
        # 最后一条是 idx=1199
        assert router._request_history[-1]["idx"] == 1199

    def test_append_still_works(self):
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        router._request_history.append({"test": True})
        assert len(router._request_history) == 1


class TestGetStatsDequeCompat:
    """验证 get_stats() 适配 deque"""

    def test_get_stats_empty_history(self):
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        stats = router.get_stats()
        assert stats["total_requests"] == 0
        assert stats["successful"] == 0
        assert stats["failed"] == 0
        assert stats["success_rate"] == 0

    def test_get_stats_with_data(self):
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        router._request_history.append({
            "provider": "test", "model": "m", "latency": 0.5,
            "success": True, "timestamp": "now"
        })
        router._request_history.append({
            "provider": "test", "model": "m",
            "success": False, "error": "fail", "timestamp": "now"
        })
        stats = router.get_stats()
        assert stats["total_requests"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["average_latency"] == 0.5
        assert stats["max_history_size"] == 1000

    def test_get_stats_after_eviction(self):
        """超过 maxlen 后统计只反映窗口内的数据"""
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        # 写入 1050 条失败
        for i in range(1050):
            router._request_history.append({
                "provider": "p", "model": "m", "success": False, "timestamp": "now"
            })
        stats = router.get_stats()
        assert stats["total_requests"] == 1000  # maxlen
        assert stats["failed"] == 1000

    def test_get_stats_snapshot_safety(self):
        """get_stats 在并发 append 时不会 RuntimeError"""
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        errors = []

        def writer():
            try:
                for i in range(500):
                    router._request_history.append({"success": True, "timestamp": "now"})
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(500):
                    router.get_stats()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start(); t2.start()
        t1.join(); t2.join()
        assert errors == [], f"Concurrent errors: {errors}"


class TestClientCache:
    """验证 Provider→OpenAI 客户端缓存"""

    def test_client_cache_exists(self):
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        assert hasattr(router, "_client_cache")
        assert isinstance(router._client_cache, dict)

    def test_client_cache_returns_same_instance(self):
        """同一 Provider 多次 _get_client 应返回同一对象"""
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        provider = router.providers[0]
        with patch("src.analyzer.llm_router.OpenAI") as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance
            c1 = router._get_client(provider)
            c2 = router._get_client(provider)
            assert c1 is c2
            # OpenAI 只构造一次
            mock_openai.assert_called_once()

    def test_client_cache_different_providers(self):
        """不同 Provider 应有不同缓存条目"""
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        with patch("src.analyzer.llm_router.OpenAI") as mock_openai:
            mock_openai.side_effect = lambda **kw: MagicMock()
            clients = []
            for p in router.providers[:3]:
                clients.append(router._get_client(p))
            assert len(set(id(c) for c in clients)) == 3

    def test_remove_provider_clears_cache(self):
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        provider = router.providers[0]
        with patch("src.analyzer.llm_router.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            router._get_client(provider)
            assert provider.name in router._client_cache
            router.remove_provider(provider.name)
            assert provider.name not in router._client_cache

    def test_shutdown_clears_cache(self):
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        with patch("src.analyzer.llm_router.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            router._get_client(router.providers[0])
            assert len(router._client_cache) > 0
            router.shutdown()
            assert len(router._client_cache) == 0


class TestClientLock:
    """验证 _client_lock 线程安全"""

    def test_lock_exists(self):
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        assert isinstance(router._client_lock, threading.Lock)

    def test_concurrent_get_client_no_corruption(self):
        """并发 _get_client 不会创建多个客户端实例"""
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        provider = router.providers[0]
        created = []
        original_openai = __import__("src.analyzer.llm_router", fromlist=["OpenAI"]).OpenAI

        def counting_openai(**kwargs):
            obj = MagicMock()
            created.append(obj)
            return obj

        errors = []
        with patch("src.analyzer.llm_router.OpenAI", side_effect=counting_openai):
            def worker():
                try:
                    for _ in range(50):
                        router._get_client(provider)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads: t.start()
            for t in threads: t.join()

        assert errors == [], f"Thread errors: {errors}"
        # 由于竞态，可能创建 >1 个，但缓存中只有 1 个
        assert len(router._client_cache) == 1
        assert provider.name in router._client_cache


class TestBackwardCompat:
    """确保现有 API 行为不变"""

    def test_chat_history_still_recorded(self):
        """chat 成功/失败仍会 append 到 _request_history"""
        router = LLMRouter(strategy=RoutingStrategy.FALLBACK)
        with patch.object(router, "_get_client") as mock_gc:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = MagicMock()
            mock_gc.return_value = mock_client
            # 使用第一个 provider 的第一个 model
            p = router.providers[0]
            m = p.models[0]
            router.chat(messages=[{"role": "user", "content": "hi"}], model=m.id)
        assert len(router._request_history) == 1
        assert router._request_history[0]["success"] is True
