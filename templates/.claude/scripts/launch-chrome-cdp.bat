@echo off
REM ICM v3.6.0 — preview loop helper.
REM Lança Chrome com remote-debugging-port=9222 + user-data-dir isolado.
REM Doc: references/preview-loop-protocol.md
REM Uso: scripts\launch-chrome-cdp.bat [URL]

setlocal

set PROFILE_DIR=%CD%\.icm-chrome-profile
set TARGET_URL=%~1
if "%TARGET_URL%"=="" set TARGET_URL=http://localhost:3000

set CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" (
    echo Chrome nao encontrado em ProgramFiles. Defina CHROME=^<path^> manualmente.
    exit /b 1
)

if not exist "%PROFILE_DIR%" mkdir "%PROFILE_DIR%"

echo Lancando Chrome com CDP em :9222
echo   profile: %PROFILE_DIR%
echo   url:     %TARGET_URL%

start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%PROFILE_DIR%" "%TARGET_URL%"

endlocal
