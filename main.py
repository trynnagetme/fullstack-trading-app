import sqlite3
import config
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# -------------------- Existing root route --------------------
@app.get("/")
def read_root(request: Request):
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT id, symbol, name FROM stock')
    rows = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "stocks": rows})

# -------------------- New API routes for TradingView --------------------
@app.get("/api/stocks")
async def get_stocks():
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT symbol, name FROM stock ORDER BY symbol")
    rows = cursor.fetchall()
    conn.close()
    return [{"symbol": row["symbol"], "name": row["name"]} for row in rows]

@app.get("/api/symbols/search")
async def search_symbols(query: str = Query(..., min_length=1)):
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, name, exchange 
        FROM stock 
        WHERE symbol LIKE ? OR name LIKE ? 
        LIMIT 20
    """, (f'%{query}%', f'%{query}%'))
    rows = cursor.fetchall()
    conn.close()
    # Format as expected by TradingView: array of { symbol, full_name, description, exchange, ticker, type }
    result = []
    for row in rows:
        result.append({
            "symbol": row["symbol"],
            "full_name": row["symbol"],
            "description": row["name"],
            "exchange": row["exchange"] if row["exchange"] else "NYSE",
            "ticker": row["symbol"],
            "type": "stock"
        })
    return result

@app.get("/api/symbols/{symbol}")
async def resolve_symbol(symbol: str):
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stock WHERE symbol = ?", (symbol.upper(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Symbol not found")
    
    # Provide default values if columns missing
    exchange = row["exchange"] if "exchange" in row.keys() and row["exchange"] else "NYSE"
    # TradingView symbol info structure
    return {
        "symbol": row["symbol"],
        "ticker": row["symbol"],
        "name": row["name"],
        "description": row["name"],
        "type": "stock",
        "session": "0930-1600",
        "timezone": "America/New_York",
        "exchange": exchange,
        "minmov": 1,
        "pricescale": 100,
        "minmove2": 0,
        "fractional": False,
        "has_intraday": False,          # We only have daily data
        "has_no_volume": False,
        "supported_resolutions": ["D"],  # Only daily
        "intraday_multipliers": [],
        "has_seconds": False,
        "has_daily": True,
        "has_weekly_and_monthly": True   # Derived from daily
    }

@app.get("/api/bars/{symbol}")
async def get_bars(
    symbol: str,
    resolution: str = Query(...),
    from_: int = Query(..., alias="from"),
    to: int = Query(...)
):
    # Since we only have daily data, return no_data for other resolutions
    if resolution not in ["D", "1D"]:
        return JSONResponse(content={"s": "no_data"})
    
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Convert Unix timestamps (seconds) to date strings (YYYY-MM-DD)
    from_dt = datetime.fromtimestamp(from_).strftime('%Y-%m-%d')
    to_dt = datetime.fromtimestamp(to).strftime('%Y-%m-%d')
    
    # Get stock_id first
    cursor.execute("SELECT id FROM stock WHERE symbol = ?", (symbol.upper(),))
    stock_row = cursor.fetchone()
    if not stock_row:
        conn.close()
        return JSONResponse(content={"s": "error", "errmsg": "Symbol not found"})
    stock_id = stock_row["id"]
    
    # Query daily bars
    cursor.execute("""
        SELECT date, open, high, low, close, volume 
        FROM stock_price 
        WHERE stock_id = ? AND date BETWEEN ? AND ?
        ORDER BY date ASC
    """, (stock_id, from_dt, to_dt))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return JSONResponse(content={"s": "no_data"})
    
    # Build response in TradingView's expected format
    bars = {
        "t": [],
        "o": [],
        "h": [],
        "l": [],
        "c": [],
        "v": []
    }
    for row in rows:
        # Parse date string to datetime then to Unix timestamp
        dt = datetime.strptime(row["date"], '%Y-%m-%d')
        bars["t"].append(int(dt.timestamp()))
        bars["o"].append(row["open"])
        bars["h"].append(row["high"])
        bars["l"].append(row["low"])
        bars["c"].append(row["close"])
        bars["v"].append(row["volume"])
    
    return {"s": "ok", **bars}

# -------------------- New page for the chart --------------------
@app.get("/chart")
async def chart_page(request: Request):
    return templates.TemplateResponse("chart.html", {"request": request})

@app.get("/test-chart")
async def test_chart(request: Request):
    return templates.TemplateResponse("test_chart.html", {"request": request})