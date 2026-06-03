"""
设置对话框
=========

v1.2.0 新增：SettingsDialog (ctk.CTkToplevel)

功能：
    - API Key 输入（按 provider 一行一行）
    - API Key 经 CredentialStore 加密存储
    - 主题选择下拉（6 个主题名预留）
    - Provider 默认值 / 扫描默认值 配置
    - 关闭时自动持久化到 ConfigLoader

依赖：
    - customtkinter (UI)
    - src.utils.config_loader.ConfigLoader
    - src.utils.credential_store.CredentialStore
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# 延迟导入 customtkinter（避免在无 tkinter 的环境 import 时崩溃）
try:
    import customtkinter as ctk
    _CTK_AVAILABLE = True
except ImportError:  # pragma: no cover - 环境探测
    ctk = None  # type: ignore
    _CTK_AVAILABLE = False


# 6 个主题名（预留；customtkinter 内建支持 blue/green/dark-blue，
# 其余 3 个为扩展位，待 Stage 4 theme 实现）
THEME_NAMES: List[str] = [
    "blue",
    "green",
    "dark-blue",
    "dark-green",
    "light",
    "system",
]


class SettingsDialog:
    """
    设置对话框（Stage 1 实现）

    Stage 1 仅需提供可用骨架与基本功能，Stage 2 会由 main_window 集成。
    本类不强制继承 ctk.CTkToplevel —— 实例化时才延迟继承，
    以便在无 tkinter 的环境下仍能 import 整个模块。
    """

    PROVIDER_NAMES: List[str] = [
        "deepseek",
        "openai",
        "anthropic",
        "openrouter",
        "siliconflow",
        "ollama",
    ]

    def __init__(
        self,
        master: Optional[Any] = None,
        config_loader: Optional[Any] = None,
        credential_store: Optional[Any] = None,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Args:
            master:            父窗口 (ctk.CTk 实例)
            config_loader:     ConfigLoader 实例（None 则取全局单例）
            credential_store:  CredentialStore 实例（None 则新建一个）
            on_close:          对话框关闭后的回调
        """
        if not _CTK_AVAILABLE:
            raise RuntimeError(
                "customtkinter / tkinter 不可用，无法实例化 SettingsDialog"
            )

        # 解析依赖（延迟 import 避免循环）
        from .config_loader import ConfigLoader
        from .credential_store import CredentialStore

        self._config: ConfigLoader = config_loader or ConfigLoader.get_instance()
        self._credentials: CredentialStore = credential_store or CredentialStore()
        self._on_close_cb = on_close

        # 真正创建 ctk.CTkToplevel 子窗口
        self.window: "ctk.CTkToplevel" = ctk.CTkToplevel(master)
        self.window.title("Settings — wiztree-cli-agent")
        self.window.geometry("640x720")
        self.window.minsize(560, 600)
        self.window.transient(master)
        self.window.grab_set()

        # 状态
        self._api_key_entries: Dict[str, Any] = {}
        self._theme_var: Any = None
        self._default_provider_var: Any = None
        self._provider_entries: Dict[str, Any] = {}
        self._status_label: Any = None

        self._build_ui()
        self._load_existing()

        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        try:
            ctk.set_appearance_mode(self._config.get("ui.appearance_mode", "system"))
        except Exception:  # pragma: no cover
            pass

        # 滚动容器（设置项可能很多）
        outer = ctk.CTkScrollableFrame(self.window, label_text="")
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        # ---- Section: API Keys ----
        ctk.CTkLabel(
            outer, text="API Keys (encrypted via OS keyring)",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=4, pady=(4, 8))

        keys_help = ctk.CTkLabel(
            outer,
            text=(
                "Keys are stored encrypted in the OS credential store "
                "(Windows Credential Manager / macOS Keychain / Linux Secret Service). "
                "They are never written to plain-text config files."
            ),
            text_color="gray",
            wraplength=560,
            justify="left",
        )
        keys_help.pack(anchor="w", padx=4, pady=(0, 8))

        for provider in self.PROVIDER_NAMES:
            row = ctk.CTkFrame(outer, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=4)

            ctk.CTkLabel(row, text=provider, width=120, anchor="w").pack(side="left")

            entry = ctk.CTkEntry(row, placeholder_text="••••••••", show="•", width=320)
            entry.pack(side="left", padx=8)

            btn = ctk.CTkButton(
                row, text="Save", width=64,
                command=lambda p=provider, e=entry: self._save_api_key(p, e),
            )
            btn.pack(side="left")

            ctk.CTkButton(
                row, text="Clear", width=64,
                command=lambda p=provider: self._clear_api_key(p),
            ).pack(side="left", padx=4)

            self._api_key_entries[provider] = entry

        # ---- Section: Theme & UI ----
        ctk.CTkLabel(
            outer, text="UI", font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=4, pady=(16, 4))

        theme_row = ctk.CTkFrame(outer, fg_color="transparent")
        theme_row.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(theme_row, text="Theme", width=120, anchor="w").pack(side="left")
        self._theme_var = ctk.StringVar(value=self._config.get("ui.theme", "blue"))
        ctk.CTkOptionMenu(
            theme_row, values=THEME_NAMES, variable=self._theme_var, width=200,
        ).pack(side="left", padx=8)

        # ---- Section: Provider default ----
        ctk.CTkLabel(
            outer, text="LLM Provider defaults", font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=4, pady=(16, 4))

        prov_row = ctk.CTkFrame(outer, fg_color="transparent")
        prov_row.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(prov_row, text="Default provider", width=120, anchor="w").pack(side="left")
        self._default_provider_var = ctk.StringVar(
            value=self._config.get("llm.default_provider", "deepseek")
        )
        ctk.CTkOptionMenu(
            prov_row, values=self.PROVIDER_NAMES,
            variable=self._default_provider_var, width=200,
        ).pack(side="left", padx=8)

        model_row = ctk.CTkFrame(outer, fg_color="transparent")
        model_row.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(model_row, text="Default model", width=120, anchor="w").pack(side="left")
        model_var = ctk.StringVar(value=self._config.get("llm.default_model", "deepseek-v4-flash"))
        ctk.CTkEntry(model_row, textvariable=model_var, width=320).pack(side="left", padx=8)
        self._provider_entries["default_model"] = model_var

        # ---- Section: Scan defaults ----
        ctk.CTkLabel(
            outer, text="Scan defaults", font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", padx=4, pady=(16, 4))

        top_n_row = ctk.CTkFrame(outer, fg_color="transparent")
        top_n_row.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(top_n_row, text="Default top-N", width=120, anchor="w").pack(side="left")
        top_n_var = ctk.StringVar(value=str(self._config.get("scan.default_top_n", 50)))
        ctk.CTkEntry(top_n_row, textvariable=top_n_var, width=120).pack(side="left", padx=8)
        self._provider_entries["default_top_n"] = top_n_var

        # ---- Bottom buttons ----
        bottom = ctk.CTkFrame(self.window, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=12)

        self._status_label = ctk.CTkLabel(bottom, text="", text_color="gray")
        self._status_label.pack(side="left", padx=4)

        ctk.CTkButton(bottom, text="Save", width=100, command=self._save_all).pack(
            side="right", padx=4
        )
        ctk.CTkButton(bottom, text="Cancel", width=100, command=self._on_close).pack(
            side="right", padx=4
        )

    # ------------------------------------------------------------------
    # 数据加载 / 保存
    # ------------------------------------------------------------------
    def _load_existing(self) -> None:
        """加载已存储的 API Key（仅显示 •，不反显明文）"""
        for provider, entry in self._api_key_entries.items():
            existing = self._credentials.get_api_key(provider)
            if existing:
                # 用占位符表示「已设置」但不明文显示
                entry.configure(placeholder_text=f"•••• (set, {len(existing)} chars)")
            else:
                entry.configure(placeholder_text="(not set)")

    def _save_api_key(self, provider: str, entry: Any) -> None:
        key = entry.get().strip()
        if not key:
            self._set_status(f"Key for {provider} is empty — nothing saved", "orange")
            return
        try:
            self._credentials.store_api_key(provider, key)
            self._set_status(f"Saved {provider} key to OS keyring", "green")
            # 清空输入框，避免明文长时间停留
            entry.delete(0, "end")
            self._load_existing()
        except Exception as e:  # pragma: no cover - 取决于后端
            self._set_status(f"Save failed: {e}", "red")

    def _clear_api_key(self, provider: str) -> None:
        try:
            self._credentials.delete_api_key(provider)
            self._set_status(f"Cleared {provider} key", "green")
            self._load_existing()
        except Exception as e:  # pragma: no cover
            self._set_status(f"Clear failed: {e}", "red")

    def _save_all(self) -> None:
        try:
            self._config.set("ui.theme", self._theme_var.get())
            self._config.set("llm.default_provider", self._default_provider_var.get())
            if "default_model" in self._provider_entries:
                self._config.set(
                    "llm.default_model",
                    self._provider_entries["default_model"].get().strip(),
                )
            if "default_top_n" in self._provider_entries:
                try:
                    top_n = int(self._provider_entries["default_top_n"].get().strip())
                except ValueError:
                    top_n = 50
                self._config.set("scan.default_top_n", top_n)
            self._set_status("Settings saved", "green")
        except Exception as e:
            self._set_status(f"Save failed: {e}", "red")

    # ------------------------------------------------------------------
    # 关闭
    # ------------------------------------------------------------------
    def _on_close(self) -> None:
        try:
            if self._on_close_cb:
                self._on_close_cb()
        finally:
            try:
                self.window.grab_release()
            except Exception:  # pragma: no cover
                pass
            self.window.destroy()

    def _set_status(self, text: str, color: str = "gray") -> None:
        try:
            self._status_label.configure(text=text, text_color=color)
        except Exception:  # pragma: no cover
            logger.info("settings status: %s", text)
