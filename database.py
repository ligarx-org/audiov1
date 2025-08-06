import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Ultra-optimized database manager with comprehensive statistics tracking"""
    
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.init_database()
        logger.info("✅ Database initialized successfully")
    
    def get_connection(self):
        """Get optimized database connection"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn
    
    def init_database(self):
        """Initialize database with all required tables and handle schema updates"""
        with self.lock:
            conn = self.get_connection()
            try:
                # Users table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        language_code TEXT DEFAULT 'uz',
                        is_banned BOOLEAN DEFAULT FALSE,
                        ban_reason TEXT,
                        ban_date DATETIME,
                        banned_by INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # User activity log - check if platform column exists
                try:
                    conn.execute("SELECT platform FROM user_activity LIMIT 1")
                except sqlite3.OperationalError:
                    # Column doesn't exist, create table with new schema
                    conn.execute("DROP TABLE IF EXISTS user_activity")
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_activity (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        activity_type TEXT,
                        activity_data TEXT,
                        platform TEXT,
                        success BOOLEAN DEFAULT TRUE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """)
                
                # Admins table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS admins (
                        user_id INTEGER PRIMARY KEY,
                        added_by INTEGER,
                        added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """)
                
                # Mandatory channels
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS mandatory_channels (
                        channel_id TEXT PRIMARY KEY,
                        username TEXT,
                        title TEXT,
                        added_by INTEGER,
                        added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """)
                
                # User subscriptions
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_subscriptions (
                        user_id INTEGER,
                        channel_id TEXT,
                        is_subscribed BOOLEAN DEFAULT FALSE,
                        last_checked DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, channel_id),
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """)
                
                # Bot settings
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS bot_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for better performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users (last_activity)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity (user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_type ON user_activity (activity_type)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_created_at ON user_activity (created_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_platform ON user_activity (platform)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions (user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_banned ON users (is_banned)")
                
                conn.commit()
                logger.info("✅ Database tables created/verified successfully")
                
            except Exception as e:
                logger.error(f"❌ Database initialization error: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
        """Add or update user"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO users 
                    (user_id, username, first_name, last_name, last_activity)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, username, first_name, last_name))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Error adding user {user_id}: {e}")
                return False
            finally:
                conn.close()
    
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user information"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT user_id, username, first_name, last_name, language_code, 
                       is_banned, ban_reason, ban_date, created_at, last_activity
                FROM users WHERE user_id = ?
            """, (user_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_language(self, user_id: int) -> str:
        """Get user's language preference"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("SELECT language_code FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result['language_code'] if result else 'uz'
        except Exception as e:
            logger.error(f"Error getting user language: {e}")
            return 'uz'
        finally:
            conn.close()
    
    def set_user_language(self, user_id: int, language: str) -> bool:
        """Set user's language preference"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    UPDATE users SET language_code = ?, last_activity = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                """, (language, user_id))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Error setting user language: {e}")
                return False
            finally:
                conn.close()
    
    def is_user_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return bool(result['is_banned']) if result else False
        except Exception as e:
            logger.error(f"Error checking ban status: {e}")
            return False
        finally:
            conn.close()
    
    def ban_user(self, user_id: int, reason: str, banned_by: int) -> bool:
        """Ban a user"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    UPDATE users 
                    SET is_banned = TRUE, ban_reason = ?, ban_date = CURRENT_TIMESTAMP, banned_by = ?
                    WHERE user_id = ?
                """, (reason, banned_by, user_id))
                conn.commit()
                
                # Log the ban activity
                self.log_user_activity(banned_by, 'ban_user', {
                    'banned_user_id': user_id,
                    'reason': reason
                })
                
                return True
            except Exception as e:
                logger.error(f"Error banning user: {e}")
                return False
            finally:
                conn.close()
    
    def unban_user(self, user_id: int, unbanned_by: int) -> bool:
        """Unban a user"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    UPDATE users 
                    SET is_banned = FALSE, ban_reason = NULL, ban_date = NULL
                    WHERE user_id = ?
                """, (user_id,))
                conn.commit()
                
                # Log the unban activity
                self.log_user_activity(unbanned_by, 'unban_user', {
                    'unbanned_user_id': user_id
                })
                
                return True
            except Exception as e:
                logger.error(f"Error unbanning user: {e}")
                return False
            finally:
                conn.close()
    
    def get_ban_info(self, user_id: int) -> Dict[str, Any]:
        """Get ban information for user"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT ban_reason, ban_date, banned_by 
                FROM users WHERE user_id = ? AND is_banned = TRUE
            """, (user_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'reason': result['ban_reason'],
                    'date': result['ban_date'],
                    'banned_by': result['banned_by']
                }
            return {}
        except Exception as e:
            logger.error(f"Error getting ban info: {e}")
            return {}
        finally:
            conn.close()
    
    def get_banned_users(self, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """Get banned users with pagination"""
        conn = self.get_connection()
        try:
            # Get total count
            cursor = conn.execute("SELECT COUNT(*) as count FROM users WHERE is_banned = TRUE")
            total = cursor.fetchone()['count']
            
            # Get paginated results
            offset = (page - 1) * per_page
            cursor = conn.execute("""
                SELECT user_id, username, first_name, last_name, ban_reason, ban_date, banned_by
                FROM users WHERE is_banned = TRUE
                ORDER BY ban_date DESC
                LIMIT ? OFFSET ?
            """, (per_page, offset))
            
            users = [dict(row) for row in cursor.fetchall()]
            
            return {
                'users': users,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
        except Exception as e:
            logger.error(f"Error getting banned users: {e}")
            return {'users': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}
        finally:
            conn.close()
    
    def add_admin(self, user_id: int, added_by: int) -> bool:
        """Add admin"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO admins (user_id, added_by)
                    VALUES (?, ?)
                """, (user_id, added_by))
                conn.commit()
                
                # Log admin addition
                self.log_user_activity(added_by, 'add_admin', {
                    'new_admin_id': user_id
                })
                
                return True
            except Exception as e:
                logger.error(f"Error adding admin: {e}")
                return False
            finally:
                conn.close()
    
    def remove_admin(self, user_id: int, removed_by: int = None) -> bool:
        """Remove admin"""
        with self.lock:
            conn = self.get_connection()
            try:
                # Get admin info before deletion
                cursor = conn.execute("""
                    SELECT user_id FROM admins WHERE user_id = ?
                """, (user_id,))
                admin_info = cursor.fetchone()

                conn.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
                conn.commit()
                
                # Log admin removal
                if removed_by and admin_info:
                    self.log_user_activity(removed_by, 'remove_admin', {
                        'removed_admin_id': user_id
                    })
                
                return True
            except Exception as e:
                logger.error(f"Error removing admin: {e}")
                return False
            finally:
                conn.close()
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False
        finally:
            conn.close()
    
    def get_admins(self) -> List[Dict[str, Any]]:
        """Get all admins with user info"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT a.user_id, u.username, u.first_name, u.last_name, a.added_at, a.added_by
                FROM admins a
                LEFT JOIN users u ON a.user_id = u.user_id
                ORDER BY a.added_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting admins: {e}")
            return []
        finally:
            conn.close()
    
    def add_mandatory_channel(self, channel_id: str, username: str, title: str, added_by: int) -> bool:
        """Add mandatory channel"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO mandatory_channels 
                    (channel_id, username, title, added_by)
                    VALUES (?, ?, ?, ?)
                """, (channel_id, username, title, added_by))
                conn.commit()
                
                # Log channel addition
                self.log_user_activity(added_by, 'add_channel', {
                    'channel_id': channel_id,
                    'title': title
                })
                
                return True
            except Exception as e:
                logger.error(f"Error adding mandatory channel: {e}")
                return False
            finally:
                conn.close()
    
    def remove_mandatory_channel(self, channel_id: str, removed_by: int) -> bool:
        """Remove mandatory channel"""
        with self.lock:
            conn = self.get_connection()
            try:
                # Get channel info before deletion
                cursor = conn.execute("""
                    SELECT title FROM mandatory_channels WHERE channel_id = ?
                """, (channel_id,))
                channel_info = cursor.fetchone()
                
                conn.execute("DELETE FROM mandatory_channels WHERE channel_id = ?", (channel_id,))
                conn.commit()
                
                # Log channel removal
                self.log_user_activity(removed_by, 'remove_channel', {
                    'channel_id': channel_id,
                    'title': channel_info['title'] if channel_info else 'Unknown'
                })
                
                return True
            except Exception as e:
                logger.error(f"Error removing mandatory channel: {e}")
                return False
            finally:
                conn.close()
    
    def get_mandatory_channels(self) -> List[Dict[str, Any]]:
        """Get all mandatory channels"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT channel_id, username, title, added_by, added_at
                FROM mandatory_channels WHERE is_active = TRUE
                ORDER BY added_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting mandatory channels: {e}")
            return []
        finally:
            conn.close()
    
    def update_user_subscription(self, user_id: int, channel_id: str, is_subscribed: bool) -> bool:
        """Update user subscription status"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO user_subscriptions 
                    (user_id, channel_id, is_subscribed, last_checked)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, channel_id, is_subscribed))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Error updating subscription: {e}")
                return False
            finally:
                conn.close()
    
    def log_user_activity(self, user_id: int, activity_type: str, activity_data: Dict[str, Any] = None, platform: str = None, success: bool = True) -> bool:
        """Log user activity with enhanced tracking for statistics"""
        with self.lock:
            conn = self.get_connection()
            try:
                # Update last activity
                conn.execute("""
                    UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?
                """, (user_id,))
                
                # Log activity with platform and success tracking
                conn.execute("""
                    INSERT INTO user_activity (user_id, activity_type, activity_data, platform, success)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, activity_type, json.dumps(activity_data) if activity_data else None, platform, success))
                
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Error logging activity: {e}")
                return False
            finally:
                conn.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive bot statistics with enhanced tracking"""
        conn = self.get_connection()
        try:
            stats = {}
            
            # Total users
            cursor = conn.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = cursor.fetchone()['count']
            
            # Active users (today)
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM users 
                WHERE date(last_activity) = date('now')
            """)
            stats['active_today'] = cursor.fetchone()['count']
            
            # Active users (this week)
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM users 
                WHERE last_activity >= date('now', '-7 days')
            """)
            stats['active_week'] = cursor.fetchone()['count']
            
            # Active users (this month)
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM users 
                WHERE last_activity >= date('now', '-30 days')
            """)
            stats['active_month'] = cursor.fetchone()['count']
            
            # Activity statistics with proper counting
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'search' AND success = TRUE
            """)
            stats['total_searches'] = cursor.fetchone()['count']
            
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'download' AND success = TRUE
            """)
            stats['total_downloads'] = cursor.fetchone()['count']
            
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'recognize' AND success = TRUE
            """)
            stats['total_recognitions'] = cursor.fetchone()['count']

            # Daily, Weekly, Monthly breakdowns for activities
            # Searches
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'search' AND success = TRUE AND date(created_at) = date('now')
            """)
            stats['searches_today'] = cursor.fetchone()['count']

            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'search' AND success = TRUE AND created_at >= date('now', '-7 days')
            """)
            stats['searches_week'] = cursor.fetchone()['count']

            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'search' AND success = TRUE AND created_at >= date('now', '-30 days')
            """)
            stats['searches_month'] = cursor.fetchone()['count']

            # Downloads
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'download' AND success = TRUE AND date(created_at) = date('now')
            """)
            stats['downloads_today'] = cursor.fetchone()['count']

            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'download' AND success = TRUE AND created_at >= date('now', '-7 days')
            """)
            stats['downloads_week'] = cursor.fetchone()['count']

            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'download' AND success = TRUE AND created_at >= date('now', '-30 days')
            """)
            stats['downloads_month'] = cursor.fetchone()['count']

            # Recognitions
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'recognize' AND success = TRUE AND date(created_at) = date('now')
            """)
            stats['recognitions_today'] = cursor.fetchone()['count']

            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'recognize' AND success = TRUE AND created_at >= date('now', '-7 days')
            """)
            stats['recognitions_week'] = cursor.fetchone()['count']

            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'recognize' AND success = TRUE AND created_at >= date('now', '-30 days')
            """)
            stats['recognitions_month'] = cursor.fetchone()['count']
            
            # Platform-specific downloads with proper JSON parsing
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'download' AND success = TRUE AND platform = 'youtube'
            """)
            stats['youtube_downloads'] = cursor.fetchone()['count']
            
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'download' AND success = TRUE AND platform = 'instagram'
            """)
            stats['instagram_downloads'] = cursor.fetchone()['count']
            
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM user_activity 
                WHERE activity_type = 'download' AND success = TRUE AND platform = 'tiktok'
            """)
            stats['tiktok_downloads'] = cursor.fetchone()['count']
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'total_users': 0,
                'active_today': 0,
                'active_week': 0,
                'active_month': 0,
                'total_searches': 0,
                'searches_today': 0,
                'searches_week': 0,
                'searches_month': 0,
                'total_downloads': 0,
                'downloads_today': 0,
                'downloads_week': 0,
                'downloads_month': 0,
                'total_recognitions': 0,
                'recognitions_today': 0,
                'recognitions_week': 0,
                'recognitions_month': 0,
                'youtube_downloads': 0,
                'instagram_downloads': 0,
                'tiktok_downloads': 0
            }
        finally:
            conn.close()
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users for broadcast"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT user_id, username, first_name, last_name
                FROM users WHERE is_banned = FALSE
                ORDER BY last_activity DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
        finally:
            conn.close()
    
    def set_bot_setting(self, key: str, value: str) -> bool:
        """Set bot setting"""
        with self.lock:
            conn = self.get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO bot_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, value))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Error setting bot setting: {e}")
                return False
            finally:
                conn.close()
    
    def get_bot_setting(self, key: str, default: str = None) -> str:
        """Get bot setting"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result['value'] if result else default
        except Exception as e:
            logger.error(f"Error getting bot setting: {e}")
            return default
        finally:
            conn.close()
    
    def close(self):
        """Close database connection"""
        # Connection is closed after each operation
        logger.info("Database manager closed")
