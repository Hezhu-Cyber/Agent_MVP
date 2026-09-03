from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    def __init__(self, path: str | Path = "data/agent.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    summarized_through INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, session_id)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'tool')),
                    content TEXT NOT NULL DEFAULT '',
                    tool_call_id TEXT,
                    tool_name TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(user_id, session_id, id);

                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open'
                        CHECK(status IN ('open', 'completed')),
                    source_session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_todos_user
                ON todos(user_id, status, id);
                """
            )

    def get_or_create_session(self, user_id: str, session_id: str) -> dict[str, Any]:
        if not user_id.strip() or not session_id.strip():
            raise ValueError("user_id 和 session_id 不能为空")
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(user_id, session_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, session_id)
                DO UPDATE SET updated_at = excluded.updated_at
                """,
                (user_id, session_id, now, now),
            )
            row = connection.execute(
                "SELECT * FROM sessions WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
        return dict(row)

    def get_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
        return dict(row) if row else None

    def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
    ) -> int:
        if role not in {"user", "assistant", "tool"}:
            raise ValueError(f"不支持的消息角色: {role}")
        self.get_or_create_session(user_id, session_id)
        now = utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages(
                    user_id, session_id, role, content,
                    tool_call_id, tool_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, session_id, role, content, tool_call_id, tool_name, now),
            )
            connection.execute(
                """
                UPDATE sessions SET updated_at = ?
                WHERE user_id = ? AND session_id = ?
                """,
                (now, user_id, session_id),
            )
            return int(cursor.lastrowid)

    def get_messages(
        self,
        user_id: str,
        session_id: str,
        *,
        after_id: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [user_id, session_id, after_id]
        if limit is None:
            query = """
                SELECT * FROM messages
                WHERE user_id = ? AND session_id = ? AND id > ?
                ORDER BY id ASC
            """
        else:
            query = """
                SELECT * FROM (
                    SELECT * FROM messages
                    WHERE user_id = ? AND session_id = ? AND id > ?
                    ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC
            """
            params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def update_summary(
        self,
        user_id: str,
        session_id: str,
        summary: str,
        summarized_through: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET summary = ?, summarized_through = ?, updated_at = ?
                WHERE user_id = ? AND session_id = ?
                """,
                (summary, summarized_through, utc_now(), user_id, session_id),
            )

    def create_todo(self, user_id: str, session_id: str, content: str) -> dict[str, Any]:
        now = utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO todos(
                    user_id, content, status, source_session_id, created_at, updated_at
                ) VALUES (?, ?, 'open', ?, ?, ?)
                """,
                (user_id, content, session_id, now, now),
            )
            row = connection.execute(
                "SELECT * FROM todos WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return dict(row)

    def list_todos(self, user_id: str, status: str = "all") -> list[dict[str, Any]]:
        with self._connect() as connection:
            if status == "all":
                rows = connection.execute(
                    "SELECT * FROM todos WHERE user_id = ? ORDER BY id ASC", (user_id,)
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM todos
                    WHERE user_id = ? AND status = ? ORDER BY id ASC
                    """,
                    (user_id, status),
                ).fetchall()
        return [dict(row) for row in rows]

    def complete_todo(self, user_id: str, todo_id: int) -> dict[str, Any] | None:
        now = utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE todos SET status = 'completed', updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (now, todo_id, user_id),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                "SELECT * FROM todos WHERE id = ? AND user_id = ?",
                (todo_id, user_id),
            ).fetchone()
        return dict(row)
