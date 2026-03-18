# ProjectHub — Final Year Project Management System

A full-stack web application that streamlines the supervision and management of undergraduate final year projects. Built with **FastAPI**, **SQLAlchemy**, **Jinja2**, and **TailwindCSS v4**, it provides a centralised platform for students, supervisors, and administrators to collaborate through every stage of the project lifecycle.

---

## Features

- **Role-Based Access Control (RBAC)** — Three distinct portals for Students, Supervisors, and Administrators, each with tailored dashboards and permissions.
- **Project Management** — Create, assign, and track projects with status updates and member management.
- **Milestone Tracking** — Set milestones with due dates; past dates are blocked both client- and server-side.
- **Document Management** — Upload and manage project documents via Firebase Storage with file-type restrictions.
- **Submission System** — Students submit work at defined stages; supervisors review and grade submissions.
- **Feedback System** — Supervisors and admins can leave structured feedback on submissions and projects.
- **In-App Messaging** — Direct messaging between users with chronologically ordered conversations.
- **Dual Notification System** — In-app notifications plus email notifications for key project events.
- **Forgot Password / Password Reset** — Token-based email password reset flow.
- **Remember Me** — Extends session token and cookie lifetime on login.
- **Department Management** — Admins manage departments; supervisors are linked to departments.
- **Email Deliverability Validation** — Registration validates that email addresses are syntactically valid and have resolvable domains.
- **Rate Limiting** — API routes protected with SlowAPI rate limiting.
- **PRG Pattern** — All form submissions follow Post/Redirect/Get to prevent back-button resubmission.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 + Alembic |
| Templating | Jinja2 3.1 |
| Frontend Styling | TailwindCSS v4 (Browser CDN) |
| Database | SQLite (development) / PostgreSQL (production) |
| File Storage | Firebase Cloud Storage |
| Authentication | JWT (PyJWT) + BCrypt |
| Email | fastapi-mail (SMTP/Gmail) |
| Python | 3.12+ |

---

## Project Structure

```
├── api/
│   ├── core/           # Middleware, dependencies, base models
│   ├── db/             # Database setup
│   ├── utils/          # Helpers, file handling, Firebase, logging
│   └── v1/
│       ├── models/     # SQLAlchemy ORM models (12 models)
│       ├── routes/     # Route handlers — auth, dashboard, external
│       ├── schemas/    # Pydantic schemas
│       └── services/   # Business logic layer
├── alembic/            # Database migration scripts
├── frontend/
│   ├── app/
│   │   ├── components/ # Reusable Jinja2 partials
│   │   └── pages/      # Page templates
│   └── static/         # Static assets
├── templates/          # Email templates
├── main.py             # Application entry point
└── requirements.txt
```

---

## Setup Instructions

### Prerequisites

- Python 3.12 or higher
- Git
- A Gmail account (for email features) or other SMTP provider
- A Firebase project with Cloud Storage enabled (for document uploads)

---

### macOS

```bash
# 1. Clone the repository
git clone https://github.com/joboy-dev/project-hub-fypms.git
cd project-hub-fypms

# 2. (Recommended) Install pyenv to manage Python versions
brew install pyenv
pyenv install 3.12.3
pyenv local 3.12.3

# 3. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment variables
cp .env.example .env
# Open .env in your editor and fill in the values (see Environment Variables section below)

# 6. Add your Firebase service account key
# Download serviceAccount.json from your Firebase project console
# and place it in the project root

# 7. Run database migrations
alembic upgrade head

# 8. Start the development server
uvicorn main:app --reload --port 7001
```

Visit `http://localhost:7001` in your browser.

---

### Linux (Ubuntu / Debian)

```bash
# 1. Install system dependencies
sudo apt update && sudo apt install -y python3.12 python3.12-venv python3-pip git

# 2. Clone the repository
git clone https://github.com/joboy-dev/project-hub-fypms.git
cd project-hub-fypms

# 3. Create and activate a virtual environment
python3.12 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment variables
cp .env.example .env
# Edit .env with your configuration values

# 6. Add your Firebase service account key
# Place serviceAccount.json (downloaded from Firebase Console) in the project root

# 7. Run database migrations
alembic upgrade head

# 8. Start the development server
uvicorn main:app --reload --port 7001
```

Visit `http://localhost:7001` in your browser.

---

### Windows

```powershell
# 1. Install Python 3.12 from https://www.python.org/downloads/
#    Ensure "Add Python to PATH" is checked during installation

# 2. Clone the repository (use Git Bash or PowerShell with Git installed)
git clone https://github.com/joboy-dev/project-hub-fypms.git
cd project-hub-fypms

# 3. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment variables
copy .env.example .env
# Open .env in Notepad or VS Code and fill in the values

# 6. Add your Firebase service account key
# Place serviceAccount.json (downloaded from Firebase Console) in the project root

# 7. Run database migrations
alembic upgrade head

# 8. Start the development server
uvicorn main:app --reload --port 7001
```

Visit `http://localhost:7001` in your browser.

> **Note for Windows users:** If you encounter issues with `python` not being found, try `py` instead. For SSL/certificate errors with email, ensure your Python installation includes the standard `certifi` package (included in `requirements.txt`).

---

## Environment Variables

Create a `.env` file in the project root. Required variables:

```env
# Application
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_MINUTES=1440

# Database
DATABASE_URL=sqlite:///./projecthub.db

# Email (Gmail example)
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_FROM=your-email@gmail.com
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=465
MAIL_SSL_TLS=True
MAIL_STARTTLS=False

# Firebase
FIREBASE_STORAGE_BUCKET=your-project.appspot.com

# App URL (used in email links)
APP_URL=http://localhost:7001

# Google OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

> For Gmail, use an **App Password** (not your account password). Enable 2FA on your Google account, then generate an App Password under Security settings.

---

## User Roles

| Role | Access |
|---|---|
| **Student** | Register, create/join projects, submit work, upload documents, track milestones, message supervisors |
| **Supervisor** | Review assigned projects, grade submissions, leave feedback, manage milestones, message students |
| **Admin** | Full system access — manage all users, departments, projects, and system settings |

Access each portal at:
- Student: `http://localhost:7001/auth?role=student`
- Supervisor: `http://localhost:7001/auth?role=supervisor`
- Admin: `http://localhost:7001/auth?role=admin`

---

## Running Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "description of change"

# Roll back one migration
alembic downgrade -1
```

---

## License

This project was developed as a final year project submission. All rights reserved.

---

## CV Description

> **ProjectHub — Final Year Project Management System**
> Designed and built a full-stack web application using FastAPI and SQLAlchemy, implementing role-based access control across 3 user roles (Student, Supervisor, Administrator), 12 database models, and over 50 route handlers covering project management, milestone tracking, document storage, in-app messaging, dual email/in-app notifications, and a submission grading workflow.