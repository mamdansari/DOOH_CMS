import sqlite3
import os

def initialize_database():
    db_path = os.path.join(os.path.dirname(__file__), "db.sqlite")
    if os.path.exists(db_path):
        return  # Skip if already initialized

    conn = sqlite3.connect(db_path)

    # Create Screens table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS screens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        area TEXT,
        building TEXT,
        floor TEXT,
        restroom TEXT,
        group_id TEXT,
        status TEXT DEFAULT 'offline',
        last_seen TEXT
    )
    ''')

    # Create Content table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        content_type TEXT,
        tags TEXT,
        category TEXT,
        expires_on TEXT
    )
    ''')

    # Assign content to screens
    conn.execute('''
    CREATE TABLE IF NOT EXISTS screen_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        screen_id INTEGER,
        content_id INTEGER,
        play_order INTEGER,
        start_time TEXT,
        end_time TEXT,
        FOREIGN KEY(screen_id) REFERENCES screens(id),
        FOREIGN KEY(content_id) REFERENCES content(id)
    )
    ''')

    # Screen Flags Table (for manual control)
    conn.execute('''
    CREATE TABLE IF NOT EXISTS screen_flags (
        screen_id INTEGER PRIMARY KEY,
        force_snapshot INTEGER DEFAULT 0,
        force_resync INTEGER DEFAULT 0,
        FOREIGN KEY(screen_id) REFERENCES screens(id)
    )
    ''')

    # Pings table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS pings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        screen_id INTEGER,
        timestamp DATETIME
    )
    ''')

    # Admin settings
    conn.execute('''
    CREATE TABLE IF NOT EXISTS admin_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')

    # Insert default admin settings
    defaults = [
        ('ping_interval', '30'),
        ('screen_mode', 'ads-only'),
        ('fallback_content', 'default.mp4')
    ]

    for key, value in defaults:
        conn.execute('INSERT OR IGNORE INTO admin_settings (key, value) VALUES (?, ?)', (key, value))

    conn.commit()
    conn.close()
    print("Database initialized ✅")
