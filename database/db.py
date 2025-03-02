import sqlite3
import os

# Erstelle den Datenbank-Ordner, falls er nicht existiert
if not os.path.exists("database"):
    os.makedirs("database")

def init_db():
    """
    Initialisiert die XP-Datenbank.
    """
    conn = sqlite3.connect("database/xp.db")
    c = conn.cursor()
    
    # Tabelle für XP
    c.execute("""
        CREATE TABLE IF NOT EXISTS xp (
            guild_id INTEGER,
            user_id INTEGER,
            xp INTEGER,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    # Tabelle für XP-Channel
    c.execute("""
        CREATE TABLE IF NOT EXISTS xp_channels (
            guild_id INTEGER,
            channel_id INTEGER,
            PRIMARY KEY (guild_id, channel_id)
        )
    """)
    
    # Tabelle für No-Level-Rollen
    c.execute("""
        CREATE TABLE IF NOT EXISTS no_level_roles (
            guild_id INTEGER,
            role_id INTEGER,
            PRIMARY KEY (guild_id, role_id)
        )
    """)
    
    conn.commit()
    conn.close()

def add_xp(guild_id, user_id, xp_amount):
    """
    Fügt XP für einen Nutzer hinzu oder aktualisiert sie.
    """
    conn = sqlite3.connect("database/xp.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO xp (guild_id, user_id, xp)
        VALUES (?, ?, COALESCE((SELECT xp FROM xp WHERE guild_id=? AND user_id=?), 0) + ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp
    """, (guild_id, user_id, guild_id, user_id, xp_amount))
    conn.commit()
    conn.close()

def get_xp(guild_id, user_id):
    """
    Gibt die XP eines Nutzers zurück.
    """
    conn = sqlite3.connect("database/xp.db")
    c = conn.cursor()
    c.execute("SELECT xp FROM xp WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def add_xp_channel(guild_id, channel_id):
    """
    Fügt einen Channel hinzu, in dem XP gefarmt werden kann.
    """
    conn = sqlite3.connect("database/xp.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO xp_channels (guild_id, channel_id) VALUES (?, ?)", (guild_id, channel_id))
    conn.commit()
    conn.close()

def remove_xp_channel(guild_id, channel_id):
    """
    Entfernt einen Channel aus der XP-Channel-Liste.
    """
    conn = sqlite3.connect("database/xp.db")
    c = conn.cursor()
    c.execute("DELETE FROM xp_channels WHERE guild_id=? AND channel_id=?", (guild_id, channel_id))
    conn.commit()
    conn.close()

def is_xp_channel(guild_id, channel_id):
    """
    Überprüft, ob ein Channel ein XP-Channel ist.
    """
    conn = sqlite3.connect("database/xp.db")
    c = conn.cursor()
    c.execute("SELECT channel_id FROM xp_channels WHERE guild_id=? AND channel_id=?", (guild_id, channel_id))
    result = c.fetchone()
    conn.close()
    return result is not None

def add_no_level_role(guild_id, role_id):
    """
    Fügt eine Rolle hinzu, die nicht leveln kann.
    """
    conn = sqlite3.connect("database/xp.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO no_level_roles (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id))
    conn.commit()
    conn.close()

def remove_no_level_role(guild_id, role_id):
    """
    Entfernt eine Rolle aus der No-Level-Rollen-Liste.
    """
    conn = sqlite3.connect("database/xp.db")
    c = conn.cursor()
    c.execute("DELETE FROM no_level_roles WHERE guild_id=? AND role_id=?", (guild_id, role_id))
    conn.commit()
    conn.close()

def can_level_up(guild_id, user):
    """
    Überprüft, ob ein Nutzer leveln kann.
    """
    conn = sqlite3.connect("database/xp.db")
    c = conn.cursor()
    for role in user.roles:
        c.execute("SELECT role_id FROM no_level_roles WHERE guild_id=? AND role_id=?", (guild_id, role.id))
        if c.fetchone():
            conn.close()
            return False
    conn.close()
    return True

def init_premium_db():
    conn = sqlite3.connect("database/premium.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS premium_users (
    user_id INTEGER PRIMARY KEY,
    expries_at TEXT  # Ablaufdatum des Premium-status
        )
    """)
    conn.commit()
    conn.close()

def init_premium_codes_db():
    conn = sqlite3.connect("database/premium_codes.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS premium_codes (
            code TEXT PRIMARY KEY,
            used BOOLEAN DEFAULT FALSE
        )
    """)
    conn.commit()
    conn.close()

def get_all_codes():
    """
    Gibt alle Premium-Codes zurück.
    """
    conn = sqlite3.connect("database/premium_codes.db")
    c = conn.cursor()
    c.execute("SELECT code, used FROM premium_codes")
    codes = c.fetchall()
    conn.close()
    return codes

def add_code(code):
    """
    Fügt einen neuen Premium-Code hinzu.
    """
    conn = sqlite3.connect("database/premium_codes.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO premium_codes (code) VALUES (?)", (code,))
    conn.commit()
    conn.close()

def delete_code(code):
    """
    Löscht einen Premium-Code.
    """
    conn = sqlite3.connect("database/premium_codes.db")
    c = conn.cursor()
    c.execute("DELETE FROM premium_codes WHERE code = ?", (code,))
    conn.commit()
    conn.close()

def init_backup_db():
    conn = sqlite3.connect("database/backups.db")
    c = conn.cursor()
    
    # Tabelle für Backups
    c.execute("""
        CREATE TABLE IF NOT EXISTS backups (
            backup_id TEXT PRIMARY KEY,
            guild_id INTEGER,
            backup_data TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def save_backup(backup_id, guild_id, backup_data):
    conn = sqlite3.connect("database/backups.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO backups (backup_id, guild_id, backup_data)
        VALUES (?, ?, ?)
        ON CONFLICT(backup_id) DO UPDATE SET
            guild_id = excluded.guild_id,
            backup_data = excluded.backup_data
    """, (backup_id, guild_id, backup_data))
    conn.commit()
    conn.close()

def load_backup(backup_id):
    conn = sqlite3.connect("database/backups.db")
    c = conn.cursor()
    c.execute("SELECT backup_data FROM backups WHERE backup_id=?", (backup_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def delete_backup(backup_id):
    conn = sqlite3.connect("database/backups.db")
    c = conn.cursor()
    c.execute("DELETE FROM backups WHERE backup_id=?", (backup_id,))
    conn.commit()
    conn.close()

def init_autorole_db():
    conn = sqlite3.connect("database/autorole.db")
    c = conn.cursor()
    
    # Tabelle für Autorole
    c.execute("""
        CREATE TABLE IF NOT EXISTS autorole (
            guild_id INTEGER PRIMARY KEY,
            user_role_id INTEGER,
            bot_role_id INTEGER
        )
    """)
    
    conn.commit()
    conn.close()

def set_autorole(guild_id, user_role_id=None, bot_role_id=None):
    conn = sqlite3.connect("database/autorole.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO autorole (guild_id, user_role_id, bot_role_id)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            user_role_id = excluded.user_role_id,
            bot_role_id = excluded.bot_role_id
    """, (guild_id, user_role_id, bot_role_id))
    conn.commit()
    conn.close()

def get_autorole(guild_id):
    conn = sqlite3.connect("database/autorole.db")
    c = conn.cursor()
    c.execute("SELECT user_role_id, bot_role_id FROM autorole WHERE guild_id=?", (guild_id,))
    result = c.fetchone()
    conn.close()
    return result if result else (None, None)

def init_crypto_db():
    conn = sqlite3.connect('database/crypto.db')
    c = conn.cursor()
    
    # Tabelle für Benutzer-Wallets
    c.execute('''CREATE TABLE IF NOT EXISTS wallets
                 (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 1000)''')
    
    # Tabelle für gehaltene Coins
    c.execute('''CREATE TABLE IF NOT EXISTS coins
                 (user_id INTEGER, coin TEXT, amount REAL,
                  PRIMARY KEY (user_id, coin))''')
    
    # Tabelle für Transaktionsverlauf
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (user_id INTEGER, type TEXT, coin TEXT, amount REAL, value REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Tabelle für Limit Orders
    c.execute('''CREATE TABLE IF NOT EXISTS limit_orders
                 (user_id INTEGER, type TEXT, coin TEXT, amount REAL, price REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

    
# Initialisiere die Datenbank beim Import
init_db()
init_premium_codes_db()
init_backup_db()
init_autorole_db()