from flask import (
    Blueprint, current_app, render_template, session, abort, send_file, request,
    redirect, url_for, flash,
)
import io
from pathlib import Path

from werkzeug.utils import secure_filename

from database import get_db
from utils.decorators import role_required
from utils.grading import compute_gwa
from utils.notifications import mark_notifications_read
from utils.pdf import build_grade_slip_pdf
from utils.qr import qr_data_uri

bp = Blueprint("student", __name__, url_prefix="/student")
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def _student(conn):
    return conn.execute(
        "SELECT * FROM students WHERE user_id = ?", (session["user_id"],)
    ).fetchone()


def _terms_for_student(conn, user_id):
    """Distinct (semester, school_year) the student has enrollments in,
    most recent first (by school_year desc, semester order)."""
    rows = conn.execute(
        """SELECT DISTINCT co.semester, co.school_year
           FROM enrollments e
           JOIN class_offerings co ON co.id = e.offering_id
           WHERE e.student_user_id = ?
           ORDER BY co.school_year DESC, co.semester""",
        (user_id,),
    ).fetchall()
    return [(r["semester"], r["school_year"]) for r in rows]


def _grades_for_term(conn, user_id, semester, school_year):
    return conn.execute(
        """SELECT s.code, s.name, s.units, co.meeting_time, co.meeting_days,
              g.prelim, g.midterm, g.finals,
                  g.final_grade, g.remarks, g.status, f.full_name AS instructor
           FROM enrollments e
           JOIN class_offerings co ON co.id = e.offering_id
           JOIN subjects s ON s.id = co.subject_id
           LEFT JOIN grades g ON g.enrollment_id = e.id
           LEFT JOIN faculty f ON f.user_id = co.faculty_user_id
           WHERE e.student_user_id = ? AND co.semester = ? AND co.school_year = ?
           ORDER BY s.code""",
        (user_id, semester, school_year),
    ).fetchall()


@bp.route("/dashboard")
@role_required("student")
def dashboard():
    conn = get_db()
    stu = _student(conn)
    terms = _terms_for_student(conn, session["user_id"])
    current = terms[0] if terms else None
    current_rows = _grades_for_term(conn, session["user_id"], *current) if current else []
    released_only = [r for r in current_rows if r["status"] == "released"]

    unread = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (session["user_id"],),
    ).fetchone()[0]

    conn.close()
    return render_template(
        "student/dashboard.html", student=stu, current=current,
        rows=current_rows, released_count=len(released_only),
        total_count=len(current_rows), unread=unread,
        student_qr=qr_data_uri(f"OGVS-STUDENT:{stu['student_id']}"),
    )


@bp.route("/profile", methods=["POST"])
@role_required("student")
def update_profile():
    image = request.files.get("profile_image")
    if not image or not image.filename:
        flash("Choose a profile picture before uploading.", "warning")
        return redirect(url_for("student.dashboard"))

    original_name = secure_filename(image.filename)
    extension = Path(original_name).suffix.lower().lstrip(".")
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        flash("Profile pictures must be JPG, PNG, or WEBP files.", "danger")
        return redirect(url_for("student.dashboard"))

    conn = get_db()
    student = _student(conn)
    if not student:
        conn.close()
        abort(404)

    upload_dir = Path(current_app.root_path) / "static" / "uploads" / "profiles"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"student_{session['user_id']}.{extension}"
    image.save(upload_dir / filename)
    conn.execute(
        "UPDATE students SET profile_image = ? WHERE user_id = ?",
        (filename, session["user_id"]),
    )
    conn.commit()
    conn.close()
    flash("Profile picture updated.", "success")
    return redirect(url_for("student.dashboard"))


@bp.route("/grades")
@role_required("student")
def grades():
    conn = get_db()
    stu = _student(conn)
    terms = _terms_for_student(conn, session["user_id"])
    sem = request.args.get("semester")
    sy = request.args.get("school_year")
    current = (sem, sy) if sem and sy else (terms[0] if terms else (None, None))
    rows = _grades_for_term(conn, session["user_id"], *current) if current[0] else []
    conn.close()
    return render_template(
        "student/grades.html", student=stu, rows=rows, terms=terms, current=current,
    )


@bp.route("/history")
@role_required("student")
def history():
    conn = get_db()
    stu = _student(conn)
    terms = _terms_for_student(conn, session["user_id"])
    history_data = []
    for semester, school_year in terms:
        rows = _grades_for_term(conn, session["user_id"], semester, school_year)
        gwa_rows = [{"final_grade": r["final_grade"], "units": r["units"]}
                    for r in rows if r["status"] == "released"]
        gwa = compute_gwa(gwa_rows)
        history_data.append({
            "semester": semester, "school_year": school_year,
            "rows": rows, "gwa": gwa,
        })
    conn.close()
    return render_template("student/history.html", student=stu, history=history_data)


@bp.route("/grade-slip/<school_year>/<path:semester>")
@role_required("student")
def grade_slip(school_year, semester):
    conn = get_db()
    stu = _student(conn)
    rows = _grades_for_term(conn, session["user_id"], semester, school_year)
    conn.close()
    if not rows:
        abort(404)
    gwa_rows = [{"final_grade": r["final_grade"], "units": r["units"]}
                for r in rows if r["status"] == "released"]
    gwa = compute_gwa(gwa_rows)
    pdf_bytes = build_grade_slip_pdf(dict(stu), (semester, school_year), rows, gwa)
    filename = f"GradeSlip_{stu['student_id']}_{school_year}_{semester}.pdf".replace(" ", "_")
    return send_file(
        io.BytesIO(pdf_bytes), mimetype="application/pdf",
        as_attachment=True, download_name=filename,
    )


@bp.route("/subjects")
@role_required("student")
def subjects():
    conn = get_db()
    stu = _student(conn)
    terms = _terms_for_student(conn, session["user_id"])
    current = terms[0] if terms else None
    rows = _grades_for_term(conn, session["user_id"], *current) if current else []
    conn.close()
    return render_template(
        "student/subjects.html", student=stu, rows=rows, current=current,
    )


@bp.route("/notifications")
@role_required("student")
def notifications():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    if not mark_notifications_read(conn, session["user_id"]):
        flash("Notifications were displayed, but this deployment could not save their read status.", "warning")
    conn.close()
    return render_template("student/notifications.html", rows=rows)
