"""
CircuitBreaker 线程安全测试
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer.llm_router import CircuitBreaker


def test_concurrent_record_failure():
    """测试并发记录失败"""
    breaker = CircuitBreaker("test", failure_threshold=10)
    threads = []
    errors = []
    
    def record_failures():
        try:
            for _ in range(100):
                breaker.record_failure()
        except Exception as e:
            errors.append(e)
    
    # 创建10个线程，每个记录100次失败
    for _ in range(10):
        t = threading.Thread(target=record_failures)
        threads.append(t)
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    # 检查结果
    assert len(errors) == 0, f"发生错误: {errors}"
    assert breaker.failures == 1000, f"预期1000次失败，实际{breaker.failures}次"
    assert breaker.state == "OPEN", f"预期OPEN状态，实际{breaker.state}状态"
    print("✓ 并发记录失败测试通过")


def test_concurrent_state_transitions():
    """测试并发状态转换"""
    breaker = CircuitBreaker("test", failure_threshold=5, recovery_timeout=1)
    results = []
    errors = []
    
    def check_can_execute():
        try:
            for _ in range(100):
                result = breaker.can_execute()
                results.append(result)
        except Exception as e:
            errors.append(e)
    
    def record_failures():
        try:
            for _ in range(10):
                breaker.record_failure()
                time.sleep(0.01)
        except Exception as e:
            errors.append(e)
    
    # 启动多个线程检查状态
    threads = []
    for _ in range(5):
        t = threading.Thread(target=check_can_execute)
        threads.append(t)
        t.start()
    
    # 启动一个线程记录失败
    t = threading.Thread(target=record_failures)
    threads.append(t)
    t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    # 检查结果
    assert len(errors) == 0, f"发生错误: {errors}"
    assert len(results) == 500, f"预期500个结果，实际{len(results)}个"
    print("✓ 并发状态转换测试通过")


def test_concurrent_mixed_operations():
    """测试并发混合操作"""
    breaker = CircuitBreaker("test", failure_threshold=3, recovery_timeout=1)
    errors = []
    
    def mixed_operations(thread_id):
        try:
            for i in range(50):
                if i % 3 == 0:
                    breaker.record_failure()
                elif i % 3 == 1:
                    breaker.record_success()
                else:
                    breaker.can_execute()
        except Exception as e:
            errors.append(f"线程{thread_id}: {e}")
    
    # 创建多个线程执行混合操作
    threads = []
    for i in range(8):
        t = threading.Thread(target=mixed_operations, args=(i,))
        threads.append(t)
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    # 检查结果
    assert len(errors) == 0, f"发生错误: {errors}"
    print("✓ 并发混合操作测试通过")


if __name__ == "__main__":
    print("开始 CircuitBreaker 线程安全测试...")
    test_concurrent_record_failure()
    test_concurrent_state_transitions()
    test_concurrent_mixed_operations()
    print("所有线程安全测试通过！")