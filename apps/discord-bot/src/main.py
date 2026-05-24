import os

import discord
from dotenv import load_dotenv
import db
# import mongo
import posthog_tracker

load_dotenv()

# Initialize database
db.init_db()

# mongo.init(os.getenv('MONGO_URI', 'mongodb://mongo:27017/wintonbot'), 'winton_bot')
posthog_tracker.init()

bot = discord.Bot(debug_guilds=os.getenv('BOT_DEV_GUILDS', '1425571463192121354').split(';'))

EXTENSIONS = [
    "commands.config",
    "commands.vcusers",
    "commands.invite",
    "cogs.invite_tracking",
    "cogs.temporary_channels",
    # "cogs.leaderboard"
]

for extension in EXTENSIONS:
    bot.load_extensions(extension)


if __name__ == '__main__':
    try:
        bot.run(os.getenv('TOKEN'))
    finally:
        posthog_tracker.shutdown()
        # mongo.close()
