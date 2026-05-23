import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "bot.db"


def get_connection() -> sqlite3.Connection:
    """Get a connection to the shared bot database."""
    return sqlite3.connect(DB_PATH)


def init_db():
    """Initialize all database tables."""
    with get_connection() as connection:
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS temporary_invites (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                had_view_channel BOOLEAN NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, channel_id, user_id)
            )
            """
        )
        connection.commit()
