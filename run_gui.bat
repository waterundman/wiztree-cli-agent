@echo off
echo WizTree CLI Agent Launcher
echo ==========================
echo.
echo Starting WizTree CLI Agent with GUI...
echo.

set PYTHON_EXE=C:\Users\wxy\AppData\Local\Programs\Python\Python313\python.exe

if not exist "%PYTHON_EXE%" (
    echo Error: Python 3.13 not found!
    echo Please install Python 3.13 from Microsoft Store.
    pause
    exit /b 1
)

echo Using Python: %PYTHON_EXE%
echo.

"%PYTHON_EXE%" app.py

pause