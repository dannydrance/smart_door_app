# database.py
import sqlite3
import hashlib
import datetime
import os

DB_PATH = "smart_door2.db"

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            display_name TEXT,
            email TEXT,
            updated_at TEXT
        )
        """)

        # Notifications table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            door_status TEXT,
            timestamp TEXT NOT NULL
        )
        """)

        self.conn.commit()

        # Default admin user
        cur.execute("SELECT * FROM users WHERE username='admin'")
        if not cur.fetchone():
            hashed = self.hash_pw("admin")
            cur.execute("""
                INSERT INTO users (username, password, display_name, email, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, ("admin", hashed, "Administrator", "admin@example.com", datetime.datetime.now().isoformat()))
            self.conn.commit()

    def hash_pw(self, password: str) -> str:
        """Return SHA256 hash of the password."""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_user(self, username, password):
        cur = self.conn.cursor()
        hashed = self.hash_pw(password)
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hashed))
        return cur.fetchone()

    def get_user(self, username):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        return cur.fetchone()

    def update_profile(self, username, display_name, email=None, new_password=None):
        """Update user display name, email, and optionally password."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        if not cur.fetchone():
            raise ValueError("User not found")

        if new_password:
            hashed = self.hash_pw(new_password)
            cur.execute("""
                UPDATE users SET display_name=?, email=?, password=?, updated_at=?
                WHERE username=?
            """, (display_name, email, hashed, datetime.datetime.now().isoformat(), username))
        else:
            cur.execute("""
                UPDATE users SET display_name=?, email=?, updated_at=?
                WHERE username=?
            """, (display_name, email, datetime.datetime.now().isoformat(), username))

        self.conn.commit()
    
    def add_notification(self, message, door_status="Unknown"):
        cur = self.conn.cursor()
        one_min_ago = (datetime.datetime.utcnow() - datetime.timedelta(minutes=1)).isoformat()
        cur.execute("""
            SELECT id FROM notifications
            WHERE message=? AND timestamp>=?
            ORDER BY timestamp DESC LIMIT 1
        """, (message, one_min_ago))
        row = cur.fetchone()
        now = datetime.datetime.utcnow().isoformat()
        if row:
            cur.execute("UPDATE notifications SET timestamp=? WHERE id=?", (now, row[0]))
            self.conn.commit()
            return row[0]
        else:
            cur.execute("""
                INSERT INTO notifications (message, door_status, timestamp)
                VALUES (?, ?, ?)
            """, (message, door_status, now))
            self.conn.commit()
            return cur.lastrowid

    def get_notifications(self, limit=50):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, message, door_status, timestamp
            FROM notifications
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        return cur.fetchall()

    def clear_notifications(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM notifications")
        deleted = cursor.rowcount
        self.conn.commit()
        return deleted
    
