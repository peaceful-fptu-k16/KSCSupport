# 🔐 Security Setup Guide

## Environment Variables Setup

Để bảo vệ API keys và tokens, bot sử dụng file `.env` thay vì hard-code trong source code.

### 1. Tạo file .env

```bash
cp .env.example .env
```

### 2. Điền thông tin vào .env

Mở file `.env` và điền các thông tin thực của bạn:

```env
# Discord Bot Token - Lấy từ https://discord.com/developers/applications
DISCORD_BOT_TOKEN=MTQwMDQxODY0NTgwNDQ0OTg5Mw.GzLTb0.YourActualTokenHere

# OpenAI API Key - Lấy từ https://platform.openai.com/api-keys  
OPENAI_API_KEY=sk-proj-YourActualOpenAIKeyHere

# Google Gemini API Key - Lấy từ https://makersuite.google.com/app/apikey
GEMINI_API_KEY=YourActualGeminiKeyHere

# Riot Games API Key - Lấy từ https://developer.riotgames.com/
RIOT_API_KEY=RGAPI-YourActualRiotKeyHere

# Discord User ID - Right click Discord profile → "Copy User ID"
DISCORD_OWNER_ID=123456789012345678
```

### 3. Cách lấy các API Keys

#### Discord Bot Token:
1. Truy cập [Discord Developer Portal](https://discord.com/developers/applications)
2. Tạo New Application
3. Vào tab "Bot" → Copy Token
4. Invite bot với permissions cần thiết

#### OpenAI API Key:
1. Đăng ký tài khoản [OpenAI](https://platform.openai.com/)
2. Vào [API Keys](https://platform.openai.com/api-keys)
3. Create new secret key
4. Copy và lưu key (chỉ hiển thị 1 lần)

#### Riot Games API Key:
1. Truy cập [Riot Developer Portal](https://developer.riotgames.com/)
2. Đăng nhập với tài khoản Riot
3. Tạo Personal API Key (miễn phí)
4. Copy key (key chỉ có hiệu lực 24h cho development)

### 4. Bảo mật quan trọng

⚠️ **CẢNH BÁO BẢO MẬT:**

- ✅ File `.env` đã được thêm vào `.gitignore` - KHÔNG BAO GIỜ commit
- ✅ Chỉ sử dụng `.env.example` như template  
- ✅ Không share token/key với ai khác
- ✅ Regenerate tokens nếu bị lộ

### 5. Kiểm tra setup

Chạy bot để kiểm tra:

```bash
python bot.py
```

Nếu thấy lỗi "Discord bot token not found!", kiểm tra lại file `.env`.

## Environment Variables được sử dụng

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ | Token bot Discord |
| `OPENAI_API_KEY` | ✅ | API key cho ChatGPT/AI features |  
| `GEMINI_API_KEY` | ✅ | Google Gemini AI key |
| `RIOT_API_KEY` | ❌ | Riot Games API key cho LoL features |
| `DISCORD_OWNER_ID` | ✅ | User ID owner bot |
| `DATABASE_URL` | ❌ | External database URL (optional) |

## Troubleshooting

### Bot không khởi động
- Kiểm tra file `.env` có tồn tại
- Kiểm tra token Discord có đúng không
- Kiểm tra bot có được invite với đủ permissions

### AI features không hoạt động  
- Kiểm tra OpenAI/Gemini API keys
- Kiểm tra balance/quota của API keys
- Kiểm tra internet connection

### LoL features không hoạt động
- Kiểm tra RIOT_API_KEY có đúng không
- Riot API key chỉ có hiệu lực 24h cho development key
- Kiểm tra kết nối đến Riot API servers
