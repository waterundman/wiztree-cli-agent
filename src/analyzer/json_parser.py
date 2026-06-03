import json
from typing import List, Tuple, Optional, Any


class StreamingJsonParser:
    """
    流式JSON解析器
    从LLM流式响应中提取完整JSON对象
    """
    
    def __init__(self):
        self.buffer = ""
        self.objects = []
    
    def feed(self, chunk: str) -> List[dict]:
        """
        喂入新的数据块，返回解析出的完整JSON对象
        
        Args:
            chunk: 新的数据块
            
        Returns:
            List[dict]: 本次解析出的JSON对象列表
        """
        self.buffer += chunk
        new_objects, self.buffer = self._extract_streaming_json(self.buffer)
        self.objects.extend(new_objects)
        return new_objects
    
    def get_all_objects(self) -> List[dict]:
        """
        获取所有已解析的对象
        
        Returns:
            List[dict]: 所有已解析的JSON对象
        """
        return self.objects.copy()
    
    def flush(self) -> List[dict]:
        """
        处理缓冲区中的剩余数据，返回解析出的对象
        
        Returns:
            List[dict]: 解析出的JSON对象
        """
        remaining_objects = []
        if self.buffer.strip():
            # 尝试修复不完整的JSON
            fixed_buffer = self._try_fix_json(self.buffer)
            remaining_objects, self.buffer = self._extract_streaming_json(fixed_buffer)
            self.objects.extend(remaining_objects)
        return remaining_objects
    
    def clear(self):
        """清空解析器状态"""
        self.buffer = ""
        self.objects = []
    
    def _extract_streaming_json(self, buffer: str) -> Tuple[List[dict], str]:
        """
        从缓冲区中提取完整的JSON对象
        
        Args:
            buffer: 输入缓冲区
            
        Returns:
            Tuple[List[dict], str]: (解析出的对象列表, 剩余缓冲区)
        """
        objects = []
        pos = 0
        
        while pos < len(buffer):
            # 跳过markdown代码块标记
            pos = self._skip_markdown_fences(buffer, pos)
            if pos >= len(buffer):
                break
            
            idx = buffer.find('{', pos)
            if idx == -1:
                break
            
            end = self._find_json_object_end(buffer, idx)
            if end == -1:
                break
            
            raw = buffer[idx:end + 1]
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict) and "file_path" in obj:
                    objects.append(obj)
            except json.JSONDecodeError:
                pass
            
            pos = end + 1
        
        remaining = buffer[pos:]
        return objects, remaining
    
    def _find_json_object_end(self, text: str, start: int) -> int:
        """
        查找JSON对象的结束位置
        
        Args:
            text: 输入文本
            start: 开始位置（'{'的位置）
            
        Returns:
            int: 结束位置（'}'的位置），未找到返回-1
        """
        depth = 0
        in_str = False
        esc = False
        
        for i in range(start, len(text)):
            c = text[i]
            
            if esc:
                esc = False
                continue
            
            if c == '\\':
                esc = True
                continue
            
            if c == '"':
                in_str = not in_str
                continue
            
            if in_str:
                continue
            
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
        
        return -1
    
    def _skip_markdown_fences(self, text: str, pos: int) -> int:
        """
        跳过markdown代码块标记
        
        Args:
            text: 输入文本
            pos: 当前位置
            
        Returns:
            int: 跳过标记后的位置
        """
        # 检查是否在代码块标记上
        if pos < len(text) - 3 and text[pos:pos+3] == '```':
            # 找到代码块结束
            end_pos = text.find('```', pos + 3)
            if end_pos != -1:
                return end_pos + 3
            else:
                # 没有找到结束标记，跳过整个剩余部分
                return len(text)
        
        # 检查行首的代码块标记
        if pos == 0 or text[pos-1] == '\n':
            line_start = pos
            line_end = text.find('\n', pos)
            if line_end == -1:
                line_end = len(text)
            
            line = text[line_start:line_end].strip()
            if line.startswith('```') or line == 'json':
                # 跳过这一行
                return line_end + 1 if line_end < len(text) else len(text)
        
        return pos
    
    def _try_fix_json(self, buffer: str) -> str:
        """
        尝试修复不完整的JSON
        
        Args:
            buffer: 可能不完整的JSON字符串
            
        Returns:
            str: 修复后的JSON字符串
        """
        buffer = buffer.strip()
        
        # 如果以逗号结尾，移除逗号
        if buffer.endswith(','):
            buffer = buffer[:-1]
        
        # 如果以[开头但没有]结尾，添加]
        if buffer.startswith('[') and not buffer.endswith(']'):
            # 检查是否有未闭合的对象
            brace_count = 0
            for char in buffer:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
            
            # 如果有未闭合的对象，先闭合它们
            if brace_count > 0:
                buffer += '}' * brace_count
            
            buffer += ']'
        
        # 如果以{开头但没有}结尾，添加}
        elif buffer.startswith('{') and not buffer.endswith('}'):
            buffer += '}'
        
        return buffer
    
    def parse_complete_json(self, text: str) -> Optional[Any]:
        """
        解析完整的JSON文本，自动处理markdown代码块
        
        Args:
            text: JSON文本
            
        Returns:
            Optional[Any]: 解析结果，失败返回None
        """
        # 移除markdown代码块标记
        cleaned = self._clean_markdown_json(text)
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None
    
    def _clean_markdown_json(self, text: str) -> str:
        """
        清理markdown中的JSON代码块
        
        Args:
            text: 包含可能markdown格式的JSON
            
        Returns:
            str: 清理后的JSON字符串
        """
        text = text.strip()
        
        # 移除```json和```标记
        if text.startswith('```json'):
            text = text[7:]
        elif text.startswith('```'):
            text = text[3:]
        
        if text.endswith('```'):
            text = text[:-3]
        
        return text.strip()