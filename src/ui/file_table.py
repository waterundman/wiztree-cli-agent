"""文件操作表模块"""
import customtkinter as ctk
import tkinter.ttk as ttk

class FileTable(ctk.CTkFrame):
    """文件操作表类"""
    
    def __init__(self, master):
        super().__init__(master, corner_radius=10)
        
    def add_files(self, files: list):
        """添加文件到表格"""
        pass
        
    def get_selected_files(self) -> list:
        """获取选中的文件"""
        return []
        
    def clear(self):
        """清空表格"""
        pass
