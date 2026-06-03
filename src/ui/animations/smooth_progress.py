"""平滑进度条动画模块"""
import customtkinter as ctk
from typing import Optional
import math

class SmoothProgressBar(ctk.CTkProgressBar):
    """平滑进度条"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.target_value = 0
        self.current_value = 0
        self.animation_speed = 0.1

    def set_smooth(self, value: float):
        """平滑设置进度"""
        self.target_value = value
        self.animate()

    def animate(self):
        """执行动画"""
        if abs(self.current_value - self.target_value) > 0.01:
            self.current_value += (self.target_value - self.current_value) * self.animation_speed
            self.set(self.current_value)
            self.after(16, self.animate)  # 60fps
        else:
            self.current_value = self.target_value
            self.set(self.current_value)


class SpinnerLabel(ctk.CTkLabel):
    """旋转器标签"""

    FRAMES = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]

    def __init__(self, master, size: int = 14, **kwargs):
        kwargs.pop("size", None)
        kwargs.setdefault("text", "")
        kwargs.setdefault("font", ctk.CTkFont(size=size))
        super().__init__(master, **kwargs)
        self.spinning = False
        self.frame_index = 0

    def start(self, message: str = "加载中"):
        """开始旋转"""
        self.spinning = True
        self.message = message
        self.animate()

    def stop(self):
        """停止旋转"""
        self.spinning = False
        self.configure(text="")

    def animate(self):
        """执行动画"""
        if not self.spinning:
            return
        frame = self.FRAMES[self.frame_index % len(self.FRAMES)]
        self.configure(text=f"{frame} {self.message}")
        self.frame_index += 1
        self.after(120, self.animate)


class FadeInEffect:
    """淡入效果"""
    
    def __init__(self, widget, duration: int = 300):
        self.widget = widget
        self.duration = duration
        self.steps = 20
        self.step_duration = duration // self.steps
        
    def apply(self):
        """应用淡入效果"""
        self.widget.attributes("-alpha", 0)
        self.fade_in(0)
        
    def fade_in(self, step: int):
        """淡入动画"""
        if step <= self.steps:
            alpha = step / self.steps
            self.widget.attributes("-alpha", alpha)
            self.widget.after(self.step_duration, lambda: self.fade_in(step + 1))
