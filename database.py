import sqlite3
from datetime import datetime

DB_NAME = "fitness_bot.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                age INTEGER,
                height REAL,
                weight REAL,
                goal TEXT,
                level TEXT,
                registered_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                exercises TEXT,
                completed BOOLEAN DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        conn.commit()

def save_user(user_id, name, age, height, weight, goal, level):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO users (user_id, full_name, age, height, weight, goal, level, registered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name, age, height, weight, goal, level, datetime.now().isoformat()))
        conn.commit()

def get_user(user_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def get_all_users():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, full_name FROM users")
        return cursor.fetchall()

def get_total_users():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]

def get_active_users_today():
    today = datetime.now().date().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) FROM workouts
            WHERE date = ? AND completed = 1
        """, (today,))
        return cursor.fetchone()[0]

def get_active_users_week():
    from datetime import timedelta
    week_ago = (datetime.now().date() - timedelta(days=7)).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) FROM workouts
            WHERE date >= ? AND completed = 1
        """, (week_ago,))
        return cursor.fetchone()[0]

def save_workout(user_id, exercises, date=None):
    if date is None:
        date = datetime.now().date().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO workouts (user_id, date, exercises, completed)
            VALUES (?, ?, ?, 0)
        """, (user_id, date, exercises))
        conn.commit()
        return cursor.lastrowid

def get_today_workout(user_id):
    today = datetime.now().date().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, exercises, completed FROM workouts
            WHERE user_id = ? AND date = ?
        """, (user_id, today))
        return cursor.fetchone()

def mark_workout_done(workout_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE workouts SET completed = 1 WHERE id = ?", (workout_id,))
        conn.commit()

def get_user_workouts(user_id, limit=7):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, exercises, completed FROM workouts
            WHERE user_id = ?
            ORDER BY date DESC LIMIT ?
        """, (user_id, limit))
        return cursor.fetchall()

def get_user_workouts_by_month(user_id, year, month):
    import calendar
    with get_connection() as conn:
        cursor = conn.cursor()
        start_date = f"{year}-{month:02d}-01"
        _, last_day = calendar.monthrange(year, month)
        end_date = f"{year}-{month:02d}-{last_day:02d}"
        cursor.execute("""
            SELECT date, completed FROM workouts
            WHERE user_id = ? AND date BETWEEN ? AND ?
            ORDER BY date
        """, (user_id, start_date, end_date))
        return cursor.fetchall()
