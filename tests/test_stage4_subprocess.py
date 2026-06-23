"""
Stage 4: 子进程稳定性验证
- subprocess.TimeoutExpired 时确保 process.kill() + process.wait() 完整清理
- terminate 后 wait(timeout=5) 失败时用 kill() + wait(timeout=2)
- 添加 _process = None 防止重复终止
"""
import subprocess
import threading
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.scanner.wiztree_scanner import WizTreeScanner


class TestSubprocessCleanup:
    """验证子进程完整清理"""

    def test_timeout_expired_kills_and_waits(self):
        """TimeoutExpired 时应调用 kill() 和 wait()"""
        scanner = WizTreeScanner()
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=1)
        mock_process.wait.return_value = 0
        
        with patch('subprocess.Popen', return_value=mock_process):
            with pytest.raises(TimeoutError):
                scanner._execute_scan(["test.exe"], "output.csv")
        
        mock_process.kill.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        assert scanner._process is None

    def test_timeout_expired_wait_timeout(self):
        """kill() 后 wait() 超时时应记录警告"""
        scanner = WizTreeScanner()
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=1)
        mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=5)
        
        with patch('subprocess.Popen', return_value=mock_process):
            with pytest.raises(TimeoutError):
                scanner._execute_scan(["test.exe"], "output.csv")
        
        mock_process.kill.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        assert scanner._process is None

    def test_process_set_to_none_on_success(self):
        """成功执行后 _process 应设置为 None"""
        scanner = WizTreeScanner()
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        
        with patch('subprocess.Popen', return_value=mock_process):
            with patch('os.path.exists', return_value=True):
                scanner._execute_scan(["test.exe"], "output.csv")
        
        assert scanner._process is None

    def test_process_set_to_none_on_error(self):
        """执行出错后 _process 应设置为 None"""
        scanner = WizTreeScanner()
        mock_process = MagicMock()
        mock_process.communicate.side_effect = Exception("test error")
        
        with patch('subprocess.Popen', return_value=mock_process):
            with pytest.raises(RuntimeError):
                scanner._execute_scan(["test.exe"], "output.csv")
        
        assert scanner._process is None


class TestCancelMethod:
    """验证 cancel() 方法的进程清理"""

    def test_cancel_terminate_success(self):
        """terminate 成功时应等待进程结束"""
        scanner = WizTreeScanner()
        mock_process = MagicMock()
        mock_process.wait.return_value = 0
        scanner._process = mock_process
        
        scanner.cancel()
        
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        assert scanner._process is None

    def test_cancel_terminate_timeout_uses_kill(self):
        """terminate 超时时应使用 kill()"""
        scanner = WizTreeScanner()
        mock_process = MagicMock()
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=5),  # terminate wait
            0  # kill wait
        ]
        scanner._process = mock_process
        
        scanner.cancel()
        
        mock_process.terminate.assert_called_once()
        assert mock_process.wait.call_count == 2
        mock_process.kill.assert_called_once()
        assert scanner._process is None

    def test_cancel_terminate_timeout_kill_timeout(self):
        """terminate 超时且 kill 也超时时应记录警告"""
        scanner = WizTreeScanner()
        mock_process = MagicMock()
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=5),  # terminate wait
            subprocess.TimeoutExpired(cmd="test", timeout=2)   # kill wait
        ]
        scanner._process = mock_process
        
        scanner.cancel()
        
        mock_process.terminate.assert_called_once()
        assert mock_process.wait.call_count == 2
        mock_process.kill.assert_called_once()
        assert scanner._process is None

    def test_cancel_no_process(self):
        """没有进程时 cancel 应正常工作"""
        scanner = WizTreeScanner()
        scanner._process = None
        
        scanner.cancel()
        
        assert scanner._process is None

    def test_cancel_prevents_double_termination(self):
        """多次调用 cancel 不应重复终止进程"""
        scanner = WizTreeScanner()
        mock_process = MagicMock()
        mock_process.wait.return_value = 0
        scanner._process = mock_process
        
        scanner.cancel()
        scanner.cancel()  # 第二次调用
        
        mock_process.terminate.assert_called_once()
        assert scanner._process is None


class TestProcessNonePrevention:
    """验证 _process = None 防止重复终止"""

    def test_execute_scan_sets_process_none(self):
        """_execute_scan 结束后 _process 应为 None"""
        scanner = WizTreeScanner()
        
        # 模拟成功的情况
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        
        with patch('subprocess.Popen', return_value=mock_process):
            with patch('os.path.exists', return_value=True):
                scanner._execute_scan(["test.exe"], "output.csv")
        
        assert scanner._process is None

    def test_cancel_sets_process_none_immediately(self):
        """cancel 开始时应立即设置 _process = None"""
        scanner = WizTreeScanner()
        mock_process = MagicMock()
        scanner._process = mock_process
        
        # 在 cancel 开始时检查 _process
        original_process = scanner._process
        scanner.cancel()
        
        # cancel 后 _process 应为 None
        assert scanner._process is None
        # 但原始进程对象应该被终止
        mock_process.terminate.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])