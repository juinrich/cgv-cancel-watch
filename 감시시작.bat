@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  CGV 취소표 감시기 - 1분 주기 상시 실행
echo  오디세이 / 용산 IMAX / 10-06 14:30, 18:00
echo ============================================
echo  잔여석이 늘어날 때만 텔레그램으로 알립니다.
echo  끄려면 이 창을 닫으세요.
echo.
set PYEXE=%USERPROFILE%\Downloads\cgv-open-watcher\venv\Scripts\python.exe
if not exist "%PYEXE%" (
  echo [오류] python 을 찾을 수 없습니다:
  echo   %PYEXE%
  pause
  exit /b 1
)
"%PYEXE%" run_local.py
echo.
echo 감시가 종료되었습니다.
pause
