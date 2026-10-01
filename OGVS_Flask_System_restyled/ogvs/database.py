"""SQLite connection handling, schema initialization, and demo seed data."""
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

from utils.grading import percentage_to_college

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "ogvs.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


def get_db():
    """Return a new SQLite connection with row access by column name."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't already exist."""
    conn = get_db()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    student_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(students)")
    }
    if "profile_image" not in student_columns:
        conn.execute("ALTER TABLE students ADD COLUMN profile_image TEXT")
    faculty_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(faculty)")
    }
    if "employee_id" not in faculty_columns:
        conn.execute("ALTER TABLE faculty ADD COLUMN employee_id TEXT")
    if "verification_status" not in faculty_columns:
        conn.execute(
            "ALTER TABLE faculty ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'approved'"
        )
    if "position" not in faculty_columns:
        conn.execute(
            "ALTER TABLE faculty ADD COLUMN position TEXT NOT NULL DEFAULT 'Faculty'"
        )
    if "profile_image" not in faculty_columns:
        conn.execute("ALTER TABLE faculty ADD COLUMN profile_image TEXT")
    offering_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(class_offerings)")
    }
    if "meeting_time" not in offering_columns:
        conn.execute("ALTER TABLE class_offerings ADD COLUMN meeting_time TEXT")
    if "meeting_days" not in offering_columns:
        conn.execute("ALTER TABLE class_offerings ADD COLUMN meeting_days TEXT")
    default_schedules = {
        "IT101": ("1:00-2:30", "MTH"),
        "IT102": ("10:30-12:00", "MTH"),
        "GE105": ("9:00-10:30", "TF"),
    }
    existing_offerings = conn.execute(
        """SELECT co.id, s.code FROM class_offerings co
           JOIN subjects s ON s.id = co.subject_id
           WHERE co.meeting_time IS NULL OR co.meeting_days IS NULL"""
    ).fetchall()
    for offering in existing_offerings:
        schedule = default_schedules.get(offering["code"])
        if schedule:
            conn.execute(
                "UPDATE class_offerings SET meeting_time=?, meeting_days=? WHERE id=?",
                (*schedule, offering["id"]),
            )
    _migrate_percentage_grades(conn)
    conn.commit()
    conn.close()


def _migrate_percentage_grades(conn):
    """Convert legacy 0-100 grades to the college 1.00-5.00 scale once."""
    rows = conn.execute(
        "SELECT id, prelim, midterm, finals, final_grade FROM grades"
    ).fetchall()
    for row in rows:
        values = [row["prelim"], row["midterm"], row["finals"], row["final_grade"]]
        if not any(value is not None and value > 5 for value in values):
            continue
        prelim = percentage_to_college(row["prelim"])
        midterm = percentage_to_college(row["midterm"])
        finals = percentage_to_college(row["finals"])
        final_grade = percentage_to_college(row["final_grade"])
        remarks = "Passed" if final_grade is not None and final_grade <= 3 else "Failed"
        conn.execute(
            "UPDATE grades SET prelim=?, midterm=?, finals=?, final_grade=?, remarks=? WHERE id=?",
            (prelim, midterm, finals, final_grade, remarks, row["id"]),
        )


def _is_seeded(conn):
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0


def seed_data():
    """Populate the database with demo accounts and sample records, once."""
    conn = get_db()
    if _is_seeded(conn):
        conn.close()
        return

    cur = conn.cursor()

    # --- Admin / Registrar ---------------------------------------------
    cur.execute(
        "INSERT INTO users (username, password_hash, role, email) VALUES (?,?,?,?)",
        ("registrar", generate_password_hash("admin123"), "admin",
         "registrar@nemsu.edu.ph"),
    )

    # --- Faculty ----------------------------------------------------------
    cur.execute(
        "INSERT INTO users (username, password_hash, role, email) VALUES (?,?,?,?)",
        ("jdelacruz", generate_password_hash("faculty123"), "faculty",
         "jdelacruz@nemsu.edu.ph"),
    )
    faculty_id = cur.lastrowid
    cur.execute(
        "INSERT INTO faculty (user_id, full_name) VALUES (?,?)",
        (faculty_id, "Prof. Juana Dela Cruz"),
    )

    # --- Subjects & section --------------------------------------------
    cur.execute("INSERT INTO subjects (code, name, units) VALUES (?,?,?)",
                ("IT101", "Introduction to Computing", 3))
    it101 = cur.lastrowid
    cur.execute("INSERT INTO subjects (code, name, units) VALUES (?,?,?)",
                ("IT102", "Web Systems and Technologies", 3))
    it102 = cur.lastrowid
    cur.execute("INSERT INTO subjects (code, name, units) VALUES (?,?,?)",
                ("GE105", "Purposive Communication", 3))
    ge105 = cur.lastrowid

    cur.execute(
        "INSERT INTO sections (program, year_level, section_name) VALUES (?,?,?)",
        ("BSIT", "3rd Year", "A"),
    )
    section_id = cur.lastrowid

    term = ("1st Semester", "2026-2027")
    offering_ids = []
    schedules = {
        it101: ("1:00-2:30", "MTH"),
        it102: ("10:30-12:00", "MTH"),
        ge105: ("9:00-10:30", "TF"),
    }
    for subj_id in (it101, it102, ge105):
        cur.execute(
            """INSERT INTO class_offerings
               (subject_id, section_id, faculty_user_id, semester, school_year,
                meeting_time, meeting_days)
               VALUES (?,?,?,?,?,?,?)""",
            (subj_id, section_id, faculty_id, *term, *schedules[subj_id]),
        )
        offering_ids.append(cur.lastrowid)

    # --- Sample enrolled student -----------------------------------------
    cur.execute(
        "INSERT INTO users (username, password_hash, role, email) VALUES (?,?,?,?)",
        ("2023-00123", generate_password_hash("student123"), "student",
         "mdelacruz.student@nemsu.edu.ph"),
    )
    student_id = cur.lastrowid
    cur.execute(
        "INSERT INTO students (user_id, student_id, full_name, program, year_level, section)"
        " VALUES (?,?,?,?,?,?)",
        (student_id, "2023-00123", "Mariel D. Santos", "BSIT", "3rd Year", "A"),
    )
    for off_id, grades in zip(
        offering_ids,
        [(1.75, 1.75, 1.50), (2.50, 4.00, 4.00), (1.25, 1.50, 1.25)],
    ):
        cur.execute(
            "INSERT INTO enrollments (student_user_id, offering_id) VALUES (?,?)",
            (student_id, off_id),
        )
        enrollment_id = cur.lastrowid
        prelim, midterm, finals = grades
        final = round(prelim * 0.3 + midterm * 0.3 + finals * 0.4, 2)
        remarks = "Passed" if final <= 3 else "Failed"
        cur.execute(
            """INSERT INTO grades
               (enrollment_id, prelim, midterm, finals, final_grade, remarks, status)
               VALUES (?,?,?,?,?,?, 'released')""",
            (enrollment_id, prelim, midterm, finals, final, remarks),
        )

    cur.execute(
        "INSERT INTO notifications (user_id, message) VALUES (?,?)",
        (student_id, "Your grades for 1st Semester, 2026-2027 have been released."),
    )

    # --- Registrar's pre-enrollment records (used to validate self-registration) --
    cur.execute(
        "INSERT OR IGNORE INTO pre_enrolled_students "
        "(student_id, full_name, program, year_level, section, is_registered) "
        "VALUES (?,?,?,?,?,1)",
        ("2023-00123", "Mariel D. Santos", "BSIT", "3rd Year", "A"),
    )
    cur.execute(
        "INSERT OR IGNORE INTO pre_enrolled_students "
        "(student_id, full_name, program, year_level, section, is_registered) "
        "VALUES (?,?,?,?,?,0)",
        ("2023-00456", "Carlo P. Reyes", "BSIT", "3rd Year", "A"),
    )

    conn.commit()
    conn.close()
