import discord
import os
from dotenv import load_dotenv
import mongo

load_dotenv()

mongo.init(os.getenv('MONGO_URI', 'mongodb://mongo:27017/wintonbot'), 'winton_bot')
bot = discord.Bot(debug_guilds=[1425571463192121354])

COCKS = [
    "cogs.leaderboard"
]

for cock in COCKS:
    bot.load_extensions(cock)


@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")


@bot.event()
async def on_join():
    print(f"{bot.user} is ready and online!")


@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!", ephemeral=True)


bot.run(os.getenv('TOKEN'))
