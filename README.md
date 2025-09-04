# 🤖 GenZ Assistant Discord Bot

> 🚀 **Production-Ready** Multi-functional Discord Bot built with ❤️ for GenZ community

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg)](https://discordpy.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ Key Features

### 🎵 **Advanced Music System**
- **YouTube Integration** - High-quality music streaming with 2025-compatible yt-dlp
- **SoundCloud Advanced** - Full SoundCloud support with playlists
- **Universal Music Player** - Smart source mixing and conflict resolution
- **Music Manager** - Prevent conflicts between different music sources

### 🎮 **Interactive Entertainment**
- **Games & Fun Commands** - Mini-games, memes, quotes, and entertainment
- **AI Integration** - ChatGPT responses and AI image generation
- **Interactive Menus** - Button-based navigation and command interface

### 👥 **Voice Features**
- **Temporary Voice Channels** - Join-to-Create VC system with auto-management
- **Voice Controls** - Advanced audio controls and volume management

### 🛡️ **Administration & Management**
- **Admin Tools** - Moderation commands and server management
- **Channel Restrictions** - Smart channel-specific bot behavior
- **Auto Cleanup** - Automatic maintenance and optimization
- **Analytics** - Server statistics and usage tracking

### 🎯 **Gaming Integration**
- **League of Legends** - Rank checking, match history, and OP.GG integration
- **Esports Features** - Tournament tracking and gaming communities

### 📅 **Utility Features**
- **Scheduler** - Reminders and event scheduling
- **Database Management** - Persistent data storage
- **Event Logging** - Welcome/goodbye messages and server events

## 🏗️ Architecture

### 📂 **Project Structure**
```
GenzAssistant/
├── 🤖 bot.py                 # Main bot entry point
├── 📁 cogs/                  # Feature modules (18 cogs)
│   ├── 🎵 music.py          # YouTube music system
│   ├── 🎵 music_manager.py  # Music conflict management
│   ├── 🎵 universal_music.py # Universal music player
│   ├── 🎵 soundcloud_advanced.py # SoundCloud integration
│   ├── 🎯 temp_voice.py     # Temporary voice channels
│   ├── 🎮 games.py          # Mini-games and entertainment
│   ├── 🤖 ai.py             # AI chat integration
│   ├── 🛡️ admin.py          # Administration tools
│   └── 📊 analytics.py      # Server analytics
├── 🔧 utils/                 # Utility functions
│   ├── 💾 database.py       # Database management
│   └── 📡 channel_manager.py # Channel restrictions
└── 📊 data/                  # Data storage
```

### 🎯 **Core Statistics**
- **18 Feature Cogs** - Modular architecture
- **31 Slash Commands** - Modern Discord interactions
- **21 Python Files** - Clean, optimized codebase
- **Channel Restrictions** - Organized bot behavior
- **Production Ready** - No test files or debug code

## 🚀 Quick Start

### 📋 **Prerequisites**
- Python 3.9+
- Discord Bot Token
- FFmpeg (for music playback)
- Required API keys (OpenAI, etc.)

### ⚡ **Installation**
```bash
# Clone repository
git clone https://github.com/peaceful-fptu-k16/KSCSupport.git
cd KSCSupport

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your tokens

# Run bot
python bot.py
```

### 🔧 **Configuration**
1. **Discord Bot Setup** - Create bot at [Discord Developer Portal](https://discord.com/developers/applications)
2. **Environment Variables** - Configure `.env` file with tokens
3. **Channel Setup** - Create channels: `👋・welcome`, `🎶・music`, `🤖・bot`
4. **Permissions** - Grant bot necessary permissions

## 🎵 Music System

### 🎬 **YouTube Player**
- 2025-compatible yt-dlp with updated extractors
- High-quality audio streaming
- Queue management and playlist support
- Advanced search and filtering

### 🎧 **SoundCloud Advanced**
- Full SoundCloud integration
- Playlist support and user tracks
- Advanced audio processing
- Smart conflict resolution

### 🎭 **Universal Music Player**
- Mix YouTube and SoundCloud seamlessly
- Intelligent source switching
- Unified queue management
- Cross-platform compatibility

## 🎮 Interactive Features

### 🕹️ **Games & Entertainment**
- Mini-games and trivia
- Meme generators and fun commands
- Random quotes and entertainment
- Interactive button interfaces

### 🤖 **AI Integration**
- ChatGPT-powered responses
- AI image generation
- Smart context understanding
- Natural language processing

## 👥 Voice Features

### 🔊 **Temporary Voice Channels**
- **Join-to-Create System** - Automatic VC creation
- **Smart Management** - Auto-delete when empty
- **User Controls** - Rename, limit, and manage channels
- **Persistent Settings** - Remember user preferences

## 🛡️ Administration

### 🔧 **Channel Restrictions**
- **Smart Behavior** - Commands restricted to appropriate channels
- **Emoji Organization** - Channel names with emoji prefixes
- **Clean Interface** - Organized command structure

### 📊 **Analytics & Monitoring**
- Server usage statistics
- Command usage tracking
- Performance monitoring
- Error logging and reporting

## 🎯 Command Overview

### 🎵 **Music Commands**
- `/play` - Play music from YouTube/SoundCloud
- `/queue` - View and manage music queue
- `/skip` - Skip current track
- `/pause` / `/resume` - Control playback
- `/volume` - Adjust volume

### 🎮 **Fun Commands**
- `/meme` - Generate random memes
- `/quote` - Get inspirational quotes
- `/game` - Start mini-games
- `/ai` - Chat with AI assistant

### 🛡️ **Admin Commands**
- `/kick` / `/ban` - Moderation actions
- `/clear` - Clear messages
- `/setup` - Configure bot settings
- `/analytics` - View server stats

### 👥 **Voice Commands**
- `/temp-voice setup` - Configure temporary VCs
- `/vc create` - Create temporary voice channel
- `/vc settings` - Manage voice settings

## 🌟 Special Features

### 🎯 **Channel Organization**
- **👋・welcome** - Welcome messages and greetings
- **🎶・music** - Music commands and playback
- **🤖・bot** - General bot commands and interactions

### 🔄 **Smart Conflict Resolution**
- Prevent music source conflicts
- Intelligent queue management
- Seamless source switching
- User-friendly conflict dialogs

### 📱 **Modern UI**
- Discord slash commands
- Interactive button interfaces
- Rich embed messages
- Emoji-enhanced navigation

## 🔧 Technical Details

### 🏗️ **Architecture**
- **Modular Design** - Separate cogs for each feature
- **Async Programming** - Non-blocking operations
- **Error Handling** - Comprehensive exception management
- **Database Integration** - Persistent data storage

### 🚀 **Performance**
- **Optimized Code** - Clean, efficient implementation
- **Memory Management** - Smart resource usage
- **Caching System** - Improved response times
- **Production Ready** - Thoroughly tested and optimized

## 📞 Support & Community

### 🤝 **Getting Help**
- **GitHub Issues** - Report bugs and request features
- **Documentation** - Comprehensive guides and examples
- **Community Support** - Discord server for assistance

### 🎯 **Contributing**
- Fork the repository
- Create feature branches
- Submit pull requests
- Follow coding standards

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Discord.py Community** - Amazing library and support
- **yt-dlp Project** - Excellent YouTube extraction
- **GenZ Community** - Inspiration and feedback
- **Contributors** - Everyone who helped build this bot

---

**Made with ❤️ for the GenZ community**

*🤖 Ready to enhance your Discord server? Deploy GenZ Assistant today!*
