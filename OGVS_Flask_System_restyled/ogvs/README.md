# OGVS — Online Grade Viewing System
### NEMSU Cantilan Campus

"Every grade, one login away."

A role-based grade viewing and encoding system for **Students**, **Faculty**, and the
**Admin / Registrar's Office**, built with Flask and SQLite.

## 1. Requirements

- Python 3.10+
- pip

## 2. Setup (VS Code)

```bash
# 1. Open this folder in VS Code
# 2. Create a virtual environment
python -m venv venv

# 3. Activate it
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the app (creates and seeds ogvs.db on first run)
python app.py

```
cd ".\OGVS_Flask_System_restyled\ogvs"
pip install -r requirements.txt
python app.py


Open **http://127.0.0.1:5000** in your browser.

## 3. Seeded demo accounts

The database is auto-created and seeded the first time you run the app
(see `database.py: seed_data()`).

| Role     | Username     | Password    | Notes                                   |
|----------|--------------|-------------|------------------------------------------|
| Admin    | `registrar`  | `admin123`  | Registrar / Admin account                |
| Faculty  | `jdelacruz`  | `faculty123`| Assigned to IT101 & IT102                |
| Student  | `2023-00123` | `student123`| Already enrolled with sample grades      |

A **new** student can also self-register through *Register* — registration
only succeeds if the Student ID matches a record the registrar already
pre-loaded (simulating validation against enrollment records). Try
Student ID `2023-00456` (pre-loaded, not yet registered) to test this.

## 4. Project structure

```
ogvs/
├── app.py                 # App factory + entry point
├── database.py             # SQLite connection, schema init, seed data
├── schema.sql               # Full DB schema
├── routes/
│   ├── auth.py              # Register / login / logout
│   ├── student.py           # Dashboard, grades, history, slip, notifications
│   ├── faculty.py           # Classes, grade encoding, release, corrections
│   └── admin.py             # Manage students/faculty, assignments, finalization, reports
├── utils/
│   ├── grading.py           # Final grade formula, GWA, remarks
│   ├── decorators.py         # login_required / role_required guards
│   └── pdf.py                 # Grade slip PDF export (reportlab)
├── templates/                # Jinja2 templates, NEMSU blue/gold theme
└── static/
    ├── css/style.css
    └── img/logo.jpg
```

## 5. Grading formula (adjust to your campus's actual formula)

```
Final Grade = (Prelim × 30%) + (Midterm × 30%) + (Finals × 40%)
Passed  : Final Grade ≤ 3.00
Failed  : Final Grade > 3.00
Incomplete : any period not yet encoded
```
Grades use the college scale: 1.00 is highest, 3.00 is passing, and 5.00 is failing.
Edit `utils/grading.py` to match NEMSU Cantilan's official computation.

## 6. Grade workflow

```
Faculty encodes → Submitted for review → Registrar approves
   → Faculty releases → Visible to student
```
A released grade can only be changed through a **correction request**
(Faculty → reason recorded → Registrar approves/returns).

## 7. Design notes

Color palette reflects NEMSU's official blue identity ("pacific blue" /
sky-blue seal, per the university hymn and seal description), paired with
gold for accreditation-style accent and contrast. The application uses the NEMSU
seal in `static/img/logo.jpg`.
