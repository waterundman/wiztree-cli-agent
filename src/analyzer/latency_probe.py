"""延迟探测器 —— 后台线程定期 ping 各 Provider，记录延迟"""

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class LatencySample:
    """单次延迟采样"""
    provider: str
    latency_ms: float
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)


class LatencyProbe:
    """
    延迟探测器 —— 后台线程定期 ping 各 Provider，记录延迟。

    用法::

        probe = LatencyProbe(providers, interval=30, timeout=5)
        probe.start()
        ...
        latencies = probe.get_latencies()  # {"deepseek": 120.5, ...}
        probe.stop()

    特性:
    - 后台 daemon 线程，不阻塞主进程退出
    - 滑动窗口保留最近 N 次采样
    - 提供 P50 / P95 / 均值统计
    - 线程安全
    """

    def __init__(
        self,
        providers: List,  # List[ProviderConfig] — 使用字符串避免循环导入
        interval: int = 30,
        timeout: int = 5,
        window_size: int = 20,
    ):
        self.providers = providers
        self.interval = interval
        self.timeout = timeout
        self.window_size = window_size

        self._samples: Dict[str, List[LatencySample]] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        for p in providers:
            self._samples[p.name] = []

    def start(self):
        """启动后台探测线程"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="latency-probe"
        )
        self._thread.start()

    def stop(self):
        """停止探测"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.interval + 2)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        while not self._stop_event.is_set():
            self._probe_all()
            self._stop_event.wait(self.interval)

    def _probe_all(self):
        for provider in self.providers:
            if self._stop_event.is_set():
                break
            self._probe_one(provider)

    def _probe_one(self, provider):
        """对单个 Provider 发送最小请求测量延迟"""
        latency_ms = 0.0
        success = False
        try:
            api_key = provider.api_key or "no-key"
            if provider.api_key_env and provider.api_key_env != "NO_AUTH":
                api_key = os.environ.get(provider.api_key_env, api_key)
                if not api_key:
                    return

            client = OpenAI(
                base_url=provider.base_url,
                api_key=api_key,
                timeout=self.timeout,
            )
            model_id = provider.models[0].id if provider.models else "unknown"

            start = time.time()
            client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            latency_ms = (time.time() - start) * 1000
            success = True
        except Exception as e:
            latency_ms = (time.time() - start) * 1000 if 'start' in dir() else 0
            logger.debug("LatencyProbe %s failed: %s", provider.name, e)
        finally:
            sample = LatencySample(
                provider=provider.name,
                latency_ms=latency_ms,
                success=success,
            )
            with self._lock:
                samples = self._samples.setdefault(provider.name, [])
                samples.append(sample)
                if len(samples) > self.window_size:
                    self._samples[provider.name] = samples[-self.window_size:]

    def record_external(self, provider: str, latency_ms: float, success: bool):
        """由外部请求自动记录延迟（无需等待探测周期）"""
        sample = LatencySample(provider=provider, latency_ms=latency_ms, success=success)
        with self._lock:
            samples = self._samples.setdefault(provider, [])
            samples.append(sample)
            if len(samples) > self.window_size:
                self._samples[provider] = samples[-self.window_size:]

    def get_latencies(self) -> Dict[str, float]:
        """返回各 Provider 的中位延迟（ms），无数据返回 inf"""
        result: Dict[str, float] = {}
        with self._lock:
            for name, samples in self._samples.items():
                ok = [s.latency_ms for s in samples if s.success]
                result[name] = sorted(ok)[len(ok) // 2] if ok else float('inf')
        return result

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """返回各 Provider 的详细延迟统计"""
        stats: Dict[str, Dict[str, float]] = {}
        with self._lock:
            for name, samples in self._samples.items():
                ok = sorted(s.latency_ms for s in samples if s.success)
                total = len(samples)
                ok_count = len(ok)
                if ok:
                    p50_idx = int(ok_count * 0.5)
                    p95_idx = min(int(ok_count * 0.95), ok_count - 1)
                    stats[name] = {
                        "samples": total,
                        "success_count": ok_count,
                        "success_rate": ok_count / total if total else 0,
                        "avg_ms": sum(ok) / ok_count,
                        "p50_ms": ok[p50_idx],
                        "p95_ms": ok[p95_idx],
                        "min_ms": ok[0],
                        "max_ms": ok[-1],
                    }
                else:
                    stats[name] = {
                        "samples": total,
                        "success_count": 0,
                        "success_rate": 0,
                        "avg_ms": float('inf'),
                        "p50_ms": float('inf'),
                        "p95_ms": float('inf'),
                        "min_ms": float('inf'),
                        "max_ms": float('inf'),
                    }
        return stats

    def clear(self):
        """清除所有采样数据"""
        with self._lock:
            for name in self._samples:
                self._samples[name] = []
