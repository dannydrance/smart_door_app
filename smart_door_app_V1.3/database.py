# database.py - Updated for Unified User System
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
        
        # Admin users table (for app login)
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

        # Door users table (RFID + Fingerprint + PIN)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS door_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            rfid_uid TEXT UNIQUE NOT NULL,
            pin TEXT NOT NULL,
            fingerprint_id INTEGER,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
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
    
    # ---------- DOOR USER MANAGEMENT ----------
    
    def add_door_user(self, name, rfid_uid, pin, fingerprint_id=None):
        """Add a new door user (called after ESP32 registration completes)"""
        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO door_users (name, rfid_uid, pin, fingerprint_id, active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (name, rfid_uid.upper(), pin, fingerprint_id, datetime.datetime.now().isoformat()))
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None  # RFID already exists
    
    def get_door_users(self):
        """Get all active door users"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, name, rfid_uid, pin, fingerprint_id, created_at, updated_at
            FROM door_users
            WHERE active = 1
            ORDER BY name ASC
        """)
        return cur.fetchall()
    
    def get_door_user_by_rfid(self, rfid_uid):
        """Get door user by RFID"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, name, rfid_uid, pin, fingerprint_id, created_at, updated_at
            FROM door_users
            WHERE rfid_uid = ? AND active = 1
        """, (rfid_uid.upper(),))
        return cur.fetchone()
    
    def delete_door_user(self, rfid_uid):
        """Delete door user (marks as inactive)"""
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE door_users
            SET active = 0, updated_at = ?
            WHERE rfid_uid = ?
        """, (datetime.datetime.now().isoformat(), rfid_uid.upper()))
        self.conn.commit()
        return cur.rowcount > 0
    
    def update_door_user(self, rfid_uid, name=None, pin=None, fingerprint_id=None):
        """Update door user details"""
        cur = self.conn.cursor()
        
        updates = []
        params = []
        
        if name:
            updates.append("name = ?")
            params.append(name)
        if pin:
            updates.append("pin = ?")
            params.append(pin)
        if fingerprint_id is not None:
            updates.append("fingerprint_id = ?")
            params.append(fingerprint_id)
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        params.append(datetime.datetime.now().isoformat())
        params.append(rfid_uid.upper())
        
        query = f"UPDATE door_users SET {', '.join(updates)} WHERE rfid_uid = ?"
        cur.execute(query, params)
        self.conn.commit()
        return cur.rowcount > 0
    
    # ---------- NOTIFICATIONS ----------
    
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