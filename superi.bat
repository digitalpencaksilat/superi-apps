@echo off
REM ============================================================
REM  SUPER-I APP - Windows Launcher (Portable, tanpa install)
REM  Usage: superi.bat [cli|sync|web|input] [options]
REM ============================================================

setlocal enabledelayedexpansion
set "SUPERI_DIR=%~dp0"

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
        pause
        exit /b 1
    )
)

REM Set PYTHONPATH ke folder libs (untuk dependencies portable)
if exist "%SUPERI_DIR%libs" (
    set "PYTHONPATH=%SUPERI_DIR%libs;%PYTHONPATH%"
)

cd /d "%SUPERI_DIR%"

if /i "%1"=="cli" (
    echo.
    echo   Menjalankan SUPER-I APP CLI...
    "%PYTHON%" superi_app.py
) else if /i "%1"=="c" (
    "%PYTHON%" superi_app.py
) else if /i "%1"=="web" (
    echo.
    echo   Menjalankan Web Dashboard... Buka: http://localhost:8888
    "%PYTHON%" superi_web.py
) else if /i "%1"=="w" (
    "%PYTHON%" superi_web.py
) else if /i "%1"=="sync" (
    shift
    "%PYTHON%" superi_sync.py %1 %2 %3 %4 %5 %6 %7 %8 %9
) else if /i "%1"=="s" (
    shift
    "%PYTHON%" superi_sync.py %1 %2 %3 %4 %5 %6 %7 %8 %9
) else if /i "%1"=="input" (
    shift
    "%PYTHON%" superi_input.py %1 %2 %3 %4 %5 %6 %7 %8 %9
) else if /i "%1"=="i" (
    shift
    "%PYTHON%" superi_input.py %1 %2 %3 %4 %5 %6 %7 %8 %9
) else (
    echo.
    echo   ============================================
    echo     SUPER-I APP Launcher ^(Windows^)
    echo   ============================================
    echo.
    echo   Usage: superi [command] [options]
    echo.
    echo   Commands:
    echo     cli, c            CLI interaktif
    echo     web, w            Web dashboard ^(http://localhost:8888^)
    echo     sync, s [opts]    Sync data ke Portal APD
    echo     input, i [opts]   Scripting mode
    echo.
    echo   Examples:
    echo     superi cli
    echo     superi sync --type all --jam 09
    echo     superi sync --type penyulang --jam 08-10 --dry-run
    echo.
    echo   Project: %SUPERI_DIR%
    echo.
)

endlocal
