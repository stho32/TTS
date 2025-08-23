@echo off
setlocal
pushd "%~dp0" >nul
uv run python tts_app.py
set RC=%ERRORLEVEL%
popd >nul
endlocal
exit /b %RC%

