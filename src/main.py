import discord
import os
from dotenv import load_dotenv
import mongo

load_dotenv()

mongo.init(os.getenv('MONGO_URI', 'mongodb://mongo:27017/wintonbot'), 'winton_bot')
bot = discord.Bot(debug_guilds=os.getenv('BOT_DEV_GUILDS', '1425571463192121354').split(';'))

COCKS = [
    "cogs.leaderboard"
]

for cock in COCKS:
    bot.load_extensions(cock)


@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")


CHANNEL_CREATE_CHANNEL_NAME = '[CREATE CHANNEL]'


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if before.channel is not None:
        channel_to_delete = before.channel
        if channel_to_delete.name != CHANNEL_CREATE_CHANNEL_NAME and len(channel_to_delete.voice_states) == 0:
            await channel_to_delete.delete(reason='Channel is empty and was therefore deleted.')

    if after.channel is not None and after.channel.name == CHANNEL_CREATE_CHANNEL_NAME:
        new_channel = await member.guild.create_voice_channel(
            name=member.display_name + "'s Channel",
            user_limit=7,
            category=after.channel.category,
            overwrites={
                member: discord.PermissionOverwrite(
                    move_members=True,
                    manage_channels=True
                )
            }
        )
        await member.move_to(new_channel)


@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!", ephemeral=True)


if __name__ == '__main__':
    bot.run(os.getenv('TOKEN'))
