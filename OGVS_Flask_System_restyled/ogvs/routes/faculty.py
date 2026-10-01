from flask import (
    Blueprint, current_app, render_template, session, request, redirect, url_for,
    flash, abort,
)
from pathlib import Path
from werkzeug.utils import secure_filename

from database import get_db
from utils.decorators import role_required
from utils.grading import compute_final

bp = Blueprint("faculty", __name__, url_prefix="/faculty")
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def _offering_belongs_to_me(conn, offering_id):
    row = conn.execute(
        "SELECT * FROM class_offerings WHERE id = ? AND faculty_user_id = ?",
        (offering_id, session["user_id"]),
    ).fetchone()
    if not row:
        abort(403)
    return row


@bp.route("/dashboard")
@role_required("faculty")
def dashboard():
    conn = get_db()
    faculty = conn.execute(
        """SELECT f.*, u.email FROM faculty f
           JOIN users u ON u.id = f.user_id WHERE f.user_id = ?""",
        (session["user_id"],),
    ).fetchone()
    offerings = conn.execute(
        """SELECT co.*, s.code, s.name, sec.program, sec.year_level, sec.section_name,
                  (SELECT COUNT(*) FROM enrollments e WHERE e.offering_id = co.id) AS enrolled
           FROM class_offerings co
           JOIN subjects s ON s.id = co.subject_id
           JOIN sections sec ON sec.id = co.section_id
           WHERE co.faculty_user_id = ?
           ORDER BY co.school_year DESC, co.semester, s.code""",
        (session["user_id"],),
    ).fetchall()
    pending_corrections = conn.execute(
        """SELECT COUNT(*) FROM correction_requests cr
           JOIN grades g ON g.id = cr.grade_id
           JOIN enrollments e ON e.id = g.enrollment_id
           JOIN class_offerings co ON co.id = e.offering_id
           WHERE co.faculty_user_id = ? AND cr.status = 'pending'""",
        (session["user_id"],),
    ).fetchone()[0]
    unread = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (session["user_id"],),
    ).fetchone()[0]
    conn.close()
    return render_template(
        "faculty/dashboard.html", offerings=offerings,
        pending_corrections=pending_corrections, unread=unread, faculty=faculty,
    )


@bp.route("/profile", methods=["POST"])
@role_required("faculty")
def update_profile():
    image = request.files.get("profile_image")
    if not image or not image.filename:
        flash("Choose a profile picture before uploading.", "warning")
        return redirect(url_for("faculty.dashboard"))

    extension = Path(secure_filename(image.filename)).suffix.lower().lstrip(".")
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        flash("Profile pictures must be JPG, PNG, or WEBP files.", "danger")
        return redirect(url_for("faculty.dashboard"))

    conn = get_db()
    faculty_exists = conn.execute(
        "SELECT 1 FROM faculty WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    if not faculty_exists:
        conn.close()
        abort(404)

    upload_dir = Path(current_app.root_path) / "static" / "uploads" / "profiles"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"faculty_{session['user_id']}.{extension}"
    image.save(upload_dir / filename)
    conn.execute(
        "UPDATE faculty SET profile_image = ? WHERE user_id = ?",
        (filename, session["user_id"]),
    )
    conn.commit()
    conn.close()
    flash("Profile picture updated.", "success")
    return redirect(url_for("faculty.dashboard"))


@bp.route("/classes")
@role_required("faculty")
def classes():
    conn = get_db()
    offerings = conn.execute(
        """SELECT co.*, s.code, s.name, sec.program, sec.year_level, sec.section_name,
                  (SELECT COUNT(*) FROM enrollments e WHERE e.offering_id = co.id) AS enrolled
           FROM class_offerings co
           JOIN subjects s ON s.id = co.subject_id
           JOIN sections sec ON sec.id = co.section_id
           WHERE co.faculty_user_id = ?
           ORDER BY co.school_year DESC, co.semester, s.code""",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return render_template("faculty/classes.html", offerings=offerings)


@bp.route("/classes/<int:offering_id>/encode", methods=["GET", "POST"])
@role_required("faculty")
def encode(offering_id):
    conn = get_db()
    offering = _offering_belongs_to_me(conn, offering_id)
    subject = conn.execute("SELECT * FROM subjects WHERE id = ?",
                            (offering["subject_id"],)).fetchone()
    section = conn.execute("SELECT * FROM sections WHERE id = ?",
                            (offering["section_id"],)).fetchone()

    if request.method == "POST":
        student_user_id = int(request.form["student_user_id"])
        enrollment = conn.execute(
            "SELECT * FROM enrollments WHERE student_user_id = ? AND offering_id = ?",
            (student_user_id, offering_id),
        ).fetchone()
        if not enrollment:
            abort(404)

        def parse(field):
            val = request.form.get(field, "").strip()
            return float(val) if val else None

        prelim, midterm, finals = parse("prelim"), parse("midterm"), parse("finals")
        if any(value is not None and not 1 <= value <= 5 for value in (prelim, midterm, finals)):
            flash("Grades must be between 1.00 and 5.00.", "danger")
            return redirect(url_for("faculty.encode", offering_id=offering_id))
        final_grade, remarks = compute_final(prelim, midterm, finals)

        existing = conn.execute(
            "SELECT * FROM grades WHERE enrollment_id = ?", (enrollment["id"],)
        ).fetchone()
        if existing and existing["status"] in ("approved", "released"):
            flash("This grade is locked (approved/released). Submit a correction "
                  "request instead of editing it directly.", "danger")
        elif existing:
            conn.execute(
                """UPDATE grades SET prelim=?, midterm=?, finals=?, final_grade=?,
                   remarks=?, status='draft', updated_at=datetime('now')
                   WHERE id = ?""",
                (prelim, midterm, finals, final_grade, remarks, existing["id"]),
            )
            conn.commit()
            flash("Grade saved as draft.", "success")
        else:
            conn.execute(
                """INSERT INTO grades
                   (enrollment_id, prelim, midterm, finals, final_grade, remarks, status)
                   VALUES (?,?,?,?,?,?, 'draft')""",
                (enrollment["id"], prelim, midterm, finals, final_grade, remarks),
            )
            conn.commit()
            flash("Grade saved as draft.", "success")

    students = conn.execute(
        """SELECT st.user_id, st.student_id, st.full_name, g.id AS grade_id,
                  g.prelim, g.midterm, g.finals, g.final_grade, g.remarks, g.status
           FROM enrollments e
           JOIN students st ON st.user_id = e.student_user_id
           LEFT JOIN grades g ON g.enrollment_id = e.id
           WHERE e.offering_id = ?
           ORDER BY st.full_name""",
        (offering_id,),
    ).fetchall()
    conn.close()
    return render_template(
        "faculty/encode.html", offering=offering, subject=subject, section=section,
        students=students,
    )


@bp.route("/classes/<int:offering_id>/submit", methods=["POST"])
@role_required("faculty")
def submit_for_review(offering_id):
    conn = get_db()
    _offering_belongs_to_me(conn, offering_id)
    conn.execute(
        """UPDATE grades SET status = 'submitted', updated_at = datetime('now')
           WHERE status = 'draft' AND enrollment_id IN (
               SELECT id FROM enrollments WHERE offering_id = ?)""",
        (offering_id,),
    )
    conn.commit()
    conn.close()
    flash("Draft grades submitted to the Registrar for review.", "success")
    return redirect(url_for("faculty.encode", offering_id=offering_id))


@bp.route("/classes/<int:offering_id>/release", methods=["POST"])
@role_required("faculty")
def release(offering_id):
    conn = get_db()
    _offering_belongs_to_me(conn, offering_id)
    rows = conn.execute(
        """SELECT g.id, e.student_user_id FROM grades g
           JOIN enrollments e ON e.id = g.enrollment_id
           WHERE g.status = 'approved' AND e.offering_id = ?""",
        (offering_id,),
    ).fetchall()
    for r in rows:
        conn.execute(
            "UPDATE grades SET status = 'released', updated_at = datetime('now') WHERE id = ?",
            (r["id"],),
        )
        conn.execute(
            "INSERT INTO notifications (user_id, message) VALUES (?,?)",
            (r["student_user_id"], "A new grade has been released. Check your dashboard."),
        )
    conn.commit()
    conn.close()
    flash(f"{len(rows)} approved grade(s) released to students.", "success")
    return redirect(url_for("faculty.encode", offering_id=offering_id))


@bp.route("/grades/<int:grade_id>/correction", methods=["POST"])
@role_required("faculty")
def request_correction(grade_id):
    reason = request.form.get("reason", "").strip()
    conn = get_db()
    grade = conn.execute(
        """SELECT g.* FROM grades g
           JOIN enrollments e ON e.id = g.enrollment_id
           JOIN class_offerings co ON co.id = e.offering_id
           WHERE g.id = ? AND co.faculty_user_id = ?""",
        (grade_id, session["user_id"]),
    ).fetchone()
    if not grade:
        abort(404)
    if not reason:
        flash("Please provide a reason for the correction request.", "danger")
    elif grade["status"] != "released":
        flash("Only released grades can have a correction request filed.", "danger")
    else:
        conn.execute(
            "INSERT INTO correction_requests (grade_id, reason) VALUES (?,?)",
            (grade_id, reason),
        )
        conn.commit()
        flash("Correction request submitted to the Registrar.", "success")
    offering_id = conn.execute(
        "SELECT offering_id FROM enrollments WHERE id = ?", (grade["enrollment_id"],)
    ).fetchone()[0]
    conn.close()
    return redirect(url_for("faculty.encode", offering_id=offering_id))


@bp.route("/notifications")
@role_required("faculty")
def notifications():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ?", (session["user_id"],)
    )
    conn.commit()
    conn.close()
    return render_template("faculty/notifications.html", rows=rows)
