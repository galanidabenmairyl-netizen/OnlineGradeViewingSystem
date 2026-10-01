import sqlite3


def mark_notifications_read(conn, user_id):
    try:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,)
        )
        conn.commit()
    except sqlite3.OperationalError as error:
        conn.rollback()
        if "readonly database" not in str(error).lower():
            raise
        return False
    return True