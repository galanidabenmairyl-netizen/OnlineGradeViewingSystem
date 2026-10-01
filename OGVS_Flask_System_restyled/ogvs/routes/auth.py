import re
import os
import socket

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db
from utils.qr import qr_data_uri

bp = Blueprint("auth", __name__)


def _login_qr_data():
    public_url = os.getenv("OGVS_PUBLIC_URL", "").strip().rstrip("/")
    if not public_url:
        host = request.host.split(":", 1)[0]
        if host in {"127.0.0.1", "localhost", "::1"}:
            host = socket.gethostbyname(socket.gethostname())
        public_url = f"{request.scheme}://{host}:{request.environ.get('SERVER_PORT', '5000')}"
    return qr_data_uri(f"{public_url}{url_for('auth.login')}")


@bp.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for(f'{session["role"]}.dashboard'))
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)
        ).fetchone()
        pending_faculty = conn.execute(
            """SELECT f.verification_status FROM users u
               JOIN faculty f ON f.user_id = u.id
               WHERE u.username = ? AND u.role = 'faculty' AND u.is_active = 0""",
            (username,),
        ).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["username"] = user["username"]
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for(f'{user["role"]}.dashboard'))
        if pending_faculty and pending_faculty["verification_status"] == "pending":
            flash("Your faculty account is waiting for Registrar verification.", "warning")
        else:
            flash("Invalid username or password.", "danger")
    return render_template("auth/login.html", login_qr=_login_qr_data())


@bp.route("/faculty-application", methods=["GET", "POST"])
def faculty_application():
    if request.method == "POST":
        username = request.form["username"].strip()
        employee_id = request.form["employee_id"].strip()
        full_name = request.form["full_name"].strip()
        position = request.form.get("position", "Faculty").strip() or "Faculty"
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm = request.form["confirm_password"]
        conn = get_db()
        error = None
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            error = "Username already exists."
        elif conn.execute("SELECT 1 FROM faculty WHERE employee_id = ?", (employee_id,)).fetchone():
            error = "That employee ID already has an application."
        elif not re.fullmatch(r"[a-z0-9._%+-]+@nemsu\.edu\.ph", email, re.IGNORECASE):
            error = "Use your official NEMSU email ending in @nemsu.edu.ph."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        if error:
            conn.close()
            flash(error, "danger")
            return render_template("auth/faculty_application.html", form=request.form)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash, role, email, is_active) VALUES (?,?,?,?,0)",
            (username, generate_password_hash(password), "faculty", email),
        )
        cur.execute(
                """INSERT INTO faculty
                    (user_id, full_name, employee_id, position, verification_status)
                    VALUES (?,?,?,?,'pending')""",
                (cur.lastrowid, full_name, employee_id, position),
        )
        conn.commit()
        conn.close()
        flash("Application submitted. The Registrar must verify and activate your account.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/faculty_application.html", form={})


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        student_id = request.form["student_id"].strip()
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        conn = get_db()
        existing_student = conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        record = conn.execute(
            "SELECT * FROM pre_enrolled_students WHERE student_id = ?", (student_id,)
        ).fetchone()

        error = None
        if existing_student:
            error = "This Student ID is already registered. Please log in instead."
        elif not record:
            error = ("This Student ID was not found in the registrar's enrollment "
                      "records. Please coordinate with the Registrar's Office.")
        elif record["is_registered"]:
            error = "This Student ID is already registered. Please log in instead."
        elif record["full_name"].strip().lower() != full_name.lower():
            error = "The name provided does not match the enrollment record."
        elif not re.fullmatch(
            r"[a-z0-9](?:[a-z0-9.]*[a-z0-9])?(?:\+[a-z0-9.-]+)?@gmail\.com",
            email,
            re.IGNORECASE,
        ):
            error = "Please enter a valid Gmail address ending in @gmail.com."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."

        if error:
            conn.close()
            flash(error, "danger")
            return render_template("auth/register.html", form=request.form)

        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash, role, email) VALUES (?,?,?,?)",
            (student_id, generate_password_hash(password), "student", email),
        )
        user_id = cur.lastrowid
        cur.execute(
            "INSERT INTO students (user_id, student_id, full_name, program, year_level, section) "
            "VALUES (?,?,?,?,?,?)",
            (user_id, student_id, record["full_name"], record["program"],
             record["year_level"], record["section"]),
        )
        cur.execute(
            "UPDATE pre_enrolled_students SET is_registered = 1 WHERE student_id = ?",
            (student_id,),
        )
        cur.execute(
            "INSERT INTO notifications (user_id, message) VALUES (?,?)",
            (user_id, "Welcome to OGVS! Your account has been verified and activated."),
        )
        conn.commit()
        conn.close()
        flash("Registration successful! You may now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form={})


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
