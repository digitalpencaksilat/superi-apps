@echo off
REM ============================================================
REM  SUPER-I APP - Windows Launcher (Portable, tanpa install)
REM  Usage: superi.bat [cli|sync|web|input] [options]
REM ============================================================

setlocal enabledelayedexpansion
set "SUPERI_DIR=%~dp0"
set "SUPERI_CMD=%~1"

REM Cari Python: prioritas portable (python\), lalu venv, lalu system
if exist "%SUPERI_DIR%python\python.exe" (
    set "PYTHON=%SUPERI_DIR%python\python.exe"
) else if exist "%SUPERI_DIR%.venv\Scripts\python.exe" (
    set "PYTHON=%SUPERI_DIR%.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON=python"
    ) else (
        echo.
        echo   [X] Python tidak ditemukan!
        echo   Jalankan setup_windows.bat dulu untuk download Python portable.
        echo.
        if /i not "%SUPERI_CMD%"=="auto" pause
        exit /b 1
    )
)

REM Set PYTHONPATH ke folder libs (untuk dependencies portable)
set "PYTHONPATH=%SUPERI_DIR%;%PYTHONPATH%"
if exist "%SUPERI_DIR%libs" (
    set "PYTHONPATH=%SUPERI_DIR%libs;%PYTHONPATH%"
)

cd /d "%SUPERI_DIR%"

REM Pastikan dependency + modul project bisa di-import sebelum jalan.
REM Ini penting untuk double-click / Task Scheduler Windows.
"%PYTHON%" -c "import sys, os; sys.path.insert(0, os.getcwd()); import requests, flask, bs4, superi_sync, superi_auto" >nul 2>nul
if errorlevel 1 (
    echo.
    echo   Menyiapkan dependency Python...
    "%PYTHON%" -m pip install -r requirements.txt --no-warn-script-location
    if errorlevel 1 (
        echo.
        echo   [X] Dependency gagal diinstall.
        echo   Jalankan setup_windows.bat lalu coba lagi.
        echo.
        if /i not "%SUPERI_CMD%"=="auto" pause
        exit /b 1
    )
    "%PYTHON%" -c "import sys, os; sys.path.insert(0, os.getcwd()); import requests, flask, bs4, superi_sync, superi_auto" >nul 2>nul
    if errorlevel 1 (
        echo.
        echo   [X] Modul SUPER-I belum bisa di-import.
        echo   Pastikan superi.bat dijalankan dari folder project SUPER-I.
        echo   Folder: %SUPERI_DIR%
        echo.
        if /i not "%SUPERI_CMD%"=="auto" pause
        exit /b 1
    )
)

REM Tanpa argumen (double-click) → langsung buka CLI interaktif
if "%1"=="" goto :run_cli

if /i "%1"=="cli" goto :run_cli
if /i "%1"=="c" goto :run_cli
if /i "%1"=="web" (
    echo.
    echo   Menjalankan Web Dashboard... Buka: http://localhost:8888
    "%PYTHON%" superi_web.py
    goto :end
)
if /i "%1"=="w" (
    "%PYTHON%" superi_web.py
    goto :end
)
if /i "%1"=="sync" (
    shift
    "%PYTHON%" superi_sync.py %1 %2 %3 %4 %5 %6 %7 %8 %9
    pause
    goto :end
)
if /i "%1"=="s" (
    shift
    "%PYTHON%" superi_sync.py %1 %2 %3 %4 %5 %6 %7 %8 %9
    pause
    goto :end
)
if /i "%1"=="input" (
    shift
    "%PYTHON%" superi_input.py %1 %2 %3 %4 %5 %6 %7 %8 %9
    pause
    goto :end
)
if /i "%1"=="i" (
    shift
    "%PYTHON%" superi_input.py %1 %2 %3 %4 %5 %6 %7 %8 %9
    pause
    goto :end
)
if /i "%1"=="auto" (
    shift
    "%PYTHON%" superi_auto.py %1 %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)
if /i "%1"=="a" (
    shift
    "%PYTHON%" superi_auto.py %1 %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

REM Help
echo.
echo   ============================================
echo     SUPER-I APP Launcher ^(Windows^)
echo   ============================================
echo.
echo   Usage: superi [command] [options]
echo.
echo   Commands:
echo     ^(tanpa argumen^)   CLI interaktif ^(default - cocok untuk double-click^)
echo     cli, c            CLI interaktif
echo     web, w            Web dashboard ^(http://localhost:8888^)
echo     sync, s [opts]    Sync data ke Portal APD
echo     auto, a [opts]    Auto input + sync ^(untuk Task Scheduler^)
echo     input, i [opts]   Scripting mode
echo.
echo   Examples:
echo     superi cli
echo     superi sync --type all --jam 09
echo     superi sync --type penyulang --jam 08-10 --dry-run
echo     superi auto --status
echo     superi auto --dry-run --jam 23
echo.
echo   Project: %SUPERI_DIR%
echo   Python : %PYTHON%
echo.
pause
goto :end

:run_cli
echo.
echo   Menjalankan SUPER-I APP CLI...
"%PYTHON%" superi_app.py
if errorlevel 1 (
    echo.
    echo   [X] SUPER-I APP berhenti dengan error. Cek pesan di atas.
    echo.
    pause
)
goto :end

:end
endlocal
