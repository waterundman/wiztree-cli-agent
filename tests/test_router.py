#!/usr/bin/env python3
"""
测试LLM Router
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer import LLMRouter, RoutingStrategy
from src.utils import get_default_router, create_router_from_config


def test_router_initialization():
    """测试路由器初始化"""
    print("=== 测试路由器初始化 ===")
    
    # 测试默认路由器
    router = get_default_router()
    print(f"默认路由器创建成功: {router.strategy.value}")
    print(f"Provider数量: {len(router.providers)}")
    
    # 显示所有Provider
    for provider in router.providers:
        print(f"  - {provider.name}: {provider.base_url}")
        print(f"    标签: {provider.tags}")
        print(f"    模型: {[m.id for m in provider.models]}")
    
    assert router is not None
    assert len(router.providers) > 0


def test_provider_status():
    """测试Provider状态"""
    print("\n=== 测试Provider状态 ===")
    
    router = get_default_router()
    status = router.get_provider_status()
    for name, info in status.items():
        print(f"{name}:")
        print(f"  有API密钥: {info['has_api_key']}")
        print(f"  断路器状态: {info['circuit_breaker_state']}")
        print(f"  优先级: {info['priority']}")
    
    assert len(status) > 0


def test_available_models():
    """测试可用模型"""
    print("\n=== 测试可用模型 ===")
    
    router = get_default_router()
    models = router.get_available_models()
    print(f"可用模型数量: {len(models)}")
    for model in models[:5]:  # 只显示前5个
        print(f"  - {model['provider']}/{model['model_id']}")
        print(f"    成本: ${model['cost_input']:.2f}/${model['cost_output']:.2f} per 1M tokens")
    
    if len(models) > 5:
        print(f"  ... 还有 {len(models) - 5} 个模型")
    
    assert len(models) > 0


def test_routing_strategy():
    """测试路由策略"""
    print("\n=== 测试路由策略 ===")
    
    strategies = [
        ("cost", "成本优先"),
        ("latency", "速度优先"),
        ("fallback", "故障转移"),
        ("manual", "手动选择")
    ]
    
    for strategy, desc in strategies:
        router = LLMRouter(
            strategy=RoutingStrategy(strategy),
            default_model="deepseek-v4-flash"
        )
        print(f"{desc} ({strategy}): {len(router.providers)} providers")


def test_config_loading():
    """测试配置加载"""
    print("\n=== 测试配置加载 ===")
    
    try:
        router = create_router_from_config()
        print(f"从配置文件加载成功")
        print(f"策略: {router.strategy.value}")
        print(f"默认模型: {router.default_model}")
        print(f"Provider数量: {len(router.providers)}")
    except FileNotFoundError:
        print("配置文件不存在，跳过测试")
    except Exception as e:
        print(f"配置加载失败: {e}")


def main():
    """主函数"""
    print("LLM Router 测试")
    print("=" * 50)
    
    # 测试初始化
    test_router_initialization()
    
    # 测试Provider状态
    test_provider_status()
    
    # 测试可用模型
    test_available_models()
    
    # 测试路由策略
    test_routing_strategy()
    
    # 测试配置加载
    test_config_loading()
    
    print("\n" + "=" * 50)
    print("测试完成!")
    print("\n使用示例:")
    print("  from src.analyzer import LLMRouter")
    print("  router = LLMRouter(strategy=RoutingStrategy.FALLBACK)")
    print("  response = router.chat(messages=[{'role': 'user', 'content': 'Hello'}])")


if __name__ == "__main__":
    main()