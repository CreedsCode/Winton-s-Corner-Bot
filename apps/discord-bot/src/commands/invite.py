import asyncio

import discord
from discord.ext import commands

from stores import invite_store


TEMP_INVITE_DURATION_MINUTES = 10

class Invite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {(guild_id, channel_id, user_id): asyncio.Task}
        self.temporary_voice_invites = {}
        self._temporary_invites_restored = False

    async def _restore_temporary_invites(self):
        """Restore temporary invites from database on bot startup."""
        rows = invite_store.get_all_temporary_invites()
        for guild_id, channel_id, user_id, had_view_channel in rows:
            expiration_task = asyncio.create_task(
                self.expire_temporary_voice_invite(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    user_id=user_id,
                    duration_minutes=TEMP_INVITE_DURATION_MINUTES 
                )
            )
            key = (guild_id, channel_id, user_id)
            self.temporary_voice_invites[key] = expiration_task

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._temporary_invites_restored:
            await self._restore_temporary_invites()
            self._temporary_invites_restored = True

    def cog_unload(self):
        for expiration_task in self.temporary_voice_invites.values():
            if not expiration_task.done():
                expiration_task.cancel()
        self.temporary_voice_invites.clear()

    async def revoke_temporary_voice_invite(self, guild_id: int, channel_id: int, user_id: int, reason: str):
        key = (guild_id, channel_id, user_id)
        expiration_task = self.temporary_voice_invites.pop(key, None)
        if expiration_task is not None and expiration_task is not asyncio.current_task() and not expiration_task.done():
            expiration_task.cancel()

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            invite_store.remove_temporary_invite(guild_id, channel_id, user_id)
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            invite_store.remove_temporary_invite(guild_id, channel_id, user_id)
            return

        member = guild.get_member(user_id)
        permission_target = member if member is not None else discord.Object(id=user_id)
        had_view_channel = invite_store.get_temporary_invite(guild_id, channel_id, user_id)

        try:
            if had_view_channel is not None:
                if not had_view_channel:
                    existing_overwrite = channel.overwrites.get(permission_target)
                    if existing_overwrite is not None:
                        new_overwrite = discord.PermissionOverwrite.from_pair(*existing_overwrite.pair())
                        new_overwrite.view_channel = None

                        allow, deny = new_overwrite.pair()
                        if allow.value == 0 and deny.value == 0:
                            await channel.set_permissions(permission_target, overwrite=None, reason=reason)
                        else:
                            await channel.set_permissions(permission_target, overwrite=new_overwrite, reason=reason)
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(
                f"Failed to revoke temporary invite permissions for user {user_id} "
                f"in channel {channel_id}: {exc}"
            )
        finally:
            invite_store.remove_temporary_invite(guild_id, channel_id, user_id)

    async def expire_temporary_voice_invite(self, guild_id: int, channel_id: int, user_id: int, duration_minutes: int):
        try:
            await asyncio.sleep(60 * duration_minutes)
        except asyncio.CancelledError:
            return

        await self.revoke_temporary_voice_invite(
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=user_id,
            reason=f"Temporary access expired after {duration_minutes} minutes."
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if after.channel is None:
            return

        await self.revoke_temporary_voice_invite(
            guild_id=member.guild.id,
            channel_id=after.channel.id,
            user_id=member.id,
            reason="Temporary access consumed."
        )

    @commands.slash_command(
        name="invite",
        description="Temporarily allow a user to view your current voice channel"
    )
    async def invite_user(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.Member, "User to invite"),
        duration: discord.Option(int, "Duration in minutes", min_value=1, max_value=90, required=False) = None
    ):
        if ctx.guild is None:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        if ctx.author.voice is None or ctx.author.voice.channel is None:
            await ctx.respond("You must be connected to a voice channel to use this command.", ephemeral=True)
            return

        voice_channel = ctx.author.voice.channel
        if not isinstance(voice_channel, discord.VoiceChannel):
            await ctx.respond("This command only works for voice channels.", ephemeral=True)
            return

        bot_member = ctx.guild.me or ctx.guild.get_member(self.bot.user.id)
        if bot_member is None:
            await ctx.respond("I could not resolve my member permissions in this server.", ephemeral=True)
            return

        if not voice_channel.permissions_for(bot_member).manage_channels:
            await ctx.respond("I need `Manage Channels` permission to update voice channel permissions.", ephemeral=True)
            return

        duration_minutes = duration if duration is not None else TEMP_INVITE_DURATION_MINUTES

        key = (ctx.guild.id, voice_channel.id, user.id)
        existing_invite = self.temporary_voice_invites.get(key)

        existing_overwrite = voice_channel.overwrites.get(user)
        had_view_channel = existing_overwrite is not None and existing_overwrite.view_channel is True

        if existing_invite is not None and not existing_invite.done():
            existing_invite.cancel()

        updated_overwrite = (
            discord.PermissionOverwrite.from_pair(*existing_overwrite.pair())
            if existing_overwrite is not None
            else discord.PermissionOverwrite()
        )
        updated_overwrite.view_channel = True

        try:
            await voice_channel.set_permissions(
                user,
                overwrite=updated_overwrite,
                reason=f"Temporary access granted by {ctx.author} for {duration_minutes} minutes."
            )
        except discord.Forbidden:
            await ctx.respond(
                "I don't have permission to change this channel's permissions for that user.",
                ephemeral=True
            )
            return
        except discord.HTTPException as exc:
            await ctx.respond(
                f"Failed to apply permissions: {exc}",
                ephemeral=True
            )
            return

        invite_store.add_temporary_invite(ctx.guild.id, voice_channel.id, user.id, had_view_channel)

        expiration_task = asyncio.create_task(
            self.expire_temporary_voice_invite(
                guild_id=ctx.guild.id,
                channel_id=voice_channel.id,
                user_id=user.id,
                duration_minutes=duration_minutes
            )
        )
        self.temporary_voice_invites[key] = expiration_task

        await ctx.respond(
            f"{user.mention} can now view `{voice_channel.name}` for {duration_minutes} minutes "
            f"or until they join the channel.",
            ephemeral=True
        )


def setup(bot):
    bot.add_cog(Invite(bot))
