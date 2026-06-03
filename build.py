#!/usr/bin/env python3
"""
WizTree CLI Agent 打包脚本
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean_build():
    """清理构建目录"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.pyc', '*.pyo']
    
    for dir_name in dirs_to_clean:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"Cleaning {dir_name}...")
            shutil.rmtree(dir_path)
    
    print("Build directories cleaned.")


def build_exe():
    """构建exe文件"""
    print("Building WizTree CLI Agent...")
    
    # 使用PyInstaller打包
    python_exe = r"C:\Users\wxy\AppData\Local\Programs\Python\Python313\python.exe"
    
    cmd = [
        python_exe, '-m', 'PyInstaller',
        '--onedir',  # 目录模式
        '--console',  # 控制台应用
        '--name', 'WizTreeCLIAgent',
        '--add-data', 'config;config',  # 添加配置文件
        '--add-data', 'README.md;.',  # 添加README
        '--collect-all', 'customtkinter',
        '--hidden-import', 'customtkinter',
        '--hidden-import', 'openai',
        '--hidden-import', 'send2trash',
        '--collect-data', 'matplotlib',
        '--hidden-import', 'matplotlib',
        '--hidden-import', 'squarify',
        '--hidden-import', 'tkinter',
        '--hidden-import', 'sqlite3',
        '--hidden-import', 'src.ui',
        '--hidden-import', 'src.ui.main_window',
        '--hidden-import', 'src.ui.tabs',
        '--hidden-import', 'src.ui.components',
        '--hidden-import', 'src.ui.animations',
        '--hidden-import', 'src.ui.themes',
        '--exclude-module', 'test',
        '--exclude-module', 'tests',
        '--exclude-module', 'pytest',
        '--exclude-module', 'unittest',
        '--exclude-module', 'distutils',
        '--exclude-module', 'setuptools',
        '--exclude-module', 'pip',
        '--exclude-module', 'wheel',
        'app.py'
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Build successful!")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:")
            print(result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print(e.stdout)
        print(e.stderr)
        return False


def create_portable_package():
    """创建便携式包"""
    print("Creating portable package...")
    
    dist_dir = Path('dist')
    package_dir = dist_dir / 'WizTreeCLIAgent_Portable'
    
    # 创建包目录
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    
    # 复制exe文件
    exe_file = dist_dir / 'WizTreeCLIAgent.exe'
    if exe_file.exists():
        shutil.copy(exe_file, package_dir)
        print(f"Copied {exe_file.name}")
    else:
        exe_dir = dist_dir / 'WizTreeCLIAgent'
        if exe_dir.exists():
            shutil.copytree(exe_dir, package_dir / 'WizTreeCLIAgent')
            print(f"Copied {exe_dir.name} directory")
    
    # 复制配置文件
    config_dir = Path('config')
    if config_dir.exists():
        shutil.copytree(config_dir, package_dir / 'config')
        print("Copied config directory")
    
    # 复制文档
    docs_dir = Path('docs')
    if docs_dir.exists():
        shutil.copytree(docs_dir, package_dir / 'docs')
        print("Copied docs directory")
    
    # 复制README
    readme_file = Path('README.md')
    if readme_file.exists():
        shutil.copy(readme_file, package_dir)
        print("Copied README.md")
    
    # 创建启动脚本
    launch_script = package_dir / 'run.bat'
    with open(launch_script, 'w', encoding='utf-8') as f:
        f.write('@echo off\n')
        f.write('echo WizTree CLI Agent\n')
        f.write('echo ================\n')
        f.write('echo.\n')
        f.write('echo Starting application...\n')
        f.write('WizTreeCLIAgent.exe --cli\n')
        f.write('pause\n')
    
    print(f"Created launch script: {launch_script}")
    
    # 创建ZIP包
    zip_file = dist_dir / 'WizTreeCLIAgent_Portable.zip'
    shutil.make_archive(str(zip_file.with_suffix('')), 'zip', dist_dir, 'WizTreeCLIAgent_Portable')
    print(f"Created portable package: {zip_file}")
    
    return True


def create_installer_script():
    """创建安装脚本"""
    print("Creating installer script...")
    
    dist_dir = Path('dist')
    installer_script = dist_dir / 'install.bat'
    
    with open(installer_script, 'w', encoding='utf-8') as f:
        f.write('@echo off\n')
        f.write('echo WizTree CLI Agent Installer\n')
        f.write('echo ==========================\n')
        f.write('echo.\n')
        f.write('set INSTALL_DIR=%PROGRAMFILES%\\WizTreeCLIAgent\n')
        f.write('echo Installing to %INSTALL_DIR%...\n')
        f.write('echo.\n')
        f.write('mkdir "%INSTALL_DIR%" 2>nul\n')
        f.write('if exist WizTreeCLIAgent.exe (\n')
        f.write('  copy WizTreeCLIAgent.exe "%INSTALL_DIR%"\n')
        f.write(') else (\n')
        f.write('  if exist WizTreeCLIAgent (xcopy /E /I /Y WizTreeCLIAgent "%INSTALL_DIR%")\n')
        f.write(')\n')
        f.write('xcopy /E /I config "%INSTALL_DIR%\\config"\n')
        f.write('xcopy /E /I docs "%INSTALL_DIR%\\docs"\n')
        f.write('copy README.md "%INSTALL_DIR%"\n')
        f.write('echo.\n')
        f.write('echo Installation complete!\n')
        f.write('echo.\n')
        f.write('echo To run the application:\n')
        f.write('echo   cd "%INSTALL_DIR%"\n')
        f.write('echo   WizTreeCLIAgent.exe --cli\n')
        f.write('echo.\n')
        f.write('pause\n')
    
    print(f"Created installer script: {installer_script}")
    return True


def main():
    """主函数"""
    print("WizTree CLI Agent Build Script")
    print("=" * 50)
    
    # 清理构建目录
    clean_build()
    
    # 构建exe
    if build_exe():
        # 创建便携式包
        create_portable_package()
        
        # 创建安装脚本
        create_installer_script()
        
        dist_dir = Path('dist')
        print("\n" + "=" * 50)
        print("Build completed successfully!")
        print("\nOutput files:")
        if (dist_dir / 'WizTreeCLIAgent.exe').exists():
            print("  - dist/WizTreeCLIAgent.exe (可执行文件)")
        if (dist_dir / 'WizTreeCLIAgent').exists():
            print("  - dist/WizTreeCLIAgent/ (程序目录)")
        print("  - dist/WizTreeCLIAgent_Portable.zip (便携式包)")
        print("  - dist/install.bat (安装脚本)")
        print("\nUsage:")
        print("  WizTreeCLIAgent.exe --cli")
    else:
        print("\nBuild failed!")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())