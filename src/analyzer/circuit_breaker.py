"""断路器模式实现"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class CircuitBreaker:
    """断路器"""
    name: str
    failure_threshold: int = 3
    recovery_timeout: int = 60  # 秒
    failures: int = 0
    last_failure: Optional[datetime] = None
    state: str = "CLOSED"  # CLOSED → OPEN → HALF_OPEN
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def record_failure(self):
        """记录失败"""
        with self._lock:
            self.failures += 1
            self.last_failure = datetime.now()
            if self.failures >= self.failure_threshold:
                self.state = "OPEN"

    def record_success(self):
        """记录成功"""
        with self._lock:
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failures = 0

    def can_execute(self) -> bool:
        """检查是否可以执行"""
        with self._lock:
            if self.state == "CLOSED":
                return True
            if self.state == "OPEN":
                if self.last_failure and datetime.now() - self.last_failure > timedelta(seconds=self.recovery_timeout):
                    self.state = "HALF_OPEN"
                    return True
                return False
            return True  # HALF_OPEN
