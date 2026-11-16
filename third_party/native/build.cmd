@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 exit /b 1
cl /nologo /O2 /EHsc /std:c++17 /MT /LD "%~dp0DomainCaptureTrace.cpp" /Fo"%~dp0DomainCaptureTrace.obj" /Fe"%~dp0DomainCaptureTrace.dll" /link /INCREMENTAL:NO
exit /b %errorlevel%
