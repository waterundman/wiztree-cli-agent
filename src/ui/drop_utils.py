"""拖放路径解析工具函数（纯函数，无 GUI 依赖）。"""
import os
from typing import List, Optional


def parse_drop_paths(data: str) -> List[str]:
    """
    解析 tkdnd 的 drop data 字符串为路径列表。

    tkdnd 格式：多个路径用空格分隔；含空格的路径用 ``{ }`` 包裹。
    例子：``{C:\\path with space} C:\\other C:\\file.txt``
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


def resolve_drop_target(paths: List[str]) -> Optional[str]:
    """
    从多个拖入路径解析单一目标：
        - 单个目录 → 该目录
        - 单个文件 → 父目录
        - 多个路径 → 公共父目录
    """
    if not paths:
        return None
    if len(paths) == 1:
        p = paths[0]
        if os.path.isdir(p):
            return p
        parent = os.path.dirname(p)
        return parent or p
    try:
        common = os.path.commonpath(paths)
        return common if common else paths[0]
    except ValueError:
        return paths[0] if paths else None
