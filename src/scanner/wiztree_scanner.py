import os
import csv
import json
import hashlib
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any, Generator
from datetime import datetime, timedelta

try:
    from ..models.file_info import FileInfo
    from ..models.scan_result import ScanResult
    from .options import ScanOptions
    from .path_validator import PathValidator
    from .scan_progress import ScanProgress, ScanStatus
    from .interface import ScannerInterface
except ImportError:
    from models.file_info import FileInfo
    from models.scan_result import ScanResult
    from scanner.options import ScanOptions
    from scanner.path_validator import PathValidator
    from scanner.scan_progress import ScanProgress, ScanStatus
    from scanner.interface import ScannerInterface


class WizTreeScanner(ScannerInterface):
    """WizTree CLI扫描器"""
    
    def __init__(
        self,
        wiztree_path: Optional[str] = None,
        progress_callback: Optional[callable] = None,
        timeout: Optional[float] = 300
    ):
        """
        初始化WizTree扫描器
        
        Args:
            wiztree_path: WizTree可执行文件路径
            progress_callback: 进度回调函数
            timeout: 超时时间（秒）
        """
        self._wiztree_path = wiztree_path
        self._progress_callback = progress_callback
        self._timeout = timeout
        self._path_validator = PathValidator()
        self._progress_manager: Optional[ScanProgress] = None
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False
    
    def scan(self, target: str, options: ScanOptions) -> ScanResult:
        """
        扫描目标路径
        
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
            csv_path = os.path.join(
                tempfile.gettempdir(), f"wiztree_{timestamp}.csv"
            )
            
            # 执行扫描
            scan_start_time = datetime.now()
            self._execute_scan(cmd, csv_path)
            
            # 检查是否被取消
            if self._cancelled:
                raise InterruptedError("扫描被取消")
            
            # 解析CSV结果
            files = self._parse_csv(csv_path)
            
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
            if 'csv_path' in locals() and os.path.exists(csv_path):
                try:
                    os.remove(csv_path)
                except OSError:
                    pass
    
    def cancel(self):
        """取消扫描"""
        self._cancelled = True
        if self._progress_manager:
            self._progress_manager.cancel()
        
        # 终止WizTree进程
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
    
    def _build_command(self, target: str, options: ScanOptions) -> List[str]:
        """
        构建WizTree命令
        
        Args:
            target: 扫描目标
            options: 扫描选项
            
        Returns:
            List[str]: 命令列表
        """
        cmd = [self._wiztree_path, target]
        
        # 添加排序参数（按大小降序）
        cmd.append('/sortby=1')
        
        # 添加文件夹导出选项
        cmd.append('/exportfolders=0')
        
        # 添加最小大小过滤
        if options.min_size:
            cmd.append(f'/filter={options.min_size}')
        
        # 添加排除模式
        if options.exclude_patterns:
            for pattern in options.exclude_patterns:
                cmd.append(f'/filterexclude={pattern}')
        
        return cmd
    
    def _execute_scan(self, cmd: List[str], csv_path: str):
        """
        执行WizTree扫描
        
        Args:
            cmd: 命令列表
            csv_path: CSV输出路径
        """
        # 添加导出参数
        cmd.append(f'/export={csv_path}')
        
        try:
            # 创建子进程
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # 等待进程完成
            _, stderr = self._process.communicate(timeout=self._timeout)
            
            # 检查返回码
            if self._process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace').strip()
                raise RuntimeError(f"WizTree执行失败 (返回码: {self._process.returncode}): {error_msg}")
            
            # 检查CSV文件是否生成
            if not os.path.exists(csv_path):
                raise RuntimeError(f"CSV文件未生成: {csv_path}")
            
        except subprocess.TimeoutExpired:
            # 超时处理
            if self._process:
                self._process.kill()
            raise TimeoutError(f"扫描超时（超过{self._timeout}秒）")
        except Exception as e:
            raise RuntimeError(f"执行WizTree扫描时出错: {e}")
    
    def _parse_csv(self, csv_path: str) -> List[FileInfo]:
        """
        解析WizTree CSV输出（使用流式解析）
        
        Args:
            csv_path: CSV文件路径
            
        Returns:
            List[FileInfo]: 文件信息列表
        """
        files = list(self._parse_csv_streaming(csv_path))
        
        # 按大小排序
        files.sort(key=lambda x: x.size, reverse=True)
        
        return files
    
    def _parse_csv_streaming(self, csv_path: str) -> Generator[FileInfo, None, None]:
        """
        流式解析WizTree CSV输出（生成器）
        
        Args:
            csv_path: CSV文件路径
            
        Yields:
            FileInfo: 逐行解析的文件信息
        """
        try:
            with open(csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                reader = csv.reader(f)
                
                # 跳过标题行
                header = next(reader, None)
                if not header:
                    return
                
                file_count = 0
                for row_num, row in enumerate(reader, start=2):
                    # 检查是否被取消
                    if self._cancelled:
                        break
                    
                    # 检查列数
                    if len(row) < 6:
                        continue
                    
                    try:
                        # 解析文件信息
                        file_info = self._parse_csv_row(row, row_num)
                        if file_info:
                            file_count += 1
                            yield file_info
                            
                            # 更新进度
                            if self._progress_manager and file_count % 100 == 0:
                                self._progress_manager.update_progress(
                                    progress=0.5,  # CSV解析阶段
                                    message=f"已解析 {file_count} 个文件",
                                    files_scanned=file_count
                                )
                    except Exception:
                        # 跳过解析错误的行
                        continue
                        
        except Exception as e:
            raise RuntimeError(f"解析CSV文件失败: {e}")
    
    def _parse_csv_row(self, row: List[str], row_num: int) -> Optional[FileInfo]:
        """
        解析CSV行
        
        Args:
            row: CSV行数据
            row_num: 行号
            
        Returns:
            Optional[FileInfo]: 文件信息，如果解析失败则返回None
        """
        try:
            # 解析文件名
            file_name = row[0].strip()
            
            # 跳过目录（以反斜杠结尾）
            if file_name.endswith('\\'):
                return None
            
            # 解析文件大小
            try:
                size_bytes = int(row[1].strip())
            except (ValueError, IndexError):
                return None
            
            # 跳过大小为0的文件
            if size_bytes <= 0:
                return None
            
            # 解析修改时间
            modified_str = row[3].strip() if len(row) > 3 else ""
            modified_time = self._parse_datetime(modified_str)
            
            # 构建文件路径
            file_path = Path(file_name)
            
            # 创建FileInfo对象
            return FileInfo(
                path=file_path,
                size=size_bytes,
                modified_time=modified_time,
                created_time=None,  # WizTree不提供创建时间
                is_directory=False,
                extension=file_path.suffix.lower() if file_path.suffix else None,
                depth=file_name.count('\\'),
                parent_path=file_path.parent
            )
            
        except Exception:
            return None
    
    def _parse_datetime(self, datetime_str: str) -> datetime:
        """
        解析日期时间字符串
        
        Args:
            datetime_str: 日期时间字符串
            
        Returns:
            datetime: 解析后的日期时间
        """
        if not datetime_str:
            return datetime.now()
        
        try:
            # 尝试解析常见的日期时间格式
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y/%m/%d %H:%M:%S',
                '%d/%m/%Y %H:%M:%S',
                '%m/%d/%Y %H:%M:%S',
                '%Y-%m-%d',
                '%Y/%m/%d',
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue
            
            # 如果所有格式都失败，返回当前时间
            return datetime.now()
            
        except Exception:
            return datetime.now()
    
    def _build_scan_result(
        self,
        target: str,
        files: List[FileInfo],
        scan_time: datetime,
        duration: float,
        options: ScanOptions
    ) -> ScanResult:
        """
        构建扫描结果
        
        Args:
            target: 扫描目标
            files: 文件列表
            scan_time: 扫描时间
            duration: 扫描时长
            options: 扫描选项
            
        Returns:
            ScanResult: 扫描结果
        """
        # 计算统计信息
        total_files = len(files)
        total_directories = sum(1 for f in files if f.is_directory)
        total_size = sum(f.size for f in files)
        
        # 构建结果对象
        return ScanResult(
            target_path=Path(target),
            files=files,
            scan_time=scan_time,
            duration_seconds=duration,
            total_files=total_files,
            total_directories=total_directories,
            total_size=total_size,
            scan_options=options.to_dict() if options else None,
            errors=[]
        )
    
    def get_supported_options(self) -> List[str]:
        """
        获取支持的选项列表
        
        Returns:
            List[str]: 支持的选项名称列表
        """
        return [
            'max_depth',
            'include_hidden',
            'min_size',
            'exclude_patterns'
        ]
    
    @property
    def is_scanning(self) -> bool:
        """是否正在扫描"""
        return self._progress_manager is not None and self._progress_manager.is_running
    
    @property
    def progress_info(self):
        """获取进度信息"""
        if self._progress_manager:
            return self._progress_manager.progress_info
        return None
    
    def set_wiztree_path(self, path: str):
        """
        设置WizTree路径
        
        Args:
            path: WizTree可执行文件路径
        """
        self._wiztree_path = path
    
    def set_timeout(self, timeout: float):
        """
        设置超时时间
        
        Args:
            timeout: 超时时间（秒）
        """
        self._timeout = timeout

    # ----------------------------------------------------------------
    # Stage 3: 扫描结果缓存
    # ----------------------------------------------------------------

    _CACHE_DIR = os.path.join(os.path.expanduser("~"), ".wiztree-cli-agent")
    _CACHE_FILE = os.path.join(_CACHE_DIR, "scan_cache.json")
    _CACHE_TTL = timedelta(hours=1)

    def scan_with_cache(self, target: str, options: ScanOptions) -> ScanResult:
        """
        带缓存的扫描。相同路径+参数在 TTL 内直接返回缓存。

        Args:
            target: 扫描目标路径
            options: 扫描选项

        Returns:
            ScanResult: 扫描结果
        """
        cache_key = self._get_cache_key(target, options)
        cached = self._load_cache(cache_key)
        if cached is not None:
            if self._progress_callback:
                try:
                    from src.scanner.scan_progress import ProgressInfo, ScanStatus
                    self._progress_callback(ProgressInfo(
                        status=ScanStatus.COMPLETED,
                        progress=1.0,
                        message="返回缓存结果",
                        files_scanned=cached.total_files,
                    ))
                except Exception:
                    pass
            return cached

        result = self.scan(target, options)
        self._save_cache(cache_key, result)
        return result

    def clear_cache(self) -> bool:
        """
        清除扫描缓存文件。

        Returns:
            bool: 是否成功清除
        """
        try:
            if os.path.exists(self._CACHE_FILE):
                os.remove(self._CACHE_FILE)
            return True
        except OSError:
            return False

    def _get_cache_key(self, target: str, options: ScanOptions) -> str:
        """生成缓存键（路径 + 参数的 SHA-256）"""
        raw = json.dumps(
            {"target": os.path.abspath(target), "options": options.to_dict()},
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def _load_cache(self, cache_key: str) -> Optional[ScanResult]:
        """从缓存加载 ScanResult，过期或缺失返回 None"""
        try:
            if not os.path.exists(self._CACHE_FILE):
                return None
            with open(self._CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            entry = data.get(cache_key)
            if not entry:
                return None
            cached_at = datetime.fromisoformat(entry["cached_at"])
            if datetime.now() - cached_at > self._CACHE_TTL:
                return None
            return self._deserialize_scan_result(entry["result"])
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            return None

    def _save_cache(self, cache_key: str, result: ScanResult) -> None:
        """将 ScanResult 保存到缓存文件"""
        try:
            os.makedirs(self._CACHE_DIR, exist_ok=True)
            data: Dict[str, Any] = {}
            if os.path.exists(self._CACHE_FILE):
                try:
                    with open(self._CACHE_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    data = {}
            data[cache_key] = {
                "cached_at": datetime.now().isoformat(),
                "result": self._serialize_scan_result(result),
            }
            with open(self._CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass

    @staticmethod
    def _serialize_scan_result(result: ScanResult) -> Dict[str, Any]:
        """将 ScanResult 序列化为 JSON 兼容字典"""
        return {
            "target_path": str(result.target_path),
            "scan_time": result.scan_time.isoformat(),
            "duration_seconds": result.duration_seconds,
            "total_files": result.total_files,
            "total_directories": result.total_directories,
            "total_size": result.total_size,
            "scan_options": result.scan_options,
            "errors": result.errors,
            "files": [
                {
                    "path": str(f.path),
                    "size": f.size,
                    "modified_time": f.modified_time.isoformat() if f.modified_time else None,
                    "created_time": f.created_time.isoformat() if f.created_time else None,
                    "is_directory": f.is_directory,
                    "extension": f.extension,
                    "depth": f.depth,
                    "parent_path": str(f.parent_path) if f.parent_path else None,
                }
                for f in result.files
            ],
        }

    @staticmethod
    def _deserialize_scan_result(data: Dict[str, Any]) -> ScanResult:
        """从 JSON 字典反序列化 ScanResult"""
        files = []
        for fd in data.get("files", []):
            mt = fd.get("modified_time")
            ct = fd.get("created_time")
            pp = fd.get("parent_path")
            files.append(FileInfo(
                path=Path(fd["path"]),
                size=fd["size"],
                modified_time=datetime.fromisoformat(mt) if mt else datetime.now(),
                created_time=datetime.fromisoformat(ct) if ct else None,
                is_directory=fd.get("is_directory", False),
                extension=fd.get("extension"),
                depth=fd.get("depth", 0),
                parent_path=Path(pp) if pp else None,
            ))
        return ScanResult(
            target_path=Path(data["target_path"]),
            files=files,
            scan_time=datetime.fromisoformat(data["scan_time"]),
            duration_seconds=data["duration_seconds"],
            total_files=data["total_files"],
            total_directories=data["total_directories"],
            total_size=data["total_size"],
            scan_options=data.get("scan_options"),
            errors=data.get("errors", []),
        )