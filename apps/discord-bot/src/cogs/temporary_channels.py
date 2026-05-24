import discord
from discord.ext import commands

import temporary_channel_store


CHANNEL_CREATE_CHANNEL_NAME = '[CREATE CHANNEL]'


class TemporaryChannels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._startup_cleanup_done = False

    async def _cleanup_stale_temporary_channels(self):
        for guild_id, channel_id in temporary_channel_store.get_all_temporary_channels():
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                temporary_channel_store.remove_temporary_channel(guild_id, channel_id)
                continue

            channel = guild.get_channel(channel_id)
            if channel is not None:
                continue

            try:
                await guild.fetch_channel(channel_id)
            except discord.NotFound:
                temporary_channel_store.remove_temporary_channel(guild_id, channel_id)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_ready(self):
        if self._startup_cleanup_done:
            return

        await self._cleanup_stale_temporary_channels()
        self._startup_cleanup_done = True

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is not None:
            channel_to_delete = before.channel
            if (
                channel_to_delete.name != CHANNEL_CREATE_CHANNEL_NAME
                and len(channel_to_delete.voice_states) == 0
                and temporary_channel_store.is_temporary_channel(member.guild.id, channel_to_delete.id)
            ):
                try:
                    await channel_to_delete.delete(reason='Temporary channel is empty.')
                except discord.NotFound:
                    pass
                temporary_channel_store.remove_temporary_channel(member.guild.id, channel_to_delete.id)

        if after.channel is not None and after.channel.name == CHANNEL_CREATE_CHANNEL_NAME:
            new_channel = await member.guild.create_voice_channel(
                name=member.display_name + "'s Channel",
                category=after.channel.category,
                bitrate=member.guild.bitrate_limit,
                overwrites={
                    member: discord.PermissionOverwrite(
                        move_members=True,
                        manage_channels=True
                    )
                }
            )
            temporary_channel_store.add_temporary_channel(member.guild.id, new_channel.id)
            await member.move_to(new_channel)

def setup(bot):
    bot.add_cog(TemporaryChannels(bot))
