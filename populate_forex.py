import sqlite3
import config
from datetime import datetime, timedelta
import random
import math

# List of forex pairs to add (symbol, name)
FOREX_PAIRS = [
    ("EURUSD", "Euro / US Dollar"),
    ("GBPUSD", "British Pound / US Dollar"),
    ("USDJPY", "US Dollar / Japanese Yen"),
    ("AUDUSD", "Australian Dollar / US Dollar"),
    ("USDCAD", "US Dollar / Canadian Dollar"),
    ("USDCHF", "US Dollar / Swiss Franc"),
    ("NZDUSD", "New Zealand Dollar / US Dollar"),
    ("EURGBP", "Euro / British Pound"),
    ("EURJPY", "Euro / Japanese Yen"),
    ("GBPJPY", "British Pound / Japanese Yen"),
]

def generate_random_walk(start_price, days, volatility=0.008, drift=0.0001):
    """
    Generate a random walk price series.
    start_price: initial price (e.g., 1.1000 for EURUSD)
    days: number of daily prices
    volatility: daily volatility (standard deviation of log returns)
    drift: average daily return (e.g., 0.0001 = 0.01% per day)
    Returns list of prices.
    """
    prices = [start_price]
    for _ in range(days - 1):
        ret = random.gauss(drift, volatility)
        new_price = prices[-1] * math.exp(ret)
        # Keep within reasonable range (optional)
        if new_price < 0.0001:
            new_price = 0.0001
        prices.append(new_price)
    return prices

def generate_ohlcv_from_close(prices):
    """
    Convert daily close prices to OHLCV with realistic intraday range.
    Returns list of tuples (open, high, low, close, volume)
    """
    ohlcv = []
    for i, close in enumerate(prices):
        # Simulate open = previous close (except first day)
        if i == 0:
            open_price = close * (1 + random.uniform(-0.002, 0.002))
        else:
            open_price = prices[i-1]
        
        # Calculate high/low based on volatility
        daily_range = abs(close - open_price) * random.uniform(1.2, 2.5)
        high = max(open_price, close) + daily_range * random.uniform(0, 0.8)
        low = min(open_price, close) - daily_range * random.uniform(0, 0.8)
        
        # Ensure high/low are not extreme (just for realism)
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        
        # Volume: random between 10M and 200M (forex volume in units, just for display)
        volume = random.randint(10_000_000, 200_000_000)
        
        ohlcv.append((open_price, high, low, close, volume))
    return ohlcv

def populate_forex():
    conn = sqlite3.connect(config.DB_FILE)
    cursor = conn.cursor()
    
    # Add forex pairs to stock table if not exist
    for symbol, name in FOREX_PAIRS:
        cursor.execute("INSERT OR IGNORE INTO stock (symbol, name) VALUES (?, ?)", (symbol, name))
    conn.commit()
    
    # Get forex stock ids
    placeholders = ','.join(['?'] * len(FOREX_PAIRS))
    symbols = [pair[0] for pair in FOREX_PAIRS]
    cursor.execute(f"SELECT id, symbol FROM stock WHERE symbol IN ({placeholders})", symbols)
    stock_ids = {row[1]: row[0] for row in cursor.fetchall()}
    
    # Generate 2 years of daily data
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=365*2)  # 2 years
    date_list = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    
    for symbol, stock_id in stock_ids.items():
        print(f"Generating data for {symbol}...")
        # Set realistic starting price for each pair
        if symbol == "EURUSD":
            start_price = 1.1000
        elif symbol == "GBPUSD":
            start_price = 1.3000
        elif symbol == "USDJPY":
            start_price = 150.00
        elif symbol == "AUDUSD":
            start_price = 0.6600
        elif symbol == "USDCAD":
            start_price = 1.3500
        elif symbol == "USDCHF":
            start_price = 0.9000
        elif symbol == "NZDUSD":
            start_price = 0.6000
        elif symbol == "EURGBP":
            start_price = 0.8500
        elif symbol == "EURJPY":
            start_price = 165.00
        elif symbol == "GBPJPY":
            start_price = 195.00
        else:
            start_price = 100.0
        
        # Generate random walk close prices
        close_prices = generate_random_walk(start_price, len(date_list), volatility=0.006, drift=0.00002)
        ohlcv = generate_ohlcv_from_close(close_prices)
        
        # Insert data into stock_price
        for i, date in enumerate(date_list):
            open_p, high_p, low_p, close_p, vol = ohlcv[i]
            cursor.execute("""
                INSERT OR REPLACE INTO stock_price (stock_id, date, open, close, high, low, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (stock_id, date.strftime('%Y-%m-%d'), open_p, close_p, high_p, low_p, vol))
        
        conn.commit()
        print(f"  Inserted {len(date_list)} days for {symbol}")
    
    conn.close()
    print("Forex data population complete.")

if __name__ == "__main__":
    populate_forex()