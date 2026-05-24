import sqlite3
from pathlib import Path
import os


DATA_DIR = Path(os.getenv('DATA_DIR', Path(__file__).resolve().parent))
DB_PATH = DATA_DIR / "bot.db"


def get_connection() -> sqlite3.Connection:
    """Get a connection to the shared bot database."""
    return sqlite3.connect(DB_PATH)


def init_db():
    """Initialize all database tables."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS temporary_voice_channels (
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
