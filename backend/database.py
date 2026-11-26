"""SQLite connection and schema."""

import sqlite3
from contextlib import contextmanager

from .config import DATABASE_PATH


def db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row  # rows can be read like row["id"]
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database():
    connection = db_connection()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


# Columns added after the first version of the schema. Older databases are
# upgraded in place with ALTER TABLE so existing users are kept.
SCREENING_COLUMNS = {
    "patient_id": "INTEGER REFERENCES users(id) ON DELETE SET NULL",
    "eye": "TEXT DEFAULT 'unspecified'",
    "status": "TEXT DEFAULT 'pending'",  # pending | reviewed | retake
    "ai_grade": "INTEGER",
    "confidence": "REAL",
    "referable": "INTEGER",
    "referable_probability": "REAL",
    "probabilities": "TEXT",  # JSON list, one value per grade
    "explanation_filename": "TEXT",
    "inference_ms": "INTEGER",
}

REVIEW_COLUMNS = {
    "final_grade": "INTEGER",
}


def add_missing_columns(connection, table, columns):
    existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns.items():
        if name not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def setup_database():
    with database() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name VARCHAR(120) NOT NULL,
                email VARCHAR(190) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('patient', 'doctor', 'admin')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS screenings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_filename VARCHAR(255) NOT NULL,
                saved_filename VARCHAR(255) NOT NULL,
                file_size INT NOT NULL,
                width INT NOT NULL,
                height INT NOT NULL,
                quality VARCHAR(30) NOT NULL,
                quality_message VARCHAR(500) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
        add_missing_columns(connection, "screenings", SCREENING_COLUMNS)

        # One row per doctor sign-off. decision is 'confirmed' when the doctor
        # agrees with the AI grade and 'overridden' otherwise.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS doctor_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                screening_id INT,
                doctor_id INT,
                decision VARCHAR(80),
                comments TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (screening_id) REFERENCES screenings(id) ON DELETE SET NULL,
                FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE SET NULL
            )""")
        add_missing_columns(connection, "doctor_reviews", REVIEW_COLUMNS)

    print("SQLite database is ready:", DATABASE_PATH)
