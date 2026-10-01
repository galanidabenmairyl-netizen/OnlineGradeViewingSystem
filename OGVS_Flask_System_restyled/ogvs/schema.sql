-- OGVS database schema

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'faculty', 'admin')),
    email TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Simulates the registrar's official enrollment records, used to validate
-- a student's self-registration (Student ID must exist here first).
CREATE TABLE IF NOT EXISTS pre_enrolled_students (
    student_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    program TEXT NOT NULL,
    year_level TEXT NOT NULL,
    section TEXT NOT NULL,
    is_registered INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS students (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    student_id TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    program TEXT NOT NULL,
    year_level TEXT NOT NULL,
    section TEXT NOT NULL,
    profile_image TEXT
);

CREATE TABLE IF NOT EXISTS faculty (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    employee_id TEXT UNIQUE,
    position TEXT NOT NULL DEFAULT 'Faculty',
    profile_image TEXT,
    verification_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (verification_status IN ('pending', 'approved', 'rejected'))
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    units REAL NOT NULL DEFAULT 3
);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program TEXT NOT NULL,
    year_level TEXT NOT NULL,
    section_name TEXT NOT NULL,
    UNIQUE(program, year_level, section_name)
);

-- A subject taught to a specific section, by a specific instructor, in a
-- specific term. This is what students actually get enrolled into.
CREATE TABLE IF NOT EXISTS class_offerings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id),
    section_id INTEGER NOT NULL REFERENCES sections(id),
    faculty_user_id INTEGER REFERENCES users(id),
    semester TEXT NOT NULL CHECK (semester IN ('1st Semester', '2nd Semester', 'Summer')),
    school_year TEXT NOT NULL,
    meeting_time TEXT,
    meeting_days TEXT
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_user_id INTEGER NOT NULL REFERENCES users(id),
    offering_id INTEGER NOT NULL REFERENCES class_offerings(id),
    UNIQUE(student_user_id, offering_id)
);

CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER UNIQUE NOT NULL REFERENCES enrollments(id),
    prelim REAL,
    midterm REAL,
    finals REAL,
    final_grade REAL,
    remarks TEXT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'submitted', 'approved', 'released')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS correction_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grade_id INTEGER NOT NULL REFERENCES grades(id),
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'returned')),
    requested_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_read INTEGER NOT NULL DEFAULT 0
);
