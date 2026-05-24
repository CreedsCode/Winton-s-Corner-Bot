import random

import discord
from discord.ext import commands


class VcUsers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="vcusers", description="Get a list of names of users in your current voice channel")
    async def vc_users(self, ctx: discord.ApplicationContext):
        if ctx.author.voice is None:
            await ctx.respond("You are not in a voice channel.", ephemeral=True)
            return

        names = [f"{member.display_name} <{member.name}>" for member in ctx.author.voice.channel.members]
        random.shuffle(names)
        await ctx.respond("Users in your voice channel:\n\n" + "\n".join(names), ephemeral=True)


def setup(bot):
    bot.add_cog(VcUsers(bot))
