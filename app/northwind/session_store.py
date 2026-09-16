"""SQLite-backed conversation session store for stateful multi-turn interactions."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional


class SessionStore:
    """Manages multi-turn conversation history using SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            self.db_path = project_root / "results" / "sessions.db"
        else:
            self.db_path = Path(db_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id ON conversation_history(session_id)
            """)
            conn.commit()

    def add_message(self, session_id: str, role: str, content: str):
        """Append a message turn to the session history."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO conversation_history (session_id, role, content, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, now_str),
            )
            conn.commit()

    def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve recent conversation history formatted for LLM messages array."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT role, content FROM conversation_history
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            )
            rows = cursor.fetchall()
            messages = [{"role": row["role"], "content": row["content"]} for row in rows]
            # Return up to the latest limit turns
            return messages[-limit:] if limit > 0 else messages

    def clear_session(self, session_id: str):
        """Reset conversation history for a specific session."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM conversation_history WHERE session_id = ?", (session_id,))
            conn.commit()

    def list_sessions(self) -> List[str]:
        """List all unique session identifiers."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT session_id FROM conversation_history")
            return [row["session_id"] for row in cursor.fetchall()]

