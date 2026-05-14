import sqlite3
import config
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel
from typing import List

app = FastAPI()

# ----- Direct Jinja2 environment (no Starlette wrapper) -----
jinja_env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=select_autoescape(['html', 'xml']),
    auto_reload=True,
    cache_size=0,
    bytecode_cache=None
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# -------------------- Watchlist landing page --------------------
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT symbol, name FROM stock ORDER BY symbol")
    all_stocks = {row["symbol"]: row["name"] for row in cursor.fetchall()}
    conn.close()
    
    template = jinja_env.get_template("index.html")
    html_content = template.render(request=request, all_stocks=all_stocks)
    return HTMLResponse(content=html_content)

# -------------------- Watchlist API --------------------
class WatchlistAddRequest(BaseModel):
    symbol: str

@app.get("/api/watchlist")
async def get_watchlist():
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Order by order_index first, then added_at for any with same order (should not happen)
    cursor.execute("SELECT symbol, added_at FROM watchlist ORDER BY order_index ASC, added_at ASC")
    rows = cursor.fetchall()
    conn.close()
    return [{"symbol": row["symbol"], "added_at": row["added_at"]} for row in rows]

@app.post("/api/watchlist")
async def add_to_watchlist(request: WatchlistAddRequest):
    symbol = request.symbol.upper()
    conn = sqlite3.connect(config.DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM stock WHERE symbol = ?", (symbol,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Symbol not found in stock database")
    # Get the maximum order_index to append at the end
    cursor.execute("SELECT COALESCE(MAX(order_index), -1) FROM watchlist")
    max_order = cursor.fetchone()[0]
    try:
        cursor.execute("INSERT INTO watchlist (symbol, order_index) VALUES (?, ?)", (symbol, max_order + 1))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="Symbol already in watchlist")
    conn.close()
    return {"status": "added", "symbol": symbol}

@app.delete("/api/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    symbol = symbol.upper()
    conn = sqlite3.connect(config.DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Symbol not in watchlist")
    return {"status": "removed", "symbol": symbol}

@app.post("/api/watchlist/reorder")
async def reorder_watchlist(symbols: List[str]):
    """Expects a JSON array of symbols in the new order."""
    conn = sqlite3.connect(config.DB_FILE)
    cursor = conn.cursor()
    for idx, sym in enumerate(symbols):
        cursor.execute("UPDATE watchlist SET order_index = ? WHERE symbol = ?", (idx, sym.upper()))
    conn.commit()
    conn.close()
    return {"status": "reordered"}

# -------------------- API routes for stock data --------------------
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
    exchange = row["exchange"] if "exchange" in row.keys() and row["exchange"] else "NYSE"
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
        "has_intraday": False,
        "has_no_volume": False,
        "supported_resolutions": ["D"],
        "intraday_multipliers": [],
        "has_seconds": False,
        "has_daily": True,
        "has_weekly_and_monthly": True
    }

@app.get("/api/bars/{symbol}")
async def get_bars(
    symbol: str,
    resolution: str = Query("D"),
    from_: int = Query(..., alias="from"),
    to: int = Query(...)
):
    # Only daily data is supported (free tier)
    if resolution not in ["D", "1D"]:
        return JSONResponse(content={"s": "no_data"})
    
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM stock WHERE symbol = ?", (symbol.upper(),))
    stock_row = cursor.fetchone()
    if not stock_row:
        conn.close()
        return JSONResponse(content={"s": "error", "errmsg": "Symbol not found"})
    stock_id = stock_row["id"]
    from_dt = datetime.fromtimestamp(from_).strftime('%Y-%m-%d')
    to_dt = datetime.fromtimestamp(to).strftime('%Y-%m-%d')
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
    bars = {"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}
    for row in rows:
        dt = datetime.strptime(row["date"], '%Y-%m-%d')
        bars["t"].append(int(dt.timestamp()))
        bars["o"].append(row["open"])
        bars["h"].append(row["high"])
        bars["l"].append(row["low"])
        bars["c"].append(row["close"])
        bars["v"].append(row["volume"])
    return {"s": "ok", **bars}

# -------------------- Chart page --------------------
@app.get("/chart", response_class=HTMLResponse)
async def chart_page(request: Request):
    template = jinja_env.get_template("chart.html")
    html_content = template.render(request=request)
    return HTMLResponse(content=html_content)