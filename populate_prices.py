import sqlite3, config
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import TimeFrame

connection = sqlite3.connect(config.DB_FILE)

connection.row_factory = sqlite3.Row

cursor = connection.cursor()

cursor.execute('''
    SELECT id, symbol, name FROM stock
''')
rows = cursor.fetchall()

symbols = [row['symbol'] for row in rows]
stock_dict = {row['symbol']: row['id'] for row in rows}

print(f"Found {len(symbols)} symbols")

api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, base_url=config.API_URL)

chunk_size = 200
for i in range(0, len(symbols), chunk_size):
    symbol_chunk = symbols[i:i+chunk_size]
    
    print(f"Processing chunk {i} / {len(symbols)}")
    bars = api.get_bars(symbol_chunk, TimeFrame.Day, "2020-01-01")
    
    for bar in bars:
        symbol = bar.S
        stock_id = stock_dict[symbol]
        cursor.execute('''
            INSERT INTO stock_price (stock_id, date, open, close, high, low, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            stock_id,
            bar.t.date(),
            bar.o,
            bar.c,
            bar.h,
            bar.l,
            bar.v
        ))
    
    connection.commit()

connection.close()
