import os
import json
import random
import threading
import time
from typing import List, Dict, Optional, Generator, Any
from datetime import datetime

from openai import OpenAI
from openai.types.chat import ChatCompletionChunk
from openai import (
    APITimeoutError as Timeout,
    APIConnectionError as ConnectionError,
    AuthenticationError,
    APIError,
)

from .interface import AnalyzerInterface
from .json_parser import StreamingJsonParser
from .rule_engine import RuleEngine
from ..models.file_info import FileInfo
from ..models.analysis_result import AnalysisResult, DeletionRecommendation, RiskLevel


# System prompts
SYSTEM_PROMPT_EN = """You are an expert Disk Cleanup Assistant. Analyze the provided list of large files from a Windows system scan.

Identify potential waste (caches, old downloads, temp files, installer packages, logs) and EXPLICITLY avoid critical system files, driver files, or active program data.

Return ONLY a JSON array (no markdown fences, no explanation text before or after) with this exact structure:
[
  {
    "file_path": "C:\\\\Users\\\\Admin\\\\Downloads\\\\heavy_installer.exe",
    "size_mb": 2048.5,
    "reason": "6-month-old installer package, safe to remove.",
    "risk_level": "Low"
  }
]

risk_level must be one of: "Low", "Medium", "High".
Only include files you recommend for deletion. If no files are safe to delete, return an empty array [].
DO NOT wrap the JSON in ```json``` code fences. Return the raw JSON array directly."""

SYSTEM_PROMPT_ZH = """你是一名磁盘清理专家。分析以下 Windows 系统扫描得到的大文件列表。

识别潜在的可清理文件（缓存、旧下载、临时文件、安装包、日志），并明确避免删除关键系统文件、驱动程序或正在使用的程序数据。

只返回一个 JSON 数组（不要 markdown 代码块，不要前后解释文本），结构如下：
[
  {
    "file_path": "C:\\\\Users\\\\Admin\\\\Downloads\\\\heavy_installer.exe",
    "size_mb": 2048.5,
    "reason": "6个月前的安装包，可安全删除。",
    "risk_level": "Low"
  }
]

risk_level 必须是 "Low"、"Medium" 或 "High" 之一。
只包含你建议删除的文件。如果没有文件可以安全删除，返回空数组 []。
不要用 ```json``` 代码块包裹。直接返回原始 JSON 数组。"""


class LLMAnalyzer(AnalyzerInterface):
    """
    LLM分析器
    使用大语言模型分析文件并提供删除建议
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "deepseek-v4-flash",
        language: str = "zh",
        max_retries: int = 3,
        timeout: int = 60,
        lazy_init: bool = False
    ):
        """
        初始化LLM分析器
        
        Args:
            api_key: OpenAI API密钥，如果不提供则从环境变量读取
            base_url: API基础URL（可选）
            model: 模型名称
            language: 语言 ('zh' 或 'en')
            max_retries: 最大重试次数
            timeout: 请求超时时间（秒）
            lazy_init: 延迟初始化，如果没有API密钥不抛出异常
        """
        self.model = model
        self.language = language
        self.max_retries = max_retries
        self.timeout = timeout
        self._available = False
        
        # 初始化API客户端
        self._api_key = api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            if lazy_init:
                # 延迟初始化模式，不抛出异常
                self._client = None
                self._json_parser = StreamingJsonParser()
                self._rule_engine = RuleEngine()
                self._is_streaming = False
                self._current_stream = None
                return
            else:
                raise ValueError("API key is required. Provide api_key parameter or set DEEPSEEK_API_KEY/OPENAI_API_KEY environment variable.")
        
        self._base_url = base_url
        self._client = self._create_client()
        self._available = True
        
        # 初始化组件
        self._json_parser = StreamingJsonParser()
        self._rule_engine = RuleEngine()
        
        # 状态
        self._is_streaming = False
        self._current_stream = None
    
    @property
    def is_available(self) -> bool:
        """检查LLM分析器是否可用"""
        return self._available and self._client is not None
    
    def _create_client(self) -> OpenAI:
        """
        创建OpenAI客户端
        
        Returns:
            OpenAI: 客户端实例
        """
        kwargs = {"api_key": self._api_key}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return OpenAI(**kwargs)
    
    def analyze(self, files: List[FileInfo]) -> AnalysisResult:
        """
        分析文件列表
        
        Args:
            files: 文件信息列表
            
        Returns:
            AnalysisResult: 分析结果
        """
        start_time = time.time()
        
        # 验证文件
        valid_files = self.validate_files(files)
        
        if not valid_files:
            return self.create_empty_result()
        
        # 检查LLM是否可用
        if not self.is_available:
            # LLM不可用，直接使用规则引擎
            recommendations, warnings = self._rule_engine.analyze_files(valid_files)
        else:
            # 尝试使用LLM分析
            try:
                recommendations = self._analyze_with_llm(valid_files)
            except Exception as e:
                # LLM分析失败，降级到规则引擎
                print(f"LLM analysis failed, falling back to rule engine: {e}")
                recommendations, warnings = self._rule_engine.analyze_files(valid_files)
        
        # 计算总节省空间
        total_savings = self.calculate_total_savings(recommendations)
        
        # 生成风险摘要
        risk_summary = self._generate_risk_summary(recommendations)
        
        # 生成文件类型摘要
        file_type_summary = self._generate_file_type_summary(valid_files)
        
        # 计算耗时
        duration = time.time() - start_time
        
        return AnalysisResult(
            recommendations=recommendations,
            total_potential_savings=total_savings,
            analysis_time=datetime.now(),
            duration_seconds=duration,
            risk_summary=risk_summary,
            file_type_summary=file_type_summary,
            warnings=[]
        )
    
    def analyze_streaming(
        self, 
        files: List[FileInfo], 
        callback: Optional[Any] = None
    ) -> Generator[Dict, None, None]:
        """
        流式分析文件列表
        
        Args:
            files: 文件信息列表
            callback: 回调函数，用于接收进度更新
            
        Yields:
            Dict: 分析结果项
        """
        valid_files = self.validate_files(files)
        
        if not valid_files:
            return
        
        try:
            yield from self._analyze_with_llm_streaming(valid_files, callback)
        except Exception as e:
            # 降级到规则引擎
            print(f"LLM streaming analysis failed, falling back to rule engine: {e}")
            recommendations, _ = self._rule_engine.analyze_files(valid_files)
            for rec in recommendations:
                yield self._recommendation_to_dict(rec)
    
    def _analyze_with_llm(self, files: List[FileInfo]) -> List[DeletionRecommendation]:
        """
        使用LLM分析文件
        
        Args:
            files: 文件信息列表
            
        Returns:
            List[DeletionRecommendation]: 删除建议列表
        """
        system_prompt = SYSTEM_PROMPT_ZH if self.language == "zh" else SYSTEM_PROMPT_EN
        user_message = self._create_user_message(files)
        
        for attempt in range(self.max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.2,
                    max_tokens=8000,
                    timeout=self.timeout
                )
                
                content = response.choices[0].message.content
                return self._parse_llm_response(content, files)
                
            except AuthenticationError:
                # 不可重试异常：认证失败，直接抛出
                raise
            except (Timeout, ConnectionError) as e:
                # 可重试异常：超时/连接错误
                if attempt == self.max_retries - 1:
                    raise
                # 指数退避 + random jitter 防止 thundering herd
                base_delay = 2 ** attempt
                jitter = random.uniform(0, base_delay * 0.5)
                delay = base_delay + jitter
                print(f"Attempt {attempt + 1} failed (retryable), retrying in {delay:.1f}s: {e}")
                time.sleep(delay)
            except APIError as e:
                # API 错误：检查是否可重试
                if attempt == self.max_retries - 1:
                    raise
                # 某些 API 错误可能可重试（如 429 限流）
                if hasattr(e, 'status_code') and e.status_code == 429:
                    base_delay = 2 ** attempt
                    jitter = random.uniform(0, base_delay * 0.5)
                    delay = base_delay + jitter
                    print(f"Attempt {attempt + 1} failed (rate limited), retrying in {delay:.1f}s: {e}")
                    time.sleep(delay)
                else:
                    # 其他 API 错误不重试
                    raise
            except Exception as e:
                # 未知异常：不重试
                raise
        
        return []
    
    def _analyze_with_llm_streaming(
        self, 
        files: List[FileInfo], 
        callback: Optional[Any] = None
    ) -> Generator[Dict, None, None]:
        """
        使用LLM流式分析文件
        
        Args:
            files: 文件信息列表
            callback: 回调函数
            
        Yields:
            Dict: 分析结果项
        """
        system_prompt = SYSTEM_PROMPT_ZH if self.language == "zh" else SYSTEM_PROMPT_EN
        user_message = self._create_user_message(files)
        
        self._is_streaming = True
        self._json_parser.clear()
        
        try:
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.2,
                max_tokens=8000,
                stream=True,
                timeout=self.timeout
            )
            
            self._current_stream = stream
            
            for chunk in stream:
                if not self._is_streaming:
                    break
                
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    new_objects = self._json_parser.feed(token)
                    
                    for obj in new_objects:
                        result = self._convert_llm_object(obj, files)
                        if result:
                            yield result
                            
                            if callback:
                                callback(result)
            
            # 处理剩余数据
            remaining = self._json_parser.flush()
            for obj in remaining:
                result = self._convert_llm_object(obj, files)
                if result:
                    yield result
                    
                    if callback:
                        callback(result)
                        
        finally:
            self._is_streaming = False
            self._current_stream = None
    
    def _create_user_message(self, files: List[FileInfo]) -> str:
        """
        创建用户消息
        
        Args:
            files: 文件信息列表
            
        Returns:
            str: 格式化的用户消息
        """
        # 转换为LLM需要的格式
        files_data = []
        for file in files:
            files_data.append({
                "file_path": str(file.path),
                "size_mb": round(file.size / (1024 * 1024), 2),
                "modified_time": file.modified_time.isoformat() if file.modified_time else None,
                "extension": file.extension
            })
        
        files_json = json.dumps(files_data, indent=2, ensure_ascii=False)
        total_size_mb = sum(f.size for f in files) / (1024 * 1024)
        
        if self.language == "zh":
            return (
                f"分析以下 {len(files)} 个来自磁盘扫描的大文件。\n"
                f"总大小: {total_size_mb:.1f} MB\n\n"
                f"文件列表（按大小降序排列）:\n{files_json}"
            )
        else:
            return (
                f"Analyze these {len(files)} largest files from a disk scan.\n"
                f"Total size: {total_size_mb:.1f} MB\n\n"
                f"Files (sorted by size, descending):\n{files_json}"
            )
    
    def _parse_llm_response(
        self, 
        content: str, 
        original_files: List[FileInfo]
    ) -> List[DeletionRecommendation]:
        """
        解析LLM响应
        
        Args:
            content: LLM响应内容
            original_files: 原始文件列表
            
        Returns:
            List[DeletionRecommendation]: 删除建议列表
        """
        # 使用JSON解析器解析响应
        parser = StreamingJsonParser()
        objects = parser.parse_complete_json(content)
        
        if not objects or not isinstance(objects, list):
            # 尝试直接解析
            try:
                # 清理可能的markdown格式
                cleaned = content.strip()
                if cleaned.startswith('```json'):
                    cleaned = cleaned[7:]
                elif cleaned.startswith('```'):
                    cleaned = cleaned[3:]
                if cleaned.endswith('```'):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                
                objects = json.loads(cleaned)
            except json.JSONDecodeError:
                return []
        
        if not isinstance(objects, list):
            return []
        
        return [
            rec for obj in objects 
            if (rec := self._convert_llm_object_to_recommendation(obj, original_files)) is not None
        ]
    
    def _convert_llm_object(
        self, 
        obj: Dict, 
        original_files: List[FileInfo]
    ) -> Optional[Dict]:
        """
        将LLM返回的对象转换为标准格式
        
        Args:
            obj: LLM返回的对象
            original_files: 原始文件列表
            
        Returns:
            Optional[Dict]: 转换后的结果，失败返回None
        """
        try:
            file_path = obj.get("file_path", "")
            size_mb = obj.get("size_mb", 0)
            reason = obj.get("reason", "")
            risk_level = obj.get("risk_level", "Medium")
            
            # 查找对应的原始文件
            file_info = self._find_file_info(file_path, original_files)
            if not file_info:
                # 创建一个临时的FileInfo
                from pathlib import Path
                file_info = FileInfo(
                    path=Path(file_path),
                    size=int(size_mb * 1024 * 1024),
                    modified_time=datetime.now()
                )
            
            # 转换风险等级
            risk = self._parse_risk_level(risk_level)
            
            return {
                "file_path": file_path,
                "size_mb": size_mb,
                "reason": reason,
                "risk_level": risk.value,
                "risk_label": risk.name,
                "file_info": file_info
            }
            
        except Exception as e:
            print(f"Error converting LLM object: {e}")
            return None
    
    def _convert_llm_object_to_recommendation(
        self, 
        obj: Dict, 
        original_files: List[FileInfo]
    ) -> Optional[DeletionRecommendation]:
        """
        将LLM返回的对象转换为DeletionRecommendation
        
        Args:
            obj: LLM返回的对象
            original_files: 原始文件列表
            
        Returns:
            Optional[DeletionRecommendation]: 删除建议，失败返回None
        """
        result = self._convert_llm_object(obj, original_files)
        if not result:
            return None
        
        return DeletionRecommendation(
            file=result["file_info"],
            reason=result["reason"],
            risk_level=result["risk_level"],
            confidence=0.8,  # 默认置信度
            potential_savings=result["file_info"].size
        )
    
    def _recommendation_to_dict(self, rec: DeletionRecommendation) -> Dict:
        """
        将DeletionRecommendation转换为字典
        
        Args:
            rec: 删除建议
            
        Returns:
            Dict: 字典格式
        """
        return {
            "file_path": str(rec.file.path),
            "size_mb": round(rec.file.size / (1024 * 1024), 2),
            "reason": rec.reason,
            "risk_level": rec.risk_level.value,
            "risk_label": rec.risk_level.name,
            "confidence": rec.confidence,
            "file_info": rec.file
        }
    
    def _find_file_info(self, file_path: str, files: List[FileInfo]) -> Optional[FileInfo]:
        """
        在文件列表中查找匹配的文件
        
        Args:
            file_path: 文件路径
            files: 文件列表
            
        Returns:
            Optional[FileInfo]: 匹配的文件信息，未找到返回None
        """
        # 标准化路径
        normalized_path = file_path.replace("/", "\\").lower()
        
        for file in files:
            if str(file.path).replace("/", "\\").lower() == normalized_path:
                return file
        
        # 尝试部分匹配
        for file in files:
            if normalized_path in str(file.path).replace("/", "\\").lower():
                return file
        
        return None
    
    def _parse_risk_level(self, risk_str: str) -> RiskLevel:
        """
        解析风险等级字符串
        
        Args:
            risk_str: 风险等级字符串
            
        Returns:
            RiskLevel: 风险等级枚举
        """
        risk_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL
        }
        
        normalized = risk_str.lower().strip()
        return risk_map.get(normalized, RiskLevel.MEDIUM)
    
    def _generate_risk_summary(self, recommendations: List[DeletionRecommendation]) -> Dict[RiskLevel, int]:
        """
        生成风险摘要
        
        Args:
            recommendations: 删除建议列表
            
        Returns:
            Dict[RiskLevel, int]: 风险等级统计
        """
        summary = {level: 0 for level in RiskLevel}
        for rec in recommendations:
            summary[rec.risk_level] += 1
        return summary
    
    def _generate_file_type_summary(self, files: List[FileInfo]) -> Dict[str, int]:
        """
        生成文件类型摘要
        
        Args:
            files: 文件列表
            
        Returns:
            Dict[str, int]: 文件类型统计
        """
        summary = {}
        for file in files:
            ext = file.extension or "无扩展名"
            summary[ext] = summary.get(ext, 0) + 1
        return summary
    
    def get_analysis_rules(self) -> List[str]:
        """
        获取分析规则列表
        
        Returns:
            List[str]: 规则描述列表
        """
        return [
            "LLM分析规则",
            "基于大语言模型的智能文件分析",
            f"模型: {self.model}",
            f"语言: {self.language}",
            "支持流式JSON解析",
            "自动降级到规则引擎"
        ]
    
    def stop_streaming(self):
        """停止流式分析"""
        self._is_streaming = False
        if self._current_stream:
            try:
                # 添加超时保护，防止 close() 阻塞
                close_timeout = 5.0  # 5秒超时
                
                def close_stream():
                    try:
                        self._current_stream.close()
                    except Exception as e:
                        print(f"Warning: error in close_stream thread: {e}")
                
                close_thread = threading.Thread(target=close_stream, daemon=True)
                close_thread.start()
                close_thread.join(timeout=close_timeout)
                
                if close_thread.is_alive():
                    print(f"Warning: stream.close() timed out after {close_timeout}s")
                    
            except Exception as e:
                print(f"Warning: error closing stream: {e}")
    
    @property
    def is_streaming(self) -> bool:
        """是否正在流式分析"""
        return self._is_streaming