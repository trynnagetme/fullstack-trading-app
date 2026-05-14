import sqlite3
import config

connection = sqlite3.connect(config.DB_FILE)
cursor = connection.cursor()

# Stocks table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL
    )
''')

# Daily OHLCV table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_price (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_id INTEGER NOT NULL,
        date NOT NULL,
        open NOT NULL,
        close NOT NULL,
        high NOT NULL,
        low NOT NULL,
        volume NOT NULL,
        FOREIGN KEY (stock_id) REFERENCES stock (id)
    )
''')

# Watchlist table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS watchlist (
        symbol TEXT PRIMARY KEY,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        order_index INTEGER DEFAULT 0
    )
''')

# Intraday table (uncommented)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_price_intraday (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        resolution TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume INTEGER NOT NULL,
        UNIQUE(symbol, resolution, timestamp)
    )
''')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_intraday_lookup ON stock_price_intraday(symbol, resolution, timestamp)')

connection.commit()
connection.close()
print("Database tables created/verified successfully (including watchlist and intraday).")