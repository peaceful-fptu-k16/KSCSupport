<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# GenZ Assistant Discord Bot - Copilot Instructions

This is a Discord bot project written in Python using discord.py library. The bot serves as a multi-functional assistant for GenZ users with entertainment, AI integration, scheduling, admin tools, and gaming features.

## Project Structure
- `bot.py` - Main bot file and entry point
- `cogs/` - Feature modules organized by functionality
- `utils/` - Utility functions and database handlers
- `config.json` - Configuration file for bot settings
- `data/` - Data storage for reminders, etc.

## Key Features to Remember
- Entertainment commands (memes, quotes, random images)
- AI integration with OpenAI API for intelligent responses
- Reminder and scheduling system
- Admin moderation tools
- Mini-games and interactive features

## Code Style Guidelines
- Use async/await for Discord.py commands
- Organize features into separate cogs for modularity
- Implement proper error handling for API calls
- Use type hints for better code clarity
- Follow PEP 8 naming conventions
- Include docstrings for all functions and classes

## Important Notes
- Always handle Discord API rate limits
- Secure API keys using environment variables
- Implement proper permission checks for admin commands
- Use Discord embeds for rich message formatting
- Consider Vietnamese language support for user interactions
