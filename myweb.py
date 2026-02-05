from fastapi import (
    FastAPI, Request, Form, Response, Cookie, Depends, HTTPException
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
import uvicorn

from database import Database
from security import DeviceSecurity
from config import AppConfig

config = AppConfig("config.ini")
app = FastAPI(title="GliderBlog")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

db = Database(config.db)
security = DeviceSecurity(db)

COOKIE_NAME = "user_session"

# --- HELPER: Recupera utente se esiste ---
async def get_optional_user(user_session: Optional[str] = Cookie(None)):
    """Restituisce lo username se loggato, altrimenti None senza bloccare"""
    return user_session

async def get_current_user(user_session: Optional[str] = Cookie(None)):
    """Blocca l'accesso se non loggato"""
    if not user_session:
        raise HTTPException(status_code=303, detail="Not logged in")
    return user_session

# --- Rotte Pubbliche ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/feed", response_class=HTMLResponse)
async def global_feed(request: Request, username: Optional[str] = Depends(get_optional_user)):
    """Bacheca pubblica accessibile a TUTTI"""
    conn = db.conn()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT b.PostID, b.titolo, b.testo, b.timestamp, l.username as autore 
                FROM blog b JOIN login l ON b.UserID = l.UserId 
                ORDER BY b.timestamp DESC
            """)
            posts = cursor.fetchall()
        return templates.TemplateResponse("feed.html", {
            "request": request, 
            "username": username, # Sarà None se non loggato
            "posts": posts
        })
    finally:
        conn.close()

# --- Rotte Autenticazione ---

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if security.verify_user(username, password):
        resp = RedirectResponse(url="/welcome", status_code=303)
        resp.set_cookie(key=COOKIE_NAME, value=username)
        return resp
    return RedirectResponse(url="/login?error=1", status_code=303)

@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/feed", status_code=302) # Logout rimanda al feed
    resp.delete_cookie(COOKIE_NAME)
    return resp

# --- Rotte Protette (Richiedono Login) ---

@app.post("/posts/add")
async def add_post(titolo: str = Form(...), testo: str = Form(...), username: str = Depends(get_current_user)):
    conn = db.conn()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT UserId FROM login WHERE username=%s", (username,))
            user = cursor.fetchone()
            cursor.execute("INSERT INTO blog (UserID, titolo, testo) VALUES (%s, %s, %s)", 
                           (user['UserId'], titolo, testo))
            conn.commit()
        return RedirectResponse(url="/feed", status_code=303)
    finally:
        conn.close()

@app.get("/posts/delete/{post_id}")
async def delete_post(post_id: int, username: str = Depends(get_current_user)):
    conn = db.conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE b FROM blog b JOIN login l ON b.UserID = l.UserId 
                WHERE b.PostID=%s AND l.username=%s
            """, (post_id, username))
            conn.commit()
        return RedirectResponse(url="/feed", status_code=303)
    finally:
        conn.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)