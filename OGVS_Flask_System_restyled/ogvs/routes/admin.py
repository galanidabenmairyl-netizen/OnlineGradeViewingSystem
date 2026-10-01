from flask import (
    Blueprint, render_template, session, request, redirect, url_for, flash, abort,
)
from werkzeug.security import generate_password_hash

from database import get_db
from utils.decorators import role_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/dashboard")
@role_required("admin")
def dashboard():
    conn = get_db()
    counts = {
        "students": conn.execute("SELECT COUNT(*) FROM students").fetchone()[0],
        "faculty": conn.execute("SELECT COUNT(*) FROM faculty").fetchone()[0],
        "subjects": conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0],
        "offerings": conn.execute("SELECT COUNT(*) FROM class_offerings").fetchone()[0],
        "submitted": conn.execute(
            "SELECT COUNT(*) FROM grades WHERE status = 'submitted'").fetchone()[0],
        "pending_corrections": conn.execute(
            "SELECT COUNT(*) FROM correction_requests WHERE status = 'pending'").fetchone()[0],
    }
    conn.close()
    return render_template("admin/dashboard.html", counts=counts)


# ---------------------------------------------------------------- students -
@bp.route("/students")
@role_required("admin")
def students():
    conn = get_db()
    q = request.args.get("q", "").strip()
    if q:
        rows = conn.execute(
            """SELECT * FROM students WHERE student_id LIKE ? OR full_name LIKE ?
               ORDER BY full_name""",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM students ORDER BY full_name").fetchall()
    conn.close()
    return render_template("admin/students.html", rows=rows, q=q)


@bp.route("/students/new", methods=["GET", "POST"])
@role_required("admin")
def new_student():
    if request.method == "POST":
        student_id = request.form["student_id"].strip()
        full_name = request.form["full_name"].strip()
        program = request.form["program"].strip()
        year_level = request.form["year_level"].strip()
        section = request.form["section"].strip()

        conn = get_db()
        exists = conn.execute(
            "SELECT 1 FROM pre_enrolled_students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if exists:
            flash("A record with this Student ID already exists.", "danger")
        else:
            conn.execute(
                """INSERT INTO pre_enrolled_students
                   (student_id, full_name, program, year_level, section, is_registered)
                   VALUES (?,?,?,?,?,0)""",
                (student_id, full_name, program, year_level, section),
            )
            conn.commit()
            flash("Student pre-enrollment record added. The student can now self-register.",
                  "success")
            conn.close()
            return redirect(url_for("admin.students"))
        conn.close()
    return render_template("admin/student_form.html", mode="new", record=None)


@bp.route("/students/<student_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_student(student_id):
    conn = get_db()
    record = conn.execute(
        "SELECT * FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    if not record:
        conn.close()
        abort(404)
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        program = request.form["program"].strip()
        year_level = request.form["year_level"].strip()
        section = request.form["section"].strip()
        conn.execute(
            """UPDATE students SET full_name=?, program=?, year_level=?, section=?
               WHERE student_id = ?""",
            (full_name, program, year_level, section, student_id),
        )
        conn.execute(
            """UPDATE pre_enrolled_students SET full_name=?, program=?, year_level=?, section=?
               WHERE student_id = ?""",
            (full_name, program, year_level, section, student_id),
        )
        conn.commit()
        conn.close()
        flash("Student record updated.", "success")
        return redirect(url_for("admin.students"))
    conn.close()
    return render_template("admin/student_form.html", mode="edit", record=record)


@bp.route("/students/<student_id>/toggle", methods=["POST"])
@role_required("admin")
def toggle_student(student_id):
    conn = get_db()
    user = conn.execute(
        """SELECT u.* FROM users u JOIN students s ON s.user_id = u.id
           WHERE s.student_id = ?""",
        (student_id,),
    ).fetchone()
    if user:
        conn.execute(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (0 if user["is_active"] else 1, user["id"]),
        )
        conn.commit()
        flash(
            "Student account deactivated." if user["is_active"] else "Student account reactivated.",
            "success",
        )
    else:
        flash("This student has not registered an account yet.", "warning")
    conn.close()
    return redirect(url_for("admin.students"))


# ----------------------------------------------------------------- faculty -
@bp.route("/faculty")
@role_required("admin")
def faculty_list():
    conn = get_db()
    rows = conn.execute(
        """SELECT f.*, u.username, u.email, u.is_active FROM faculty f
           JOIN users u ON u.id = f.user_id ORDER BY f.full_name"""
    ).fetchall()
    conn.close()
    return render_template("admin/faculty.html", rows=rows)


@bp.route("/faculty/new", methods=["GET", "POST"])
@role_required("admin")
def new_faculty():
    if request.method == "POST":
        username = request.form["username"].strip()
        full_name = request.form["full_name"].strip()
        position = request.form.get("position", "Faculty").strip() or "Faculty"
        email = request.form["email"].strip()
        password = request.form["password"]

        conn = get_db()
        exists = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if exists:
            flash("Username already taken.", "danger")
            conn.close()
            return render_template("admin/faculty_form.html", mode="new", record=None)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash, role, email) VALUES (?,?,?,?)",
            (username, generate_password_hash(password), "faculty", email),
        )
        cur.execute(
                """INSERT INTO faculty (user_id, full_name, position, verification_status)
                    VALUES (?,?,?,'approved')""",
                (cur.lastrowid, full_name, position),
        )
        conn.commit()
        conn.close()
        flash("Faculty account created.", "success")
        return redirect(url_for("admin.faculty_list"))
    return render_template("admin/faculty_form.html", mode="new", record=None)


@bp.route("/faculty/<int:user_id>/approve", methods=["POST"])
@role_required("admin")
def approve_faculty(user_id):
    conn = get_db()
    conn.execute(
        "UPDATE users SET is_active = 1 WHERE id = ? AND role = 'faculty'", (user_id,)
    )
    conn.execute(
        "UPDATE faculty SET verification_status = 'approved' WHERE user_id = ?",
        (user_id,),
    )
    conn.commit()
    conn.close()
    flash("Faculty application approved and account activated.", "success")
    return redirect(url_for("admin.faculty_list"))


@bp.route("/faculty/<int:user_id>/toggle", methods=["POST"])
@role_required("admin")
def toggle_faculty(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user:
        conn.execute(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (0 if user["is_active"] else 1, user_id),
        )
        conn.commit()
    conn.close()
    flash("Faculty account status updated.", "success")
    return redirect(url_for("admin.faculty_list"))


# -------------------------------------------------------------- assignment -
@bp.route("/assignments", methods=["GET", "POST"])
@role_required("admin")
def assignments():
    conn = get_db()
    if request.method == "POST":
        subject_id = int(request.form["subject_id"])
        section_id = int(request.form["section_id"])
        faculty_user_id = int(request.form["faculty_user_id"])
        semester = request.form["semester"]
        school_year = request.form["school_year"].strip()
        meeting_time = request.form["meeting_time"].strip()
        meeting_days = request.form["meeting_days"].strip().upper()
        conn.execute(
            """INSERT INTO class_offerings
               (subject_id, section_id, faculty_user_id, semester, school_year,
                meeting_time, meeting_days)
               VALUES (?,?,?,?,?,?,?)""",
            (subject_id, section_id, faculty_user_id, semester, school_year,
             meeting_time, meeting_days),
        )
        conn.commit()

        # Auto-enroll every student currently in that section.
        students_in_section = conn.execute(
            """SELECT st.user_id FROM students st
               JOIN sections sec ON sec.program = st.program
                   AND sec.year_level = st.year_level AND sec.section_name = st.section
               WHERE sec.id = ?""",
            (section_id,),
        ).fetchall()
        offering_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for s in students_in_section:
            conn.execute(
                "INSERT OR IGNORE INTO enrollments (student_user_id, offering_id) VALUES (?,?)",
                (s["user_id"], offering_id),
            )
        conn.commit()
        flash("Subject assigned to instructor and students auto-enrolled.", "success")

    subjects = conn.execute("SELECT * FROM subjects ORDER BY code").fetchall()
    sections = conn.execute("SELECT * FROM sections ORDER BY program, year_level, section_name").fetchall()
    faculty = conn.execute(
        """SELECT f.user_id, f.full_name FROM faculty f
           JOIN users u ON u.id = f.user_id WHERE u.is_active = 1 ORDER BY f.full_name"""
    ).fetchall()
    offerings = conn.execute(
        """SELECT co.*, s.code, s.name, sec.program, sec.year_level, sec.section_name,
                  f.full_name AS instructor,
                  (SELECT COUNT(*) FROM enrollments e WHERE e.offering_id = co.id) AS enrolled
           FROM class_offerings co
           JOIN subjects s ON s.id = co.subject_id
           JOIN sections sec ON sec.id = co.section_id
           LEFT JOIN faculty f ON f.user_id = co.faculty_user_id
           ORDER BY co.school_year DESC, co.semester, s.code"""
    ).fetchall()
    conn.close()
    return render_template(
        "admin/assignments.html", subjects=subjects, sections=sections,
        faculty=faculty, offerings=offerings,
    )


# ------------------------------------------------------------ finalization -
@bp.route("/finalization")
@role_required("admin")
def finalization():
    conn = get_db()
    submitted = conn.execute(
        """SELECT g.*, st.full_name AS student_name, st.student_id, s.code, s.name,
                  co.semester, co.school_year, f.full_name AS instructor
           FROM grades g
           JOIN enrollments e ON e.id = g.enrollment_id
           JOIN students st ON st.user_id = e.student_user_id
           JOIN class_offerings co ON co.id = e.offering_id
           JOIN subjects s ON s.id = co.subject_id
           LEFT JOIN faculty f ON f.user_id = co.faculty_user_id
           WHERE g.status = 'submitted'
           ORDER BY co.school_year DESC, co.semester, s.code, st.full_name"""
    ).fetchall()
    corrections = conn.execute(
        """SELECT cr.*, st.full_name AS student_name, st.student_id, s.code, s.name,
                  g.final_grade, g.remarks
           FROM correction_requests cr
           JOIN grades g ON g.id = cr.grade_id
           JOIN enrollments e ON e.id = g.enrollment_id
           JOIN students st ON st.user_id = e.student_user_id
           JOIN class_offerings co ON co.id = e.offering_id
           JOIN subjects s ON s.id = co.subject_id
           WHERE cr.status = 'pending'
           ORDER BY cr.requested_at"""
    ).fetchall()
    conn.close()
    return render_template("admin/finalization.html", submitted=submitted, corrections=corrections)


@bp.route("/finalization/grades/<int:grade_id>/approve", methods=["POST"])
@role_required("admin")
def approve_grade(grade_id):
    conn = get_db()
    conn.execute(
        "UPDATE grades SET status = 'approved', updated_at = datetime('now') WHERE id = ?",
        (grade_id,),
    )
    conn.commit()
    conn.close()
    flash("Grade approved and locked for release.", "success")
    return redirect(url_for("admin.finalization"))


@bp.route("/finalization/grades/<int:grade_id>/return", methods=["POST"])
@role_required("admin")
def return_grade(grade_id):
    conn = get_db()
    conn.execute(
        "UPDATE grades SET status = 'draft', updated_at = datetime('now') WHERE id = ?",
        (grade_id,),
    )
    conn.commit()
    conn.close()
    flash("Grade returned to the instructor for revision.", "info")
    return redirect(url_for("admin.finalization"))


@bp.route("/finalization/corrections/<int:cr_id>/approve", methods=["POST"])
@role_required("admin")
def approve_correction(cr_id):
    conn = get_db()
    cr = conn.execute("SELECT * FROM correction_requests WHERE id = ?", (cr_id,)).fetchone()
    if cr:
        conn.execute(
            "UPDATE correction_requests SET status='approved', resolved_at=datetime('now') WHERE id=?",
            (cr_id,),
        )
        conn.execute(
            "UPDATE grades SET status='draft', updated_at=datetime('now') WHERE id=?",
            (cr["grade_id"],),
        )
        conn.commit()
    conn.close()
    flash("Correction approved — grade unlocked for the instructor to re-encode.", "success")
    return redirect(url_for("admin.finalization"))


@bp.route("/finalization/corrections/<int:cr_id>/return", methods=["POST"])
@role_required("admin")
def return_correction(cr_id):
    conn = get_db()
    conn.execute(
        "UPDATE correction_requests SET status='returned', resolved_at=datetime('now') WHERE id=?",
        (cr_id,),
    )
    conn.commit()
    conn.close()
    flash("Correction request denied.", "info")
    return redirect(url_for("admin.finalization"))


# ------------------------------------------------------------------ reports -
@bp.route("/reports")
@role_required("admin")
def reports():
    conn = get_db()
    program = request.args.get("program", "")
    year_level = request.args.get("year_level", "")

    query = """SELECT st.student_id, st.full_name, st.program, st.year_level, st.section,
                      s.code, s.name, co.semester, co.school_year, g.final_grade, g.remarks
               FROM enrollments e
               JOIN students st ON st.user_id = e.student_user_id
               JOIN class_offerings co ON co.id = e.offering_id
               JOIN subjects s ON s.id = co.subject_id
               LEFT JOIN grades g ON g.enrollment_id = e.id AND g.status = 'released'
               WHERE 1=1"""
    params = []
    if program:
        query += " AND st.program = ?"
        params.append(program)
    if year_level:
        query += " AND st.year_level = ?"
        params.append(year_level)
    query += " ORDER BY st.program, st.year_level, st.section, st.full_name, s.code"
    rows = conn.execute(query, params).fetchall()

    programs = [r[0] for r in conn.execute("SELECT DISTINCT program FROM students").fetchall()]
    year_levels = [r[0] for r in conn.execute("SELECT DISTINCT year_level FROM students").fetchall()]
    conn.close()
    return render_template(
        "admin/reports.html", rows=rows, programs=programs, year_levels=year_levels,
        program=program, year_level=year_level,
    )
