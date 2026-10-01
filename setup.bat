@echo off
echo ========================================
echo   KSC Music Bot - Setup
echo ========================================
echo.

:: Check if .env exists
if exist .env (
    echo ✅ File .env đã tồn tại
) else (
    echo 📝 Tạo file .env từ template...
    copy .env.example .env
    echo ✅ Đã tạo file .env
    echo.
    echo ⚠️  QUAN TRỌNG: Hãy mở file .env và điền token thật của bạn!
    echo.
)

:: Check if virtual environment exists
if exist venv (
    echo ✅ Virtual environment đã tồn tại
) else (
    echo 📦 Tạo virtual environment...
    python -m venv venv
    echo ✅ Đã tạo virtual environment
)

:: Activate virtual environment and install dependencies
echo 📥 Cài đặt dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt

echo.
echo ========================================
echo           SETUP HOÀN THÀNH!
echo ========================================
echo.
echo 📋 Các bước tiếp theo:
echo 1. Mở file .env và điền token thật
echo 2. Chạy: python bot.py
echo.
pause
