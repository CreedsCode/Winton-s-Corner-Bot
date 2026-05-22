import discord
from discord.ext import commands

import glue_store


class Glue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(
        name="glue",
        description="Mark your current voice channel as permanent so it won't auto-delete",
        default_permission=False
    )
    async def glue_channel(self, ctx: discord.ApplicationContext):
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

        was_added = glue_store.add_glued_channel(ctx.guild.id, voice_channel.id)
        if was_added:
            await ctx.respond(
                f"✅ **{voice_channel.name}** is now glued and will not be auto-deleted when empty.",
                ephemeral=True
            )
            return

        await ctx.respond(
            f"ℹ️ **{voice_channel.name}** is already glued.",
            ephemeral=True
        )


def setup(bot):
    bot.add_cog(Glue(bot))
