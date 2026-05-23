import db


def add_temporary_invite(guild_id: int, channel_id: int, user_id: int, had_view_channel: bool):
    with db.get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO temporary_invites 
            (guild_id, channel_id, user_id, had_view_channel) 
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, channel_id, user_id, had_view_channel)
        )
        connection.commit()


def get_temporary_invite(guild_id: int, channel_id: int, user_id: int) -> bool | None:
    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT had_view_channel FROM temporary_invites WHERE guild_id = ? AND channel_id = ? AND user_id = ? LIMIT 1",
            (guild_id, channel_id, user_id)
        ).fetchone()
        return row[0] if row is not None else None


def remove_temporary_invite(guild_id: int, channel_id: int, user_id: int):
    with db.get_connection() as connection:
        connection.execute(
            "DELETE FROM temporary_invites WHERE guild_id = ? AND channel_id = ? AND user_id = ?",
            (guild_id, channel_id, user_id)
        )
        connection.commit()


def get_all_temporary_invites() -> list[tuple[int, int, int, bool]]:
    with db.get_connection() as connection:
        rows = connection.execute(
            "SELECT guild_id, channel_id, user_id, had_view_channel FROM temporary_invites"
        ).fetchall()
        return rows
