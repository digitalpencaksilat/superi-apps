@echo off
REM ============================================================
REM  SUPER-I APP - Windows Portable Setup
REM  Download Python embeddable + pip + dependencies
REM  Tanpa install, tanpa admin
REM ============================================================

setlocal enabledelayedexpansion
set "SUPERI_DIR=%~dp0"
cd /d "%SUPERI_DIR%"

echo.
echo   ============================================
echo     SUPER-I APP - Setup Portable ^(Windows^)
echo   ============================================
echo.
echo   Akan download:
echo     1. Python 3.11 portable ^(~10 MB^)
echo     2. pip ^(installer paket Python^)
echo     3. Dependencies: requests, flask, beautifulsoup4
echo.
echo   Total ~30 MB. Tidak butuh admin.
echo.
pause

REM ============================================================
REM 1. Download Python embeddable
REM ============================================================
set "PY_VERSION=3.11.9"
set "PY_ZIP=python-%PY_VERSION%-embed-amd64.zip"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/%PY_ZIP%"

if exist "%SUPERI_DIR%python\python.exe" (
    echo   [OK] Python portable sudah ada di python\
    goto :install_pip
)

echo.
echo   [1/3] Download Python %PY_VERSION% portable...
powershell -Command "Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_ZIP%' -UseBasicParsing"
if not exist "%PY_ZIP%" (
    echo   [X] Gagal download Python. Cek koneksi internet.
    pause
    exit /b 1
)

echo   [OK] Extract Python ke folder python\...
powershell -Command "Expand-Archive -Path '%PY_ZIP%' -DestinationPath '%SUPERI_DIR%python' -Force"
del "%PY_ZIP%"

REM Aktifkan import site-packages di Python embeddable (default disabled)
REM Cari file python*._pth dan uncomment baris "import site"
for %%f in (python\python*._pth) do (
    powershell -Command "(Get-Content '%%f') -replace '#import site', 'import site' | Set-Content '%%f'"
)
echo   [OK] Python portable siap

:install_pip
REM ============================================================
REM 2. Install pip
REM ============================================================
if exist "%SUPERI_DIR%python\Scripts\pip.exe" (
    echo   [OK] pip sudah terinstall
    goto :install_deps
)

echo.
echo   [2/3] Install pip...
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py' -UseBasicParsing"
"%SUPERI_DIR%python\python.exe" get-pip.py --no-warn-script-location
del get-pip.py
echo   [OK] pip terinstall

:install_deps
REM ============================================================
REM 3. Install dependencies dari requirements.txt
REM ============================================================
echo.
echo   [3/3] Install dependencies ^(requests, flask, beautifulsoup4^)...
"%SUPERI_DIR%python\python.exe" -m pip install -r requirements.txt --no-warn-script-location

if errorlevel 1 (
    echo.
    echo   [X] Install dependencies gagal. Cek pesan error di atas.
    pause
    exit /b 1
)

REM ============================================================
REM 4. Setup config
REM ============================================================
if not exist "%SUPERI_DIR%.superi_config.json" (
    if exist "%SUPERI_DIR%.superi_config.example.json" (
        copy ".superi_config.example.json" ".superi_config.json" >nul
        echo.
        echo   [OK] Config template dibuat di .superi_config.json
        echo   Edit file tersebut untuk isi NIP / password.
    )
)

echo.
echo   ============================================
echo     SETUP SELESAI
echo   ============================================
echo.
echo   Cara pakai:
echo     superi.bat cli           - CLI interaktif ^(setup credentials di sini^)
echo     superi.bat sync          - Sync ke Portal APD
echo     superi.bat web           - Web dashboard
echo.
echo   Atau klik 2x file superi.bat
echo.
pause
endlocal
