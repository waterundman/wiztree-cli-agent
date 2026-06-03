import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FilePreview:
    """文件预览信息"""
    path: str
    name: str
    size: int
    size_formatted: str
    file_type: str
    is_dir: bool
    last_modified: Optional[str] = None


class ConfirmDialog:
    """删除确认对话框"""
    
    def __init__(self, show_size_stats: bool = True, show_file_list: bool = True):
        """
        初始化确认对话框
        
        Args:
            show_size_stats: 是否显示大小统计
            show_file_list: 是否显示文件列表
        """
        self.show_size_stats = show_size_stats
        self.show_file_list = show_file_list
    
    def _format_size(self, size_bytes: int) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 字节大小
            
        Returns:
            格式化后的大小字符串
        """
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.2f} {units[unit_index]}"
    
    def _get_file_type(self, file_path: str) -> str:
        """
        获取文件类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件类型描述
        """
        _, ext = os.path.splitext(file_path)
        if ext:
            return ext.upper()[1:]  # 移除点号并大写
        return "未知"
    
    def _create_file_preview(self, file_path: str) -> FilePreview:
        """
        创建文件预览
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件预览对象
        """
        name = os.path.basename(file_path)
        is_dir = os.path.isdir(file_path)
        
        # 获取文件大小
        size = 0
        last_modified = None
        
        try:
            if os.path.exists(file_path):
                stat_result = os.stat(file_path)
                size = stat_result.st_size if not is_dir else 0
                last_modified = datetime.fromtimestamp(stat_result.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        except (OSError, PermissionError):
            pass
        
        # 计算目录大小
        if is_dir:
            try:
                total_size = 0
                for dirpath, dirnames, filenames in os.walk(file_path):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            total_size += os.path.getsize(filepath)
                        except (OSError, PermissionError):
                            pass
                size = total_size
            except (OSError, PermissionError):
                pass
        
        return FilePreview(
            path=file_path,
            name=name,
            size=size,
            size_formatted=self._format_size(size),
            file_type="文件夹" if is_dir else self._get_file_type(file_path),
            is_dir=is_dir,
            last_modified=last_modified
        )
    
    def _calculate_statistics(self, previews: List[FilePreview]) -> Dict[str, Any]:
        """
        计算统计信息
        
        Args:
            previews: 文件预览列表
            
        Returns:
            统计信息字典
        """
        total_files = 0
        total_dirs = 0
        total_size = 0
        
        file_types = {}
        
        for preview in previews:
            if preview.is_dir:
                total_dirs += 1
            else:
                total_files += 1
            
            total_size += preview.size
            
            # 统计文件类型
            file_type = preview.file_type
            if file_type not in file_types:
                file_types[file_type] = {'count': 0, 'size': 0}
            file_types[file_type]['count'] += 1
            file_types[file_type]['size'] += preview.size
        
        return {
            'total_files': total_files,
            'total_dirs': total_dirs,
            'total_size': total_size,
            'total_size_formatted': self._format_size(total_size),
            'file_types': file_types,
            'total_items': len(previews)
        }
    
    def format_confirmation_message(self, file_paths: List[str], 
                                  custom_message: Optional[str] = None) -> str:
        """
        格式化确认消息
        
        Args:
            file_paths: 文件路径列表
            custom_message: 自定义消息
            
        Returns:
            格式化的确认消息
        """
        if not file_paths:
            return "没有选择要删除的文件。"
        
        # 创建文件预览
        previews = [self._create_file_preview(path) for path in file_paths]
        
        # 计算统计信息
        stats = self._calculate_statistics(previews)
        
        # 构建消息
        lines = []
        
        # 标题
        lines.append("=" * 60)
        lines.append("文件删除确认")
        lines.append("=" * 60)
        
        # 自定义消息
        if custom_message:
            lines.append("")
            lines.append(custom_message)
            lines.append("")
        
        # 统计信息
        if self.show_size_stats:
            lines.append("📊 统计信息:")
            lines.append(f"   • 总项目数: {stats['total_items']}")
            
            if stats['total_files'] > 0:
                lines.append(f"   • 文件数量: {stats['total_files']}")
            
            if stats['total_dirs'] > 0:
                lines.append(f"   • 文件夹数量: {stats['total_dirs']}")
            
            lines.append(f"   • 总大小: {stats['total_size_formatted']}")
            
            # 文件类型统计
            if stats['file_types']:
                lines.append("")
                lines.append("📁 文件类型:")
                for file_type, type_stats in stats['file_types'].items():
                    size_formatted = self._format_size(type_stats['size'])
                    lines.append(f"   • {file_type}: {type_stats['count']}个 ({size_formatted})")
            
            lines.append("")
        
        # 文件列表
        if self.show_file_list:
            lines.append("📋 文件列表:")
            lines.append("-" * 60)
            
            # 限制显示数量
            max_display = 20
            displayed_previews = previews[:max_display]
            
            for i, preview in enumerate(displayed_previews, 1):
                # 构建文件信息
                type_icon = "📁" if preview.is_dir else "📄"
                size_info = f" ({preview.size_formatted})" if preview.size > 0 else ""
                
                lines.append(f"{i:3d}. {type_icon} {preview.name}{size_info}")
                
                # 显示完整路径（缩进）
                if preview.path != preview.name:
                    lines.append(f"      路径: {preview.path}")
                
                # 显示修改时间
                if preview.last_modified:
                    lines.append(f"      修改时间: {preview.last_modified}")
            
            # 如果还有更多文件
            if len(previews) > max_display:
                remaining = len(previews) - max_display
                lines.append(f"\n   ... 还有 {remaining} 个文件未显示")
            
            lines.append("-" * 60)
        
        # 警告信息
        lines.append("")
        lines.append("⚠️  警告:")
        lines.append("   • 删除的文件无法恢复")
        lines.append("   • 请仔细检查要删除的文件")
        lines.append("   • 系统文件和重要数据请勿删除")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def get_confirmation(self, file_paths: List[str], 
                        custom_message: Optional[str] = None) -> bool:
        """
        获取用户确认（控制台版本）
        
        Args:
            file_paths: 文件路径列表
            custom_message: 自定义消息
            
        Returns:
            用户是否确认删除
        """
        message = self.format_confirmation_message(file_paths, custom_message)
        print(message)
        
        while True:
            response = input("\n确认删除这些文件吗？(y/N): ").strip().lower()
            
            if response in ['y', 'yes', '是']:
                return True
            elif response in ['n', 'no', '否', '']:
                return False
            else:
                print("请输入 y (是) 或 n (否)")
    
    def get_confirmation_with_options(self, file_paths: List[str],
                                    custom_message: Optional[str] = None) -> Dict[str, Any]:
        """
        获取用户确认（带选项）
        
        Args:
            file_paths: 文件路径列表
            custom_message: 自定义消息
            
        Returns:
            确认结果字典
        """
        message = self.format_confirmation_message(file_paths, custom_message)
        print(message)
        
        print("\n选项:")
        print("  1. 确认删除所有文件")
        print("  2. 选择性删除")
        print("  3. 取消操作")
        
        while True:
            choice = input("\n请选择 (1/2/3): ").strip()
            
            if choice == '1':
                return {
                    'confirmed': True,
                    'action': 'delete_all',
                    'selected_files': file_paths
                }
            elif choice == '2':
                # 选择性删除
                selected_files = []
                for i, file_path in enumerate(file_paths, 1):
                    while True:
                        response = input(f"删除 {os.path.basename(file_path)}? (y/n): ").strip().lower()
                        if response in ['y', 'yes']:
                            selected_files.append(file_path)
                            break
                        elif response in ['n', 'no']:
                            break
                        else:
                            print("请输入 y 或 n")
                
                return {
                    'confirmed': len(selected_files) > 0,
                    'action': 'delete_selected',
                    'selected_files': selected_files
                }
            elif choice == '3':
                return {
                    'confirmed': False,
                    'action': 'cancelled',
                    'selected_files': []
                }
            else:
                print("请输入 1、2 或 3")
    
    def create_summary_report(self, file_paths: List[str]) -> str:
        """
        创建摘要报告
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            摘要报告字符串
        """
        previews = [self._create_file_preview(path) for path in file_paths]
        stats = self._calculate_statistics(previews)
        
        report_lines = [
            "删除操作摘要",
            "=" * 40,
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"项目数量: {stats['total_items']}",
            f"总大小: {stats['total_size_formatted']}",
            "",
            "详细统计:",
            f"  - 文件: {stats['total_files']}",
            f"  - 文件夹: {stats['total_dirs']}",
        ]
        
        if stats['file_types']:
            report_lines.append("")
            report_lines.append("文件类型分布:")
            for file_type, type_stats in stats['file_types'].items():
                size_formatted = self._format_size(type_stats['size'])
                report_lines.append(f"  - {file_type}: {type_stats['count']}个 ({size_formatted})")
        
        return "\n".join(report_lines)