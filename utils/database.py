import sqlite3
import aiosqlite # type: ignore
import asyncio
from datetime import datetime, timedelta
import json
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def initialize(self):
        """Initialize database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Reminders table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    channel_id INTEGER,
                    guild_id INTEGER,
                    message TEXT,
                    remind_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Custom commands table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS custom_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    command_name TEXT,
                    response TEXT,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Todo lists table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    guild_id INTEGER,
                    task TEXT,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Server settings table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS server_settings (
                    guild_id INTEGER PRIMARY KEY,
                    prefix TEXT DEFAULT '!',
                    welcome_channel INTEGER,
                    log_channel INTEGER,
                    mute_role INTEGER,
                    settings_json TEXT
                )
            ''')
            
            await db.commit()
            logger.info("Database initialized successfully")
    
    async def add_reminder(self, user_id: int, channel_id: int, guild_id: int, 
                          message: str, remind_time: datetime) -> int:
        """Add a reminder and return its ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                INSERT INTO reminders (user_id, channel_id, guild_id, message, remind_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, channel_id, guild_id, message, remind_time)) as cursor:
                reminder_id = cursor.lastrowid
            
            await db.commit()
            return reminder_id
    
    async def get_pending_reminders(self) -> List[Tuple]:
        """Get all pending reminders that are due"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT id, user_id, channel_id, guild_id, message, remind_time
                FROM reminders 
                WHERE completed = FALSE AND remind_time <= CURRENT_TIMESTAMP
            ''') as cursor:
                return await cursor.fetchall()
    
    async def complete_reminder(self, reminder_id: int):
        """Mark reminder as completed"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE reminders SET completed = TRUE WHERE id = ?',
                (reminder_id,)
            )
            await db.commit()
    
    async def add_todo(self, user_id: int, guild_id: int, task: str) -> int:
        """Add a todo item"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                INSERT INTO todos (user_id, guild_id, task)
                VALUES (?, ?, ?)
            ''', (user_id, guild_id, task)) as cursor:
                todo_id = cursor.lastrowid
            
            await db.commit()
            return todo_id
    
    async def get_todos(self, user_id: int, guild_id: int) -> List[Tuple]:
        """Get user's todo list"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT id, task, completed, created_at
                FROM todos 
                WHERE user_id = ? AND guild_id = ?
                ORDER BY created_at DESC
            ''', (user_id, guild_id)) as cursor:
                return await cursor.fetchall()
    
    async def complete_todo(self, todo_id: int, user_id: int) -> bool:
        """Complete a todo item"""
        async with aiosqlite.connect(self.db_path) as db:
            result = await db.execute('''
                UPDATE todos 
                SET completed = TRUE 
                WHERE id = ? AND user_id = ? AND completed = FALSE
            ''', (todo_id, user_id))
            
            await db.commit()
            return result.rowcount > 0
    
    async def delete_todo(self, todo_id: int, user_id: int) -> bool:
        """Delete a todo item"""
        async with aiosqlite.connect(self.db_path) as db:
            result = await db.execute('''
                DELETE FROM todos 
                WHERE id = ? AND user_id = ?
            ''', (todo_id, user_id))
            
            await db.commit()
            return result.rowcount > 0
