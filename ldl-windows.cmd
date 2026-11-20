@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ldl-windows.ps1" %*
exit /b %ERRORLEVEL%
