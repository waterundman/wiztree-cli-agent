"""
LLM Router - 统一的大模型API网关层
支持多Provider、智能路由、故障转移和成本优化

v1.5.0 新增:
- LatencyProbe: 延迟探测（后台线程定期 ping Provider）
- WeightedRouter: 动态权重路由（基于延迟/成功率/成本计算权重）
- batch_chat: 批量并行请求
- RequestCoalescer: 请求合并（相同消息的并发请求自动合并）

v2.1.0 拆分:
- CircuitBreaker → circuit_breaker.py
- LatencyProbe, LatencySample → latency_probe.py
- RequestCoalescer → request_coalescer.py
- BatchRequest, BatchResult, batch_chat → batch.py
"""

import logging
import os
import random
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any, Callable, Dict, List, Optional, Tuple, Union,
)
from datetime import datetime, timedelta
from openai import OpenAI
from openai import (
    APITimeoutError as Timeout,
    APIConnectionError as ConnectionError,
    AuthenticationError,
    APIError,
)

from .circuit_breaker import CircuitBreaker
from .latency_probe import LatencyProbe, LatencySample
from .request_coalescer import RequestCoalescer
from .batch import BatchRequest, BatchResult, batch_chat

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """路由策略"""
    COST = "cost"           # 成本优先
    LATENCY = "latency"     # 速度优先
    FALLBACK = "fallback"   # 故障转移
    MANUAL = "manual"       # 手动选择


class ProviderStatus(Enum):
    """Provider状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass
class ModelConfig:
    """模型配置"""
    id: str
    aliases: List[str] = field(default_factory=list)
    context_window: int = 4096
    max_output: int = 4096
    cost_input: float = 0.0      # USD per 1M tokens
    cost_output: float = 0.0     # USD per 1M tokens
    features: Dict[str, bool] = field(default_factory=dict)


@dataclass
class ProviderConfig:
    """Provider配置"""
    name: str
    base_url: str
    api_key_env: str           # 环境变量名
    api_key: Optional[str] = None  # 直接提供的API key
    auth_type: str = "bearer"
    compatibility: List[str] = field(default_factory=lambda: ["openai"])
    models: List[ModelConfig] = field(default_factory=list)
    priority: int = 1          # 优先级，数字越小优先级越高
    weight: float = 1.0        # 权重，用于加权路由
    tags: List[str] = field(default_factory=list)
    timeout: int = 30
    max_retries: int = 2
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None


class LLMRouter:
    """LLM路由器"""

    # 默认Provider配置
    DEFAULT_PROVIDERS = [
        ProviderConfig(
            name="deepseek",
            base_url="https://api.deepseek.com",
            api_key_env="DEEPSEEK_API_KEY",
            compatibility=["openai", "anthropic"],
            models=[
                ModelConfig(
                    id="deepseek-v4-flash",
                    aliases=["deepseek-chat"],
                    context_window=1000000,
                    max_output=8192,
                    cost_input=0.14,
                    cost_output=0.28,
                    features={"streaming": True, "thinking": True, "tool_calls": True}
                ),
                ModelConfig(
                    id="deepseek-v4-pro",
                    aliases=["deepseek-reasoner"],
                    context_window=1000000,
                    max_output=8192,
                    cost_input=0.44,
                    cost_output=0.87,
                    features={"streaming": True, "thinking": True, "tool_calls": True}
                ),
            ],
            priority=3,
            tags=["cost", "thinking", "china"]
        ),
        ProviderConfig(
            name="openai",
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
            compatibility=["openai"],
            models=[
                ModelConfig(
                    id="gpt-4o-mini",
                    context_window=128000,
                    max_output=16384,
                    cost_input=0.15,
                    cost_output=0.60,
                    features={"streaming": True, "tool_calls": True, "vision": True}
                ),
                ModelConfig(
                    id="gpt-4o",
                    context_window=128000,
                    max_output=16384,
                    cost_input=2.50,
                    cost_output=10.00,
                    features={"streaming": True, "tool_calls": True, "vision": True}
                ),
            ],
            priority=2,
            tags=["general", "vision"]
        ),
        ProviderConfig(
            name="anthropic",
            base_url="https://api.anthropic.com/v1",
            api_key_env="ANTHROPIC_API_KEY",
            compatibility=["anthropic", "openai"],
            models=[
                ModelConfig(
                    id="claude-3-haiku-20240307",
                    aliases=["claude-haiku"],
                    context_window=200000,
                    max_output=4096,
                    cost_input=0.25,
                    cost_output=1.25,
                    features={"streaming": True, "tool_calls": True}
                ),
                ModelConfig(
                    id="claude-3-5-sonnet-20241022",
                    aliases=["claude-sonnet"],
                    context_window=200000,
                    max_output=8192,
                    cost_input=3.00,
                    cost_output=15.00,
                    features={"streaming": True, "tool_calls": True, "vision": True}
                ),
            ],
            priority=1,
            tags=["core", "reasoning"]
        ),
        ProviderConfig(
            name="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key_env="OPENROUTER_API_KEY",
            compatibility=["openai"],
            models=[
                ModelConfig(
                    id="deepseek/deepseek-v4-flash",
                    context_window=1000000,
                    max_output=8192,
                    cost_input=0.14,
                    cost_output=0.28,
                    features={"streaming": True, "thinking": True}
                ),
                ModelConfig(
                    id="google/gemini-2.0-flash-exp:free",
                    aliases=["gemini-flash-free"],
                    context_window=1000000,
                    max_output=8192,
                    cost_input=0,
                    cost_output=0,
                    features={"streaming": True}
                ),
            ],
            priority=4,
            tags=["aggregator", "fallback"]
        ),
        ProviderConfig(
            name="siliconflow",
            base_url="https://api.siliconflow.cn/v1",
            api_key_env="SILICONFLOW_API_KEY",
            compatibility=["openai"],
            models=[
                ModelConfig(
                    id="deepseek-ai/DeepSeek-V3",
                    aliases=["deepseek-v3-sf"],
                    context_window=65536,
                    max_output=8192,
                    cost_input=0.0,
                    cost_output=0.0,
                    features={"streaming": True}
                ),
                ModelConfig(
                    id="Qwen/Qwen2.5-7B-Instruct",
                    aliases=["qwen-2.5-7b"],
                    context_window=32768,
                    max_output=8192,
                    cost_input=0.0,
                    cost_output=0.0,
                    features={"streaming": True}
                ),
            ],
            priority=5,
            tags=["free", "china", "fallback"]
        ),
        ProviderConfig(
            name="ollama",
            base_url="http://localhost:11434/v1",
            api_key_env="NO_AUTH",
            api_key="ollama",
            compatibility=["openai"],
            models=[
                ModelConfig(
                    id="llama3.2",
                    context_window=8192,
                    max_output=4096,
                    cost_input=0,
                    cost_output=0,
                    features={"streaming": True}
                ),
                ModelConfig(
                    id="qwen2.5",
                    context_window=32768,
                    max_output=8192,
                    cost_input=0,
                    cost_output=0,
                    features={"streaming": True}
                ),
            ],
            priority=10,
            tags=["local", "free", "fallback"]
        ),
    ]

    def __init__(
        self,
        strategy: RoutingStrategy = RoutingStrategy.FALLBACK,
        providers: Optional[List[ProviderConfig]] = None,
        default_model: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 2,
        enable_probe: bool = False,
        probe_interval: int = 30,
    ):
        """
        初始化LLM路由器
        
        Args:
            strategy: 路由策略
            providers: Provider配置列表，None则使用默认配置
            default_model: 默认模型ID
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
            enable_probe: 是否启动延迟探测线程
            probe_interval: 探测间隔（秒）
        """
        self.strategy = strategy
        self.providers = providers or self.DEFAULT_PROVIDERS
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 断路器
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Provider健康状态
        self._provider_status: Dict[str, ProviderStatus] = {}
        
        # 请求历史（用于统计）—— deque(maxlen) 自动淘汰旧记录，防止内存泄漏
        self._request_history: deque = deque(maxlen=1000)
        
        # Provider → OpenAI 客户端缓存（避免重复创建对象）
        self._client_cache: Dict[str, OpenAI] = {}
        self._client_lock: threading.Lock = threading.Lock()
        
        # 延迟探测
        self._latency_probe: Optional[LatencyProbe] = None
        if enable_probe:
            self._latency_probe = LatencyProbe(
                self.providers, interval=probe_interval
            )
            self._latency_probe.start()
        
        # 初始化
        self._initialize()

    def _initialize(self):
        """初始化路由器"""
        for provider in self.providers:
            # 初始化断路器
            self._circuit_breakers[provider.name] = CircuitBreaker(
                name=provider.name,
                failure_threshold=3,
                recovery_timeout=60
            )
            # 初始化状态
            self._provider_status[provider.name] = ProviderStatus.HEALTHY
            
            # 加载API密钥
            if provider.api_key_env and provider.api_key_env != "NO_AUTH":
                if not provider.api_key:
                    provider.api_key = os.environ.get(provider.api_key_env)

    def _get_client(self, provider: ProviderConfig) -> OpenAI:
        """获取OpenAI客户端（带缓存，避免重复创建连接对象）"""
        cache_key = provider.name
        with self._client_lock:
            if cache_key in self._client_cache:
                return self._client_cache[cache_key]

        api_key = provider.api_key or "no-key"
        if provider.api_key_env and provider.api_key_env != "NO_AUTH":
            api_key = os.environ.get(provider.api_key_env, api_key)
        
        client = OpenAI(
            base_url=provider.base_url,
            api_key=api_key,
            timeout=provider.timeout
        )
        with self._client_lock:
            self._client_cache[cache_key] = client
        return client

    def _find_model(self, model_id: str) -> Optional[tuple[ProviderConfig, ModelConfig]]:
        """查找模型配置"""
        for provider in self.providers:
            for model in provider.models:
                if model.id == model_id or model_id in model.aliases:
                    return provider, model
        return None

    def _select_provider(
        self,
        model_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[ProviderConfig]:
        """根据策略选择Provider"""
        candidates = []
        
        for provider in self.providers:
            # 检查断路器
            breaker = self._circuit_breakers.get(provider.name)
            if breaker and not breaker.can_execute():
                continue
            
            # 检查API密钥
            if provider.api_key_env != "NO_AUTH" and not provider.api_key:
                api_key = os.environ.get(provider.api_key_env)
                if not api_key:
                    continue
                provider.api_key = api_key
            
            # 检查标签
            if tags:
                if not any(tag in provider.tags for tag in tags):
                    continue
            
            # 检查模型
            if model_id:
                has_model = any(
                    m.id == model_id or model_id in m.aliases
                    for m in provider.models
                )
                if not has_model:
                    continue
            
            candidates.append(provider)
        
        # 根据策略排序
        if self.strategy == RoutingStrategy.COST:
            candidates.sort(key=lambda p: self._get_provider_cost(p, model_id))
        elif self.strategy == RoutingStrategy.LATENCY:
            if self._latency_probe:
                latencies = self._latency_probe.get_latencies()
                candidates.sort(key=lambda p: latencies.get(p.name, float('inf')))
            else:
                candidates.sort(key=lambda p: p.priority)
        elif self.strategy == RoutingStrategy.FALLBACK:
            candidates.sort(key=lambda p: p.priority)
        elif self.strategy == RoutingStrategy.MANUAL:
            pass  # 保持原始顺序
        
        return candidates

    def _get_provider_cost(self, provider: ProviderConfig, model_id: Optional[str] = None) -> float:
        """获取Provider的成本"""
        if not model_id:
            # 返回平均成本
            if provider.models:
                return sum(m.cost_input + m.cost_output for m in provider.models) / len(provider.models)
            return float('inf')
        
        for model in provider.models:
            if model.id == model_id or model_id in model.aliases:
                return model.cost_input + model.cost_output
        return float('inf')

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Any:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            model: 模型ID
            temperature: 温度
            max_tokens: 最大token数
            stream: 是否流式
            **kwargs: 其他参数
            
        Returns:
            响应对象
        """
        model_id = model or self.default_model
        if not model_id:
            model_id = "deepseek-v4-flash"  # 默认模型
        
        # 查找模型
        model_info = self._find_model(model_id)
        if model_info:
            provider, model_config = model_info
            providers_to_try = [provider]
        else:
            # 使用路由策略选择Provider
            providers_to_try = self._select_provider(model_id)
        
        if not providers_to_try:
            raise RuntimeError("No available provider")
        
        errors = []
        for provider in providers_to_try:
            breaker = self._circuit_breakers.get(provider.name)
            
            for attempt in range(self.max_retries + 1):
                try:
                    client = self._get_client(provider)
                    
                    # 确定使用的模型ID
                    actual_model = model_id
                    for m in provider.models:
                        if m.id == model_id or model_id in m.aliases:
                            actual_model = m.id
                            break
                    
                    # 发送请求
                    start_time = time.time()
                    response = client.chat.completions.create(
                        model=actual_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=stream,
                        **kwargs
                    )
                    latency = time.time() - start_time
                    
                    # 记录成功
                    if breaker:
                        breaker.record_success()
                    
                    # 记录到延迟探测器
                    if self._latency_probe:
                        self._latency_probe.record_external(
                            provider.name, latency * 1000, True
                        )
                    
                    # 记录历史
                    self._request_history.append({
                        "provider": provider.name,
                        "model": actual_model,
                        "latency": latency,
                        "success": True,
                        "timestamp": datetime.now()
                    })
                    
                    return response
                    
                except AuthenticationError as e:
                    # 不可重试异常：认证失败，记录错误并继续到下一个Provider
                    errors.append(f"{provider.name}: {str(e)}")
                    
                    # 记录失败
                    if breaker:
                        breaker.record_failure()
                    
                    # 记录到延迟探测器
                    if self._latency_probe:
                        self._latency_probe.record_external(
                            provider.name, 0, False
                        )
                    
                    # 记录历史
                    self._request_history.append({
                        "provider": provider.name,
                        "model": model_id,
                        "success": False,
                        "error": str(e),
                        "timestamp": datetime.now()
                    })
                    
                    # 认证错误不重试，直接跳到下一个Provider
                    break
                    
                except (Timeout, ConnectionError) as e:
                    # 可重试异常：超时/连接错误
                    errors.append(f"{provider.name}: {str(e)}")
                    
                    # 记录失败
                    if breaker:
                        breaker.record_failure()
                    
                    # 记录到延迟探测器
                    if self._latency_probe:
                        self._latency_probe.record_external(
                            provider.name, 0, False
                        )
                    
                    # 记录历史
                    self._request_history.append({
                        "provider": provider.name,
                        "model": model_id,
                        "success": False,
                        "error": str(e),
                        "timestamp": datetime.now()
                    })
                    
                    # 如果是最后一次尝试，继续到下一个Provider
                    if attempt < self.max_retries:
                        # 指数退避 + random jitter 防止 thundering herd
                        base_delay = 1 * (attempt + 1)
                        jitter = random.uniform(0, base_delay * 0.5)
                        delay = base_delay + jitter
                        print(f"Attempt {attempt + 1} failed (retryable), retrying in {delay:.1f}s: {e}")
                        time.sleep(delay)
                        
                except APIError as e:
                    # API 错误：检查是否可重试
                    errors.append(f"{provider.name}: {str(e)}")
                    
                    # 记录失败
                    if breaker:
                        breaker.record_failure()
                    
                    # 记录到延迟探测器
                    if self._latency_probe:
                        self._latency_probe.record_external(
                            provider.name, 0, False
                        )
                    
                    # 记录历史
                    self._request_history.append({
                        "provider": provider.name,
                        "model": model_id,
                        "success": False,
                        "error": str(e),
                        "timestamp": datetime.now()
                    })
                    
                    # 某些 API 错误可能可重试（如 429 限流）
                    if hasattr(e, 'status_code') and e.status_code == 429:
                        if attempt < self.max_retries:
                            # 指数退避 + random jitter
                            base_delay = 1 * (attempt + 1)
                            jitter = random.uniform(0, base_delay * 0.5)
                            delay = base_delay + jitter
                            print(f"Attempt {attempt + 1} failed (rate limited), retrying in {delay:.1f}s: {e}")
                            time.sleep(delay)
                    else:
                        # 其他 API 错误不重试，继续到下一个Provider
                        break
                        
                except Exception as e:
                    # 未知异常：记录错误并继续到下一个Provider
                    errors.append(f"{provider.name}: {str(e)}")
                    
                    # 记录失败
                    if breaker:
                        breaker.record_failure()
                    
                    # 记录到延迟探测器
                    if self._latency_probe:
                        self._latency_probe.record_external(
                            provider.name, 0, False
                        )
                    
                    # 记录历史
                    self._request_history.append({
                        "provider": provider.name,
                        "model": model_id,
                        "success": False,
                        "error": str(e),
                        "timestamp": datetime.now()
                    })
                    
                    # 未知异常不重试，继续到下一个Provider
                    break
        
        raise RuntimeError(f"All providers failed: {'; '.join(errors)}")

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        流式聊天请求
        
        Args:
            messages: 消息列表
            model: 模型ID
            temperature: 温度
            max_tokens: 最大token数
            **kwargs: 其他参数
            
        Yields:
            响应chunk
        """
        model_id = model or self.default_model
        if not model_id:
            model_id = "deepseek-v4-flash"
        
        # 查找模型
        model_info = self._find_model(model_id)
        if model_info:
            provider, model_config = model_info
            providers_to_try = [provider]
        else:
            providers_to_try = self._select_provider(model_id)
        
        if not providers_to_try:
            raise RuntimeError("No available provider")
        
        for provider in providers_to_try:
            try:
                client = self._get_client(provider)
                
                actual_model = model_id
                for m in provider.models:
                    if m.id == model_id or model_id in m.aliases:
                        actual_model = m.id
                        break
                
                stream = client.chat.completions.create(
                    model=actual_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    **kwargs
                )
                
                for chunk in stream:
                    yield chunk
                    
                return  # 成功，退出
                
            except AuthenticationError as e:
                # 不可重试异常：认证失败，继续到下一个Provider
                logger.warning(f"Provider {provider.name} authentication failed: {e}")
                continue
            except (Timeout, ConnectionError) as e:
                # 可重试异常：超时/连接错误，继续到下一个Provider
                logger.warning(f"Provider {provider.name} connection failed: {e}")
                continue
            except APIError as e:
                # API 错误：继续到下一个Provider
                logger.warning(f"Provider {provider.name} API error: {e}")
                continue
            except Exception as e:
                # 未知异常：继续到下一个Provider
                logger.warning(f"Provider {provider.name} unknown error: {e}")
                continue
        
        raise RuntimeError("All providers failed for streaming")

    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取所有可用模型"""
        models = []
        for provider in self.providers:
            if provider.api_key_env == "NO_AUTH" or provider.api_key or os.environ.get(provider.api_key_env):
                for model in provider.models:
                    models.append({
                        "provider": provider.name,
                        "model_id": model.id,
                        "aliases": model.aliases,
                        "context_window": model.context_window,
                        "cost_input": model.cost_input,
                        "cost_output": model.cost_output,
                        "features": model.features,
                        "tags": provider.tags
                    })
        return models

    def get_provider_status(self) -> Dict[str, Dict]:
        """获取Provider状态（含延迟探测数据）"""
        status = {}
        probe_stats = {}
        if self._latency_probe:
            probe_stats = self._latency_probe.get_stats()

        for provider in self.providers:
            breaker = self._circuit_breakers.get(provider.name)
            has_key = provider.api_key_env == "NO_AUTH" or provider.api_key or os.environ.get(provider.api_key_env)
            
            info = {
                "has_api_key": has_key,
                "circuit_breaker_state": breaker.state if breaker else "N/A",
                "failures": breaker.failures if breaker else 0,
                "priority": provider.priority,
                "tags": provider.tags,
                "models": [m.id for m in provider.models]
            }
            if provider.name in probe_stats:
                info["latency"] = probe_stats[provider.name]
            status[provider.name] = info
        return status

    def get_stats(self) -> Dict:
        """获取统计信息（_request_history 为 deque，len/迭代/列表推导均兼容）"""
        history = list(self._request_history)  # snapshot 防止迭代时并发修改
        total = len(history)
        successful = sum(1 for r in history if r["success"])
        failed = total - successful
        
        avg_latency = 0
        latencies = [r["latency"] for r in history if r.get("latency")]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
        
        return {
            "total_requests": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "average_latency": avg_latency,
            "max_history_size": self._request_history.maxlen,
            "providers": self.get_provider_status()
        }

    def set_strategy(self, strategy: RoutingStrategy):
        """设置路由策略"""
        self.strategy = strategy

    def add_provider(self, provider: ProviderConfig):
        """添加Provider"""
        self.providers.append(provider)
        self._circuit_breakers[provider.name] = CircuitBreaker(
            name=provider.name,
            failure_threshold=3,
            recovery_timeout=60
        )
        self._provider_status[provider.name] = ProviderStatus.HEALTHY
        if provider.api_key_env and provider.api_key_env != "NO_AUTH":
            if not provider.api_key:
                provider.api_key = os.environ.get(provider.api_key_env)

    def remove_provider(self, name: str):
        """移除Provider"""
        self.providers = [p for p in self.providers if p.name != name]
        self._circuit_breakers.pop(name, None)
        self._provider_status.pop(name, None)
        with self._client_lock:
            self._client_cache.pop(name, None)

    def shutdown(self):
        """停止后台线程，释放资源"""
        if self._latency_probe:
            self._latency_probe.stop()
        with self._client_lock:
            self._client_cache.clear()


# ---------------------------------------------------------------------------
# v1.5.0 — WeightedRouter（动态权重路由）
# ---------------------------------------------------------------------------

class WeightedRouter(LLMRouter):
    """
    动态权重路由器 —— 基于延迟 / 成功率 / 成本 综合计算权重，按权重随机选择 Provider。

    权重公式::

        score = w_latency * f(latency)
              + w_success * f(success_rate)
              + w_cost    * f(cost)

    其中 f 为归一化函数，最终 score 归一化为概率分布。

    用法::

        router = WeightedRouter(
            strategy=RoutingStrategy.COST,
            enable_probe=True,
            weights={"latency": 0.4, "success": 0.4, "cost": 0.2},
        )
        response = router.chat(messages=[...])
    """

    DEFAULT_WEIGHTS = {"latency": 0.4, "success": 0.3, "cost": 0.3}

    def __init__(
        self,
        strategy: RoutingStrategy = RoutingStrategy.FALLBACK,
        providers: Optional[List[ProviderConfig]] = None,
        default_model: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 2,
        enable_probe: bool = True,
        probe_interval: int = 30,
        weights: Optional[Dict[str, float]] = None,
    ):
        super().__init__(
            strategy=strategy,
            providers=providers,
            default_model=default_model,
            timeout=timeout,
            max_retries=max_retries,
            enable_probe=enable_probe,
            probe_interval=probe_interval,
        )
        self._weights = weights or self.DEFAULT_WEIGHTS

    def _select_provider(
        self,
        model_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[ProviderConfig]:
        """动态权重选择 Provider"""
        candidates = []
        for provider in self.providers:
            breaker = self._circuit_breakers.get(provider.name)
            if breaker and not breaker.can_execute():
                continue
            if provider.api_key_env != "NO_AUTH" and not provider.api_key:
                api_key = os.environ.get(provider.api_key_env)
                if not api_key:
                    continue
                provider.api_key = api_key
            if tags and not any(tag in provider.tags for tag in tags):
                continue
            if model_id:
                has_model = any(
                    m.id == model_id or model_id in m.aliases
                    for m in provider.models
                )
                if not has_model:
                    continue
            candidates.append(provider)

        if not candidates:
            return []

        if len(candidates) == 1:
            return candidates

        weights = self._compute_weights(candidates, model_id)
        sorted_candidates = [
            c for _, c in sorted(
                zip(weights, candidates), key=lambda x: x[0], reverse=True
            )
        ]
        return sorted_candidates

    def _compute_weights(
        self,
        candidates: List[ProviderConfig],
        model_id: Optional[str] = None,
    ) -> List[float]:
        """计算各候选 Provider 的综合得分"""
        n = len(candidates)
        latency_scores = [0.0] * n
        success_scores = [0.0] * n
        cost_scores = [0.0] * n

        # 延迟分
        if self._latency_probe:
            latencies = self._latency_probe.get_latencies()
            lat_values = [latencies.get(c.name, float('inf')) for c in candidates]
            max_lat = max((v for v in lat_values if v < float('inf')), default=1)
            if max_lat == 0:
                max_lat = 1
            for i, v in enumerate(lat_values):
                if v == float('inf'):
                    latency_scores[i] = 0.0
                else:
                    latency_scores[i] = 1.0 - (v / (max_lat * 1.1))
        else:
            for i, c in enumerate(candidates):
                latency_scores[i] = 1.0 / c.priority

        # 成功率分
        if self._latency_probe:
            probe_stats = self._latency_probe.get_stats()
            for i, c in enumerate(candidates):
                s = probe_stats.get(c.name, {})
                success_scores[i] = s.get("success_rate", 0.5)
        else:
            for i in range(n):
                success_scores[i] = 0.5

        # 成本分（越低越好）
        costs = [self._get_provider_cost(c, model_id) for c in candidates]
        max_cost = max((c for c in costs if c < float('inf')), default=1)
        if max_cost == 0:
            max_cost = 1
        for i, c in enumerate(costs):
            if c == float('inf'):
                cost_scores[i] = 0.0
            else:
                cost_scores[i] = 1.0 - (c / (max_cost * 1.1))

        # 综合得分
        w_lat = self._weights.get("latency", 0.4)
        w_suc = self._weights.get("success", 0.3)
        w_cost = self._weights.get("cost", 0.3)

        scores = []
        for i in range(n):
            score = (
                w_lat * latency_scores[i]
                + w_suc * success_scores[i]
                + w_cost * cost_scores[i]
            )
            scores.append(max(score, 0.01))

        return scores

    def get_routing_weights(self) -> Dict[str, float]:
        """返回当前各 Provider 的路由权重（可直接用于调试/UI 展示）"""
        candidates = [
            p for p in self.providers
            if self._circuit_breakers.get(p.name, CircuitBreaker("")).can_execute()
        ]
        if not candidates:
            return {}
        scores = self._compute_weights(candidates)
        total = sum(scores) or 1
        return {
            c.name: round(s / total, 4)
            for c, s in zip(candidates, scores)
        }


# 预设配置
def create_cost_optimized_router() -> LLMRouter:
    """创建成本优化路由器"""
    return LLMRouter(
        strategy=RoutingStrategy.COST,
        default_model="deepseek-v4-flash"
    )

def create_latency_optimized_router() -> LLMRouter:
    """创建延迟优化路由器"""
    return LLMRouter(
        strategy=RoutingStrategy.LATENCY,
        default_model="deepseek-v4-flash"
    )

def create_fallback_router() -> LLMRouter:
    """创建故障转移路由器"""
    return LLMRouter(
        strategy=RoutingStrategy.FALLBACK,
        default_model="deepseek-v4-flash"
    )
