@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /EHsc /O2 /MT /Fe:"%~dp0TraceVerify.exe" /Fo:"%~dp0TraceVerify.obj" "%~dp0TraceVerify.cpp" advapi32.lib
exit /b %errorlevel%
