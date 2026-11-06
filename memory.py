import sqlite3
import re
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "jarvis_memory.db"


def connect():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.commit()


def remember(memory_text):
    memory_text = str(memory_text).strip()

    if not memory_text:
        return "Please tell me what to remember."

    with connect() as db:
        db.execute(
            """
            INSERT INTO memories (memory, created_at)
            VALUES (?, ?)
            """,
            (
                memory_text,
                datetime.now().isoformat(timespec="seconds")
            )
        )
        db.commit()

    return "I have saved that to my memory."


def remember_unique(memory_text):
    memory_text = str(memory_text).strip()

    if not memory_text:
        return "Please provide something to remember."

    with connect() as db:
        existing = db.execute(
            """
            SELECT id FROM memories
            WHERE LOWER(TRIM(memory)) = LOWER(TRIM(?))
            LIMIT 1
            """,
            (memory_text,)
        ).fetchone()

        if existing:
            return "This information is already saved."

        db.execute(
            """
            INSERT INTO memories (memory, created_at)
            VALUES (?, ?)
            """,
            (
                memory_text,
                datetime.now().isoformat(timespec="seconds")
            )
        )
        db.commit()

    return "I have saved that to my memory."


def recall():
    memories = list_memories()

    if not memories:
        return "No saved memories."

    return "\n".join(
        f"{item['id']}. {item['memory']}"
        for item in memories
    )


def list_memories():
    with connect() as db:
        rows = db.execute(
            """
            SELECT id, memory, created_at
            FROM memories
            ORDER BY id DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def forget(memory_id):
    with connect() as db:
        cursor = db.execute(
            "DELETE FROM memories WHERE id = ?",
            (int(memory_id),)
        )
        db.commit()

    return (
        "Memory deleted."
        if cursor.rowcount
        else "Memory not found."
    )


def forget_all():
    with connect() as db:
        cursor = db.execute("DELETE FROM memories")
        deleted_count = cursor.rowcount
        db.commit()

    return f"Deleted {deleted_count} saved memories."


def relevant_memories(query, limit=3):
    stop_words = {
        "what", "when", "where", "which", "who", "why",
        "how", "the", "and", "for", "are", "is", "my",
        "me", "you", "your", "about", "can", "do",
        "tell", "please", "jarvis"
    }

    words = set(
        re.findall(r"[a-zA-Z0-9]+", str(query).lower())
    )
    words -= stop_words

    if not words:
        return []

    with connect() as db:
        rows = db.execute(
            "SELECT memory FROM memories ORDER BY id DESC"
        ).fetchall()

    scored = []

    for row in rows:
        saved_memory = row["memory"]

        memory_words = set(
            re.findall(
                r"[a-zA-Z0-9]+",
                saved_memory.lower()
            )
        )

        score = len(words & memory_words)

        if score:
            scored.append((score, saved_memory))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [
        item[1]
        for item in scored[:max(1, min(limit, 10))]
    ]


initialize()
