from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "elearning_secret_key"


def create_database():

    conn = sqlite3.connect("database.db")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            duration TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            course_id INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            title TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            lesson_id INTEGER,
            completed INTEGER DEFAULT 0
        )
    """)

    course_count = conn.execute(
        "SELECT COUNT(*) FROM courses"
    ).fetchone()[0]

    if course_count == 0:

        conn.execute("""
            INSERT INTO courses
            (name, description, duration)
            VALUES (?, ?, ?)
        """, (
            "Python for Beginners",
            "Learn Python programming from basic concepts.",
            "8 Weeks"
        ))

        conn.execute("""
            INSERT INTO courses
            (name, description, duration)
            VALUES (?, ?, ?)
        """, (
            "Web Development",
            "Learn HTML, CSS and JavaScript.",
            "6 Weeks"
        ))

        conn.execute("""
            INSERT INTO courses
            (name, description, duration)
            VALUES (?, ?, ?)
        """, (
            "Data Structures",
            "Learn arrays, linked lists, trees and graphs.",
            "10 Weeks"
        ))

    lesson_count = conn.execute(
        "SELECT COUNT(*) FROM lessons"
    ).fetchone()[0]

    if lesson_count == 0:

        lessons = [
            (1, "Introduction to Python",
             "Python is a high-level programming language."),

            (1, "Python Variables",
             "Variables are used to store data values."),

            (1, "Python Data Types",
             "Python has integer, float, string, list and dictionary data types."),

            (2, "Introduction to HTML",
             "HTML creates the structure of web pages."),

            (2, "Introduction to CSS",
             "CSS is used to style web pages."),

            (3, "Introduction to Data Structures",
             "Data structures organize and store data efficiently.")
        ]

        conn.executemany("""
            INSERT INTO lessons
            (course_id, title, content)
            VALUES (?, ?, ?)
        """, lessons)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        try:

            conn = sqlite3.connect("database.db")

            conn.execute(
                """
                INSERT INTO users
                (name, email, password)
                VALUES (?, ?, ?)
                """,
                (name, email, password)
            )

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:

            return "Email already registered!"

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")

        user = conn.execute(
            """
            SELECT * FROM users
            WHERE email=? AND password=?
            """,
            (email, password)
        ).fetchone()

        conn.close()

        if user:

            session["user_id"] = user[0]
            session["user_name"] = user[1]

            return redirect("/dashboard")

        return "Invalid email or password!"

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    return render_template(
        "dashboard.html",
        name=session["user_name"]
    )


@app.route("/courses")
def courses():

    conn = sqlite3.connect("database.db")

    courses = conn.execute(
        "SELECT * FROM courses"
    ).fetchall()

    conn.close()

    return render_template(
        "courses.html",
        courses=courses
    )


@app.route("/course/<int:course_id>")
def course_details(course_id):

    conn = sqlite3.connect("database.db")

    course = conn.execute(
        "SELECT * FROM courses WHERE id=?",
        (course_id,)
    ).fetchone()

    lessons = conn.execute(
        "SELECT * FROM lessons WHERE course_id=?",
        (course_id,)
    ).fetchall()

    conn.close()

    return render_template(
        "course.html",
        course=course,
        lessons=lessons
    )


@app.route("/enroll/<int:course_id>")
def enroll(course_id):

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")

    existing = conn.execute(
        """
        SELECT * FROM enrollments
        WHERE user_id=? AND course_id=?
        """,
        (user_id, course_id)
    ).fetchone()

    if not existing:

        conn.execute(
            """
            INSERT INTO enrollments
            (user_id, course_id)
            VALUES (?, ?)
            """,
            (user_id, course_id)
        )

        conn.commit()

    conn.close()

    return redirect("/my-courses")


@app.route("/my-courses")
def my_courses():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")

    courses = conn.execute(
        """
        SELECT courses.*
        FROM courses
        JOIN enrollments
        ON courses.id = enrollments.course_id
        WHERE enrollments.user_id=?
        """,
        (user_id,)
    ).fetchall()

    course_data = []

    for course in courses:

        total_lessons = conn.execute(
            """
            SELECT COUNT(*)
            FROM lessons
            WHERE course_id=?
            """,
            (course[0],)
        ).fetchone()[0]

        completed_lessons = conn.execute(
            """
            SELECT COUNT(*)
            FROM progress
            JOIN lessons
            ON progress.lesson_id = lessons.id
            WHERE progress.user_id=?
            AND lessons.course_id=?
            AND progress.completed=1
            """,
            (user_id, course[0])
        ).fetchone()[0]

        if total_lessons > 0:
            percentage = int(
                (completed_lessons / total_lessons) * 100
            )
        else:
            percentage = 0

        course_data.append(
            (
                course,
                total_lessons,
                completed_lessons,
                percentage
            )
        )

    conn.close()

    return render_template(
        "my_courses.html",
        course_data=course_data
    )


@app.route("/lessons/<int:course_id>")
def lessons(course_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")

    lessons = conn.execute(
        """
        SELECT * FROM lessons
        WHERE course_id=?
        """,
        (course_id,)
    ).fetchall()

    conn.close()

    return render_template(
        "lessons.html",
        lessons=lessons,
        course_id=course_id
    )


@app.route("/lesson/<int:lesson_id>")
def lesson(lesson_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")

    lesson = conn.execute(
        "SELECT * FROM lessons WHERE id=?",
        (lesson_id,)
    ).fetchone()

    conn.close()

    return render_template(
        "lesson.html",
        lesson=lesson
    )


@app.route("/complete/<int:lesson_id>")
def complete_lesson(lesson_id):

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")

    existing = conn.execute(
        """
        SELECT * FROM progress
        WHERE user_id=? AND lesson_id=?
        """,
        (user_id, lesson_id)
    ).fetchone()

    if existing:

        conn.execute(
            """
            UPDATE progress
            SET completed=1
            WHERE user_id=? AND lesson_id=?
            """,
            (user_id, lesson_id)
        )

    else:

        conn.execute(
            """
            INSERT INTO progress
            (user_id, lesson_id, completed)
            VALUES (?, ?, 1)
            """,
            (user_id, lesson_id)
        )

    conn.commit()
    conn.close()

    return redirect("/my-courses")
@app.route('/quiz')
def quiz():
    return render_template('quiz.html')

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


if __name__ == "__main__":

    create_database()

    app.run()
            


