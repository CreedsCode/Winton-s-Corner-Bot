import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "glue_channels.db"


def _get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS glued_channels (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, channel_id)
        )
        """
    )
    return connection


def add_glued_channel(guild_id: int, channel_id: int) -> bool:
    with _get_connection() as connection:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO glued_channels (guild_id, channel_id) VALUES (?, ?)",
            (guild_id, channel_id)
        )
        connection.commit()
        return cursor.rowcount > 0


def is_channel_glued(guild_id: int, channel_id: int) -> bool:
    with _get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM glued_channels WHERE guild_id = ? AND channel_id = ? LIMIT 1",
            (guild_id, channel_id)
        ).fetchone()
        return row is not None
