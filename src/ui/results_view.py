"""结果视图模块"""
import customtkinter as ctk
import tkinter.ttk as ttk

class ResultsView(ctk.CTkFrame):
    """结果视图类"""
    
    def __init__(self, master):
        super().__init__(master, corner_radius=10)
        
    def populate_results(self, files: list):
        """填充扫描结果"""
        pass
        
    def clear_results(self):
        """清空结果"""
        pass
