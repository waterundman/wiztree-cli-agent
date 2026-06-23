import sqlite3
import json
import os
import shutil
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Callable, TypeVar
from pathlib import Path
from contextlib import contextmanager

T = TypeVar('T')


def _detect_user() -> str:
    """Detect current OS user, fallback to 'unknown'."""
    try:
        return os.getlogin() or "unknown"
    except Exception:
        try:
            return os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"
        except Exception:
            return "unknown"


class AuditLogger:
    """审计日志管理器 - SQLite持久化删除记录"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化审计日志管理器
        
        Args:
            db_path: 数据库文件路径，默认为当前目录下的audit.db
        """
        if db_path is None:
            db_path = os.path.join(os.getcwd(), "audit.db")
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 设置 PRAGMA 以提高并发性能
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            
            # 创建删除记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deletion_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER,
                    file_type TEXT,
                    parent_directory TEXT,
                    deletion_status TEXT NOT NULL,
                    error_message TEXT,
                    session_id TEXT,
                    metadata TEXT
                )
            ''')
            
            # 创建操作记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    description TEXT,
                    file_count INTEGER,
                    total_size INTEGER,
                    status TEXT NOT NULL,
                    details TEXT
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_deletion_timestamp 
                ON deletion_records(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_deletion_status 
                ON deletion_records(deletion_status)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_operation_timestamp 
                ON operation_logs(timestamp)
            ''')
            
            # ------------------------------------------------------------------
            # Stage 5 (v1.2.0): 统一审计日志 + 回收站表
            # - audit_log: Stage 5 统一的操作历史表（list_recent / restore / get_stats）
            # - trash:     软删除回收站（restore 时按 original_path 找回）
            # ------------------------------------------------------------------
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target_path TEXT,
                    status TEXT NOT NULL DEFAULT 'success',
                    metadata TEXT,
                    user TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_log(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_audit_action_type
                ON audit_log(action_type)
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trash (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_path TEXT NOT NULL,
                    deleted_path TEXT NOT NULL,
                    deleted_at TEXT NOT NULL,
                    size INTEGER
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_trash_original
                ON trash(original_path)
            ''')
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接上下文管理器"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 返回字典格式结果
        try:
            yield conn
        finally:
            conn.close()
    
    def _execute_with_retry(self, operation: Callable[..., T], max_retries: int = 3, base_delay: float = 0.1) -> T:
        """
        执行数据库操作，遇到 database locked 错误时指数退避重试
        
        Args:
            operation: 要执行的数据库操作函数
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
            
        Returns:
            操作结果
            
        Raises:
            sqlite3.OperationalError: 超过最大重试次数后仍然失败
        """
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return operation()
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries:
                    last_error = e
                    delay = base_delay * (2 ** attempt)  # 指数退避
                    time.sleep(delay)
                else:
                    raise
        raise last_error  # type: ignore
    
    def log_deletion(self, file_path: str, file_name: str, file_size: Optional[int] = None,
                    file_type: Optional[str] = None, parent_directory: Optional[str] = None,
                    deletion_status: str = "success", error_message: Optional[str] = None,
                    session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        记录文件删除操作
        
        Args:
            file_path: 文件完整路径
            file_name: 文件名
            file_size: 文件大小（字节）
            file_type: 文件类型
            parent_directory: 父目录
            deletion_status: 删除状态（success/failed/cancelled）
            error_message: 错误信息
            session_id: 会话ID
            metadata: 额外元数据
            
        Returns:
            记录ID
        """
        timestamp = datetime.now().isoformat()
        metadata_json = json.dumps(metadata) if metadata else None
        
        def _insert():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO deletion_records 
                    (timestamp, file_path, file_name, file_size, file_type, 
                     parent_directory, deletion_status, error_message, session_id, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (timestamp, file_path, file_name, file_size, file_type,
                      parent_directory, deletion_status, error_message, session_id, metadata_json))
                
                conn.commit()
                return cursor.lastrowid
        
        return self._execute_with_retry(_insert)
    
    def log_operation(self, operation_type: str, description: str, 
                     file_count: int = 0, total_size: int = 0,
                     status: str = "success", details: Optional[Dict[str, Any]] = None) -> int:
        """
        记录操作日志
        
        Args:
            operation_type: 操作类型
            description: 操作描述
            file_count: 文件数量
            total_size: 总大小
            status: 操作状态
            details: 详细信息
            
        Returns:
            记录ID
        """
        timestamp = datetime.now().isoformat()
        details_json = json.dumps(details) if details else None
        
        def _insert():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO operation_logs 
                    (timestamp, operation_type, description, file_count, total_size, status, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (timestamp, operation_type, description, file_count, total_size, status, details_json))
                
                conn.commit()
                return cursor.lastrowid
        
        return self._execute_with_retry(_insert)
    
    def query_deletions(self, start_date: Optional[str] = None, end_date: Optional[str] = None,
                       status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        查询删除记录
        
        Args:
            start_date: 开始日期（ISO格式）
            end_date: 结束日期（ISO格式）
            status: 删除状态
            limit: 返回记录数限制
            
        Returns:
            删除记录列表
        """
        query = "SELECT * FROM deletion_records WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        if status:
            query += " AND deletion_status = ?"
            params.append(status)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                record = dict(row)
                if record.get('metadata'):
                    record['metadata'] = json.loads(record['metadata'])
                results.append(record)
            
            return results
    
    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        获取删除统计信息
        
        Args:
            days: 统计天数
            
        Returns:
            统计信息字典
        """
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = start_date.replace(day=start_date.day - days)
        start_date_str = start_date.isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 总删除数
            cursor.execute('''
                SELECT COUNT(*) as total_count,
                       SUM(file_size) as total_size,
                       COUNT(CASE WHEN deletion_status = 'success' THEN 1 END) as success_count,
                       COUNT(CASE WHEN deletion_status = 'failed' THEN 1 END) as failed_count
                FROM deletion_records 
                WHERE timestamp >= ?
            ''', (start_date_str,))
            
            stats = dict(cursor.fetchone())
            
            # 按文件类型统计
            cursor.execute('''
                SELECT file_type, COUNT(*) as count, SUM(file_size) as size
                FROM deletion_records 
                WHERE timestamp >= ? AND file_type IS NOT NULL
                GROUP BY file_type
                ORDER BY count DESC
                LIMIT 10
            ''', (start_date_str,))
            
            stats['by_file_type'] = [dict(row) for row in cursor.fetchall()]
            
            # 按日期统计
            cursor.execute('''
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM deletion_records 
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            ''', (start_date_str,))
            
            stats['by_date'] = [dict(row) for row in cursor.fetchall()]
            
            return stats
    
    def export_to_json(self, output_path: str, start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> bool:
        """
        导出删除记录到JSON文件
        
        Args:
            output_path: 输出文件路径
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            是否成功导出
        """
        try:
            records = self.query_deletions(start_date, end_date, limit=10000)
            
            export_data = {
                "export_time": datetime.now().isoformat(),
                "record_count": len(records),
                "records": records
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"导出失败: {e}")
            return False
    
    def export_to_csv(self, output_path: str, start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> bool:
        """
        导出删除记录到CSV文件
        
        Args:
            output_path: 输出文件路径
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            是否成功导出
        """
        import csv
        
        try:
            records = self.query_deletions(start_date, end_date, limit=10000)
            
            if not records:
                return False
            
            # 获取所有字段名
            fieldnames = records[0].keys()
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for record in records:
                    # 处理metadata字段
                    if 'metadata' in record and isinstance(record['metadata'], dict):
                        record['metadata'] = json.dumps(record['metadata'])
                    writer.writerow(record)
            
            return True
        except Exception as e:
            print(f"导出失败: {e}")
            return False
    
    def clear_old_records(self, days: int = 90) -> int:
        """
        清理旧记录
        
        Args:
            days: 保留天数
            
        Returns:
            删除的记录数
        """
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)
        cutoff_date_str = cutoff_date.isoformat()
        
        def _clear():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 删除旧记录
                cursor.execute('''
                    DELETE FROM deletion_records 
                    WHERE timestamp < ?
                ''', (cutoff_date_str,))
                
                deleted_count = cursor.rowcount
                
                # 删除旧操作日志
                cursor.execute('''
                    DELETE FROM operation_logs 
                    WHERE timestamp < ?
                ''', (cutoff_date_str,))
                
                conn.commit()
                
                return deleted_count
        
        return self._execute_with_retry(_clear)
    
    def get_recent_operations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取最近的操作记录
        
        Args:
            limit: 返回记录数
            
        Returns:
            操作记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM operation_logs 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            results = []
            for row in cursor.fetchall():
                record = dict(row)
                if record.get('details'):
                    record['details'] = json.loads(record['details'])
                results.append(record)
            
            return results
    
    # ==================================================================
    # Stage 5 (v1.2.0): 统一审计日志 + 还原 API
    # 
    # 新增表:
    #   - audit_log(id, timestamp, action_type, target_path, status, metadata, user)
    #   - trash(id, original_path, deleted_path, deleted_at, size)
    # 
    # 新增 API:
    #   - log()           : 写一条审计记录（向 audit_log）
    #   - delete()        : 删除一条审计记录
    #   - list_recent()   : 查询最近 N 条（可按 action_type 过滤）
    #   - restore()       : 还原指定 ID 的操作（file_delete / file_move）
    #   - get_stats()     : 总览统计
    #   - record_trash()  : 在 trash 表登记一个软删除条目（restore 用）
    #   - list_trash()    : 列出 trash 中的条目（调试 / UI 用）
    # 
    # 注意：保留所有 v1.1.0 现有方法（log_deletion / log_operation / 
    #       query_deletions / get_statistics / export_to_json / csv / 
    #       clear_old_records / get_recent_operations）以不破坏 296 回归。
    # ==================================================================
    
    def log(
        self,
        action_type: str,
        target_path: Optional[str] = None,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
        user: Optional[str] = None,
    ) -> int:
        """
        写一条审计记录到 ``audit_log`` 表（Stage 5 新表）。
        
        Args:
            action_type: 操作类型（如 ``file_delete`` / ``file_move`` / ``scan`` / ``restore``）
            target_path: 操作目标路径
            status:      操作状态，默认 ``success``
            metadata:    额外元数据 dict（会被 json.dumps 持久化）
            user:        操作用户，默认自动探测当前 OS 用户
        
        Returns:
            新插入记录的 id
        """
        timestamp = datetime.now().isoformat()
        metadata_json = json.dumps(metadata) if metadata else None
        user_str = user if user else _detect_user()
        
        def _insert():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO audit_log
                        (timestamp, action_type, target_path, status, metadata, user)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (timestamp, action_type, target_path, status, metadata_json, user_str),
                )
                conn.commit()
                return int(cursor.lastrowid or 0)
        
        return self._execute_with_retry(_insert)
    
    def delete(self, action_id: int) -> bool:
        """
        根据 ID 删除 ``audit_log`` 中的一条记录。
        
        Returns:
            是否成功删除（id 不存在时返回 False）
        """
        def _delete():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM audit_log WHERE id = ?",
                    (action_id,),
                )
                conn.commit()
                return cursor.rowcount > 0
        
        return self._execute_with_retry(_delete)
    
    def list_recent(
        self,
        limit: int = 50,
        action_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取最近 N 条审计记录（按 timestamp DESC 排序）。
        
        Args:
            limit:       返回记录上限
            action_type: 按 action_type 过滤；None 表示不过滤
        
        Returns:
            list of dict，每个 dict 包含字段：
                id, timestamp, action_type, target_path, status, metadata, user
            ``metadata`` 字段会被自动 json.loads（解析失败时为 None）。
        """
        query = (
            "SELECT id, timestamp, action_type, target_path, status, metadata, user "
            "FROM audit_log WHERE 1=1"
        )
        params: List[Any] = []
        if action_type:
            query += " AND action_type = ?"
            params.append(action_type)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                record = dict(row)
                meta_str = record.get("metadata")
                if meta_str:
                    try:
                        record["metadata"] = json.loads(meta_str)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        record["metadata"] = None
                else:
                    record["metadata"] = None
                results.append(record)
            return results
    
    def record_trash(
        self,
        original_path: str,
        deleted_path: str,
        size: Optional[int] = None,
        deleted_at: Optional[str] = None,
    ) -> int:
        """
        在 ``trash`` 表登记一个软删除条目（``restore()`` 据此还原）。
        
        Args:
            original_path: 文件原路径
            deleted_path:  回收站中的实际路径
            size:          文件大小（字节）
            deleted_at:    ISO 时间戳，默认 ``datetime.now().isoformat()``
        
        Returns:
            新插入的 id
        """
        if deleted_at is None:
            deleted_at = datetime.now().isoformat()
        
        def _insert():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO trash (original_path, deleted_path, deleted_at, size)
                    VALUES (?, ?, ?, ?)
                    ''',
                    (original_path, deleted_path, deleted_at, size),
                )
                conn.commit()
                return int(cursor.lastrowid or 0)
        
        return self._execute_with_retry(_insert)
    
    def list_trash(
        self,
        original_path: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        列出 trash 表中的条目（按 deleted_at DESC）。
        
        Args:
            original_path: 按原路径过滤；None 不过滤
            limit:         返回上限
        """
        query = "SELECT id, original_path, deleted_path, deleted_at, size FROM trash WHERE 1=1"
        params: List[Any] = []
        if original_path:
            query += " AND original_path = ?"
            params.append(original_path)
        query += " ORDER BY deleted_at DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
    
    def restore(self, action_id: int) -> bool:
        """
        还原 ``action_id`` 指定的操作。
        
        - ``file_delete``: 从 ``trash`` 表找回 deleted_path，``shutil.copy2`` 回 ``target_path``
        - ``file_move``:   从 metadata.original_path 读取原位置，``shutil.move`` 回原路径
        - ``scan`` / 其他: 返回 False
        
        成功时还会写一条新的 ``action_type='restore'`` 审计记录。
        
        Returns:
            是否成功还原
        """
        def _restore():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, action_type, target_path, status, metadata "
                    "FROM audit_log WHERE id = ?",
                    (action_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return False
                record = dict(row)
                action_type = record.get("action_type")
                target_path = record.get("target_path")
                meta_str = record.get("metadata")
                
                meta: Dict[str, Any] = {}
                if meta_str:
                    try:
                        meta = json.loads(meta_str)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        meta = {}
                
                success = False
                try:
                    if action_type == "file_delete":
                        success = self._restore_file_delete(target_path, meta)
                    elif action_type == "file_move":
                        success = self._restore_file_move(target_path, meta)
                    else:
                        # scan / restore / 未知类型 → 不支持还原
                        success = False
                except Exception:
                    # 任何 IO 异常都视为还原失败
                    success = False
                
                if success:
                    # 写一条新的 audit log 记录（spec: "写入新的 audit log 记录 restore 操作"）
                    timestamp = datetime.now().isoformat()
                    meta_out = json.dumps({"restored_from": action_id, "original": meta})
                    cursor.execute(
                        '''
                        INSERT INTO audit_log
                            (timestamp, action_type, target_path, status, metadata, user)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            timestamp,
                            "restore",
                            target_path,
                            "success",
                            meta_out,
                            _detect_user(),
                        ),
                    )
                
                conn.commit()
                return success
        
        return self._execute_with_retry(_restore)
    
    def _restore_file_delete(
        self,
        target_path: Optional[str],
        meta: Dict[str, Any],
    ) -> bool:
        """从 trash 表中根据 target_path 找回 deleted_path 并复制回去。"""
        if not target_path:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT id, deleted_path FROM trash
                WHERE original_path = ?
                ORDER BY deleted_at DESC
                LIMIT 1
                ''',
                (target_path,),
            )
            row = cursor.fetchone()
            if row is None:
                return False
            deleted_path = row["deleted_path"]
        if not deleted_path or not os.path.exists(deleted_path):
            return False
        # 确保目标目录存在
        target_dir = os.path.dirname(target_path)
        if target_dir:
            try:
                os.makedirs(target_dir, exist_ok=True)
            except OSError:
                return False
        try:
            shutil.copy2(deleted_path, target_path)
        except OSError:
            return False
        return True
    
    def _restore_file_move(
        self,
        target_path: Optional[str],
        meta: Dict[str, Any],
    ) -> bool:
        """从 metadata.original_path 读取原位置，将 target_path 移回。"""
        if not target_path or not os.path.exists(target_path):
            return False
        original_path = (
            meta.get("original_path")
            or meta.get("source_path")
            or meta.get("from_path")
        )
        if not original_path:
            return False
        original_dir = os.path.dirname(original_path)
        if original_dir:
            try:
                os.makedirs(original_dir, exist_ok=True)
            except OSError:
                return False
        try:
            shutil.move(target_path, original_path)
        except OSError:
            return False
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取审计总览统计。
        
        Returns:
            dict with keys:
                - total_actions: int
                - by_type:       Dict[action_type, count]
                - by_status:     Dict[status, count]
                - recent_24h:    int  (24h 内的记录数)
        """
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # total
            cursor.execute("SELECT COUNT(*) AS n FROM audit_log")
            total_row = cursor.fetchone()
            total = int(total_row["n"] if total_row else 0)
            
            # by_type
            cursor.execute(
                "SELECT action_type, COUNT(*) AS n FROM audit_log GROUP BY action_type"
            )
            by_type = {r["action_type"]: int(r["n"]) for r in cursor.fetchall()}
            
            # by_status
            cursor.execute(
                "SELECT status, COUNT(*) AS n FROM audit_log GROUP BY status"
            )
            by_status = {r["status"]: int(r["n"]) for r in cursor.fetchall()}
            
            # recent_24h
            cursor.execute(
                "SELECT COUNT(*) AS n FROM audit_log WHERE timestamp >= ?",
                (cutoff,),
            )
            recent_row = cursor.fetchone()
            recent_24h = int(recent_row["n"] if recent_row else 0)
            
            return {
                "total_actions": total,
                "by_type": by_type,
                "by_status": by_status,
                "recent_24h": recent_24h,
            }