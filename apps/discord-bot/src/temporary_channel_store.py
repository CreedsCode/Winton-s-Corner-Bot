import db


def add_temporary_channel(guild_id: int, channel_id: int):
    with db.get_connection() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO temporary_voice_channels (guild_id, channel_id) VALUES (?, ?)",
            (guild_id, channel_id)
        )
        connection.commit()


def is_temporary_channel(guild_id: int, channel_id: int) -> bool:
    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM temporary_voice_channels WHERE guild_id = ? AND channel_id = ? LIMIT 1",
            (guild_id, channel_id)
        ).fetchone()
        return row is not None


def remove_temporary_channel(guild_id: int, channel_id: int):
    with db.get_connection() as connection:
        connection.execute(
            "DELETE FROM temporary_voice_channels WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id)
        )
        connection.commit()


def get_all_temporary_channels() -> list[tuple[int, int]]:
    with db.get_connection() as connection:
        rows = connection.execute(
            "SELECT guild_id, channel_id FROM temporary_voice_channels"
        ).fetchall()
        return rows
