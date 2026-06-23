"""请求合并器 —— 相同内容的并发请求自动合并为一次 API 调用"""

import hashlib
import threading
from concurrent.futures import Future
from typing import Any, Dict, List, Optional


class RequestCoalescer:
    """
    请求合并器 —— 相同内容的并发请求自动合并为一次 API 调用。

    原理:
    1. 将 (messages, model, temperature, max_tokens) 哈希为请求 key
    2. 首个请求实际执行，后续相同 key 的请求等待同一 Future
    3. Future 完成后所有等待者共享结果

    用法::

        coalescer = RequestCoalescer(router)
        # 两个并发的相同请求只会实际调用一次 API
        result1, result2 = await asyncio.gather(
            coalescer.chat(messages=[...]),
            coalescer.chat(messages=[...]),
        )

    注意: 当前实现是同步阻塞版本，使用 threading.Event 实现等待。
    """

    def __init__(self, router):
        self._router = router
        self._inflight: Dict[str, Future] = {}
        self._lock = threading.Lock()

    def _make_key(self, **kwargs) -> str:
        parts = [
            str(kwargs.get("messages", "")),
            str(kwargs.get("model", "")),
            str(kwargs.get("temperature", 0.7)),
            str(kwargs.get("max_tokens", "")),
        ]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """发送请求（自动合并相同请求）"""
        key = self._make_key(
            messages=messages, model=model,
            temperature=temperature, max_tokens=max_tokens,
        )

        with self._lock:
            if key in self._inflight:
                future = self._inflight[key]
                return future.result()

            future: Future = Future()
            self._inflight[key] = future

        try:
            result = self._router.chat(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens,
                **kwargs,
            )
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            with self._lock:
                self._inflight.pop(key, None)
