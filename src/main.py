from dataclasses import dataclass, field
from datetime import datetime, timezone
import discord
import os # default module
from dotenv import load_dotenv
from discord.ext import tasks
from pymongo import MongoClient
from overwatch_api import get_player_summary

## mongodb
def initMongoDB():
    global DB
    global PLAYERSTATCOLLECTION
    try:
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://mongo:27017/wintonbot')
        client = MongoClient(mongo_uri, 
                           serverSelectionTimeoutMS=5000,  # 5 second timeout
                           connectTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        print("MongoDB connection successful")
        
        db = client['winton_bot']
        DB = db
        PLAYERSTATCOLLECTION = DB["PlayerStat"]
    except Exception as e:
        print(f"MongoDB connection error: {str(e)}")
        return None
    
    return db

## player collection class
@dataclass
class PlayerStat:
    discord_id: int
    blizzard_username: str
    last_fetched: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stats: list = field(default_factory=list)

## end mongodb


DEV_GUILD_ID = 1425571463192121354
DEV_GUILDS = [DEV_GUILD_ID]

DB = None
PLAYERSTATCOLLECTION = None
load_dotenv() 
bot = discord.Bot(debug_guilds=DEV_GUILDS)


@tasks.loop(hours=1)
async def fetch_player_stats():
    # get registered players from database
    try:
        global DB
        global PLAYERSTATCOLLECTION
        if DB is not None and PLAYERSTATCOLLECTION is not None:
            players = PLAYERSTATCOLLECTION.find()
            for player in players:
                print(f"Fetching stats for {player['blizzard_username']}")
                get_player_summary_result = get_player_summary(player['blizzard_username'])
                if get_player_summary_result is None:
                    raise Exception("Failed to fetch player summary")
                
                PLAYERSTATCOLLECTION.update_one(
                    {"discord_id": player['discord_id']},
                    {"$push": {"stats": get_player_summary_result},
                     "$set": {"last_fetched": datetime.now(timezone.utc)}}
                )
        else:
            print("Database connection not initialized.")
    except Exception as e:
        print(f"Error fetching player stats: {str(e)}")


@bot.event
async def on_ready():
    fetch_player_stats.start()

    ## test and init mongodb connection
    try:
        initMongoDB()
        print("MongoDB initialized")
    except Exception as e:
        print(f"Error initializing MongoDB: {str(e)}")
        return 0

    print(f"{bot.user} is ready and online!")


@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!", ephemeral=True)



@bot.slash_command(name="refreshstats", description="Refresh the stats of all registered players")
async def register_player(ctx: discord.ApplicationContext):
    await fetch_player_stats()
    await ctx.respond("Stats refreshed!", ephemeral=True)


@bot.slash_command(name="stats", description="Show your Overwatch 2 stats")
@discord.option(
    name="display_type",
    description="Choose how to display the stats",
    choices=["embed", "text"],
    required=False,
    default="embed"
)
async def show_stats(ctx: discord.ApplicationContext, display_type: str = "embed"):
    global DB
    global PLAYERSTATCOLLECTION
    
    try:
        # Get player stats from database
        player_data = PLAYERSTATCOLLECTION.find_one({"discord_id": ctx.author.id})
        
        if not player_data or not player_data.get('stats'):
            await ctx.respond("No stats found! Please make sure you're registered.", ephemeral=True)
            return
        
        # Get the most recent stats
        latest_stats = player_data['stats'][-1]
        
        # Create embed
        embed = discord.Embed(
            title=f"Overwatch 2 Stats - {latest_stats['username']}",
            color=discord.Color.blue(),
            timestamp=datetime.fromtimestamp(latest_stats['last_updated_at'])
        )
        
        # Set thumbnail to player avatar
        embed.set_thumbnail(url=latest_stats['avatar'])
        
        # Set banner image to namecard
        embed.set_image(url=latest_stats['namecard'])
        
        # Add title field
        if latest_stats.get('title'):
            embed.add_field(name="Title", value=latest_stats['title'], inline=True)
        
        # Add endorsement level
        if latest_stats.get('endorsement'):
            embed.add_field(
                name="Endorsement Level",
                value=f"Level {latest_stats['endorsement']['level']}",
                inline=True
            )
        
        # Add competitive stats if available
        if latest_stats.get('competitive') and latest_stats['competitive'].get('pc'):
            comp_data = latest_stats['competitive']['pc']
            embed.add_field(name="\u200b", value="**Competitive Rankings**", inline=False)
            
            # Tank rank
            if comp_data.get('tank'):
                tank = comp_data['tank']
                embed.add_field(
                    name="Tank",
                    value=f"{tank['division'].capitalize()} {tank['tier']}",
                    inline=True
                )
            
            # Damage rank
            if comp_data.get('damage'):
                damage = comp_data['damage']
                embed.add_field(
                    name="Damage",
                    value=f"{damage['division'].capitalize()} {damage['tier']}",
                    inline=True
                )
            
            # Support rank
            if comp_data.get('support'):
                support = comp_data['support']
                embed.add_field(
                    name="Support",
                    value=f"{support['division'].capitalize()} {support['tier']}",
                    inline=True
                )
        
        # Add footer with last update time
        embed.set_footer(text="Last updated")
        
        if display_type == "embed":
            await ctx.respond(embed=embed)
        else:
            # Create plain text message
            text_message = [
                f"**Overwatch 2 Stats - {latest_stats['username']}**",
                f"Title: {latest_stats.get('title', 'N/A')}",
                f"Endorsement Level: {latest_stats['endorsement']['level'] if latest_stats.get('endorsement') else 'N/A'}"
            ]
            
            # Add competitive stats if available
            if latest_stats.get('competitive') and latest_stats['competitive'].get('pc'):
                comp_data = latest_stats['competitive']['pc']
                text_message.append("\n**Competitive Rankings**")
                
                # Tank rank
                if comp_data.get('tank'):
                    tank = comp_data['tank']
                    text_message.append(f"Tank: {tank['division'].capitalize()} {tank['tier']}")
                
                # Damage rank
                if comp_data.get('damage'):
                    damage = comp_data['damage']
                    text_message.append(f"Damage: {damage['division'].capitalize()} {damage['tier']}")
                
                # Support rank
                if comp_data.get('support'):
                    support = comp_data['support']
                    text_message.append(f"Support: {support['division'].capitalize()} {support['tier']}")
            
            # Add last updated time
            text_message.append(f"\nLast updated: <t:{latest_stats['last_updated_at']}:R>")
            
            await ctx.respond('\n'.join(text_message))
        
    except Exception as e:
        print(f"Error showing stats: {str(e)}")
        await ctx.respond("An error occurred while fetching your stats!", ephemeral=True)
@bot.slash_command(name="registerplayer", description="Register a player to track their stats")
async def register_player(ctx: discord.ApplicationContext, username: str):
    global DB
    global PLAYERSTATCOLLECTION
    username = username.strip()
    # validate for valid blizzard username
    # check for presence of one '#'
    if not username or '#' not in username:
        await ctx.respond("Please provide a valid Blizzard username (e.g., Player#123456).", ephemeral=True)
        return
    # check for tag length
    tag = username.split('#')[-1]
    if len(tag) > 6 or  len(tag) < 4 or not tag.isdigit():
        await ctx.respond("Please provide a valid Blizzard username with a tag (e.g., Player#123456).", ephemeral=True)
        return
    
    # store in database
    if DB is not None and PLAYERSTATCOLLECTION is not None:
        try:
            existing_player = PLAYERSTATCOLLECTION.find_one({"discord_id": ctx.author.id})
            if existing_player:
                await ctx.respond("You are already registered.", ephemeral=True)
                return
            new_player = PlayerStat(discord_id=ctx.author.id, blizzard_username=username)
            PLAYERSTATCOLLECTION.insert_one(new_player.__dict__)
            # fetch adhoc
            await fetch_player_stats()
            await ctx.respond(f"Successfully registered {username}!", ephemeral=True)
            return 
        except Exception as e:
            await ctx.respond("An error occurred while registering. Please try again later.", ephemeral=True)
            return 

    else:
        await ctx.respond("Database connection not initialized.", ephemeral=True)
        return 

bot.run(os.getenv('TOKEN')) 