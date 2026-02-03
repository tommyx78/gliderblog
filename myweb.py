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

# --- Initial Configuration ---
config = AppConfig("config.ini")
app = FastAPI(title="Web Login")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

db = Database(config.db)
security = DeviceSecurity(db)

# Session Constants
COOKIE_NAME = "user_session"
COOKIE_TYPE = "user_type"  # "0" = admin, "1" = user
COOKIE_EXPIRE_MINUTES = 60

# --- Email Logic (Dynamic SMTP) ---

def send_verification_email(email: str, username: str, token: str):
    """Sends the activation email using data from config.ini"""
    
    # Activation link construction
    host_link = config.email["hostlink"]
    port_link = config.email["portlink"]
    verify_link = f"https://{host_link}:{port_link}/verify/{token}"
    
    # Message Preparation
    msg = MIMEMultipart()
    msg["From"] = config.smtp["user"]
    msg["To"] = email
    msg["Subject"] = "Account Activation - Glider Portal"
    
    body = f"""
    Hello {username},
    Your account has been created. To activate it and be able to log in, 
    please click the following link:
    
    {verify_link}
    
    If you did not request this activation, please ignore this email.
    """
    msg.attach(MIMEText(body, "plain"))
    
    try:
        with smtplib.SMTP(config.smtp["server"], config.smtp["port"]) as server:
            server.starttls()
            server.login(config.smtp["user"], config.smtp["password"])
            server.send_message(msg)
    except Exception as e:
        print(f"EMAIL SEND ERROR: {e}")

# --- Dependency Injection & Route Protection ---

async def get_current_user(user_session: Optional[str] = Cookie(None)):
    """Verifies if the user has an active session."""
    if not user_session:
        raise HTTPException(status_code=307)
    return user_session

async def get_admin_user(
    user_session: str = Depends(get_current_user), 
    user_type: Optional[str] = Cookie(None)
):
    """Verifies if the logged-in user is an administrator."""
    if user_type != "0":
        raise HTTPException(status_code=403)
    return user_session

@app.exception_handler(307)
async def redirect_login_handler(request: Request, exc: HTTPException):
    return RedirectResponse(url="/login")

@app.exception_handler(403)
async def redirect_admin_error_handler(request: Request, exc: HTTPException):
    return RedirectResponse(url="/welcome?error=Access+denied:+admin+permissions+required")

# --- Public Routes ---

@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    """Displays the self-registration form"""
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


# --- 1. Password Reset Request Page ---
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
                # Asynchronous email sending
                background_tasks.add_task(send_reset_email, email, user['username'], token)
        
        # For security reasons, show the same message even if the email does not exist
        return templates.TemplateResponse("forgot_password.html", {
            "request": request, "success": "If the email is in our system, you will receive a reset link shortly."
        })
    finally:
        if 'conn' in locals(): conn.close()

# --- 2. New Password Setup Page ---
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
                return templates.TemplateResponse("login.html", {"request": request, "success": "Password updated! You can now log in."})
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid or expired token."})
    finally:
        if 'conn' in locals(): conn.close()

# --- Password Recovery Email Function ---
def send_reset_email(email: str, username: str, token: str):
    host_link, port_link = config.email["hostlink"], config.email["portlink"]
    reset_link = f"https://{host_link}:{port_link}/reset-password/{token}"
    
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = config.smtp["user"], email, "Password Recovery"
    body = f"Hello {username},\n\nPlease click here to reset your password: {reset_link}\n\nIf you did not request this reset, please ignore this email."
    msg.attach(MIMEText(body, "plain"))
    
    try:
        with smtplib.SMTP(config.smtp["server"], config.smtp["port"]) as server:
            server.starttls()
            server.login(config.smtp["user"], config.smtp["password"])
            server.send_message(msg)
    except Exception as e:
        print(f"Error: {e}")


@app.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """Handles registration form submission"""
    token = secrets.token_urlsafe(32)
    user_type = 1  # Standard registration = non-admin user

    try:
        conn = db.conn()
        with conn.cursor() as cursor:
            # Check if user already exists
            cursor.execute("SELECT UserId FROM login WHERE username=%s OR email=%s", (username, email))
            if cursor.fetchone():
                return templates.TemplateResponse("register.html", {"request": request, "error": "Username or Email already taken"})

            pw_hash = security.hash_password(password)
            cursor.execute(
                "INSERT INTO login (username, email, password, type, email_token, is_active) VALUES (%s, %s, %s, %s, %s, 0)",
                (username, email, pw_hash, user_type, token)
            )
            conn.commit()
            
            # Send activation email
            background_tasks.add_task(send_verification_email, email, username, token)

        return templates.TemplateResponse("login.html", {
            "request": request, 
            "success": "Registration complete! Please check your email to activate your account."
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
        # Check if the user has activated via email
        if user.get("is_active") == 0:
            return templates.TemplateResponse("login.html", {
                "request": request, 
                "error": "Account not active. Please check your verification email."
            })
            
        max_age = int(timedelta(minutes=COOKIE_EXPIRE_MINUTES).total_seconds())
        resp = RedirectResponse(url="/welcome", status_code=302)
        
        # Secure cookie parameters
        cookie_params = {"httponly": True, "max_age": max_age, "samesite": "lax"}
        resp.set_cookie(key=COOKIE_NAME, value=user["username"], **cookie_params)
        resp.set_cookie(key=COOKIE_TYPE, value=str(user.get("type", "1")), **cookie_params)
        return resp
    
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/verify/{token}", response_class=HTMLResponse)
async def verify_account(request: Request, token: str):
    """Endpoint for account activation via email link."""
    try:
        conn = db.conn()
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT username FROM login WHERE email_token=%s", (token,))
            if cursor.fetchone():
                cursor.execute("UPDATE login SET is_active=1, email_token=NULL WHERE email_token=%s", (token,))
                conn.commit()
                return templates.TemplateResponse("login.html", {
                    "request": request, 
                    "success": "Account activated successfully! You can now log in."
                })
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid or expired token."})
    finally:
        if 'conn' in locals(): conn.close()

# --- Protected Routes ---

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
            # Uniqueness check (Case Insensitivity usually handled by the DB)
            cursor.execute("SELECT UserId FROM login WHERE username=%s OR email=%s", (username, email))
            if cursor.fetchone():
                return templates.TemplateResponse("create_user.html", {
                    "request": request, "username": admin_name, "error": "Username or Email already present"
                })

            pw_hash = security.hash_password(password)
            # Insertion with is_active=0 (requires email activation)
            cursor.execute(
                "INSERT INTO login (username, email, password, type, email_token, is_active) VALUES (%s, %s, %s, %s, %s, 0)",
                (username, email, pw_hash, user_type, token)
            )
            conn.commit()
            
            # Asynchronous email sending (does not block execution)
            background_tasks.add_task(send_verification_email, email, username, token)

        return templates.TemplateResponse("create_user.html", {
            "request": request, 
            "username": admin_name, 
            "success": f"User '{username}' created. Activation email sent."
        })
    except Exception as e:
        return templates.TemplateResponse("create_user.html", {
            "request": request, "username": admin_name, "error": f"Error: {e}"
        })
    finally:
        if 'conn' in locals(): conn.close()

@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    resp.delete_cookie(COOKIE_TYPE)
    return resp

# --- Startup ---

if __name__ == "__main__":
    uvicorn.run(
        "myweb:app", 
        host=config.server["host"], 
        port=config.server["port"], 
        reload=True
    )