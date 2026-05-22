import asyncio

import discord
from discord.ext import commands


TEMP_INVITE_DURATION_SECONDS = 20 * 60


class Invite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {(guild_id, channel_id, user_id): {"previous_overwrite": PermissionOverwrite | None, "task": asyncio.Task}}
        self.temporary_voice_invites = {}

    def cog_unload(self):
        for invite_state in self.temporary_voice_invites.values():
            expiration_task = invite_state["task"]
            if not expiration_task.done():
                expiration_task.cancel()
        self.temporary_voice_invites.clear()

    @staticmethod
    def _clone_permission_overwrite(overwrite: discord.PermissionOverwrite) -> discord.PermissionOverwrite:
        allow, deny = overwrite.pair()
        return discord.PermissionOverwrite.from_pair(allow, deny)

    async def revoke_temporary_voice_invite(self, guild_id: int, channel_id: int, user_id: int, reason: str):
        key = (guild_id, channel_id, user_id)
        invite_state = self.temporary_voice_invites.pop(key, None)
        if invite_state is None:
            return

        expiration_task = invite_state["task"]
        if expiration_task is not asyncio.current_task() and not expiration_task.done():
            expiration_task.cancel()

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return

        member = guild.get_member(user_id)
        permission_target = member if member is not None else discord.Object(id=user_id)
        previous_overwrite = invite_state["previous_overwrite"]

        try:
            if previous_overwrite is None:
                await channel.set_permissions(permission_target, overwrite=None, reason=reason)
            else:
                await channel.set_permissions(permission_target, overwrite=previous_overwrite, reason=reason)
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(
                f"Failed to revoke temporary invite permissions for user {user_id} "
                f"in channel {channel_id}: {exc}"
            )

    async def expire_temporary_voice_invite(self, guild_id: int, channel_id: int, user_id: int):
        try:
            await asyncio.sleep(TEMP_INVITE_DURATION_SECONDS)
        except asyncio.CancelledError:
            return

        await self.revoke_temporary_voice_invite(
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=user_id,
            reason="Temporary /invite access expired after 20 minutes."
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if after.channel is None:
            return

        await self.revoke_temporary_voice_invite(
            guild_id=member.guild.id,
            channel_id=after.channel.id,
            user_id=member.id,
            reason="Temporary /invite access revoked after joining the voice channel."
        )

    @commands.slash_command(
        name="invite",
        description="Temporarily allow a user to view your current voice channel"
    )
    async def invite_user(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.Member, "User to invite")
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
            await ctx.respond("I need **Manage Channels** permission to update voice channel permissions.", ephemeral=True)
            return

        key = (ctx.guild.id, voice_channel.id, user.id)
        existing_invite = self.temporary_voice_invites.get(key)

        if existing_invite is None:
            existing_overwrite = voice_channel.overwrites.get(user)
            previous_overwrite = (
                self._clone_permission_overwrite(existing_overwrite)
                if existing_overwrite is not None
                else None
            )
        else:
            previous_overwrite = existing_invite["previous_overwrite"]
            existing_task = existing_invite["task"]
            if not existing_task.done():
                existing_task.cancel()

        updated_overwrite = (
            self._clone_permission_overwrite(previous_overwrite)
            if previous_overwrite is not None
            else discord.PermissionOverwrite()
        )
        updated_overwrite.view_channel = True

        try:
            await voice_channel.set_permissions(
                user,
                overwrite=updated_overwrite,
                reason=f"Temporary /invite access granted by {ctx.author} for 20 minutes."
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

        expiration_task = asyncio.create_task(
            self.expire_temporary_voice_invite(
                guild_id=ctx.guild.id,
                channel_id=voice_channel.id,
                user_id=user.id
            )
        )
        self.temporary_voice_invites[key] = {
            "previous_overwrite": previous_overwrite,
            "task": expiration_task
        }

        await ctx.respond(
            f"{user.mention} can now view **{voice_channel.name}** for 20 minutes "
            f"or until they join the channel.",
            ephemeral=True
        )


def setup(bot):
    bot.add_cog(Invite(bot))
