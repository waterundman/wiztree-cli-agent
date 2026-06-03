"""
AuditLogger 扩展 API 测试 (v1.2.0 / Stage 5)
============================================

覆盖：
    1. ``log()``  写入 audit_log 表
    2. ``delete()``  按 id 删除
    3. ``list_recent()``  按 timestamp DESC 排序
    4. ``list_recent(action_type=...)``  按类型过滤
    5. ``record_trash()``  / ``list_trash()``
    6. ``restore(file_delete)``  从 trash 复制回去
    7. ``restore(file_move)``    从 metadata.original_path 移回
    8. ``restore()``  写入新的 'restore' 审计记录
    9. ``restore()``  对 scan / 不存在 id 返回 False
    10. ``get_stats()``  返回 4 个键
    11. v1.1.0 旧方法（log_deletion, log_operation, query_deletions 等）不被破坏

策略：每次测试用 ``tmp_path`` 下的临时 SQLite 文件（不污染 ``audit.db``）。
"""
from __future__ import annotations

import os
import json
import sys
import sqlite3
import shutil
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.safety.audit_logger import AuditLogger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def db_path(tmp_path):
    """每个测试一个全新的临时 audit.db"""
    return str(tmp_path / "audit.db")


@pytest.fixture
def al(db_path):
    return AuditLogger(db_path)


# ---------------------------------------------------------------------------
# Test: 初始化 + 新表
# ---------------------------------------------------------------------------
class TestSchema:
    def test_init_creates_new_tables(self, al, db_path):
        """audit_log + trash 表存在（兼容旧 deletion_records / operation_logs）"""
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        conn.close()
        assert "audit_log" in tables
        assert "trash" in tables
        # 旧表也要保留（v1.1.0 兼容）
        assert "deletion_records" in tables
        assert "operation_logs" in tables
    
    def test_init_idempotent(self, db_path):
        """重复初始化不会报错"""
        AuditLogger(db_path)
        AuditLogger(db_path)
        AuditLogger(db_path)
        # 连接 + 简单查询确认 DB 仍然可用
        al = AuditLogger(db_path)
        al.log("scan", "/foo")
        assert len(al.list_recent()) == 1


# ---------------------------------------------------------------------------
# Test: log / delete / list_recent
# ---------------------------------------------------------------------------
class TestLog:
    def test_log_basic(self, al):
        aid = al.log("file_delete", "/a/b.txt")
        assert isinstance(aid, int) and aid > 0
    
    def test_log_with_metadata_is_json(self, al):
        al.log("file_move", "/x", metadata={"original_path": "/y", "size": 1024})
        recs = al.list_recent()
        assert len(recs) == 1
        meta = recs[0]["metadata"]
        assert isinstance(meta, dict)
        assert meta["original_path"] == "/y"
        assert meta["size"] == 1024
    
    def test_log_default_user_is_string(self, al):
        al.log("scan", "/disk")
        recs = al.list_recent()
        assert isinstance(recs[0]["user"], str)
        assert recs[0]["user"]  # not empty
    
    def test_log_explicit_user(self, al):
        al.log("scan", "/disk", user="alice")
        assert al.list_recent()[0]["user"] == "alice"
    
    def test_log_default_status(self, al):
        al.log("scan", "/disk")
        assert al.list_recent()[0]["status"] == "success"
    
    def test_log_custom_status(self, al):
        al.log("scan", "/disk", status="failed")
        assert al.list_recent()[0]["status"] == "failed"


class TestDelete:
    def test_delete_existing(self, al):
        aid = al.log("file_delete", "/a")
        assert al.delete(aid) is True
        assert al.list_recent() == []
    
    def test_delete_nonexistent_returns_false(self, al):
        assert al.delete(99999) is False
    
    def test_delete_one_keeps_others(self, al):
        a1 = al.log("scan", "/a")
        a2 = al.log("scan", "/b")
        al.delete(a1)
        remaining = al.list_recent()
        assert len(remaining) == 1
        assert remaining[0]["id"] == a2


class TestListRecent:
    def test_returns_expected_fields(self, al):
        al.log("file_delete", "/a.txt", metadata={"k": "v"})
        recs = al.list_recent()
        assert len(recs) == 1
        keys = set(recs[0].keys())
        for f in ("id", "timestamp", "action_type", "target_path",
                  "status", "metadata", "user"):
            assert f in keys, f"missing field: {f}"
    
    def test_order_desc_by_timestamp(self, al):
        a1 = al.log("scan", "/first")
        a2 = al.log("scan", "/second")
        a3 = al.log("scan", "/third")
        recs = al.list_recent()
        ids = [r["id"] for r in recs]
        assert ids == [a3, a2, a1]
    
    def test_limit(self, al):
        for i in range(10):
            al.log("scan", f"/disk{i}")
        recs = al.list_recent(limit=3)
        assert len(recs) == 3
    
    def test_filter_by_action_type(self, al):
        al.log("file_delete", "/a")
        al.log("file_move", "/b")
        al.log("scan", "/c")
        recs = al.list_recent(action_type="file_delete")
        assert len(recs) == 1
        assert recs[0]["action_type"] == "file_delete"
    
    def test_filter_unknown_type_returns_empty(self, al):
        al.log("scan", "/c")
        assert al.list_recent(action_type="nonexistent") == []
    
    def test_metadata_none_when_absent(self, al):
        al.log("scan", "/c")
        assert al.list_recent()[0]["metadata"] is None
    
    def test_metadata_corrupt_json_does_not_raise(self, al, db_path):
        """手动写入坏 JSON，list_recent 应安全降级为 None（不抛异常）"""
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO audit_log (timestamp, action_type, target_path, status, metadata, user)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("2020-01-01T00:00:00", "scan", "/x", "success", "NOT_JSON", "test"),
        )
        conn.commit()
        conn.close()
        recs = al.list_recent()
        assert recs[0]["metadata"] is None


# ---------------------------------------------------------------------------
# Test: trash / restore
# ---------------------------------------------------------------------------
class TestTrash:
    def test_record_trash_returns_id(self, al):
        tid = al.record_trash("/orig", "/trash/orig", size=100)
        assert tid > 0
    
    def test_list_trash_returns_entries(self, al):
        al.record_trash("/a", "/trash/a", size=10)
        al.record_trash("/b", "/trash/b", size=20)
        rows = al.list_trash()
        assert len(rows) == 2
        paths = {r["original_path"] for r in rows}
        assert paths == {"/a", "/b"}
    
    def test_list_trash_filter_by_original(self, al):
        al.record_trash("/a", "/trash/a")
        al.record_trash("/b", "/trash/b")
        rows = al.list_trash(original_path="/a")
        assert len(rows) == 1
        assert rows[0]["original_path"] == "/a"


class TestRestore:
    def test_restore_nonexistent_id(self, al):
        assert al.restore(99999) is False
    
    def test_restore_scan_returns_false(self, al):
        aid = al.log("scan", "/disk")
        assert al.restore(aid) is False
    
    def test_restore_unknown_type_returns_false(self, al):
        aid = al.log("weird_type", "/x")
        assert al.restore(aid) is False
    
    def test_restore_file_delete_success(self, al, tmp_path):
        """trash 中有 deleted_path，原路径不存在 → restore 后文件应被还原"""
        # 准备
        trash = tmp_path / "trash_dir" / "a.txt"
        trash.parent.mkdir(parents=True, exist_ok=True)
        trash.write_text("hello", encoding="utf-8")
        orig = tmp_path / "orig_dir" / "a.txt"
        # orig 不存在
        
        aid = al.log("file_delete", str(orig))
        al.record_trash(str(orig), str(trash), size=5)
        
        assert al.restore(aid) is True
        assert orig.exists()
        assert orig.read_text(encoding="utf-8") == "hello"
    
    def test_restore_file_delete_missing_trash_entry(self, al, tmp_path):
        """没有 trash 记录 → 还原失败"""
        orig = tmp_path / "x" / "a.txt"
        aid = al.log("file_delete", str(orig))
        assert al.restore(aid) is False
    
    def test_restore_file_delete_trash_file_gone(self, al, tmp_path):
        """trash 路径上的文件已不存在 → 还原失败"""
        orig = tmp_path / "x" / "a.txt"
        trash = tmp_path / "trash" / "a.txt"  # never created
        aid = al.log("file_delete", str(orig))
        al.record_trash(str(orig), str(trash), size=5)
        assert al.restore(aid) is False
    
    def test_restore_file_move_success(self, al, tmp_path):
        """file_move 还原：dst 存在 + metadata.original_path → 移回原位置"""
        src = tmp_path / "src" / "a.txt"
        dst = tmp_path / "dst" / "a.txt"
        src.parent.mkdir(parents=True, exist_ok=True)
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("data", encoding="utf-8")
        # 模拟"已移动"——把文件放到 dst
        shutil.move(str(src), str(dst))
        
        aid = al.log("file_move", str(dst), metadata={"original_path": str(src)})
        assert al.restore(aid) is True
        # 文件应回到 src
        assert src.exists()
        assert not dst.exists()
        assert src.read_text(encoding="utf-8") == "data"
    
    def test_restore_file_move_missing_metadata(self, al, tmp_path):
        """file_move 没有 metadata.original_path → 还原失败"""
        dst = tmp_path / "dst" / "a.txt"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("data", encoding="utf-8")
        aid = al.log("file_move", str(dst))  # no metadata
        assert al.restore(aid) is False
    
    def test_restore_writes_audit_log(self, al, tmp_path):
        """成功 restore 后应写一条 action_type='restore' 记录"""
        trash = tmp_path / "trash" / "x"
        trash.parent.mkdir(parents=True, exist_ok=True)
        trash.write_text("x")
        orig = tmp_path / "x"
        aid = al.log("file_delete", str(orig))
        al.record_trash(str(orig), str(trash))
        assert al.restore(aid) is True
        
        recs = al.list_recent(limit=10)
        restore_recs = [r for r in recs if r["action_type"] == "restore"]
        assert len(restore_recs) == 1
        meta = restore_recs[0]["metadata"]
        assert meta["restored_from"] == aid


# ---------------------------------------------------------------------------
# Test: get_stats
# ---------------------------------------------------------------------------
class TestGetStats:
    def test_empty_stats(self, al):
        s = al.get_stats()
        assert s["total_actions"] == 0
        assert s["by_type"] == {}
        assert s["by_status"] == {}
        assert s["recent_24h"] == 0
    
    def test_basic_count(self, al):
        al.log("file_delete", "/a")
        al.log("file_delete", "/b")
        al.log("scan", "/disk")
        s = al.get_stats()
        assert s["total_actions"] == 3
        assert s["by_type"]["file_delete"] == 2
        assert s["by_type"]["scan"] == 1
    
    def test_by_status(self, al):
        al.log("scan", "/a", status="success")
        al.log("scan", "/b", status="failed")
        al.log("scan", "/c", status="failed")
        s = al.get_stats()
        assert s["by_status"]["success"] == 1
        assert s["by_status"]["failed"] == 2
    
    def test_recent_24h_excludes_old(self, al, db_path):
        """手工插入 30 天前的记录 → 不计入 recent_24h"""
        # 现在的
        al.log("scan", "/now")
        # 旧的（直接 SQL 注入避免 time.sleep）
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO audit_log (timestamp, action_type, target_path, status, metadata, user)"
            " VALUES (?, 'scan', '/old', 'success', NULL, 'test')",
            ("2020-01-01T00:00:00",),
        )
        conn.commit()
        conn.close()
        s = al.get_stats()
        assert s["total_actions"] == 2
        assert s["recent_24h"] == 1


# ---------------------------------------------------------------------------
# Test: v1.1.0 向后兼容（绝不能破坏）
# ---------------------------------------------------------------------------
class TestBackwardCompat:
    def test_log_deletion_still_works(self, al):
        """v1.1.0 API: log_deletion 仍然返回 id"""
        rid = al.log_deletion(
            file_path="/a/b.txt",
            file_name="b.txt",
            file_size=100,
            file_type="TXT",
            parent_directory="/a",
            deletion_status="success",
        )
        assert rid > 0
    
    def test_log_operation_still_works(self, al):
        rid = al.log_operation("scan", "scanned C:\\", file_count=42, total_size=1024)
        assert rid > 0
    
    def test_query_deletions_still_works(self, al):
        al.log_deletion("/a", "a", 0, None, "/", "success")
        al.log_deletion("/b", "b", 0, None, "/", "success")
        recs = al.query_deletions(limit=10)
        assert len(recs) == 2
    
    def test_query_deletions_with_status_filter(self, al):
        """v1.1.0 API: query_deletions 仍支持 status 过滤"""
        al.log_deletion("/a", "a", 0, None, "/", "success")
        al.log_deletion("/b", "b", 0, None, "/", "failed")
        recs = al.query_deletions(status="failed", limit=10)
        assert len(recs) == 1
        assert recs[0]["file_path"] == "/b"
    
    def test_get_recent_operations_still_works(self, al):
        al.log_operation("scan", "x")
        recs = al.get_recent_operations(limit=5)
        assert len(recs) == 1
    
    def test_old_and_new_tables_coexist(self, al):
        """新旧 API 可以混用，互不干扰"""
        al.log_deletion("/a", "a", 0, None, "/", "success")
        al.log("file_delete", "/a", metadata={"v": 2})
        assert len(al.query_deletions()) == 1
        assert len(al.list_recent()) == 1
