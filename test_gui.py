#!/usr/bin/env python3
"""
测试GUI是否能正常工作
"""

import sys
import os

# 测试tkinter
try:
    import tkinter as tk
    print("[OK] tkinter is available")
except ImportError as e:
    print(f"[FAIL] tkinter not available: {e}")
    sys.exit(1)

# 测试customtkinter
try:
    import customtkinter as ctk
    print("[OK] customtkinter is available")
except ImportError as e:
    print(f"[FAIL] customtkinter not available: {e}")
    sys.exit(1)

# 创建简单的测试窗口
def test_gui():
    print("\nTesting GUI creation...")
    
    # 创建主窗口
    root = ctk.CTk()
    root.title("WizTree CLI Agent - GUI Test")
    root.geometry("400x300")
    
    # 添加标签
    label = ctk.CTkLabel(root, text="GUI Test Successful!", font=("Arial", 20))
    label.pack(pady=50)
    
    # 添加按钮
    def on_click():
        print("Button clicked!")
        root.destroy()
    
    button = ctk.CTkButton(root, text="Close", command=on_click)
    button.pack(pady=20)
    
    print("[OK] GUI window created")
    print("Close the window to continue...")
    
    # 运行主循环
    root.mainloop()
    
    print("[OK] GUI test completed")

if __name__ == "__main__":
    test_gui()