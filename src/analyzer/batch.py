"""批量并行请求支持"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .request_coalescer import RequestCoalescer


@dataclass
class BatchRequest:
    """批量请求中的单项"""
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    kwargs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    """批量请求的单项结果"""
    index: int
    success: bool
    response: Any = None
    error: Optional[str] = None
    provider: Optional[str] = None
    latency: float = 0.0


def batch_chat(
    router,
    requests: List[BatchRequest],
    max_workers: int = 4,
    coalesce: bool = False,
) -> List[BatchResult]:
    """
    批量并行发送聊天请求。

    Args:
        router: LLM路由器实例
        requests: 批量请求列表
        max_workers: 最大并行数
        coalesce: 是否启用请求合并

    Returns:
        与输入等长的结果列表（保持顺序）

    用法::

        from src.analyzer.batch import batch_chat, BatchRequest

        results = batch_chat(router, [
            BatchRequest(messages=[{"role": "user", "content": "你好"}]),
            BatchRequest(messages=[{"role": "user", "content": "Hello"}]),
        ])
        for r in results:
            if r.success:
                print(r.response.choices[0].message.content)
    """
    coalescer = RequestCoalescer(router) if coalesce else None
    results: List[BatchResult] = [None] * len(requests)  # type: ignore

    def _execute(idx: int, req: BatchRequest) -> BatchResult:
        start = time.time()
        try:
            if coalescer:
                response = coalescer.chat(
                    messages=req.messages, model=req.model,
                    temperature=req.temperature, max_tokens=req.max_tokens,
                    **req.kwargs,
                )
            else:
                response = router.chat(
                    messages=req.messages, model=req.model,
                    temperature=req.temperature, max_tokens=req.max_tokens,
                    **req.kwargs,
                )
            latency = time.time() - start
            return BatchResult(
                index=idx, success=True, response=response, latency=latency,
            )
        except Exception as e:
            latency = time.time() - start
            return BatchResult(
                index=idx, success=False, error=str(e), latency=latency,
            )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_execute, i, req): i
            for i, req in enumerate(requests)
        }
        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()

    return results
