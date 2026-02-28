import sqlite3, config
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/")
def read_root(request: Request):
    connection = sqlite3.connect(config.DB_FILE) 
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute('SELECT id, symbol, name FROM stock')
    rows = cursor.fetchall()

    return templates.TemplateResponse("index.html", {"request": request, "stocks": rows})
