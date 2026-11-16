@echo off
setlocal
cd /d "%~dp0"
where cl >nul 2>nul
if errorlevel 1 exit /b 1
if not exist "..\..\.build\overlay" mkdir "..\..\.build\overlay"
rc /nologo /fo"..\..\.build\overlay\brand.res" brand.rc
if errorlevel 1 exit /b %errorlevel%
cl /nologo /std:c++17 /utf-8 /O2 /W4 /EHsc /MT /DUNICODE /D_UNICODE /D_WIN32_WINNT=0x0A00 overlay.cpp "..\..\.build\overlay\brand.res" /Fo"..\..\.build\overlay\overlay.obj" /Fe"..\..\.build\overlay\OverlayWindow.exe" /link /SUBSYSTEM:WINDOWS /MANIFEST:EMBED /MANIFESTINPUT:app.manifest user32.lib gdi32.lib gdiplus.lib shell32.lib dwmapi.lib d3d11.lib dxgi.lib dcomp.lib
exit /b %errorlevel%
