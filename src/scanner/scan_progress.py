import threading
import time
from typing import Callable, Optional, Any
from dataclasses import dataclass
from enum import Enum


class ScanStatus(Enum):
    """扫描状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class ProgressInfo:
    """进度信息"""
    status: ScanStatus
    progress: float  # 0.0 - 1.0
    message: str
    current_file: Optional[str] = None
    files_scanned: int = 0
    directories_scanned: int = 0
    elapsed_time: float = 0.0
    estimated_remaining: Optional[float] = None
    error: Optional[str] = None


class ScanProgress:
    """扫描进度管理器"""
    
    def __init__(
        self,
        on_progress: Optional[Callable[[ProgressInfo], None]] = None,
        on_complete: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        timeout: Optional[float] = None
    ):
        """
        初始化扫描进度管理器
        
        Args:
            on_progress: 进度回调函数
            on_complete: 完成回调函数
            on_error: 错误回调函数
            timeout: 超时时间（秒）
        """
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._on_error = on_error
        self._timeout = timeout
        
        self._status = ScanStatus.PENDING
        self._progress = 0.0
        self._message = "等待开始"
        self._current_file: Optional[str] = None
        self._files_scanned = 0
        self._directories_scanned = 0
        self._start_time: Optional[float] = None
        self._error: Optional[str] = None
        
        self._cancel_event = threading.Event()
        self._timeout_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
    
    @property
    def status(self) -> ScanStatus:
        """获取扫描状态"""
        return self._status
    
    @property
    def is_cancelled(self) -> bool:
        """是否已取消"""
        return self._cancel_event.is_set()
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._status == ScanStatus.RUNNING
    
    @property
    def progress_info(self) -> ProgressInfo:
        """获取进度信息"""
        elapsed = 0.0
        if self._start_time:
            elapsed = time.time() - self._start_time
        
        estimated_remaining = None
        if self._progress > 0 and self._progress < 1.0:
            estimated_remaining = elapsed * (1.0 - self._progress) / self._progress
        
        return ProgressInfo(
            status=self._status,
            progress=self._progress,
            message=self._message,
            current_file=self._current_file,
            files_scanned=self._files_scanned,
            directories_scanned=self._directories_scanned,
            elapsed_time=elapsed,
            estimated_remaining=estimated_remaining,
            error=self._error
        )
    
    def start(self):
        """开始扫描"""
        with self._lock:
            if self._status != ScanStatus.PENDING:
                raise RuntimeError("扫描已经开始")
            
            self._status = ScanStatus.RUNNING
            self._start_time = time.time()
            self._message = "扫描开始"
            self._notify_progress()
            
            # 设置超时定时器
            if self._timeout:
                self._timeout_timer = threading.Timer(
                    self._timeout, self._handle_timeout
                )
                self._timeout_timer.daemon = True
                self._timeout_timer.start()
    
    def update_progress(
        self,
        progress: float,
        message: str,
        current_file: Optional[str] = None,
        files_scanned: Optional[int] = None,
        directories_scanned: Optional[int] = None
    ):
        """
        更新进度
        
        Args:
            progress: 进度值 (0.0 - 1.0)
            message: 进度消息
            current_file: 当前扫描的文件
            files_scanned: 已扫描文件数
            directories_scanned: 已扫描目录数
        """
        with self._lock:
            if self._status != ScanStatus.RUNNING:
                return
            
            self._progress = min(max(progress, 0.0), 1.0)
            self._message = message
            
            if current_file is not None:
                self._current_file = current_file
            if files_scanned is not None:
                self._files_scanned = files_scanned
            if directories_scanned is not None:
                self._directories_scanned = directories_scanned
            
            self._notify_progress()
    
    def complete(self, result: Any = None):
        """
        完成扫描
        
        Args:
            result: 扫描结果
        """
        with self._lock:
            if self._status != ScanStatus.RUNNING:
                return
            
            self._status = ScanStatus.COMPLETED
            self._progress = 1.0
            self._message = "扫描完成"
            self._cancel_timeout_timer()
            self._notify_progress()
            
            if self._on_complete:
                try:
                    self._on_complete(result)
                except Exception:
                    pass
    
    def fail(self, error: Exception):
        """
        扫描失败
        
        Args:
            error: 错误信息
        """
        with self._lock:
            if self._status != ScanStatus.RUNNING:
                return
            
            self._status = ScanStatus.FAILED
            self._error = str(error)
            self._message = f"扫描失败: {error}"
            self._cancel_timeout_timer()
            self._notify_progress()
            
            if self._on_error:
                try:
                    self._on_error(error)
                except Exception:
                    pass
    
    def cancel(self):
        """取消扫描"""
        with self._lock:
            if self._status != ScanStatus.RUNNING:
                return
            
            self._cancel_event.set()
            self._status = ScanStatus.CANCELLED
            self._message = "扫描已取消"
            self._cancel_timeout_timer()
            self._notify_progress()
    
    def _handle_timeout(self):
        """处理超时"""
        with self._lock:
            if self._status != ScanStatus.RUNNING:
                return
            
            self._cancel_event.set()
            self._status = ScanStatus.TIMEOUT
            self._error = f"扫描超时（超过{self._timeout}秒）"
            self._message = self._error
            self._notify_progress()
            
            if self._on_error:
                try:
                    self._on_error(TimeoutError(self._error))
                except Exception:
                    pass
    
    def _cancel_timeout_timer(self):
        """取消超时定时器"""
        if self._timeout_timer:
            self._timeout_timer.cancel()
            self._timeout_timer = None
    
    def _notify_progress(self):
        """通知进度更新"""
        if self._on_progress:
            try:
                self._on_progress(self.progress_info)
            except Exception:
                pass
    
    def reset(self):
        """重置进度管理器"""
        with self._lock:
            self._cancel_timeout_timer()
            self._cancel_event.clear()
            
            self._status = ScanStatus.PENDING
            self._progress = 0.0
            self._message = "等待开始"
            self._current_file = None
            self._files_scanned = 0
            self._directories_scanned = 0
            self._start_time = None
            self._error = None
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        等待扫描完成
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否在超时前完成
        """
        if self._status == ScanStatus.PENDING:
            return False
        
        start_time = time.time()
        while self._status == ScanStatus.RUNNING:
            if timeout and (time.time() - start_time) >= timeout:
                return False
            time.sleep(0.1)
        
        return True
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if exc_type is not None:
            self.fail(exc_val)
        elif self._status == ScanStatus.RUNNING:
            self.complete()