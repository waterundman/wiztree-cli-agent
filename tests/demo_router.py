#!/usr/bin/env python3
"""
LLM Router 演示脚本
展示如何使用多Provider路由、故障转移和成本优化
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer import LLMRouter, RoutingStrategy


def demo_basic_usage():
    """基本用法演示"""
    print("=== 基本用法演示 ===")
    
    # 创建路由器（使用故障转移策略）
    router = LLMRouter(
        strategy=RoutingStrategy.FALLBACK,
        default_model="deepseek-v4-flash"
    )
    
    print(f"路由策略: {router.strategy.value}")
    print(f"默认模型: {router.default_model}")
    print(f"Provider数量: {len(router.providers)}")
    
    # 显示所有Provider
    print("\n可用Provider:")
    for provider in router.providers:
        models = [m.id for m in provider.models]
        print(f"  - {provider.name}: {models}")
    
    return router


def demo_provider_status(router):
    """Provider状态演示"""
    print("\n=== Provider状态演示 ===")
    
    status = router.get_provider_status()
    
    print("Provider状态:")
    for name, info in status.items():
        has_key = "有" if info['has_api_key'] else "无"
        print(f"  {name}:")
        print(f"    API密钥: {has_key}")
        print(f"    断路器: {info['circuit_breaker_state']}")
        print(f"    优先级: {info['priority']}")
        print(f"    标签: {info['tags']}")


def demo_available_models(router):
    """可用模型演示"""
    print("\n=== 可用模型演示 ===")
    
    models = router.get_available_models()
    
    print(f"可用模型数量: {len(models)}")
    print("\n模型列表:")
    for model in models:
        cost = f"${model['cost_input']:.2f}/${model['cost_output']:.2f}" if model['cost_input'] > 0 else "免费"
        print(f"  - {model['provider']}/{model['model_id']}")
        print(f"    成本: {cost} per 1M tokens")
        print(f"    上下文窗口: {model['context_window']:,} tokens")


def demo_routing_strategies():
    """路由策略演示"""
    print("\n=== 路由策略演示 ===")
    
    strategies = [
        (RoutingStrategy.COST, "成本优先", "自动选择最便宜的模型"),
        (RoutingStrategy.LATENCY, "速度优先", "自动选择最快的Provider"),
        (RoutingStrategy.FALLBACK, "故障转移", "按优先级尝试，失败自动切换"),
        (RoutingStrategy.MANUAL, "手动选择", "用户指定Provider")
    ]
    
    for strategy, name, desc in strategies:
        router = LLMRouter(strategy=strategy)
        print(f"\n{name} ({strategy.value}):")
        print(f"  描述: {desc}")
        print(f"  Provider数量: {len(router.providers)}")


def demo_chat_example(router):
    """聊天示例演示"""
    print("\n=== 聊天示例演示 ===")
    
    # 注意：这个示例需要有效的API密钥才能运行
    print("要测试聊天功能，请设置API密钥：")
    print("  set DEEPSEEK_API_KEY=sk-your-key-here")
    print("  或")
    print("  set OPENAI_API_KEY=sk-your-key-here")
    
    # 示例代码（注释掉，因为需要API密钥）
    """
    try:
        response = router.chat(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello! How are you?"}
            ],
            model="deepseek-v4-flash",
            temperature=0.7,
            max_tokens=100
        )
        
        print(f"\n响应:")
        print(f"  模型: {response.model}")
        print(f"  内容: {response.choices[0].message.content}")
        print(f"  Token使用: {response.usage.total_tokens}")
        
    except Exception as e:
        print(f"\n错误: {e}")
        print("请确保设置了有效的API密钥")
    """


def demo_streaming_example(router):
    """流式输出演示"""
    print("\n=== 流式输出演示 ===")
    
    print("流式输出示例代码：")
    print("""
    for chunk in router.chat_stream(
        messages=[{"role": "user", "content": "Tell me a short story"}],
        model="deepseek-v4-flash"
    ):
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="")
    """)


def demo_custom_router():
    """自定义路由器演示"""
    print("\n=== 自定义路由器演示 ===")
    
    # 创建自定义Provider配置
    custom_providers = [
        {
            "name": "my-deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key_env": "DEEPSEEK_API_KEY",
            "priority": 1,
            "tags": ["primary", "cost"],
            "models": [
                {
                    "id": "deepseek-v4-flash",
                    "cost_input": 0.14,
                    "cost_output": 0.28
                }
            ]
        },
        {
            "name": "my-openai",
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "OPENAI_API_KEY",
            "priority": 2,
            "tags": ["backup"],
            "models": [
                {
                    "id": "gpt-4o-mini",
                    "cost_input": 0.15,
                    "cost_output": 0.60
                }
            ]
        }
    ]
    
    # 使用自定义配置创建路由器
    from src.utils import create_custom_router
    
    router = create_custom_router(
        strategy="fallback",
        providers=custom_providers,
        default_model="deepseek-v4-flash"
    )
    
    print("自定义路由器创建成功:")
    print(f"  策略: {router.strategy.value}")
    print(f"  默认模型: {router.default_model}")
    print(f"  Provider数量: {len(router.providers)}")
    
    for provider in router.providers:
        print(f"  - {provider.name}: {[m.id for m in provider.models]}")


def demo_error_handling(router):
    """错误处理演示"""
    print("\n=== 错误处理演示 ===")
    
    print("LLM Router 内置错误处理机制:")
    print("  1. 断路器模式 - 防止故障Provider拖慢系统")
    print("  2. 自动重试 - 失败时自动重试")
    print("  3. 故障转移 - 自动切换到可用Provider")
    print("  4. 指数退避 - 重试间隔逐渐增加")
    
    print("\n断路器状态:")
    print("  CLOSED - 正常状态，允许请求")
    print("  OPEN - 失败次数超过阈值，拒绝请求")
    print("  HALF_OPEN - 恢复超时后，允许测试请求")


def main():
    """主函数"""
    print("LLM Router 演示")
    print("=" * 60)
    
    # 基本用法
    router = demo_basic_usage()
    
    # Provider状态
    demo_provider_status(router)
    
    # 可用模型
    demo_available_models(router)
    
    # 路由策略
    demo_routing_strategies()
    
    # 聊天示例
    demo_chat_example(router)
    
    # 流式输出
    demo_streaming_example(router)
    
    # 自定义路由器
    demo_custom_router()
    
    # 错误处理
    demo_error_handling(router)
    
    print("\n" + "=" * 60)
    print("演示完成!")
    print("\n更多信息请参考:")
    print("  - README_LLM_ROUTER.md")
    print("  - config/llm_config.json")
    print("  - src/analyzer/llm_router.py")


if __name__ == "__main__":
    main()