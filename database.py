import sqlite3
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table: Discord ID -> R6 username and cached rank
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                discord_id INTEGER PRIMARY KEY,
                r6_username TEXT NOT NULL,
                current_rank TEXT,
                UNIQUE(r6_username)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def link_user(self, discord_id: int, r6_username: str) -> bool:
        """Link a Discord user to an R6 account. If r6_username is already linked, unlink it first."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if this R6 username is already linked to someone else
            cursor.execute('SELECT discord_id FROM users WHERE r6_username = ?', (r6_username,))
            result = cursor.fetchone()
            if result and result[0] != discord_id:
                # Unlink the old user
                cursor.execute('DELETE FROM users WHERE r6_username = ?', (r6_username,))
                logger.info(f"Unlinked Discord ID {result[0]} from R6 username {r6_username}")
            
            # Link the new user (insert or replace)
            cursor.execute('''
                INSERT OR REPLACE INTO users (discord_id, r6_username, current_rank)
                VALUES (?, ?, NULL)
            ''', (discord_id, r6_username))
            
            conn.commit()
            conn.close()
            logger.info(f"Linked Discord ID {discord_id} to R6 username {r6_username}")
            return True
        except Exception as e:
            logger.error(f"Error linking user: {e}")
            return False
    
    def unlink_user(self, discord_id: int) -> bool:
        """Unlink a Discord user from their R6 account"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE discord_id = ?', (discord_id,))
            conn.commit()
            conn.close()
            logger.info(f"Unlinked Discord ID {discord_id}")
            return True
        except Exception as e:
            logger.error(f"Error unlinking user: {e}")
            return False
    
    def get_user(self, discord_id: int) -> Optional[Tuple[str, str]]:
        """Get R6 username and cached rank for a Discord user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT r6_username, current_rank FROM users WHERE discord_id = ?', (discord_id,))
            result = cursor.fetchone()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    def get_all_users(self) -> List[Tuple[int, str, str]]:
        """Get all linked users"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT discord_id, r6_username, current_rank FROM users')
            results = cursor.fetchall()
            conn.close()
            return results
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    def update_rank(self, discord_id: int, rank: str) -> bool:
        """Update cached rank for a Discord user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET current_rank = ? WHERE discord_id = ?', (rank, discord_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating rank: {e}")
            return False
    
    def get_rank(self, discord_id: int) -> Optional[str]:
        """Get cached rank for a Discord user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT current_rank FROM users WHERE discord_id = ?', (discord_id,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting rank: {e}")
            return None
    
    def user_exists(self, discord_id: int) -> bool:
        """Check if a user is linked"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM users WHERE discord_id = ?', (discord_id,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            logger.error(f"Error checking if user exists: {e}")
            return False
