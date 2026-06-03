#!/usr/bin/env python3
"""Test module imports"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.scanner import WizTreeScanner, PathValidator, DeepSearcher
    print("[OK] Scanner module imported successfully")
except ImportError as e:
    print(f"[FAIL] Scanner module import failed: {e}")

try:
    from src.analyzer import LLMAnalyzer, RuleEngine
    print("[OK] Analyzer module imported successfully")
except ImportError as e:
    print(f"[FAIL] Analyzer module import failed: {e}")

try:
    from src.safety import ComprehensiveSafetyManager
    print("[OK] Safety module imported successfully")
except ImportError as e:
    print(f"[FAIL] Safety module import failed: {e}")

try:
    from src.models import FileInfo, ScanResult, AnalysisResult
    print("[OK] Models module imported successfully")
except ImportError as e:
    print(f"[FAIL] Models module import failed: {e}")

try:
    from src.ui import MainWindow
    print("[OK] UI module imported successfully")
except ImportError as e:
    print(f"[FAIL] UI module import failed: {e}")

print("\nTesting tkinter availability...")
try:
    import tkinter
    print("[OK] tkinter is available")
except ImportError as e:
    print(f"[FAIL] tkinter is not available: {e}")
    print("  Note: GUI features require tkinter to be installed")

print("\nTesting customtkinter availability...")
try:
    import customtkinter
    print("[OK] customtkinter is available")
except ImportError as e:
    print(f"[FAIL] customtkinter is not available: {e}")

print("\nTest completed.")