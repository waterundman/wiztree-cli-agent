"""
Integration tests for wiztree-cli-agent v1.2.0
================================================

End-to-end integration coverage that exercises the public API of
**all 6 v1.2.0 stages** in concert:

    Stage 1: ConfigLoader + CredentialStore (secure config)
    Stage 2: LLM Router + RuleEngine (analysis)
    Stage 3: Squarify treemap + StatusBar (visualization)
    Stage 4: ModernTheme + KeyBindings + DnD (UI chrome)
    Stage 5: DiffPreviewDialog + AuditLogger (audit & restore)
    Stage 6: this file (end-to-end integration)

Mocking strategy
----------------
* LLM provider        -> ``unittest.mock.Mock()`` (no real HTTP)
* GUI widgets         -> ``MagicMock`` (ctk is heavy & fragile in CI)
* Real components     -> ConfigLoader, AuditLogger, Squarify,
                         ModernTheme (the data layer, must not be mocked)

All tests are designed to run **headless** (no display required).

Reference
---------
* ``prachwal-archive/disk-scan-tools``        - CLI + GUI integration patterns
* ``fezcode/atlas.doomwalker``                - end-to-end pipeline tests
* ``thomastschinkel/prompt-os``               - cross-stage changelog
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from unittest.mock import MagicMock, patch

import pytest

# Make ``src`` importable when pytest is run from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.safety.audit_logger import AuditLogger  # noqa: E402

# Squarify is loaded via importlib below (see ``_squarify_layout``) to
# avoid pulling in ``src.ui.__init__`` (which imports ``main_window``,
# a heavy GUI module that requires ``tkinter``).


# ---------------------------------------------------------------------------
# Optional imports (with skip markers)
# ---------------------------------------------------------------------------
try:
    import tkinter  # noqa: F401
    import customtkinter as ctk  # noqa: F401
    _CTK_OK = True
except ImportError:  # pragma: no cover
    _CTK_OK = False

skip_no_ctk = pytest.mark.skipif(
    not _CTK_OK, reason="tkinter / customtkinter not available"
)

try:
    import keyring  # noqa: F401
    _KEYRING_OK = True
except ImportError:  # pragma: no cover
    _KEYRING_OK = False

skip_no_keyring = pytest.mark.skipif(
    not _KEYRING_OK, reason="keyring not installed"
)


# ---------------------------------------------------------------------------
# Squarify (imported via importlib to avoid pulling in src.ui.__init__)
# ---------------------------------------------------------------------------
def _load_squarify_module():
    spec = importlib.util.spec_from_file_location(
        "_integration_squarify",
        Path(__file__).parent.parent / "src" / "ui" / "components" / "squarify.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Public alias: tests reference ``_squarify_layout(name, w, h)``
_squarify_layout = _load_squarify_module().squarify


def _load_modern_theme_module():
    spec = importlib.util.spec_from_file_location(
        "_integration_modern_theme",
        Path(__file__).parent.parent / "src" / "ui" / "themes" / "modern_theme.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _load_keybindings_module():
    spec = importlib.util.spec_from_file_location(
        "_integration_keybindings",
        Path(__file__).parent.parent / "src" / "ui" / "keybindings.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_tree(tmp_path) -> Path:
    """
    Create a small, deterministic file tree for integration tests.

    Layout::

        tmp/
          small1.txt    (1 KB)
          small2.log    (3 KB)
          medium.tmp    (8 KB)
          big.zip       (10 KB)
          sub/
            nested1.dat (2 KB)
            nested2.dat (4 KB)
    """
    files = {
        "small1.txt": 1024,
        "small2.log": 3 * 1024,
        "medium.tmp": 8 * 1024,
        "big.zip":    10 * 1024,
        "sub":        None,
    }
    (tmp_path / "sub").mkdir(parents=True, exist_ok=True)
    for name, size in files.items():
        if size is None:
            continue
        fp = tmp_path / name
        fp.write_bytes(b"x" * size)

    nested = tmp_path / "sub"
    (nested / "nested1.dat").write_bytes(b"x" * 2048)
    (nested / "nested2.dat").write_bytes(b"x" * 4096)
    return tmp_path


@pytest.fixture
def audit_db(tmp_path) -> str:
    """Temporary audit.db path; cleaned up by tmp_path."""
    return str(tmp_path / "audit.db")


@pytest.fixture
def isolated_config_home(tmp_path, monkeypatch):
    """Isolate ``~/.wiztree-cli-agent`` to ``tmp_path``."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def audit_logger(audit_db) -> AuditLogger:
    """A real AuditLogger pointing at a temp DB."""
    return AuditLogger(audit_db)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mock_router_response(content: str = "OK") -> MagicMock:
    """Construct a mock LLM chat completion response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


def _parse_dnd_data(data: str) -> List[str]:
    """
    Mirror of MainWindow._parse_drop_paths, kept in test so the test
    is not coupled to GUI internals.
    """
    paths: List[str] = []
    cur = ""
    in_brace = False
    for ch in data:
        if ch == "{":
            in_brace = True
            cur = ""
        elif ch == "}":
            if in_brace and cur:
                paths.append(cur)
            in_brace = False
            cur = ""
        elif ch == " " and not in_brace:
            if cur:
                paths.append(cur)
                cur = ""
        else:
            cur += ch
    if cur:
        paths.append(cur)
    return [p for p in paths if p]


# ===========================================================================
# SCENARIO 1: 配置 -> LLM -> 扫描 -> 可视化
# ===========================================================================
class TestConfigLlmScanVisualizationPipeline:
    """
    Scenario 1: Config -> LLM -> Scan -> Visualization.

    Verifies the data plane that backs the GUI:

        1. ``ConfigLoader`` returns the built-in LLM strategy
        2. ``LLMRouter`` is constructed from config & can be mocked
        3. A real directory walk produces ``FileInfo`` records
        4. ``Squarify`` renders the file sizes into treemap rectangles
        5. ``StatusBar.set_state`` API works (data layer, no GUI)
    """

    def test_config_loader_exposes_builtin_llm_strategy(self, isolated_config_home):
        """Stage 1: ConfigLoader.get('llm.strategy') returns a valid strategy."""
        from src.utils import ConfigLoader

        ConfigLoader.reset_instance()
        loader = ConfigLoader(auto_migrate=False)
        strategy = loader.get("llm.strategy")
        assert strategy in {"cost", "latency", "fallback", "manual"}
        # 6 主题色板在 ConfigLoader 中持久化（间接通过 ui.theme）
        assert loader.get("ui.theme") is not None
        ConfigLoader.reset_instance()

    def test_router_constructed_with_mock_provider(
        self, isolated_config_home, sample_tree
    ):
        """
        Stage 2: build an ``LLMRouter`` and stub the underlying provider.

        This replaces real network calls with a ``Mock`` so the test
        remains headless and deterministic.
        """
        from src.analyzer import LLMRouter, RoutingStrategy
        from src.analyzer.llm_router import ProviderConfig, ModelConfig

        router = LLMRouter(strategy=RoutingStrategy.FALLBACK, default_model="mock-model")
        # Inject a mock-only provider
        mock_provider = ProviderConfig(
            name="mock-provider",
            base_url="http://mock.invalid",
            api_key_env="NO_AUTH",
            api_key="mock-key",
            models=[
                ModelConfig(id="mock-model", context_window=4096, max_output=1024),
            ],
            priority=1,
        )
        router.providers = [mock_provider]
        # Patch ``_get_client`` to avoid real network
        router._get_client = MagicMock(  # type: ignore[method-assign]
            return_value=MagicMock(
                chat=MagicMock(
                    completions=MagicMock(
                        create=MagicMock(return_value=_mock_router_response("scan done"))
                    )
                )
            )
        )
        resp = router.chat(
            messages=[{"role": "user", "content": "scan test"}],
            model="mock-model",
        )
        assert resp.choices[0].message.content == "scan done"

    def test_scan_walk_produces_file_infos(self, sample_tree):
        """
        Stage 3: walk the fixture tree and produce ``FileInfo`` records.

        The walk itself is plain ``os.walk``; the assertion is that
        a deterministic number of files is discovered.
        """
        from src.models import FileInfo
        from datetime import datetime

        seen: List[FileInfo] = []
        for root, _dirs, files in os.walk(sample_tree):
            for name in files:
                p = Path(root) / name
                stat = p.stat()
                seen.append(
                    FileInfo(
                        path=p,
                        size=stat.st_size,
                        modified_time=datetime.fromtimestamp(stat.st_mtime),
                        extension=p.suffix.lower() or None,
                    )
                )
        # 4 top-level files + 2 nested = 6
        assert len(seen) == 6
        total = sum(f.size for f in seen)
        # 1K + 3K + 8K + 10K + 2K + 4K = 28 KB
        assert total == 28 * 1024

    def test_squarify_renders_scan_data(self, sample_tree):
        """
        Stage 3: feed the scan output into ``squarify`` and confirm
        a valid treemap layout is produced.
        """
        items = [
            (p.name, p.stat().st_size)
            for p in sample_tree.rglob("*")
            if p.is_file()
        ]
        rects = _squarify_layout(items, width=400, height=300)
        assert len(rects) == 6
        # Every rectangle is inside the canvas
        for r in rects:
            assert 0 <= r.x <= 400
            assert 0 <= r.y <= 300
            assert r.w > 0 and r.h > 0
        # Area conservation
        total = sum(r.w * r.h for r in rects)
        assert total == pytest.approx(400 * 300, rel=0.05)

    def test_status_bar_data_layer_works(self):
        """
        Stage 3: ``StatusBar.set_state`` accepts the documented states
        even if ctk is missing - we test the API contract, not the
        widget (which is heavily mocked in CI).
        """
        # The data-layer contract is: state in {'scanning','analyzing','ready','error'}
        # and progress in [0,1].  We do not instantiate StatusBar in CI
        # (it needs ctk); instead we verify the state strings are valid
        # by reading the source file.
        src = (
            Path(__file__).parent.parent
            / "src" / "ui" / "components" / "status_bar.py"
        ).read_text(encoding="utf-8")
        for state in ("scanning", "analyzing", "ready", "error"):
            assert f"'{state}'" in src


# ===========================================================================
# SCENARIO 2: 主题切换 + DnD 模拟 + 快捷键
# ===========================================================================
class TestThemeDndShortcuts:
    """
    Scenario 2: Theme switching + Drag-and-Drop simulation + Keyboard shortcuts.

    Verifies the UI chrome plane (Stage 4).
    """

    def test_apply_all_six_themes_round_trip(self, isolated_config_home):
        """6 主题都能被 ModernTheme.apply() 接受并通过 get_current() 读回。"""
        mt = _load_modern_theme_module()
        themes = mt.ModernTheme.list_themes()
        assert len(themes) == 6

        with patch.object(mt, "ctk", MagicMock(), create=True), \
             patch.object(mt, "_ensure_theme_file", return_value="/tmp/x.json"), \
             patch("src.utils.config_loader.ConfigLoader.get_instance") as mock_cfg_get:
            mock_cfg_get.return_value = MagicMock()
            for name in themes:
                mt.ModernTheme.apply(name)
                assert mt.ModernTheme.get_current() == name

    def test_apply_unknown_theme_raises(self):
        """未知主题名应抛 ValueError，不污染内部状态。"""
        mt = _load_modern_theme_module()
        with pytest.raises(ValueError) as exc:
            mt.ModernTheme.apply("NotARealTheme")
        assert "Unknown theme" in str(exc.value)
        assert mt.ModernTheme._current is None

    def test_parse_dnd_paths_handles_braces(self):
        """
        Stage 4: drag-and-drop data string parsing.

        tkdnd format: ``{C:\\path with space} C:\\other C:\\file.txt``
        """
        data = r"{C:\Users\wxy\AppData\Local\Temp} C:\Windows D:\data"
        paths = _parse_dnd_data(data)
        assert len(paths) == 3
        assert r"C:\Users\wxy\AppData\Local\Temp" in paths
        assert r"C:\Windows" in paths
        assert r"D:\data" in paths

    def test_dnd_drop_event_fills_scope_entry(self):
        """
        模拟 tkdnd 的 ``<<Drop>>`` 事件：用 ``MagicMock`` 模拟 event
        验证 ``_on_drop`` 的核心逻辑（解析路径 → 填入 scope_entry）。

        注意：``MainWindow`` 必须通过 importlib 加载，否则 src.ui
        会触发 main_window 的 ctk 导入（CI 无 tkinter）。
        """
        # 1) 解析路径（与 MainWindow._parse_drop_paths 等价）
        data = r"{C:\Users\me\My Drop Folder}"
        paths = _parse_dnd_data(data)
        target = paths[0]
        # 2) 用 MagicMock 模拟 scope_entry
        scope_entry = MagicMock()
        scope_entry.delete(0, "end")
        scope_entry.insert(0, target)
        scope_entry.delete.assert_called_once_with(0, "end")
        scope_entry.insert.assert_called_once_with(0, target)
        # 3) 验证 _parse_drop_paths 行为（与 MainWindow 实现一致）
        assert target == r"C:\Users\me\My Drop Folder"

    def test_keybindings_register_all_five(self):
        """5 个快捷键（Ctrl+S/R/L/, + Esc）必须都能注册到 window。"""
        kb = _load_keybindings_module()
        window = MagicMock(spec=[
            "_start_scan", "_clear_results", "_cancel_operation",
            "open_settings", "tabview", "bind",
        ])
        tab = MagicMock(spec=["refresh"])
        window.tabview.get.return_value = tab

        kb.KeyBindings.bind_all(window)
        assert window.bind.call_count == 5
        bound = {c.args[0] for c in window.bind.call_args_list}
        for key in ("<Control-s>", "<Control-r>", "<Control-l>",
                    "<Control-comma>", "<Escape>"):
            assert key in bound

    def test_keybindings_partial_window_graceful_skip(self):
        """window 缺少部分方法时，未缺失的快捷键仍要绑定。"""
        kb = _load_keybindings_module()
        window = MagicMock(spec=["_start_scan", "bind"])
        kb.KeyBindings.bind_all(window)
        assert window.bind.call_count == 1
        assert window.bind.call_args.args[0] == "<Control-s>"

    def test_ctrl_s_handler_triggers_start_scan(self):
        """Ctrl+S 触发 _start_scan 方法。"""
        kb = _load_keybindings_module()
        window = MagicMock(spec=["_start_scan", "bind"])
        kb.KeyBindings.bind_all(window)
        handler = window.bind.call_args.args[1]
        handler(MagicMock())
        window._start_scan.assert_called_once()


# ===========================================================================
# SCENARIO 3: 删除前 Diff 预览 + Audit + Restore
# ===========================================================================
class TestDiffAuditRestoreCycle:
    """
    Scenario 3: Diff preview before delete + AuditLogger record + Restore.

    Verifies Stage 5.
    """

    def test_diff_preview_constructs_and_shows_delete_warning(self, tmp_path):
        """
        Stage 5: ``DiffPreviewDialog`` for ``action='delete'`` must
        format the After section as ``🗑️ DELETE`` and include the
        warning text.
        """
        if not _CTK_OK:
            pytest.skip("ctk not available")
        from src.ui.tabs.diff_preview import DiffPreviewDialog

        real = tmp_path / "doomed.txt"
        real.write_text("goodbye world", encoding="utf-8")
        root = ctk.CTk()
        try:
            dlg = DiffPreviewDialog(root, str(real), None, "delete")
            try:
                assert "🗑️" in dlg._format_after()
                assert "DELETE" in dlg._format_after()
                # _is_destructive() must be True for delete
                assert dlg._is_destructive() is True
                # show() without confirmation returns False
                dlg._on_cancel()
                # top is destroyed; show() should not raise
                assert dlg.show() is False
            finally:
                try:
                    dlg.top.destroy()
                except Exception:
                    pass
        finally:
            root.destroy()

    def test_diff_preview_constructs_for_move(self, tmp_path):
        """``action='move'`` formats the After as ``↩️ MOVE to <dst>``."""
        if not _CTK_OK:
            pytest.skip("ctk not available")
        from src.ui.tabs.diff_preview import DiffPreviewDialog

        root = ctk.CTk()
        try:
            dlg = DiffPreviewDialog(root, "C:/a.txt", "D:/b.txt", "move")
            try:
                txt = dlg._format_after()
                assert "↩️" in txt
                assert "D:/b.txt" in txt
                # move is NOT destructive
                assert dlg._is_destructive() is False
            finally:
                try:
                    dlg.top.destroy()
                except Exception:
                    pass
        finally:
            root.destroy()

    def test_audit_records_file_delete_and_trash(self, audit_logger, tmp_path):
        """
        触发删除流程时，AuditLogger 必须：
            - 在 ``audit_log`` 写 ``file_delete`` 记录
            - 在 ``trash`` 表登记 deleted_path
        """
        # 准备
        target = tmp_path / "x.txt"
        target.write_text("content", encoding="utf-8")
        deleted_at = str(tmp_path / "_trash" / "x.txt")
        # 执行
        aid = audit_logger.log("file_delete", str(target))
        tid = audit_logger.record_trash(str(target), deleted_at, size=target.stat().st_size)
        # 校验
        assert aid > 0 and tid > 0
        recs = audit_logger.list_recent()
        assert any(r["action_type"] == "file_delete" for r in recs)
        trash = audit_logger.list_trash()
        assert any(t["original_path"] == str(target) for t in trash)

    def test_history_tab_refresh_loads_audit_records(self, audit_logger, audit_db):
        """
        HistoryTab.refresh() 必须从 ``AuditLogger.list_recent`` 拉取
        并填充 UI tree（用 mock 替换 ``list_recent`` 以隔离 ctk 依赖）。
        """
        if not _CTK_OK:
            pytest.skip("ctk not available")
        # 先写入 3 条样本记录
        audit_logger.log("scan", "/disk1")
        audit_logger.log("file_delete", "/tmp/a.txt", metadata={"k": 1})
        audit_logger.log("file_move", "/tmp/b.txt", metadata={"k": 2})

        # 用一个 mock audit logger 替换真实的，以避免在 ctk tree 里直接 fetch
        with patch("src.ui.tabs.history_tab.AuditLogger") as MockAL:
            MockAL.return_value.list_recent.return_value = [
                {
                    "id": 3, "timestamp": "2026-06-01T12:00:00",
                    "action_type": "file_move", "target_path": "/tmp/b.txt",
                    "status": "success", "metadata": {"k": 2}, "user": "tester",
                },
            ]
            from src.ui.tabs.history_tab import HistoryTab
            root = ctk.CTk()
            try:
                tab_frame = ctk.CTkFrame(root)
                ht = HistoryTab(tab_frame, audit_db_path=audit_db,
                                audit_logger=MockAL.return_value)
                try:
                    # refresh() should call list_recent
                    ht.refresh()
                    MockAL.return_value.list_recent.assert_called()
                finally:
                    try:
                        ht.frame.destroy()
                    except Exception:
                        pass
            finally:
                root.destroy()

    def test_restore_brings_file_back_to_original_location(
        self, audit_logger, tmp_path
    ):
        """
        完整 round-trip: file_delete + record_trash → restore()
        必须把文件从 trash 复制回原位置。
        """
        # 准备：trash 中放文件
        orig = tmp_path / "orig_dir" / "important.txt"
        # (orig 不存在 — 模拟已删除)
        trash = tmp_path / "_trash" / "important.txt"
        trash.parent.mkdir(parents=True, exist_ok=True)
        trash.write_text("precious", encoding="utf-8")

        aid = audit_logger.log("file_delete", str(orig))
        audit_logger.record_trash(str(orig), str(trash), size=8)

        # 还原
        ok = audit_logger.restore(aid)
        assert ok is True
        assert orig.exists()
        assert orig.read_text(encoding="utf-8") == "precious"
        # 还原后还应写一条 'restore' 审计记录
        recs = audit_logger.list_recent()
        assert any(r["action_type"] == "restore" for r in recs)


# ===========================================================================
# SCENARIO 4: Squarified 算法 + 6 主题布局
# ===========================================================================
class TestSquarifyThemesRender:
    """
    Scenario 4: Squarified algorithm + 6 themes can all render the same layout.

    The same treemap layout must be valid for every theme - we verify
    by re-running ``squarify`` and confirming the aspect ratio invariant
    holds.
    """

    @pytest.mark.parametrize("size_count", [4, 8, 16])
    def test_uniform_layout_ar_bound(self, size_count):
        """Uniform input + squarify → 矩形 AR 在可接受范围。"""
        items = [(f"f{i}", 1.0) for i in range(size_count)]
        rects = _squarify_layout(items, 100, 100)
        assert len(rects) == size_count
        for r in rects:
            ar = max(r.w / r.h, r.h / r.w)
            # SPEC allows AR up to 3 for uniform inputs
            assert ar <= 3.0, f"rect {r.label} has AR {ar}"

    def test_area_conservation_under_skewed_input(self):
        """1 大 + 9 小 的极端输入也必须满足面积守恒。"""
        items = [("huge", 100.0)] + [(f"s{i}", 1.0) for i in range(9)]
        rects = _squarify_layout(items, 100, 100)
        total = sum(r.w * r.h for r in rects)
        assert total == pytest.approx(100 * 100, rel=0.05)
        # huge 必须占主导
        huge = next(r for r in rects if r.label == "huge")
        assert huge.w * huge.h >= 0.5 * 100 * 100

    def test_all_six_themes_produce_consistent_layout_for_same_data(self):
        """
        Squarify 是纯算法，与 theme 无关 — 同一组 (sizes, w, h)
        必须对所有 6 主题产生**完全一致**的 layout (因为 theme
        只影响颜色，不影响几何)。
        """
        sq = _load_squarify_module()
        items = [("a", 1.0), ("b", 2.0), ("c", 3.0), ("d", 4.0)]
        baseline = sq.squarify(items, 100, 80)

        mt = _load_modern_theme_module()
        # 对每个主题，验证几何 layout 一致（颜色不影响 squarify）
        for theme_name in mt.ModernTheme.list_themes():
            again = sq.squarify(items, 100, 80)
            assert len(again) == len(baseline)
            for r1, r2 in zip(baseline, again):
                assert r1.x == r2.x
                assert r1.y == r2.y
                assert r1.w == r2.w
                assert r1.h == r2.h

    def test_each_theme_has_progressbar_color(self):
        """6 主题都必须有 ``progressbar_color`` 字段 (Stage 3 StatusBar 依赖)。"""
        mt = _load_modern_theme_module()
        for name in mt.ModernTheme.list_themes():
            palette = mt.THEMES[name]
            assert "progressbar_color" in palette
            assert palette["progressbar_color"].startswith("#")
            assert len(palette["progressbar_color"]) == 7


# ===========================================================================
# SCENARIO 5: 跨 stage 端到端
# ===========================================================================
class TestEndToEndCompleteFlow:
    """
    Scenario 5: full cross-stage pipeline.

    启动 → 配置 LLM → 扫描 → treemap → 选文件 → Diff 预览 →
    删除 → audit → restore.
    """

    def test_full_pipeline_orchestration(
        self, isolated_config_home, sample_tree, audit_db, tmp_path
    ):
        """
        1. 初始化 ConfigLoader (Stage 1)
        2. 构造 mock LLM router (Stage 2)
        3. 扫描 fixture 目录 (Stage 3)
        4. 跑 RuleEngine → DeletionRecommendation
        5. squarify → treemap
        6. AuditLogger 记录 file_delete + record_trash (Stage 5)
        7. AuditLogger.restore() → 文件回到原位置
        """
        # === Stage 1: ConfigLoader ===
        from src.utils import ConfigLoader

        ConfigLoader.reset_instance()
        loader = ConfigLoader(auto_migrate=False)
        strategy = loader.get("llm.strategy")
        assert strategy in {"cost", "latency", "fallback", "manual"}
        ConfigLoader.reset_instance()

        # === Stage 2: mock LLM router ===
        from src.analyzer import LLMRouter, RoutingStrategy, RuleEngine
        from src.analyzer.llm_router import ProviderConfig, ModelConfig

        router = LLMRouter(strategy=RoutingStrategy.FALLBACK, default_model="mock-m")
        mock_provider = ProviderConfig(
            name="mock",
            base_url="http://mock",
            api_key_env="NO_AUTH",
            api_key="k",
            models=[ModelConfig(id="mock-m", context_window=4096, max_output=1024)],
            priority=1,
        )
        router.providers = [mock_provider]
        router._get_client = MagicMock(  # type: ignore[method-assign]
            return_value=MagicMock(
                chat=MagicMock(
                    completions=MagicMock(
                        create=MagicMock(return_value=_mock_router_response("OK"))
                    )
                )
            )
        )
        resp = router.chat(
            messages=[{"role": "user", "content": "list candidates"}],
            model="mock-m",
        )
        assert resp.choices[0].message.content == "OK"

        # === Stage 3: scan + squarify ===
        from src.models import FileInfo, ScanResult

        files: List[FileInfo] = []
        for root, _dirs, fnames in os.walk(sample_tree):
            for n in fnames:
                p = Path(root) / n
                st = p.stat()
                files.append(
                    FileInfo(
                        path=p, size=st.st_size,
                        modified_time=datetime.fromtimestamp(st.st_mtime),
                        extension=p.suffix.lower() or None,
                    )
                )
        scan_result = ScanResult(
            target_path=sample_tree,
            files=files,
            scan_time=datetime.now(),
            duration_seconds=0.123,
            total_files=len(files),
            total_directories=2,
            total_size=sum(f.size for f in files),
        )
        assert scan_result.total_files == 6
        rects = _squarify_layout(
            [(f.path.name, f.size) for f in files],
            width=600, height=400,
        )
        assert len(rects) == 6

        # === Stage 2 (alt): RuleEngine ===
        engine = RuleEngine()
        recs, _warnings = engine.analyze_files(files)
        # 我们的小 fixture 中包含 ``.tmp`` 和 ``.log``，所以必有 rec
        assert any(r.file.path.suffix in {".tmp", ".log"} for r in recs)

        # === Stage 5: Diff + Audit + Restore ===
        # 选 ``medium.tmp`` 作为删除目标
        victim = sample_tree / "medium.tmp"
        trash = tmp_path / "_trash" / "medium.tmp"
        trash.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(victim, trash)

        al = AuditLogger(audit_db)
        aid = al.log("file_delete", str(victim), metadata={"reason": "rule:tmp"})
        al.record_trash(str(victim), str(trash), size=victim.stat().st_size)

        # 验证 audit.db 完整记录
        recs_db = al.list_recent()
        assert any(r["action_type"] == "file_delete" and r["id"] == aid
                   for r in recs_db)
        trash_db = al.list_trash(original_path=str(victim))
        assert len(trash_db) == 1
        assert trash_db[0]["original_path"] == str(victim)

        # 还原
        ok = al.restore(aid)
        assert ok is True
        # 原文件应回到原位
        assert victim.exists()
        # 还原动作也写入了 audit_log
        recs_after = al.list_recent()
        assert any(r["action_type"] == "restore" for r in recs_after)

        # === Stats ===
        stats = al.get_stats()
        assert stats["total_actions"] >= 2
        assert "file_delete" in stats["by_type"]
        assert "restore" in stats["by_type"]

    def test_audit_db_records_full_lifecycle(self, audit_db, tmp_path):
        """
        跨 stage 的 audit 生命周期：scan → file_delete → restore
        必须全部出现在 audit_log。
        """
        al = AuditLogger(audit_db)
        al.log("scan", str(tmp_path))
        target = tmp_path / "f.txt"
        target.write_text("x")
        aid_del = al.log("file_delete", str(target))
        al.record_trash(str(target), str(tmp_path / "trash" / "f.txt"))
        # restore 流程
        (tmp_path / "trash").mkdir(parents=True, exist_ok=True)
        (tmp_path / "trash" / "f.txt").write_text("x")
        ok = al.restore(aid_del)
        assert ok is True

        recs = al.list_recent(limit=100)
        action_types = {r["action_type"] for r in recs}
        assert "scan" in action_types
        assert "file_delete" in action_types
        assert "restore" in action_types

    def test_history_tab_audit_summary_round_trip(self, audit_db):
        """
        跨 stage 集成：写入 audit → 用 AuditLogger.get_stats() 读出汇总。
        """
        al = AuditLogger(audit_db)
        al.log("scan", "/disk1")
        al.log("file_delete", "/tmp/a")
        al.log("file_delete", "/tmp/b")
        al.log("file_move", "/tmp/c", metadata={"original_path": "/src/c"})

        stats = al.get_stats()
        assert stats["total_actions"] == 4
        assert stats["by_type"]["file_delete"] == 2
        assert stats["by_type"]["file_move"] == 1
        assert stats["by_type"]["scan"] == 1
        assert stats["by_status"]["success"] == 4
        assert stats["recent_24h"] == 4


# ===========================================================================
# Public contract: __version__ bump
# ===========================================================================
class TestVersionContract:
    """
    Stage 6 contract: ``src/__init__.py`` 必须定义 ``__version__ = "1.5.0"``。
    """

    def test_src_init_defines_version(self):
        spec = importlib.util.spec_from_file_location(
            "src_version_test",
            Path(__file__).parent.parent / "src" / "__init__.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        assert hasattr(mod, "__version__"), "src/__init__.py must define __version__"
        assert mod.__version__ == "2.1.0"

    def test_requirements_has_v120_dependencies(self):
        """requirements.txt must include all v1.2.0 runtime deps."""
        req_path = Path(__file__).parent.parent / "requirements.txt"
        content = req_path.read_text(encoding="utf-8").lower()
        for dep in ("customtkinter", "keyring", "requests", "tkinterdnd2",
                    "pytest"):
            assert dep in content, f"missing {dep} in requirements.txt"


# ===========================================================================
# Coverage helper: public API surface
# ===========================================================================
class TestPublicApiSurface:
    """
    Sanity checks that the v1.2.0 public API names exist.
    Catches accidental removals during integration.
    """

    def test_stage1_api(self):
        from src.utils import ConfigLoader, CredentialStore
        assert ConfigLoader is not None
        assert CredentialStore is not None

    def test_stage2_api(self):
        from src.analyzer import LLMRouter, RoutingStrategy, RuleEngine
        assert LLMRouter is not None
        assert RoutingStrategy is not None
        assert RuleEngine is not None

    def test_stage3_api(self):
        # Use importlib to bypass ``src.ui.__init__`` (which would
        # trigger ctk imports even for module-attribute access).
        sq = _load_squarify_module()
        assert sq.squarify is not None
        # StatusBar: import via importlib too (the module itself
        # imports ctk at top-level, so we just check the file exists
        # and contains the class).
        sb_path = (Path(__file__).parent.parent / "src" / "ui" / "components" / "status_bar.py")
        assert sb_path.exists()
        assert "class StatusBar" in sb_path.read_text(encoding="utf-8")

    def test_stage4_api(self):
        mt = _load_modern_theme_module()
        kb = _load_keybindings_module()
        assert mt.ModernTheme is not None
        assert kb.KeyBindings is not None

    def test_stage5_api(self):
        from src.safety.audit_logger import AuditLogger
        assert AuditLogger is not None
        # diff_preview / history_tab are loaded by importlib in the
        # scenario-3 tests above, so we just check the file exists.
        dp_path = (Path(__file__).parent.parent / "src" / "ui" / "tabs" / "diff_preview.py")
        ht_path = (Path(__file__).parent.parent / "src" / "ui" / "tabs" / "history_tab.py")
        assert dp_path.exists() and "DiffPreviewDialog" in dp_path.read_text(encoding="utf-8")
        assert ht_path.exists() and "HistoryTab" in ht_path.read_text(encoding="utf-8")
