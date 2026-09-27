from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB = "elearning.db"
CERT_DIR = "certificates"
os.makedirs(CERT_DIR, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student'
    );

    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        duration TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        completed INTEGER DEFAULT 0,
        score INTEGER DEFAULT 0,
        UNIQUE(user_id, course_id)
    );
    """)
    count = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO courses(title, description, duration) VALUES (?, ?, ?)",
            [
                ("Python Basics", "Learn Python programming from the fundamentals.", "4 Weeks"),
                ("Web Development", "Learn HTML, CSS, JavaScript and Flask basics.", "6 Weeks"),
                ("Data Structures", "Learn arrays, linked lists, trees, graphs and algorithms.", "5 Weeks"),
            ],
        )
    conn.commit()
    conn.close()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if not name or not email or not password:
            flash("All fields are required.")
            return redirect(url_for("register"))
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users(name,email,password) VALUES (?,?,?)",
                (name, email, generate_password_hash(password))
            )
            conn.commit()
            flash("Registration successful. Please login.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.")
            return redirect(url_for("register"))
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    courses = conn.execute("""
        SELECT c.*, e.completed, e.score
        FROM courses c
        LEFT JOIN enrollments e
        ON c.id=e.course_id AND e.user_id=?
    """, (session["user_id"],)).fetchall()
    conn.close()
    return render_template("dashboard.html", courses=courses)

@app.route("/enroll/<int:course_id>", methods=["POST"])
def enroll(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO enrollments(user_id,course_id) VALUES (?,?)",
            (session["user_id"], course_id)
        )
        conn.commit()
        flash("Course enrolled successfully.")
    except sqlite3.IntegrityError:
        flash("You are already enrolled in this course.")
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/complete/<int:course_id>", methods=["POST"])
def complete(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    score = int(request.form.get("score", 80))
    conn = get_db()
    conn.execute(
        "UPDATE enrollments SET completed=1, score=? WHERE user_id=? AND course_id=?",
        (score, session["user_id"], course_id)
    )
    conn.commit()
    conn.close()
    flash("Course completed! Your certificate is ready.")
    return redirect(url_for("dashboard"))

@app.route("/certificate/<int:course_id>")
def certificate(course_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    row = conn.execute("""
        SELECT u.name, c.title, e.completed, e.score
        FROM enrollments e
        JOIN users u ON u.id=e.user_id
        JOIN courses c ON c.id=e.course_id
        WHERE e.user_id=? AND e.course_id=?
    """, (session["user_id"], course_id)).fetchone()
    conn.close()

    if not row or not row["completed"]:
        flash("Complete the course before downloading the certificate.")
        return redirect(url_for("dashboard"))

    safe_name = "".join(ch for ch in row["name"] if ch.isalnum() or ch in " _-").strip()
    filename = f"certificate_{row['name'].replace(' ', '_')}_{course_id}.pdf"
    path = os.path.join(CERT_DIR, filename)

    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    c.setLineWidth(3)
    c.rect(40, 40, width-80, height-80)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width/2, height-140, "CERTIFICATE OF COMPLETION")
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height-200, "This certificate is proudly presented to")
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height-250, row["name"])
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height-300, "for successfully completing")
    c.setFont("Helvetica-Bold", 21)
    c.drawCentredString(width/2, height-340, row["title"])
    c.setFont("Helvetica", 13)
    c.drawCentredString(width/2, height-390, f"Quiz Score: {row['score']}%")
    c.drawCentredString(width/2, height-420, f"Completion Date: {datetime.now().strftime('%d-%m-%Y')}")
    c.setFont("Helvetica-Oblique", 11)
    c.drawCentredString(width/2, 90, "E-Learning Management System")
    c.save()
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
