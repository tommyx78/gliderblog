GliderBlog - Microblog Platform
--------------------------------
GliderBlog is a lightweight, secure, and high-performance microblogging platform built with FastAPI. It features a robust user management system, a protected administrative area, and an asynchronous email notification system for account activation and password recovery.

Key Features
----------------------------
Robust Authentication: Session management via HTTPOnly and SameSite cookies to prevent XSS and CSRF attacks.
- Admin Dashboard: Dedicated area for managing users and assigning roles (Admin vs. Standard User).
- Self-Registration: Public registration flow with mandatory email verification to prevent bot accounts.
- Secure Password Reset: Secure "Forgot Password" workflow using time-sensitive unique tokens.
- Asynchronous Emails: Leverages FastAPI BackgroundTasks to send emails via SMTP without blocking the user interface.
- Clean Architecture: Fully configurable via config.ini for seamless transitions between development and production environments.

Tech Stack
----------------------------
Backend: Python 3.x, FastAPI, Uvicorn.

Database: MySQL / MariaDB (via MySQL Connector).

Template Engine: Jinja2.

Frontend: Responsive HTML5 & CSS3.

Email: SMTP Protocol (TLS supported).
