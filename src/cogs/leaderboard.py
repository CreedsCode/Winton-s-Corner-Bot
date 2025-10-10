from dataclasses import dataclass
import discord
from discord.ext import commands
from discord.ext import tasks
from mongo import get_collection
from overwatch_api import OverwatchAPIError, get_player_summary
from datetime import datetime, timezone
from pymongo import MongoClient
from dataclasses import dataclass, field

@dataclass
class PlayerStat:
    discord_id: int
    blizzard_username: str
    last_fetched: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stats: list = field(default_factory=list)


class Leaderboard(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        
        try:
            self.player_stats_collection = get_collection("PlayerStat")
            print("Player stats collection initialized")
        except Exception as e:
            print(f"Error initializing player stats collection: {str(e)}")
            raise RuntimeError("Failed to initialize player stats collection")
        
        self.fetch_player_stats.start()

    @tasks.loop(hours=1)
    async def fetch_player_stats(self):
        # get registered players from database
        try:
            for player in self.player_stats_collection.find():
                print(f"Fetching stats for {player['blizzard_username']}")
                get_player_summary_result = get_player_summary(player['blizzard_username'])
                if get_player_summary_result is not None:
                    self.player_stats_collection.update_one(
                        {"discord_id": player['discord_id']},
                        {"$push": {"stats": get_player_summary_result},
                        "$set": {"last_fetched": datetime.now(timezone.utc)}}
                        )
                else:
                    print("No data brrr.")
        except Exception as e:
            print(f"Error fetching player stats: {str(e)}")
            if isinstance(e, OverwatchAPIError) and e.status_code == 404:
                print("Player not found. Or private profile.")
                raise RuntimeError("Player not found or profile is private")
            elif isinstance(e, OverwatchAPIError):
                print("Overwatch API error occurred.")
                raise RuntimeError(f"Overwatch API error: {e.message}")
            else:
                print("Unknown error occurred.")
                raise RuntimeError("Failed to fetch player stats")

        @self.bot.slash_command(name="refreshstats", description="Refresh the stats of all registered players")
        async def register_player(ctx: discord.ApplicationContext):
            try:
                await self.fetch_player_stats()
                await ctx.respond("Stats refreshed!", ephemeral=True)
            except Exception as e:
                print(f"Error refreshing stats: {str(e)}")
                if isinstance(e, OverwatchAPIError):
                    if e.status_code == 404:
                        await ctx.respond("Player not found or have private profile.", ephemeral=True)
                        return
                    else:
                        await ctx.respond(f"Error refreshing stats: {str(e)}", ephemeral=True)
                        return
                await ctx.respond("Unknown error occurred.", ephemeral=True)

        @self.bot.slash_command(name="stats", description="Show your Overwatch 2 stats")
        @discord.option(
            name="display_type",
            description="Choose how to display the stats",
            choices=["embed", "text"],
            required=False,
            default="embed"
        )
        async def show_stats(ctx: discord.ApplicationContext, display_type: str = "embed"):
            try:
                # Get player stats from database
                player_data = self.player_stats_collection.find_one({"discord_id": ctx.author.id})

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

        @self.bot.slash_command(name="registerplayer", description="Register a player to track their stats")
        async def register_player(ctx: discord.ApplicationContext, username: str):
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
            try:
                existing_player = self.player_stats_collection.find_one({"discord_id": ctx.author.id})
                if existing_player:
                    await ctx.respond("You are already registered.", ephemeral=True)
                    return
                new_player = PlayerStat(discord_id=ctx.author.id, blizzard_username=username)
                self.player_stats_collection.insert_one(new_player.__dict__)
                # fetch adhoc
                await self.fetch_player_stats()
                await ctx.respond(f"Successfully registered {username}!", ephemeral=True)
                return 
            except Exception as e:
                await ctx.respond("An error occurred while registering. Please try again later.", ephemeral=True)
                return 

def setup(bot: discord.Bot):
    print("Loading Leaderboard Cog")
    bot.add_cog(Leaderboard(bot))