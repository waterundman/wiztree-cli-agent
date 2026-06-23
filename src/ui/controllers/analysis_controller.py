"""AnalysisController — LLM / 规则引擎分析逻辑，UI 无关。"""
import logging
from typing import Callable, List, Optional

from src.models import FileInfo, ScanResult, DeletionRecommendation, RiskLevel
from src.analyzer import RuleEngine

logger = logging.getLogger(__name__)


class AnalysisController:
    """管理 LLM 分析和规则引擎 fallback。不导入任何 GUI 库。"""

    def __init__(
        self,
        rule_engine: Optional[RuleEngine] = None,
        *,
        llm_router=None,
        model_var_getter: Optional[Callable[[], str]] = None,
        # UI 回调
        on_status: Optional[Callable[[str, str], None]] = None,
        on_ai_status: Optional[Callable[[str], None]] = None,
        on_prepare_streaming: Optional[Callable[[], None]] = None,
        on_append_text: Optional[Callable[[str], None]] = None,
        on_finish_streaming: Optional[Callable[[], None]] = None,
        on_show_fallback: Optional[Callable[[], None]] = None,
        on_show_error: Optional[Callable[[str], None]] = None,
        on_update_analysis: Optional[Callable[[], None]] = None,
        on_update_action_table: Optional[Callable[[], None]] = None,
    ):
        self._rule_engine = rule_engine or RuleEngine()
        self._llm_router = llm_router
        self._model_var_getter = model_var_getter

        # 回调
        self._on_status = on_status
        self._on_ai_status = on_ai_status
        self._on_prepare_streaming = on_prepare_streaming
        self._on_append_text = on_append_text
        self._on_finish_streaming = on_finish_streaming
        self._on_show_fallback = on_show_fallback
        self._on_show_error = on_show_error
        self._on_update_analysis = on_update_analysis
        self._on_update_action_table = on_update_action_table

        # 状态
        self.recommendations: List[DeletionRecommendation] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze(self, files: List[FileInfo], scan_result: Optional[ScanResult] = None) -> None:
        """启动分析（同步，由调用方决定线程）。优先 LLM，fallback 到规则引擎。"""
        if self.is_llm_available():
            self._run_llm_analysis(files)
        else:
            if self._on_show_fallback:
                self._on_show_fallback()
            self._run_rule_engine_analysis(files)

    def stop(self) -> None:
        """停止分析（目前为占位）。"""
        pass

    def is_llm_available(self) -> bool:
        """检查 LLM 路由器和模型选择是否可用。"""
        if not self._llm_router or not self._model_var_getter:
            return False
        model_choice = self._model_var_getter().strip()
        return bool(model_choice and model_choice != "(no API key configured)")

    def get_recommendations(self) -> List[DeletionRecommendation]:
        return list(self.recommendations)

    def set_recommendations(self, recs: List[DeletionRecommendation]) -> None:
        self.recommendations = recs

    def remove_deleted_recommendations(self, deleted_paths: set) -> None:
        """从推荐列表中移除已删除的文件。"""
        self.recommendations = [
            rec for rec in self.recommendations
            if str(rec.file.path) not in deleted_paths
        ]

    def set_llm_router(self, router) -> None:
        self._llm_router = router

    def reanalyze_files(self, files: List[FileInfo]) -> None:
        """使用规则引擎重新分析一批文件。"""
        self.recommendations, _ = self._rule_engine.analyze_files(files)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    def _run_llm_analysis(self, files: list) -> None:
        """使用 LLM 流式分析文件，失败时降级到规则引擎。"""
        from src.analyzer import LLMAnalyzer

        try:
            model_choice = self._model_var_getter().strip()
            model_name = model_choice.split(": ", 1)[-1] if ": " in model_choice else model_choice

            analyzer = LLMAnalyzer(model=model_name, language="zh", lazy_init=True)

            if self._on_prepare_streaming:
                self._on_prepare_streaming()

            def on_llm_chunk(result_dict):
                try:
                    text = (
                        f"  [{result_dict.get('risk_level', 'Medium')}] "
                        f"{result_dict.get('file_path', 'N/A')}\n"
                        f"     {result_dict.get('size_mb', 0):.1f} MB — "
                        f"{result_dict.get('reason', '')}\n\n"
                    )
                    if self._on_append_text:
                        self._on_append_text(text)
                except Exception:
                    logger.warning("LLM streaming chunk callback failed", exc_info=True)

            llm_results = list(analyzer.analyze_streaming(files, callback=on_llm_chunk))

            # 转换为 DeletionRecommendation
            risk_map = {v.value: v for v in RiskLevel}
            recommendations = []
            for r in llm_results:
                fi = r.get("file_info")
                if fi:
                    rl_str = str(r.get("risk_level", "medium")).lower()
                    rl = risk_map.get(rl_str, RiskLevel.MEDIUM)
                    recommendations.append(DeletionRecommendation(
                        file=fi,
                        reason=r.get("reason", ""),
                        risk_level=rl,
                        confidence=r.get("confidence", 0.8),
                        potential_savings=fi.size,
                    ))

            self.recommendations = recommendations

            if self._on_finish_streaming:
                self._on_finish_streaming()
            if self._on_update_action_table:
                self._on_update_action_table()
            if self._on_status:
                self._on_status(
                    f"LLM analysis complete, {len(self.recommendations)} recommendations",
                    "green",
                )

        except Exception as e:
            logger.error("LLM analysis failed, falling back to rule engine: %s", e, exc_info=True)
            if self._on_show_error:
                self._on_show_error(str(e))
            self._run_rule_engine_analysis(files)

    def _run_rule_engine_analysis(self, files: list) -> None:
        """使用规则引擎分析文件（fallback 路径）。"""
        self.recommendations, _ = self._rule_engine.analyze_files(files)

        if self._on_update_analysis:
            self._on_update_analysis()
        if self._on_update_action_table:
            self._on_update_action_table()
