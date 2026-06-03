"""
ModelsTab 测试 (v1.2.0 / Stage 2)

策略：不真正渲染 CTk（避免在无显示的 CI 中崩溃）。
- 检查类/方法存在
- 用 mock 验证 ``ModelsTab._on_card_select`` 会调用 ``ConfigLoader.set``
- 用 mock 验证 ``refresh()`` 会调用 ``ModelCatalog.refresh``
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# tkinter / customtkinter 可用性探测
try:
    import tkinter
    import customtkinter
    _CTK_OK = True
except ImportError:
    _CTK_OK = False

skip_no_ctk = pytest.mark.skipif(not _CTK_OK, reason="tkinter / customtkinter not available")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_master():
    """创建一个不会真正渲染的 master（仅作为 widget 容器）"""
    if not _CTK_OK:
        pytest.skip("tkinter not available")
    import customtkinter as ctk
    root = ctk.CTk()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def mock_catalog():
    cat = MagicMock()
    cat.info.return_value = {
        "source": "fallback", "model_count": 2, "provider_count": 1,
        "providers": ["openrouter"],
    }
    from src.analyzer.model_catalog import ModelInfo
    cat.list.return_value = [
        ModelInfo(
            id="openai/gpt-4o", name="GPT-4o", provider="openai",
            context_length=128_000, prompt_price=2.5, completion_price=10.0,
        ),
        ModelInfo(
            id="anthropic/claude-3.5-sonnet", name="Claude 3.5 Sonnet",
            provider="anthropic", context_length=200_000,
            prompt_price=3.0, completion_price=15.0,
        ),
    ]
    return cat


@pytest.fixture
def mock_config():
    return MagicMock()


# ---------------------------------------------------------------------------
# Test: import / API
# ---------------------------------------------------------------------------
class TestImport:
    @skip_no_ctk
    def test_module_imports(self):
        from src.ui.tabs.models_tab import ModelsTab, PROVIDER_FILTERS, SORT_OPTIONS
        assert ModelsTab is not None
        assert "All" in PROVIDER_FILTERS
        assert "name" in SORT_OPTIONS


# ---------------------------------------------------------------------------
# Test: 构造 + 公共 API
# ---------------------------------------------------------------------------
@skip_no_ctk
class TestConstruction:
    def test_constructs_with_mock(self, fake_master, mock_catalog, mock_config):
        from src.ui.tabs.models_tab import ModelsTab
        tab = ModelsTab(
            fake_master,
            catalog=mock_catalog,
            config_loader=mock_config,
        )
        assert tab.frame is not None
        assert tab._catalog is mock_catalog
        assert tab._config is mock_config

    def test_refresh_calls_catalog_refresh(self, fake_master, mock_catalog, mock_config):
        from src.ui.tabs.models_tab import ModelsTab
        tab = ModelsTab(fake_master, catalog=mock_catalog, config_loader=mock_config)
        mock_catalog.refresh.reset_mock()
        tab.refresh()
        mock_catalog.refresh.assert_called_once()

    def test_render_calls_list(self, fake_master, mock_catalog, mock_config):
        from src.ui.tabs.models_tab import ModelsTab
        tab = ModelsTab(fake_master, catalog=mock_catalog, config_loader=mock_config)
        mock_catalog.list.assert_called()  # constructor triggers one render

    def test_provider_filter_passes_provider(self, fake_master, mock_catalog, mock_config):
        from src.ui.tabs.models_tab import ModelsTab
        tab = ModelsTab(fake_master, catalog=mock_catalog, config_loader=mock_config)
        # 模拟点 OpenAI 分段
        tab._on_provider_change("OpenAI")
        # 最近一次 list 调用应带 provider=openai
        args, kwargs = mock_catalog.list.call_args
        assert kwargs.get("provider") == "openai" or (args and args[0] == "openai")

    def test_sort_change_passes_sort_by(self, fake_master, mock_catalog, mock_config):
        from src.ui.tabs.models_tab import ModelsTab
        tab = ModelsTab(fake_master, catalog=mock_catalog, config_loader=mock_config)
        tab._on_sort_change("price")
        args, kwargs = mock_catalog.list.call_args
        assert kwargs.get("sort_by") == "price" or (len(args) >= 2 and args[1] == "price")

    def test_select_writes_config(self, fake_master, mock_catalog, mock_config):
        from src.ui.tabs.models_tab import ModelsTab
        from src.analyzer.model_catalog import ModelInfo
        tab = ModelsTab(fake_master, catalog=mock_catalog, config_loader=mock_config)
        m = ModelInfo(
            id="openai/gpt-4o-mini", name="GPT-4o mini", provider="openai",
            context_length=128_000, prompt_price=0.15, completion_price=0.6,
        )
        tab._on_card_select(m)
        # ConfigLoader.set 应被调用，key="llm.selected_model", value=model.id
        mock_config.set.assert_called()
        call_args = mock_config.set.call_args
        assert call_args[0][0] == "llm.selected_model"
        assert call_args[0][1] == "openai/gpt-4o-mini"

    def test_select_invokes_callback(self, fake_master, mock_catalog, mock_config):
        from src.ui.tabs.models_tab import ModelsTab
        from src.analyzer.model_catalog import ModelInfo
        cb = MagicMock()
        tab = ModelsTab(
            fake_master, catalog=mock_catalog, config_loader=mock_config, on_select=cb,
        )
        m = ModelInfo(
            id="x/y", name="X", provider="x", context_length=1,
            prompt_price=0.0, completion_price=0.0,
        )
        tab._on_card_select(m)
        cb.assert_called_once_with(m)
