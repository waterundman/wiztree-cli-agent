import logging
import os
import csv
import json
import hashlib
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any, Generator, Tuple, Iterator
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    from ..models.file_info import FileInfo
    from ..models.scan_result import ScanResult
    from .options import ScanOptions
    from .path_validator import PathValidator
    from .scan_progress import ScanProgress, ScanStatus
    from .wiztree_scanner import WizTreeScanner
except ImportError as _e:
    logger.debug("Relative import failed (%s), falling back to absolute imports", _e)
    from models.file_info import FileInfo
    from models.scan_result import ScanResult
    from scanner.options import ScanOptions
    from scanner.path_validator import PathValidator
    from scanner.scan_progress import ScanProgress, ScanStatus
    from scanner.wiztree_scanner import WizTreeScanner


class StreamingScanner(WizTreeScanner):
    """流式扫描器，支持批次扫描和延迟加载"""
    
    def __init__(
        self,
        wiztree_path: Optional[str] = None,
        progress_callback: Optional[callable] = None,
        timeout: Optional[float] = 300
    ):
        """
        初始化流式扫描器
        
        Args:
            wiztree_path: WizTree可执行文件路径
            progress_callback: 进度回调函数
            timeout: 超时时间（秒）
        """
        super().__init__(wiztree_path, progress_callback, timeout)
        self._batch_cache: Dict[str, List[FileInfo]] = {}
        self._total_files_cache: Optional[int] = None
        self._csv_path: Optional[str] = None
    
    def scan(self, target: str, options: ScanOptions) -> ScanResult:
        """
        流式扫描目标路径（覆盖父类方法，优化内存使用）
        
        Args:
            target: 目标路径（驱动器或文件夹）
            options: 扫描选项
            
        Returns:
            ScanResult: 扫描结果
        """
        # 验证目标路径
        is_valid, error_msg = self._path_validator.validate(target)
        if not is_valid:
            raise ValueError(f"无效的扫描目标: {error_msg}")
        
        # 初始化进度管理器
        self._progress_manager = ScanProgress(
            on_progress=self._progress_callback,
            timeout=self._timeout
        )
        
        self._cancelled = False
        self._batch_cache.clear()
        self._total_files_cache = None
        
        try:
            # 开始扫描
            self._progress_manager.start()
            
            # 检查WizTree路径
            if not self._wiztree_path or not os.path.isfile(self._wiztree_path):
                raise FileNotFoundError("WizTree可执行文件不存在")
            
            # 准备扫描命令
            cmd = self._build_command(target, options)
            
            # 创建临时CSV文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._csv_path = os.path.join(
                tempfile.gettempdir(), f"wiztree_stream_{timestamp}.csv"
            )
            
            # 执行扫描
            scan_start_time = datetime.now()
            self._execute_scan(cmd, self._csv_path)
            
            # 检查是否被取消
            if self._cancelled:
                raise InterruptedError("扫描被取消")
            
            # 使用流式解析，不一次性加载所有文件到内存
            files = list(self._parse_csv_streaming(self._csv_path))
            
            # 计算扫描时长
            scan_duration = (datetime.now() - scan_start_time).total_seconds()
            
            # 构建扫描结果
            result = self._build_scan_result(
                target, files, scan_start_time, scan_duration, options
            )
            
            # 完成扫描
            self._progress_manager.complete(result)
            
            return result
            
        except Exception as e:
            if self._progress_manager:
                self._progress_manager.fail(e)
            raise
        finally:
            # 清理临时文件
            if self._csv_path and os.path.exists(self._csv_path):
                try:
                    os.remove(self._csv_path)
                except OSError:
                    logger.debug("Failed to remove temp CSV: %s", self._csv_path)
    
    def scan_batch(
        self,
        target: str,
        options: ScanOptions,
        batch_size: int = 50,
        batch_index: int = 0
    ) -> ScanResult:
        """
        批次扫描，返回指定批次的结果
        
        Args:
            target: 扫描目标路径
            options: 扫描选项
            batch_size: 每批次文件数量
            batch_index: 批次索引（从0开始）
            
        Returns:
            ScanResult: 该批次的扫描结果
        """
        # 验证目标路径
        is_valid, error_msg = self._path_validator.validate(target)
        if not is_valid:
            raise ValueError(f"无效的扫描目标: {error_msg}")
        
        # 初始化进度管理器
        self._progress_manager = ScanProgress(
            on_progress=self._progress_callback,
            timeout=self._timeout
        )
        
        self._cancelled = False
        
        try:
            # 开始扫描
            self._progress_manager.start()
            
            # 检查WizTree路径
            if not self._wiztree_path or not os.path.isfile(self._wiztree_path):
                raise FileNotFoundError("WizTree可执行文件不存在")
            
            # 准备扫描命令
            cmd = self._build_command(target, options)
            
            # 创建临时CSV文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._csv_path = os.path.join(
                tempfile.gettempdir(), f"wiztree_batch_{timestamp}.csv"
            )
            
            # 执行扫描
            scan_start_time = datetime.now()
            self._execute_scan(cmd, self._csv_path)
            
            # 检查是否被取消
            if self._cancelled:
                raise InterruptedError("扫描被取消")
            
            # 使用批次解析
            batch_files, total_files = self._parse_csv_batch(
                self._csv_path, batch_size, batch_index
            )
            
            # 计算扫描时长
            scan_duration = (datetime.now() - scan_start_time).total_seconds()
            
            # 构建扫描结果
            result = self._build_batch_scan_result(
                target, batch_files, total_files, batch_size, batch_index,
                scan_start_time, scan_duration, options
            )
            
            # 完成扫描
            self._progress_manager.complete(result)
            
            return result
            
        except Exception as e:
            if self._progress_manager:
                self._progress_manager.fail(e)
            raise
        finally:
            # 清理临时文件
            if self._csv_path and os.path.exists(self._csv_path):
                try:
                    os.remove(self._csv_path)
                except OSError:
                    logger.debug("Failed to remove temp CSV: %s", self._csv_path)
    
    def scan_streaming(
        self,
        target: str,
        options: ScanOptions
    ) -> Generator[FileInfo, None, None]:
        """
        流式扫描，逐个返回文件信息（生成器）
        
        Args:
            target: 扫描目标路径
            options: 扫描选项
            
        Yields:
            FileInfo: 文件信息
        """
        # 验证目标路径
        is_valid, error_msg = self._path_validator.validate(target)
        if not is_valid:
            raise ValueError(f"无效的扫描目标: {error_msg}")
        
        # 初始化进度管理器
        self._progress_manager = ScanProgress(
            on_progress=self._progress_callback,
            timeout=self._timeout
        )
        
        self._cancelled = False
        
        try:
            # 开始扫描
            self._progress_manager.start()
            
            # 检查WizTree路径
            if not self._wiztree_path or not os.path.isfile(self._wiztree_path):
                raise FileNotFoundError("WizTree可执行文件不存在")
            
            # 准备扫描命令
            cmd = self._build_command(target, options)
            
            # 创建临时CSV文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._csv_path = os.path.join(
                tempfile.gettempdir(), f"wiztree_stream_{timestamp}.csv"
            )
            
            # 执行扫描
            self._execute_scan(cmd, self._csv_path)
            
            # 检查是否被取消
            if self._cancelled:
                raise InterruptedError("扫描被取消")
            
            # 流式解析CSV
            file_count = 0
            for file_info in self._parse_csv_streaming(self._csv_path):
                file_count += 1
                
                # 更新进度
                if self._progress_manager and file_count % 100 == 0:
                    self._progress_manager.update_progress(
                        progress=0.5,  # CSV解析阶段
                        message=f"已解析 {file_count} 个文件",
                        files_scanned=file_count
                    )
                
                yield file_info
            
            # 完成扫描
            self._progress_manager.complete()
            
        except Exception as e:
            if self._progress_manager:
                self._progress_manager.fail(e)
            raise
        finally:
            # 清理临时文件
            if self._csv_path and os.path.exists(self._csv_path):
                try:
                    os.remove(self._csv_path)
                except OSError:
                    logger.debug("Failed to remove temp CSV: %s", self._csv_path)
    
    def _parse_csv_batch(
        self,
        csv_path: str,
        batch_size: int,
        batch_index: int
    ) -> Tuple[List[FileInfo], int]:
        """
        解析CSV文件的指定批次
        
        Args:
            csv_path: CSV文件路径
            batch_size: 每批次文件数量
            batch_index: 批次索引
            
        Returns:
            Tuple[List[FileInfo], int]: (批次文件列表, 总文件数)
        """
        # 计算跳过的行数
        skip_count = batch_index * batch_size
        collect_start = skip_count
        collect_end = skip_count + batch_size
        
        batch_files = []
        total_files = 0
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                reader = csv.reader(f)
                
                # 跳过标题行
                header = next(reader, None)
                if not header:
                    return [], 0
                
                for row_num, row in enumerate(reader, start=2):
                    # 检查是否被取消
                    if self._cancelled:
                        break
                    
                    # 检查列数
                    if len(row) < 6:
                        continue
                    
                    try:
                        # 快速验证是否为有效文件（不创建FileInfo）
                        file_name = row[0].strip()
                        if file_name.endswith('\\'):
                            continue
                        try:
                            size_bytes = int(row[1].strip())
                        except (ValueError, IndexError):
                            continue
                        if size_bytes <= 0:
                            continue
                        
                        # 这是一个有效文件
                        current_file_index = total_files
                        total_files += 1
                        
                        # 只在当前批次范围内创建FileInfo对象
                        if collect_start <= current_file_index < collect_end:
                            file_info = self._parse_csv_row(row, row_num)
                            if file_info:
                                batch_files.append(file_info)
                                
                                # 更新进度
                                if self._progress_manager and total_files % 100 == 0:
                                    self._progress_manager.update_progress(
                                        progress=0.5,
                                        message=f"已处理 {total_files} 个文件",
                                        files_scanned=total_files
                                    )
                                
                    except Exception:
                        logger.debug("CSV row %d parse error, skipping", row_num, exc_info=True)
                        continue
                        
        except Exception as e:
            raise RuntimeError(f"解析CSV文件失败: {e}")
        
        return batch_files, total_files
    
    def _build_batch_scan_result(
        self,
        target: str,
        batch_files: List[FileInfo],
        total_files: int,
        batch_size: int,
        batch_index: int,
        scan_time: datetime,
        duration: float,
        options: ScanOptions
    ) -> ScanResult:
        """
        构建批次扫描结果
        
        Args:
            target: 扫描目标
            batch_files: 批次文件列表
            total_files: 总文件数
            batch_size: 批次大小
            batch_index: 批次索引
            scan_time: 扫描时间
            duration: 扫描时长
            options: 扫描选项
            
        Returns:
            ScanResult: 批次扫描结果
        """
        # 计算批次统计信息
        batch_total_size = sum(f.size for f in batch_files)
        batch_total_directories = sum(1 for f in batch_files if f.is_directory)
        
        # 构建结果对象
        return ScanResult(
            target_path=Path(target),
            files=batch_files,
            scan_time=scan_time,
            duration_seconds=duration,
            total_files=total_files,  # 总文件数
            total_directories=batch_total_directories,  # 批次目录数
            total_size=batch_total_size,  # 批次总大小
            scan_options=options.to_dict() if options else None,
            errors=[]
        )
    
    def get_total_files_count(self, target: str, options: ScanOptions) -> int:
        """
        获取总文件数量（不加载所有文件到内存）
        
        Args:
            target: 扫描目标路径
            options: 扫描选项
            
        Returns:
            int: 总文件数量
        """
        # 验证目标路径
        is_valid, error_msg = self._path_validator.validate(target)
        if not is_valid:
            raise ValueError(f"无效的扫描目标: {error_msg}")
        
        # 检查WizTree路径
        if not self._wiztree_path or not os.path.isfile(self._wiztree_path):
            raise FileNotFoundError("WizTree可执行文件不存在")
        
        # 准备扫描命令
        cmd = self._build_command(target, options)
        
        # 创建临时CSV文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._csv_path = os.path.join(
            tempfile.gettempdir(), f"wiztree_count_{timestamp}.csv"
        )
        
        try:
            # 执行扫描
            self._execute_scan(cmd, self._csv_path)
            
            # 计算文件数量
            total_files = 0
            try:
                with open(self._csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                    reader = csv.reader(f)
                    
                    # 跳过标题行
                    header = next(reader, None)
                    if not header:
                        return 0
                    
                    for row_num, row in enumerate(reader, start=2):
                        # 检查列数
                        if len(row) < 6:
                            continue
                        
                        try:
                            # 解析文件名
                            file_name = row[0].strip()
                            
                            # 跳过目录
                            if file_name.endswith('\\'):
                                continue
                            
                            # 解析文件大小
                            try:
                                size_bytes = int(row[1].strip())
                            except (ValueError, IndexError):
                                continue
                            
                            # 跳过大小为0的文件
                            if size_bytes <= 0:
                                continue
                            
                            total_files += 1
                            
                        except Exception:
                            continue
                            
            except Exception as e:
                raise RuntimeError(f"解析CSV文件失败: {e}")
            
            return total_files
            
        finally:
            # 清理临时文件
            if self._csv_path and os.path.exists(self._csv_path):
                try:
                    os.remove(self._csv_path)
                except OSError:
                    logger.debug("Failed to remove temp CSV: %s", self._csv_path)
    
    def get_batch_info(
        self,
        target: str,
        options: ScanOptions,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        获取批次信息
        
        Args:
            target: 扫描目标路径
            options: 扫描选项
            batch_size: 批次大小
            
        Returns:
            Dict[str, Any]: 批次信息
        """
        total_files = self.get_total_files_count(target, options)
        total_batches = (total_files + batch_size - 1) // batch_size if total_files > 0 else 0
        
        return {
            'total_files': total_files,
            'batch_size': batch_size,
            'total_batches': total_batches,
            'last_batch_size': total_files % batch_size if total_files % batch_size != 0 else batch_size
        }
    
    def clear_cache(self):
        """清除批次缓存"""
        self._batch_cache.clear()
        self._total_files_cache = None