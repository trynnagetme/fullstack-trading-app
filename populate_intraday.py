import sqlite3
import config
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import TimeFrame, TimeFrameUnit
from datetime import datetime, timedelta
import time

# Only fetch intraday for your watchlist
WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX"]

# Resolutions
RESOLUTIONS = {
    '1min': TimeFrame(1, TimeFrameUnit.Minute),
    '5min': TimeFrame(5, TimeFrameUnit.Minute),
    '15min': TimeFrame(15, TimeFrameUnit.Minute),
    '1H': TimeFrame(1, TimeFrameUnit.Hour),
}

def populate_intraday(symbols, days_back=7):
    api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, base_url=config.API_URL)
    conn = sqlite3.connect(config.DB_FILE)
    cursor = conn.cursor()
    
    # Ensure table exists
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
    conn.commit()
    
    # Format dates correctly for Alpaca API (RFC3339)
    end = datetime.now()
    start = end - timedelta(days=days_back)
    start_str = start.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_str = end.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    for res_name, tf in RESOLUTIONS.items():
        print(f"Fetching {res_name} data for {len(symbols)} symbols...")
        for i in range(0, len(symbols), 200):
            chunk = symbols[i:i+200]
            try:
                bars = api.get_bars(chunk, tf, start=start_str, end=end_str, adjustment='raw')
                count = 0
                for bar in bars:
                    cursor.execute('''
                        INSERT OR REPLACE INTO stock_price_intraday
                        (symbol, resolution, timestamp, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        bar.S,
                        res_name,
                        int(bar.t.timestamp()),
                        bar.o, bar.h, bar.l, bar.c, bar.v
                    ))
                    count += 1
                conn.commit()
                print(f"  Saved {count} {res_name} bars for chunk {i//200 + 1}")
            except Exception as e:
                print(f"Error with {res_name} chunk: {e}")
            time.sleep(0.5)  # rate limit
    
    conn.close()

if __name__ == "__main__":
    print(f"Fetching intraday data for watchlist: {WATCHLIST}")
    populate_intraday(WATCHLIST)