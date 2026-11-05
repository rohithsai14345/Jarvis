import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "jarvis_memory.db"


def connect():
    return sqlite3.connect(DB_PATH)


def initialize():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def remember(memory):
    memory = memory.strip()

    if not memory:
        return "Please tell me what to remember."

    with connect() as db:
        db.execute(
            "INSERT INTO memories (memory, created_at) VALUES (?, ?)",
            (memory, datetime.now().isoformat(timespec="seconds"))
        )

    return "I have saved that to my memory."


def recall():
    with connect() as db:
        rows = db.execute(
            "SELECT id, memory FROM memories ORDER BY id DESC"
        ).fetchall()

    if not rows:
        return "No saved memories."

    return "\n".join(
        f"{memory_id}. {memory}"
        for memory_id, memory in rows
    )


def forget(memory_id):
    with connect() as db:
        cursor = db.execute(
            "DELETE FROM memories WHERE id = ?",
            (memory_id,)
        )

    return "Memory deleted." if cursor.rowcount else "Memory not found."


initialize()

def relevant_memories(query, limit=3):
    import re

    words = set(re.findall(r"[a-zA-Z0-9]+", query.lower()))
    stop_words = {
        "what", "when", "where", "which", "who", "why",
        "how", "the", "and", "for", "are", "is", "my",
        "me", "you", "your", "about", "can", "do"
    }
    words -= stop_words

    with connect() as db:
        rows = db.execute(
            "SELECT memory FROM memories ORDER BY id DESC"
        ).fetchall()

    scored = []

    for (saved_memory,) in rows:
        memory_words = set(
            re.findall(r"[a-zA-Z0-9]+", saved_memory.lower())
        )
        score = len(words & memory_words)

        if score > 0:
            scored.append((score, saved_memory))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [item[1] for item in scored[:limit]]


def remember_unique(memory_text):
    memory_text = memory_text.strip()

    if not memory_text:
        return "Please provide something to remember."

    with connect() as db:
        rows = db.execute(
            "SELECT memory FROM memories"
        ).fetchall()

        for (saved,) in rows:
            if saved.strip().lower() == memory_text.lower():
                return "This information is already saved."

    return remember(memory_text)


def list_memories():
    with connect() as db:
        rows = db.execute(
            "SELECT id, memory, created_at FROM memories ORDER BY id DESC"
        ).fetchall()

    return [
        {"id": row[0], "memory": row[1], "created_at": row[2]}
        for row in rows
    ]


def forget_all():
    with connect() as db:
        cursor = db.execute("DELETE FROM memories")
        deleted_count = cursor.rowcount

    return f"Deleted {deleted_count} saved memories."
