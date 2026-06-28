@echo off
REM ============================================================
REM  ADB 打包脚本 — 生成独立 .exe（无需 Python 环境）
REM  使用方法:
REM    1. pip install pyinstaller pyside6
REM    2. build_exe.bat
REM    输出: dist/ADB_GUI.exe 和 dist/ADB_CLI.exe
REM ============================================================

echo.
echo ========================================
echo   Abaqus Data Bridge — 打包工具
echo ========================================
echo.

REM 检查 PyInstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller not found. Installing...
    pip install pyinstaller
)

REM 检查 PySide6
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] PySide6 not found. GUI will not work.
    echo   Install: pip install pyside6
)

echo [1/3] Cleaning old builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [2/3] Building GUI exe (console-less)...
pyinstaller adb_gui.spec --noconfirm

echo [3/3] Done!
echo.
echo Output:
echo   dist/ADB_GUI.exe  — GUI 桌面应用（双击运行）
echo   dist/ADB_CLI.exe  — 命令行版本（终端运行）
echo.
echo To distribute: just copy the dist/ folder to another computer.
echo.

pause
