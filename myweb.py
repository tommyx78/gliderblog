from fastapi import (
    FastAPI, Request, Form, Response, Cookie, Depends, HTTPException, BackgroundTasks
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from typing import Optional
from datetime import timedelta
import uvicorn
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from database import Database
from security import DeviceSecurity
from config import AppConfig

# --- Configurazione Iniziale ---
config = AppConfig("config.ini")
app = FastAPI(title="Web Login")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

db = Database(config.db)
security = DeviceSecurity(db)

# Costanti Sessione
COOKIE_NAME = "user_session"
COOKIE_TYPE = "user_type"  # "0" = admin, "1" = user
COOKIE_EXPIRE_MINUTES = 60

# --- Logica Email (SMTP Dinamico) ---

def send_verification_email(email: str, username: str, token: str):
    """Invia l'email di attivazione usando i dati dal config.ini"""
    
    # Costruzione link di attivazione
    host_link = config.email["hostlink"]
    port_link = config.email["portlink"]
    verify_link = f"https://{host_link}:{port_link}/verify/{token}"
    
    # Preparazione Messaggio
    msg = MIMEMultipart()
    msg["From"] = config.smtp["user"]
    msg["To"] = email
    msg["Subject"] = "Attivazione Account - Portale Glider"
    
    body = f"""
    Ciao {username},
    Il tuo account è stato creato. Per attivarlo e poter accedere, 
    clicca sul link seguente:
    
    {verify_link}
    
    Se non hai richiesto tu l'attivazione, ignora questa mail.
    """
    msg.attach(MIMEText(body, "plain"))
    
    try:
        with smtplib.SMTP(config.smtp["server"], config.smtp["port"]) as server:
            server.starttls()
            server.login(config.smtp["user"], config.smtp["password"])
            server.send_message(msg)
    except Exception as e:
        print(f"ERRORE INVIO MAIL: {e}")

# --- Dependency Injection & Protezione Rotte ---

async def get_current_user(user_session: Optional[str] = Cookie(None)):
    """Verifica se l'utente ha una sessione attiva."""
    if not user_session:
        raise HTTPException(status_code=307)
    return user_session

async def get_admin_user(
    user_session: str = Depends(get_current_user), 
    user_type: Optional[str] = Cookie(None)
):
    """Verifica se l'utente loggato è un amministratore."""
    if user_type != "0":
        raise HTTPException(status_code=403)
    return user_session

@app.exception_handler(307)
async def redirect_login_handler(request: Request, exc: HTTPException):
    return RedirectResponse(url="/login")

@app.exception_handler(403)
async def redirect_admin_error_handler(request: Request, exc: HTTPException):
    return RedirectResponse(url="/welcome?error=Accesso+negato:+permessi+admin+necessari")

# --- Rotte Pubbliche ---

@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    """Visualizza il form di auto-registrazione"""
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


# --- 1. Pagina Richiesta Reset ---
@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_form(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@app.post("/forgot-password")
async def forgot_password_submit(request: Request, background_tasks: BackgroundTasks, email: str = Form(...)):
    token = secrets.token_urlsafe(32)
    try:
        conn = db.conn()
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT username FROM login WHERE email=%s", (email,))
            user = cursor.fetchone()
            if user:
                cursor.execute("UPDATE login SET reset_token=%s WHERE email=%s", (token, email))
                conn.commit()
                # Invio mail asincrono
                background_tasks.add_task(send_reset_email, email, user['username'], token)
        
        # Per sicurezza, mostriamo lo stesso messaggio anche se l'email non esiste
        return templates.TemplateResponse("forgot_password.html", {
            "request": request, "success": "Se l'email è nel sistema, riceverai un link di reset a breve."
        })
    finally:
        if 'conn' in locals(): conn.close()

# --- 2. Pagina Impostazione Nuova Password ---
@app.get("/reset-password/{token}", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    return templates.TemplateResponse("reset_password_confirm.html", {"request": request, "token": token})

@app.post("/reset-password/{token}")
async def reset_password_submit(request: Request, token: str, new_password: str = Form(...)):
    try:
        conn = db.conn()
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT UserId FROM login WHERE reset_token=%s", (token,))
            if cursor.fetchone():
                new_hash = security.hash_password(new_password)
                cursor.execute("UPDATE login SET password=%s, reset_token=NULL WHERE reset_token=%s", (new_hash, token))
                conn.commit()
                return templates.TemplateResponse("login.html", {"request": request, "success": "Password aggiornata! Ora puoi accedere."})
            return templates.TemplateResponse("login.html", {"request": request, "error": "Token non valido o scaduto."})
    finally:
        if 'conn' in locals(): conn.close()

# --- Funzione Email Recupero ---
def send_reset_email(email: str, username: str, token: str):
    host_link, port_link = config.email["hostlink"], config.email["portlink"]
    reset_link = f"https://{host_link}:{port_link}/reset-password/{token}"
    
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = config.smtp["user"], email, "Recupero Password"
    body = f"Ciao {username},\n\nClicca qui per reimpostare la tua password: {reset_link}\n\nSe non hai richiesto tu il reset, ignora questa mail."
    msg.attach(MIMEText(body, "plain"))
    
    try:
        with smtplib.SMTP(config.smtp["server"], config.smtp["port"]) as server:
            server.starttls()
            server.login(config.smtp["user"], config.smtp["password"])
            server.send_message(msg)
    except Exception as e:
        print(f"Errore: {e}")


@app.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """Gestisce l'invio del form di registrazione"""
    token = secrets.token_urlsafe(32)
    user_type = 1  # Registrazione standard = utente non admin

    try:
        conn = db.conn()
        with conn.cursor() as cursor:
            # Verifica se esiste già
            cursor.execute("SELECT UserId FROM login WHERE username=%s OR email=%s", (username, email))
            if cursor.fetchone():
                return templates.TemplateResponse("register.html", {"request": request, "error": "Username o Email già occupati"})

            pw_hash = security.hash_password(password)
            cursor.execute(
                "INSERT INTO login (username, email, password, type, email_token, is_active) VALUES (%s, %s, %s, %s, %s, 0)",
                (username, email, pw_hash, user_type, token)
            )
            conn.commit()
            
            # Invio email di attivazione
            background_tasks.add_task(send_verification_email, email, username, token)

        return templates.TemplateResponse("login.html", {
            "request": request, 
            "success": "Registrazione completata! Controlla la mail per attivare l'account."
        })
    except Exception as e:
        return templates.TemplateResponse("register.html", {"request": request, "error": str(e)})
    finally:
        if 'conn' in locals(): conn.close()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
async def login_submit(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...)
):
    user = None
    try:
        conn = db.conn()
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM login WHERE username=%s", (username,))
            user = cursor.fetchone()
    finally:
        if 'conn' in locals(): conn.close()

    if user and security.verify_password(password, user["password"]):
        # Controllo se l'utente ha attivato l'email
        if user.get("is_active") == 0:
            return templates.TemplateResponse("login.html", {
                "request": request, 
                "error": "Account non attivo. Controlla la mail di verifica."
            })
            
        max_age = int(timedelta(minutes=COOKIE_EXPIRE_MINUTES).total_seconds())
        resp = RedirectResponse(url="/welcome", status_code=302)
        
        # Parametri cookie sicuri
        cookie_params = {"httponly": True, "max_age": max_age, "samesite": "lax"}
        resp.set_cookie(key=COOKIE_NAME, value=user["username"], **cookie_params)
        resp.set_cookie(key=COOKIE_TYPE, value=str(user.get("type", "1")), **cookie_params)
        return resp
    
    return templates.TemplateResponse("login.html", {"request": request, "error": "Credenziali errate"})

@app.get("/verify/{token}", response_class=HTMLResponse)
async def verify_account(request: Request, token: str):
    """Endpoint per l'attivazione dell'account tramite link email."""
    try:
        conn = db.conn()
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT username FROM login WHERE email_token=%s", (token,))
            if cursor.fetchone():
                cursor.execute("UPDATE login SET is_active=1, email_token=NULL WHERE email_token=%s", (token,))
                conn.commit()
                return templates.TemplateResponse("login.html", {
                    "request": request, 
                    "success": "Account attivato con successo! Ora puoi accedere."
                })
            return templates.TemplateResponse("login.html", {"request": request, "error": "Token non valido o scaduto."})
    finally:
        if 'conn' in locals(): conn.close()

# --- Rotte Protette ---

@app.get("/welcome", response_class=HTMLResponse)
async def welcome_page(
    request: Request, 
    username: str = Depends(get_current_user), 
    user_type: Optional[str] = Cookie(None)
):
    return templates.TemplateResponse("welcome.html", {
        "request": request, 
        "username": username, 
        "is_admin": user_type == "0",
        "error": request.query_params.get("error")
    })

@app.get("/create_user", response_class=HTMLResponse)
async def create_user_form(request: Request, username: str = Depends(get_admin_user)):
    return templates.TemplateResponse("create_user.html", {
        "request": request, 
        "username": username,
        "error": None,
        "success": None
    })

@app.post("/create_user", response_class=HTMLResponse)
async def create_user_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_admin: Optional[str] = Form(None),
    admin_name: str = Depends(get_admin_user)
):
    user_type = 0 if is_admin == "on" else 1
    token = secrets.token_urlsafe(32)

    try:
        conn = db.conn()
        with conn.cursor() as cursor:
            # Controllo unicità (Case Insensitive solitamente gestito dal DB)
            cursor.execute("SELECT UserId FROM login WHERE username=%s OR email=%s", (username, email))
            if cursor.fetchone():
                return templates.TemplateResponse("create_user.html", {
                    "request": request, "username": admin_name, "error": "Username o Email già presenti"
                })

            pw_hash = security.hash_password(password)
            # Inserimento con is_active=0 (necessita attivazione email)
            cursor.execute(
                "INSERT INTO login (username, email, password, type, email_token, is_active) VALUES (%s, %s, %s, %s, %s, 0)",
                (username, email, pw_hash, user_type, token)
            )
            conn.commit()
            
            # Invio email asincrono (non blocca l'esecuzione)
            background_tasks.add_task(send_verification_email, email, username, token)

        return templates.TemplateResponse("create_user.html", {
            "request": request, 
            "username": admin_name, 
            "success": f"Utente '{username}' creato. Mail di attivazione inviata."
        })
    except Exception as e:
        return templates.TemplateResponse("create_user.html", {
            "request": request, "username": admin_name, "error": f"Errore: {e}"
        })
    finally:
        if 'conn' in locals(): conn.close()

@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    resp.delete_cookie(COOKIE_TYPE)
    return resp

# --- Avvio ---

if __name__ == "__main__":
    uvicorn.run(
        "myweb:app", 
        host=config.server["host"], 
        port=config.server["port"], 
        reload=True
    )