import os
import re
import shutil
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import pytesseract

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "classroom.db")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "tif", "tiff"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-development-key")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                full_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                author_name TEXT,
                role TEXT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                is_public INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        # Safe migration if table previously existed without new columns
        existing_cols = [c[1] for c in conn.execute("PRAGMA table_info(saved_notes)").fetchall()]
        if "user_id" not in existing_cols:
            conn.execute("ALTER TABLE saved_notes ADD COLUMN user_id INTEGER")
        if "author_name" not in existing_cols:
            conn.execute("ALTER TABLE saved_notes ADD COLUMN author_name TEXT")
        if "role" not in existing_cols:
            conn.execute("ALTER TABLE saved_notes ADD COLUMN role TEXT")
        if "is_public" not in existing_cols:
            conn.execute("ALTER TABLE saved_notes ADD COLUMN is_public INTEGER DEFAULT 1")

        # Seed initial demo accounts for quick testing if table empty
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            now_iso = datetime.now().isoformat(timespec="seconds")
            conn.execute(
                "INSERT INTO users (username, password_hash, role, full_name, created_at) VALUES (?, ?, ?, ?, ?)",
                ("lecturer", generate_password_hash("lecturer123"), "lecturer", "Prof. Sharma", now_iso)
            )
            conn.execute(
                "INSERT INTO users (username, password_hash, role, full_name, created_at) VALUES (?, ?, ?, ?, ?)",
                ("student", generate_password_hash("student123"), "student", "Rahul Kumar", now_iso)
            )

@app.context_processor
def inject_user():
    if "user_id" in session:
        return {
            "current_user": {
                "id": session["user_id"],
                "username": session["username"],
                "role": session["role"],
                "full_name": session["full_name"],
            }
        }
    return {"current_user": None}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access that page.", "error")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def summarize_text(text, max_sentences=3):
    """Small offline extractive summary; this is not a generative AI model."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
    if len(sentences) <= max_sentences:
        return " ".join(sentences) if sentences else text.strip()
    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    stop = {"the","and","is","in","to","of","a","for","on","with","as","by","an","are","be","this","that","it","from","or","at","we","can"}
    freq = {}
    for word in words:
        if word not in stop and len(word) > 2:
            freq[word] = freq.get(word, 0) + 1
    scored = []
    for i, sentence in enumerate(sentences):
        terms = re.findall(r"[A-Za-z0-9']+", sentence.lower())
        score = sum(freq.get(w, 0) for w in terms if w not in stop) / max(len(terms), 1)
        scored.append((score, i, sentence))
    selected = sorted(sorted(scored, reverse=True)[:max_sentences], key=lambda x: x[1])
    return " ".join(item[2] for item in selected)

def keywords(text, limit=8):
    stop = {"the","and","is","in","to","of","a","for","on","with","as","by","an","are","be","this","that","it","from","or","at","we","can","will","into","their","they","these","those"}
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text.lower())
    counts = {}
    for word in words:
        if word not in stop:
            counts[word] = counts.get(word, 0) + 1
    return [w for w, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:limit]]

@app.route("/")
def index():
    return render_template("index.html")

def configure_tesseract():
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(
            r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"
        ),
    ]

    env_path = os.environ.get("TESSERACT_CMD")
    if env_path and os.path.isfile(env_path):
        pytesseract.pytesseract.tesseract_cmd = env_path
        return pytesseract.pytesseract.tesseract_cmd

    path_executable = shutil.which("tesseract")
    if path_executable:
        pytesseract.pytesseract.tesseract_cmd = path_executable
        return pytesseract.pytesseract.tesseract_cmd

    for path in possible_paths:
        if os.path.isfile(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return pytesseract.pytesseract.tesseract_cmd

    raise FileNotFoundError(
        "Tesseract OCR is not installed or could not be found."
    )

try:
    configure_tesseract()
except Exception as _tess_err:
    app.logger.warning("Initial Tesseract config: %s", _tess_err)

@app.route("/ocr", methods=["GET", "POST"])
def ocr():
    extracted = ""
    if request.method == "POST":
        file = request.files.get("document")
        if not file or not file.filename:
            flash("Choose an image of a printed page first.", "error")
        elif not allowed_file(file.filename):
            flash("Supported image formats: PNG, JPG, JPEG, BMP, TIF and TIFF.", "error")
        else:
            filename = secure_filename(file.filename)
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(path)
            try:
                from PIL import Image
                configure_tesseract()
                image = Image.open(path)
                extracted = pytesseract.image_to_string(image).strip()
                if not extracted:
                    flash("No readable text was detected. Try a clearer, well-lit image.", "error")
            except ImportError:
                flash("OCR dependencies are missing. Install Pillow and pytesseract, then install the Tesseract OCR application on your computer.", "error")
            except FileNotFoundError as fnf_err:
                app.logger.error("Tesseract not found: %s", fnf_err)
                flash("Tesseract OCR is not installed or could not be found. Check your installation.", "error")
            except Exception as exc:
                app.logger.error("OCR error: %s", exc)
                flash(f"OCR could not process this image. Details: {exc}", "error")
    return render_template("ocr.html", extracted=extracted)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        demo_role = request.form.get("demo_role")
        if demo_role in ("lecturer", "student"):
            with connect_db() as conn:
                user = conn.execute("SELECT * FROM users WHERE role = ? ORDER BY id ASC LIMIT 1", (demo_role,)).fetchone()
                if user:
                    session["user_id"] = user["id"]
                    session["username"] = user["username"]
                    session["role"] = user["role"]
                    session["full_name"] = user["full_name"]
                    flash(f"Welcome back, {user['full_name']}! Signed in as {user['role'].capitalize()}.", "success")
                    return redirect(url_for("dashboard"))

        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Enter both username and password.", "error")
            return render_template("login.html", username=username)

        with connect_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if user and check_password_hash(user["password_hash"], password):
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                session["full_name"] = user["full_name"]
                flash(f"Signed in as {user['full_name']} ({user['role'].capitalize()}).", "success")
                next_url = request.args.get("next")
                return redirect(next_url or url_for("dashboard"))
            else:
                flash("Invalid username or password. Check credentials or try one-click demo login.", "error")
                return render_template("login.html", username=username)

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        role = request.form.get("role", "student").strip().lower()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        if role not in ("lecturer", "student"):
            role = "student"

        if not full_name or not username or not password:
            flash("All fields are required.", "error")
            return render_template("register.html", full_name=full_name, username=username, role=role)

        if len(password) < 4:
            flash("Password must be at least 4 characters long.", "error")
            return render_template("register.html", full_name=full_name, username=username, role=role)

        with connect_db() as conn:
            existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                flash("That username is already taken. Choose another username.", "error")
                return render_template("register.html", full_name=full_name, username=username, role=role)

            pwd_hash = generate_password_hash(password)
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, role, full_name, created_at) VALUES (?, ?, ?, ?, ?)",
                (username, pwd_hash, role, full_name, datetime.now().isoformat(timespec="seconds"))
            )
            new_id = cursor.lastrowid
            session["user_id"] = new_id
            session["username"] = username
            session["role"] = role
            session["full_name"] = full_name
            flash(f"Account registered! Welcome, {full_name} ({role.capitalize()})!", "success")
            return redirect(url_for("dashboard"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    with connect_db() as conn:
        if session.get("role") == "lecturer":
            recent = conn.execute(
                "SELECT * FROM saved_notes WHERE user_id = ? OR role = 'lecturer' ORDER BY id DESC LIMIT 6",
                (session["user_id"],)
            ).fetchall()
        else:
            recent = conn.execute(
                "SELECT * FROM saved_notes WHERE is_public = 1 OR user_id = ? ORDER BY id DESC LIMIT 6",
                (session["user_id"],)
            ).fetchall()
    return render_template("dashboard.html", recent_notes=recent)

@app.route("/notes", methods=["GET", "POST"])
def notes():
    content = ""
    title = ""
    summary = ""
    key_terms = []
    if request.method == "POST":
        title = request.form.get("title", "").strip() or "Untitled lecture"
        content = request.form.get("content", "").strip()
        action = request.form.get("action", "analyze")
        if not content:
            flash("Enter or paste lecture text first.", "error")
        else:
            summary = summarize_text(content)
            key_terms = keywords(content)
            if action == "save":
                user_id = session.get("user_id")
                role = session.get("role", "guest")
                author_name = session.get("full_name") or ("Lecturer" if role == "lecturer" else "Student")
                is_public = 1 if (role == "lecturer" and request.form.get("is_public") == "1") else (1 if role != "student" else 0)

                with connect_db() as conn:
                    conn.execute(
                        "INSERT INTO saved_notes(user_id, author_name, role, title, content, is_public, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (user_id, author_name, role, title, content, is_public, datetime.now().isoformat(timespec="seconds"))
                    )
                flash("Lecture notes saved successfully.", "success")

    with connect_db() as conn:
        saved = conn.execute(
            "SELECT id, title, author_name, role, is_public, created_at FROM saved_notes ORDER BY id DESC LIMIT 15"
        ).fetchall()
    return render_template("notes.html", content=content, title=title, summary=summary, key_terms=key_terms, saved=saved)

@app.route("/saved/<int:note_id>")
def saved_note(note_id):
    with connect_db() as conn:
        note = conn.execute("SELECT * FROM saved_notes WHERE id = ?", (note_id,)).fetchone()
    if not note:
        flash("That saved note was not found.", "error")
        return redirect(url_for("notes"))
    return render_template("saved_note.html", note=note)

@app.errorhandler(413)
def too_large(_error):
    flash("The uploaded file is too large. Maximum size is 10 MB.", "error")
    return redirect(request.referrer or url_for("ocr"))

@app.route("/health")
def health():
    return {"status": "ok", "app": "Accessible Classroom Assistant"}

init_db()

if __name__ == "__main__":
    app.run(debug=True)
