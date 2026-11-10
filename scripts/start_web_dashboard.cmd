@echo off
setlocal
rem Invoke PowerShell directly; never use the .ps1 Open file association.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_web_dashboard.ps1" %*
exit /b %errorlevel%
