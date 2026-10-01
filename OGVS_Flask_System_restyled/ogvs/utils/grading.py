"""Grade computation logic.

Adjust WEIGHTS and PASSING_GRADE to match NEMSU Cantilan Campus's actual
grading formula and passing standard.
"""

WEIGHTS = {"prelim": 0.30, "midterm": 0.30, "finals": 0.40}
PASSING_GRADE = 3.00


def compute_final(prelim, midterm, finals):
    """Return (final_grade, remarks). Any missing period -> Incomplete."""
    if prelim is None or midterm is None or finals is None:
        return None, "Incomplete"
    final = (
        prelim * WEIGHTS["prelim"]
        + midterm * WEIGHTS["midterm"]
        + finals * WEIGHTS["finals"]
    )
    final = round(final, 2)
    remarks = "Passed" if final <= PASSING_GRADE else "Failed"
    return final, remarks


def percentage_to_college(percentage):
    """Convert legacy percentage grades to the 1.00-5.00 college scale."""
    if percentage is None:
        return None
    if percentage >= 97:
        return 1.00
    if percentage >= 94:
        return 1.25
    if percentage >= 91:
        return 1.50
    if percentage >= 88:
        return 1.75
    if percentage >= 85:
        return 2.00
    if percentage >= 82:
        return 2.25
    if percentage >= 79:
        return 2.50
    if percentage >= 76:
        return 2.75
    if percentage >= 75:
        return 3.00
    if percentage >= 70:
        return 4.00
    return 5.00


def compute_gwa(rows):
    """rows: iterable of sqlite3.Row/dict with 'final_grade' and 'units'.
    Only rows with a numeric final_grade are counted. Returns None if empty.
    """
    total_units = 0.0
    weighted_sum = 0.0
    for r in rows:
        fg = r["final_grade"]
        units = r["units"]
        if fg is None:
            continue
        total_units += units
        weighted_sum += fg * units
    if total_units == 0:
        return None
    return round(weighted_sum / total_units, 2)
