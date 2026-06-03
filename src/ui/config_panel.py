"""配置面板模块"""
import customtkinter as ctk

class ConfigPanel(ctk.CTkFrame):
    """配置面板类"""
    
    def __init__(self, master):
        super().__init__(master, width=320, corner_radius=10)
        
    def get_scan_config(self) -> dict:
        """获取扫描配置"""
        return {}
        
    def get_api_config(self) -> dict:
        """获取API配置"""
        return {}
