"""
LLM Router v1.5.0 测试 — Stage 1 动态路由优化

覆盖:
1. LatencyProbe — 延迟探测
2. WeightedRouter — 动态权重路由
3. batch_chat — 批量并行请求
4. RequestCoalescer — 请求合并
"""

import sys
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer.llm_router import (
    LLMRouter,
    RoutingStrategy,
    ProviderConfig,
    ModelConfig,
    CircuitBreaker,
    LatencyProbe,
    LatencySample,
    WeightedRouter,
    RequestCoalescer,
    BatchRequest,
    BatchResult,
    batch_chat,
)


# ============================================================
# Helper
# ============================================================

def _make_provider(name="test", priority=1, models=None, api_key="fake-key"):
    if models is None:
        models = [ModelConfig(id="test-model")]
    return ProviderConfig(
        name=name,
        base_url="https://example.com/v1",
        api_key_env="NO_AUTH",
        api_key=api_key,
        models=models,
        priority=priority,
        tags=["test"],
    )


def _mock_response(content="ok", provider_name="test"):
    """创建 mock OpenAI 响应"""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message = MagicMock()
    mock_resp.choices[0].message.content = content
    mock_resp.choices[0].finish_reason = "stop"
    mock_resp.usage = MagicMock()
    mock_resp.usage.prompt_tokens = 1
    mock_resp.usage.completion_tokens = 1
    mock_resp.usage.total_tokens = 2
    mock_resp.model = "test-model"
    return mock_resp


# ============================================================
# Test: LatencyProbe 数据结构
# ============================================================

class TestLatencySample:
    def test_creation(self):
        sample = LatencySample(provider="deepseek", latency_ms=150.0, success=True)
        assert sample.provider == "deepseek"
        assert sample.latency_ms == 150.0
        assert sample.success is True
        assert isinstance(sample.timestamp, datetime)


# ============================================================
# Test: LatencyProbe
# ============================================================

class TestLatencyProbe:
    def test_init(self):
        providers = [_make_provider("a"), _make_provider("b")]
        probe = LatencyProbe(providers, interval=10)
        assert probe.interval == 10
        assert not probe.is_running()
        assert "a" in probe._samples
        assert "b" in probe._samples

    def test_record_external(self):
        providers = [_make_provider("p1")]
        probe = LatencyProbe(providers, interval=60)
        probe.record_external("p1", 100.0, True)
        probe.record_external("p1", 200.0, True)
        probe.record_external("p1", 50.0, False)

        stats = probe.get_stats()
        assert stats["p1"]["samples"] == 3
        assert stats["p1"]["success_count"] == 2
        assert abs(stats["p1"]["success_rate"] - 2 / 3) < 0.01

    def test_window_size(self):
        providers = [_make_provider("p1")]
        probe = LatencyProbe(providers, interval=60, window_size=3)
        for i in range(10):
            probe.record_external("p1", float(i * 10), True)
        stats = probe.get_stats()
        assert stats["p1"]["samples"] == 3

    def test_get_latencies(self):
        providers = [_make_provider("fast"), _make_provider("slow")]
        probe = LatencyProbe(providers)
        probe.record_external("fast", 50.0, True)
        probe.record_external("fast", 60.0, True)
        probe.record_external("slow", 500.0, True)

        latencies = probe.get_latencies()
        # median of [50, 60] with len//2 index = 1 → 60
        assert latencies["fast"] == 60.0
        assert latencies["slow"] == 500.0

    def test_get_latencies_no_data(self):
        providers = [_make_provider("empty")]
        probe = LatencyProbe(providers)
        latencies = probe.get_latencies()
        assert latencies["empty"] == float('inf')

    def test_clear(self):
        providers = [_make_provider("p1")]
        probe = LatencyProbe(providers)
        probe.record_external("p1", 100.0, True)
        probe.clear()
        stats = probe.get_stats()
        assert stats["p1"]["samples"] == 0

    def test_start_stop(self):
        providers = [_make_provider("p1")]
        probe = LatencyProbe(providers, interval=1)
        probe.start()
        assert probe.is_running()
        probe.stop()
        time.sleep(0.2)
        assert not probe.is_running()

    def test_probe_all_failure(self):
        """探测全部失败不影响系统"""
        providers = [_make_provider("down")]
        probe = LatencyProbe(providers, interval=1, timeout=1)
        with patch.object(probe, '_probe_one'):
            probe._probe_all()
        stats = probe.get_stats()
        assert "down" in stats


# ============================================================
# Test: LatencyProbe 集成到 LLMRouter
# ============================================================

class TestLLMRouterProbeIntegration:
    def test_probe_disabled_by_default(self):
        router = LLMRouter(strategy=RoutingStrategy.LATENCY)
        assert router._latency_probe is None

    def test_probe_enabled(self):
        providers = [_make_provider("p1")]
        router = LLMRouter(
            strategy=RoutingStrategy.LATENCY,
            providers=providers,
            enable_probe=True,
            probe_interval=60,
        )
        assert router._latency_probe is not None
        router.shutdown()

    def test_shutdown(self):
        providers = [_make_provider("p1")]
        router = LLMRouter(
            providers=providers, enable_probe=True, probe_interval=1
        )
        router.shutdown()
        assert not router._latency_probe.is_running()

    @patch("src.analyzer.llm_router.OpenAI")
    def test_chat_records_latency_to_probe(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response("hi")

        providers = [_make_provider("p1")]
        router = LLMRouter(
            providers=providers, enable_probe=True, probe_interval=60
        )
        router.chat(messages=[{"role": "user", "content": "test"}], model="test-model")

        assert router._latency_probe is not None
        stats = router._latency_probe.get_stats()
        assert stats["p1"]["success_count"] >= 1
        router.shutdown()
        providers = [
            _make_provider("slow", priority=1),
            _make_provider("fast", priority=2),
        ]
        router = LLMRouter(
            strategy=RoutingStrategy.LATENCY,
            providers=providers,
            enable_probe=True,
            probe_interval=60,
        )
        router._latency_probe.record_external("slow", 500.0, True)
        router._latency_probe.record_external("fast", 50.0, True)

        selected = router._select_provider()
        assert selected[0].name == "fast"
        router.shutdown()

    def test_provider_status_includes_latency(self):
        providers = [_make_provider("p1")]
        router = LLMRouter(
            providers=providers, enable_probe=True, probe_interval=60
        )
        router._latency_probe.record_external("p1", 123.4, True)
        status = router.get_provider_status()
        assert "latency" in status["p1"]
        assert status["p1"]["latency"]["p50_ms"] == 123.4
        router.shutdown()


# ============================================================
# Test: WeightedRouter
# ============================================================

class TestWeightedRouter:
    def test_init_default_weights(self):
        providers = [_make_provider("p1")]
        router = WeightedRouter(providers=providers, enable_probe=False)
        assert router._weights == {"latency": 0.4, "success": 0.3, "cost": 0.3}

    def test_init_custom_weights(self):
        providers = [_make_provider("p1")]
        router = WeightedRouter(
            providers=providers,
            enable_probe=False,
            weights={"latency": 0.6, "success": 0.2, "cost": 0.2},
        )
        assert router._weights["latency"] == 0.6

    def test_compute_weights_single(self):
        providers = [_make_provider("only")]
        router = WeightedRouter(providers=providers, enable_probe=False)
        scores = router._compute_weights(providers)
        assert len(scores) == 1
        assert scores[0] > 0

    def test_compute_weights_prefers_fast(self):
        providers = [
            _make_provider("slow", priority=10),
            _make_provider("fast", priority=1),
        ]
        router = WeightedRouter(providers=providers, enable_probe=False)
        router._latency_probe = LatencyProbe(providers)
        router._latency_probe.record_external("slow", 500.0, True)
        router._latency_probe.record_external("fast", 50.0, True)

        scores = router._compute_weights(providers)
        fast_idx = next(i for i, p in enumerate(providers) if p.name == "fast")
        slow_idx = next(i for i, p in enumerate(providers) if p.name == "slow")
        assert scores[fast_idx] > scores[slow_idx]

    def test_get_routing_weights(self):
        providers = [_make_provider("a"), _make_provider("b")]
        router = WeightedRouter(providers=providers, enable_probe=False)
        weights = router.get_routing_weights()
        assert "a" in weights
        assert "b" in weights
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01

    @patch("src.analyzer.llm_router.OpenAI")
    def test_chat_uses_weighted_routing(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response("ok")

        providers = [_make_provider("p1"), _make_provider("p2")]
        router = WeightedRouter(providers=providers, enable_probe=False)
        result = router.chat(messages=[{"role": "user", "content": "test"}])
        assert result is not None

    def test_select_provider_filters_unavailable(self):
        p1 = _make_provider("no_key", api_key=None)
        p1.api_key_env = "FAKE_KEY_ENV"
        p2 = _make_provider("has_key")
        router = WeightedRouter(providers=[p1, p2], enable_probe=False)
        selected = router._select_provider()
        assert len(selected) == 1
        assert selected[0].name == "has_key"


# ============================================================
# Test: RequestCoalescer
# ============================================================

class TestRequestCoalescer:
    def test_make_key_deterministic(self):
        router = LLMRouter(providers=[_make_provider()])
        coalescer = RequestCoalescer(router)
        key1 = coalescer._make_key(
            messages=[{"role": "user", "content": "hi"}],
            model="test",
            temperature=0.7,
        )
        key2 = coalescer._make_key(
            messages=[{"role": "user", "content": "hi"}],
            model="test",
            temperature=0.7,
        )
        assert key1 == key2

    def test_make_key_different_messages(self):
        router = LLMRouter(providers=[_make_provider()])
        coalescer = RequestCoalescer(router)
        key1 = coalescer._make_key(
            messages=[{"role": "user", "content": "hi"}],
        )
        key2 = coalescer._make_key(
            messages=[{"role": "user", "content": "hello"}],
        )
        assert key1 != key2

    @patch("src.analyzer.llm_router.OpenAI")
    def test_coalesce_same_requests(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response("ok")

        router = LLMRouter(providers=[_make_provider()])
        coalescer = RequestCoalescer(router)

        msgs = [{"role": "user", "content": "same"}]
        r1 = coalescer.chat(messages=msgs)
        r2 = coalescer.chat(messages=msgs)

        assert r1 is not None
        assert r2 is not None
        assert mock_client.chat.completions.create.call_count == 2

    @patch("src.analyzer.llm_router.OpenAI")
    def test_coalesce_cleans_up_key(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response("ok")

        router = LLMRouter(providers=[_make_provider()])
        coalescer = RequestCoalescer(router)

        msgs = [{"role": "user", "content": "test"}]
        coalescer.chat(messages=msgs)
        assert len(coalescer._inflight) == 0

    @patch("src.analyzer.llm_router.OpenAI")
    def test_coalesce_error_propagation(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("API Error")

        router = LLMRouter(providers=[_make_provider()])
        coalescer = RequestCoalescer(router)

        try:
            coalescer.chat(messages=[{"role": "user", "content": "fail"}])
            assert False, "Should have raised"
        except RuntimeError:
            pass
        assert len(coalescer._inflight) == 0


# ============================================================
# Test: batch_chat
# ============================================================

class TestBatchChat:
    @patch("src.analyzer.llm_router.OpenAI")
    def test_batch_basic(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response("ok")

        router = LLMRouter(providers=[_make_provider()])
        requests = [
            BatchRequest(messages=[{"role": "user", "content": "q1"}]),
            BatchRequest(messages=[{"role": "user", "content": "q2"}]),
            BatchRequest(messages=[{"role": "user", "content": "q3"}]),
        ]
        results = batch_chat(router, requests, max_workers=2)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.response is not None for r in results)

    @patch("src.analyzer.llm_router.OpenAI")
    def test_batch_preserves_order(self, mock_openai_class):
        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            resp = _mock_response(f"reply-{call_count[0]}")
            if call_count[0] % 2 == 0:
                time.sleep(0.02)
            return resp

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = side_effect

        router = LLMRouter(providers=[_make_provider()])
        requests = [
            BatchRequest(messages=[{"role": "user", "content": f"q{i}"}])
            for i in range(5)
        ]
        results = batch_chat(router, requests, max_workers=3)

        assert len(results) == 5
        for i, r in enumerate(results):
            assert r.index == i

    @patch("src.analyzer.llm_router.OpenAI")
    def test_batch_partial_failure(self, mock_openai_class):
        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("fail on 2nd")
            return _mock_response("ok")

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = side_effect

        router = LLMRouter(providers=[_make_provider()])
        requests = [
            BatchRequest(messages=[{"role": "user", "content": f"q{i}"}])
            for i in range(3)
        ]
        results = batch_chat(router, requests, max_workers=2)

        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        assert len(successes) == 2
        assert len(failures) == 1
        assert "fail on 2nd" in failures[0].error

    @patch("src.analyzer.llm_router.OpenAI")
    def test_batch_with_coalescing(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response("ok")

        router = LLMRouter(providers=[_make_provider()])
        same_msg = [{"role": "user", "content": "same"}]
        requests = [
            BatchRequest(messages=same_msg),
            BatchRequest(messages=same_msg),
        ]
        results = batch_chat(router, requests, max_workers=2, coalesce=True)

        assert len(results) == 2
        assert all(r.success for r in results)

    def test_batch_empty(self):
        router = LLMRouter(providers=[_make_provider()])
        results = batch_chat(router, [])
        assert results == []

    @patch("src.analyzer.llm_router.OpenAI")
    def test_batch_custom_params(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response("ok")

        router = LLMRouter(providers=[_make_provider()])
        requests = [
            BatchRequest(
                messages=[{"role": "user", "content": "q1"}],
                model="custom-model",
                temperature=0.3,
                max_tokens=100,
            )
        ]
        results = batch_chat(router, requests)
        assert results[0].success


# ============================================================
# Test: 路由策略兼容性
# ============================================================

class TestRoutingStrategyCompat:
    """确保新增功能不破坏原有路由策略"""

    @patch("src.analyzer.llm_router.OpenAI")
    def test_cost_strategy_unchanged(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response("ok")

        router = LLMRouter(
            strategy=RoutingStrategy.COST,
            providers=[_make_provider("cheap"), _make_provider("expensive")],
        )
        result = router.chat(messages=[{"role": "user", "content": "test"}])
        assert result is not None

    @patch("src.analyzer.llm_router.OpenAI")
    def test_fallback_strategy_unchanged(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response("ok")

        router = LLMRouter(
            strategy=RoutingStrategy.FALLBACK,
            providers=[_make_provider("p1"), _make_provider("p2")],
        )
        result = router.chat(messages=[{"role": "user", "content": "test"}])
        assert result is not None

    @patch("src.analyzer.llm_router.OpenAI")
    def test_manual_strategy_unchanged(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response("ok")

        router = LLMRouter(
            strategy=RoutingStrategy.MANUAL,
            providers=[_make_provider("p1")],
        )
        result = router.chat(messages=[{"role": "user", "content": "test"}])
        assert result is not None

    def test_factory_functions_unchanged(self):
        from src.analyzer.llm_router import (
            create_cost_optimized_router,
            create_latency_optimized_router,
            create_fallback_router,
        )
        r1 = create_cost_optimized_router()
        r2 = create_latency_optimized_router()
        r3 = create_fallback_router()
        assert r1.strategy == RoutingStrategy.COST
        assert r2.strategy == RoutingStrategy.LATENCY
        assert r3.strategy == RoutingStrategy.FALLBACK


# ============================================================
# Test: 导入兼容性
# ============================================================

class TestImports:
    def test_import_from_analyzer(self):
        from src.analyzer import (
            LatencyProbe, LatencySample,
            WeightedRouter,
            RequestCoalescer,
            batch_chat, BatchRequest, BatchResult,
        )
        assert LatencyProbe is not None
        assert WeightedRouter is not None
        assert RequestCoalescer is not None
        assert batch_chat is not None
        assert BatchRequest is not None
        assert BatchResult is not None

    def test_import_from_router(self):
        from src.analyzer.llm_router import (
            LatencyProbe, LatencySample,
            WeightedRouter,
            RequestCoalescer,
            batch_chat, BatchRequest, BatchResult,
        )
        assert all(x is not None for x in [
            LatencyProbe, LatencySample, WeightedRouter,
            RequestCoalescer, batch_chat, BatchRequest, BatchResult,
        ])


# ============================================================
# 运行
# ============================================================

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
