from datetime import datetime, timezone
import discord
import os # default module
from dotenv import load_dotenv
from discord.ext import tasks
from cogs import leaderboard
import mongo

load_dotenv() 

mongo.init(os.getenv('MONGO_URI', 'mongodb://mongo:27017/wintonbot'), 'winton_bot')

DEV_GUILD_ID = 1425571463192121354
DEV_GUILDS = [DEV_GUILD_ID]

bot = discord.Bot(debug_guilds=DEV_GUILDS)

COCKS = [
    "cogs.leaderboard"
    ]

for cock in COCKS:
   bot.load_extensions(cock)


@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")
    # if mongo.is_initialized():
    #     print("MongoDB is initialized.")
    # else:
    #     print("MongoDB is not initialized.")

@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!", ephemeral=True)


bot.run(os.getenv('TOKEN')) 