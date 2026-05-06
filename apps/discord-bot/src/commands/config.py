import discord
from discord.ext import commands


class Configure(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    config = discord.SlashCommandGroup(
        "config",
        "Configuration commands",
        default_permission=False
    )

    config_gs = config.create_subgroup(
        "gameserver",
        "Game server related configurations",
    )

    @config_gs.command(
        name="minecraft",
        description="Set the minecraft server address"
    )
    async def set_mc_server_address(self, ctx, server_address: str = None):
        if server_address is None:
            await ctx.respond(
                f"Successfully removed the minecraft server address.",
                ephemeral=True)
            return

        await ctx.respond(
            f"Successfully set the minecraft server address to `{server_address}`.",
            ephemeral=True)


def setup(bot):
    bot.add_cog(Configure(bot))
