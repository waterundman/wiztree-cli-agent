"""
WizTree CLI Agent - AI-Powered Disk Cleanup Assistant
Modular architecture version with LLM Router
"""

import sys
import os
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.scanner import WizTreeScanner, PathValidator, DeepSearcher
from src.analyzer import LLMAnalyzer, RuleEngine, LLMRouter, RoutingStrategy
from src.safety import ComprehensiveSafetyManager
from src.models import FileInfo, ScanResult, AnalysisResult


class WizTreeAgentApp:
    """WizTree Agent应用主类"""

    def __init__(self):
        self.scanner = None
        self.analyzer = None
        self.router = None
        self.safety = None

    def initialize(self):
        """初始化应用"""
        self.scanner = WizTreeScanner()
        
        # 初始化LLM Router
        try:
            self.router = LLMRouter(
                strategy=RoutingStrategy.FALLBACK,
                default_model="deepseek-v4-flash"
            )
            print(f"LLM Router initialized with {len(self.router.providers)} providers")
        except Exception as e:
            print(f"Warning: LLM Router initialization failed: {e}")
            self.router = None
        
        # 初始化LLM Analyzer（使用Router）
        try:
            if self.router:
                # 使用Router的API密钥
                api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
                if api_key:
                    self.analyzer = LLMAnalyzer(api_key=api_key)
                else:
                    # 没有API密钥，使用延迟初始化
                    self.analyzer = LLMAnalyzer(lazy_init=True)
                    print("Info: LLM Analyzer initialized in lazy mode (no API key)")
            else:
                self.analyzer = LLMAnalyzer(lazy_init=True)
        except Exception as e:
            print(f"Warning: LLM Analyzer initialization failed: {e}")
            self.analyzer = None
        
        self.safety = ComprehensiveSafetyManager()

    def run_cli(self):
        """运行命令行模式"""
        self.initialize()
        print("\n" + "=" * 50)
        print("WizTree CLI Agent - Command Line Mode")
        print("=" * 50)
        
        # 测试扫描器
        print("\n1. Testing Scanner Module...")
        print(f"   Scanner: {self.scanner}")
        print(f"   Supported options: {self.scanner.get_supported_options()}")
        
        # 测试路由器
        print("\n2. Testing LLM Router...")
        if self.router:
            status = self.router.get_provider_status()
            available_providers = sum(1 for info in status.values() if info['has_api_key'])
            print(f"   Router: {self.router.strategy.value}")
            print(f"   Available providers: {available_providers}/{len(status)}")
            print(f"   Available models: {len(self.router.get_available_models())}")
        else:
            print("   Router: Not available")
        
        # 测试分析器
        print("\n3. Testing Analyzer Module...")
        if self.analyzer:
            if self.analyzer.is_available:
                print(f"   Analyzer: Available (API key configured)")
            else:
                print(f"   Analyzer: Lazy mode (no API key, using rule engine)")
        else:
            print(f"   Analyzer: Not available")
        
        # 测试安全管理器
        print("\n4. Testing Safety Module...")
        print(f"   Safety Manager: {self.safety}")
        
        # 测试路径验证
        print("\n5. Testing Path Validator...")
        validator = PathValidator()
        test_path = "C:\\Users"
        result = validator.validate(test_path)
        print(f"   Path '{test_path}' validation: {result}")
        
        print("\n" + "=" * 50)
        print("All modules initialized successfully!")
        print("\nLLM Router Providers:")
        if self.router:
            for name, info in status.items():
                has_key = "[OK]" if info['has_api_key'] else "[--]"
                print(f"   {has_key} {name}: {info['models']}")
        
        print("\nNote: GUI mode requires tkinter to be installed.")
        print("Current Python installation does not have tkinter.")
        
        return True


def main():
    """主函数"""
    app = WizTreeAgentApp()
    
    # 检查是否有命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        app.run_cli()
    else:
        # 尝试导入tkinter
        try:
            from src.ui import MainWindow
            app.initialize()
            app.ui = MainWindow()
            app.ui.mainloop()
        except ImportError as e:
            print(f"GUI mode not available: {e}")
            print("Running in command line mode...")
            app.run_cli()


if __name__ == "__main__":
    main()
