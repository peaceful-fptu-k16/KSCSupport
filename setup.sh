#!/bin/bash

echo "========================================"
echo "   KSC Music Bot - Setup"
echo "========================================"
echo

# Check if .env exists
if [ -f .env ]; then
    echo "✅ File .env đã tồn tại"
else
    echo "📝 Tạo file .env từ template..."
    cp .env.example .env
    echo "✅ Đã tạo file .env"
    echo
    echo "⚠️  QUAN TRỌNG: Hãy mở file .env và điền token thật của bạn!"
    echo
fi

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "✅ Virtual environment đã tồn tại"
else
    echo "📦 Tạo virtual environment..."
    python3 -m venv venv
    echo "✅ Đã tạo virtual environment"
fi

# Activate virtual environment and install dependencies
echo "📥 Cài đặt dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo
echo "========================================"
echo "           SETUP HOÀN THÀNH!"
echo "========================================"
echo
echo "📋 Các bước tiếp theo:"
echo "1. Mở file .env và điền token thật"
echo "2. Chạy: python bot.py"
echo
