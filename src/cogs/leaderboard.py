import logging
from dataclasses import dataclass
import discord
import requests
from aiohttp import request
from discord.ext import commands
from discord.ext import tasks
from mongo import get_collection
from overwatch_api import OverwatchAPI
from datetime import datetime, timezone
from pymongo import MongoClient
from dataclasses import dataclass, field

overwatch_api = OverwatchAPI()


@dataclass
class PlayerStat:
    discord_id: int
    blizzard_username: str
    last_fetched: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stats: list = field(default_factory=list)


class Leaderboard(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        self.leaderboard_channel = 1426238135876190321
        self.rank_values = {
            'grandmaster': 7,
            'master': 6,
            'diamond': 5,
            'platinum': 4,
            'gold': 3,
            'silver': 2,
            'bronze': 1
        }

        try:
            self.player_stats_collection = get_collection("PlayerStat")
            print("Player stats collection initialized")
        except Exception as e:
            print(f"Error initializing player stats collection: {str(e)}")
            raise RuntimeError("Failed to initialize player stats collection")

        self.fetch_player_stats.start()
        self.update_leaderboard.start()

    @tasks.loop(hours=1)
    async def fetch_player_stats(self):
        for player in self.player_stats_collection.find():
            battletag = player['blizzard_username']
            logging.debug("Fetching player stats for %s" % battletag)

            try:
                get_player_summary_result = overwatch_api.get_player_summary(battletag)
                if get_player_summary_result is not None:
                    self.player_stats_collection.update_one(
                        {"discord_id": player['discord_id']},
                        {"$push": {"stats": get_player_summary_result},
                         "$set": {"last_fetched": datetime.now(timezone.utc)}}
                    )
            except requests.HTTPError as e:
                logging.error("Failed to fetch or save player stats for %s: %s" % (battletag, str(e)))
            except Exception as e:
                logging.error("Unknown error while fetching stats for %s: %s" % (battletag, str(e)))

        @self.bot.slash_command(name="refreshstats", description="Refresh the stats of all registered players")
        async def register_player(ctx: discord.ApplicationContext):
            try:
                await self.fetch_player_stats()
                await ctx.respond("Attempted to refresh stats", ephemeral=True)
            except Exception as e:
                await ctx.respond("Unknown error occured while trying to force-refresh stats", ephemeral=True)

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

    def get_player_rank_value(self, player_stats):
        if not player_stats.get('competitive') or not player_stats['competitive'].get('pc'):
            return -1
        
        comp_data = player_stats['competitive']['pc']
        if not comp_data:
            return -1
        
        division = comp_data.get('division', '').lower()
        tier = comp_data.get('tier', 5)  # Default to lowest tier
        
        base_value = self.rank_values.get(division, 0)
        return base_value * 5 + (5 - tier)

    async def create_role_leaderboard(self, role: str):
        all_players = list(self.player_stats_collection.find())
        ranked_players = []
        
        for player in all_players:
            if not player.get('stats') or not player['stats'][-1].get('competitive'):
                continue
                
            latest_stats = player['stats'][-1]
            comp_data = latest_stats['competitive'].get('pc', {})
            
            if not comp_data or not comp_data.get(role):
                continue
                
            role_data = comp_data[role]
            ranked_players.append({
                'discord_id': player['discord_id'],
                'username': latest_stats['username'],
                'blizzard_username': player['blizzard_username'],
                'avatar': latest_stats['avatar'],
                'division': role_data['division'],
                'tier': role_data['tier'],
                'rank_icon': role_data['rank_icon']
            })
        
        # Sort players by division and tier
        ranked_players.sort(key=lambda x: (
            self.rank_values.get(x['division'].lower(), 0) * 5 + (5 - x['tier'])
        ), reverse=True)
        
        return ranked_players[:10]  # Return top 10

    @tasks.loop(minutes=1)
    async def update_leaderboard(self):
        try:
            channel = await self.bot.get_channel(self.leaderboard_channel)
            if not channel:
                print("Could not find leaderboard channel")
                return

            # # get latest messages to edit
            # async for message in channel.history(limit=10):
            #     await message.delete()

            roles = ['tank', 'damage', 'support']
            role_emojis = {
                'tank': '🛡️',
                'damage': '⚔️',
                'support': '💉'
            }

            for role in roles:
                ranked_players = await self.create_role_leaderboard(role)
                
                if not ranked_players:
                    continue

                # Create leaderboard message
                message_lines = [
                    f"**{role_emojis[role]} Top {role.capitalize()} Players {role_emojis[role]}**",
                    "```md",  # Start of markdown-style code block
                ]

                for idx, player in enumerate(ranked_players, 1):
                    member = await self.bot.fetch_user(player['discord_id'])
                    discord_name = member.name if member else "Unknown"
                    
                    # Format each player entry
                    rank_display = f"{idx:2d}."  # Right-aligned number with dot
                    division_display = f"{player['division'].capitalize()} {player['tier']}"
                    player_line = f"{rank_display} {discord_name:<20} - {division_display:<15} ({player['blizzard_username']})"
                    message_lines.append(player_line)

                message_lines.append("```")  # End of code block
                message_lines.append(f"Last updated: <t:{int(datetime.now(timezone.utc).timestamp())}:R>")
                
                # Send the formatted message
                await channel.send('\n'.join(message_lines))

        except Exception as e:
            print(f"Error updating leaderboard: {str(e)}")


    # @update_leaderboard.before_loop
    # async def before_update_leaderboard(self):
    #     await self.bot.wait_until_ready()

    @commands.slash_command(name="updateleaderboard", description="Manually update the leaderboard")
    async def update_leaderboard_command(self, ctx: discord.ApplicationContext):
        try:
            await self.update_leaderboard()
            await ctx.respond("Leaderboard updated!", ephemeral=True)
        except Exception as e:
            print(f"Error updating leaderboard: {str(e)}")
            await ctx.respond("An error occurred while updating the leaderboard!", ephemeral=True)

    @commands.slash_command(name="registerplayer", description="Register a player to track their stats")
    async def register_player(self, ctx: discord.ApplicationContext, username: str):
        username = username.strip()
        # validate for valid blizzard username
        # check for presence of one '#'
        if not username or '#' not in username:
            await ctx.respond("Please provide a valid Blizzard username (e.g., Player#123456).", ephemeral=True)
            return
        # check for tag length
        tag = username.split('#')[-1]
        if len(tag) > 6 or len(tag) < 4 or not tag.isdigit():
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
        except Exception as e:
            await ctx.respond("An error occurred while registering. Please try again later.", ephemeral=True)


    @tasks.loop(hours=1)
    async def update_leaderboard_message(self):
        channel = self.bot.get_channel(self.leaderboard_channel)
        if channel is None:
            print("Leaderboard channel not found.")
            raise RuntimeError("Leaderboard channel not found")

        players = self.player_stats_collection.find()
        player_stats = []
        rank_order = {
            "champion": 0, "grandmaster": 1, "master": 2, "diamond": 3,
            "platinum": 4, "gold": 5, "silver": 6, "bronze": 7, "unranked": 8
        }

        for player in players:
            # Get latest stats
            stats_list = player.get('stats', [])
            if not stats_list:
                continue
            latest_stats = stats_list[-1]
            comp = latest_stats.get('competitive', {}).get('pc', {})
            # Determine top role and rank
            roles = ['tank', 'damage', 'support']
            top_role = None
            top_rank = None
            for role in roles:
                role_data = comp.get(role)
                if role_data and role_data.get('division'):
                    if not top_role or rank_order[role_data['division'].lower()] < rank_order.get(top_rank, 8):
                        top_role = role
                        top_rank = role_data['division'].lower()
            # Prepare rank breakdown
            player_stats.append({
                'blizzard_username': player['blizzard_username'],
                'top_role': top_role if top_role else 'unranked',
                'top_rank': top_rank if top_rank else 'unranked',
                'tank_rank': comp.get('tank', {}).get('division', 'N/A') if comp.get('tank') else 'N/A',
                'damage_rank': comp.get('damage', {}).get('division', 'N/A') if comp.get('damage') else 'N/A',
                'support_rank': comp.get('support', {}).get('division', 'N/A') if comp.get('support') else 'N/A',
                'open_rank': comp.get('open', {}).get('division', 'N/A') if comp.get('open') else 'N/A'
            })

        # Sort by highest rank (lowest value in rank_order)
        player_stats.sort(key=lambda x: rank_order.get(x['top_rank'], 8))

        leaderboard_message = "**Overwatch 2 Leaderboard**\n\n"
        leaderboard_message += "Discord Username | Top Role | Top Rank\n"
        for player in player_stats:
            leaderboard_message += f"{player['blizzard_username']} | {player['top_role'].capitalize()} | {player['top_rank'].capitalize()}\n"

        leaderboard_message += "\n**Rank Breakdown**\n"
        leaderboard_message += "Discord Username | Tank | Damage | Support | Open\n"
        for player in player_stats:
            leaderboard_message += (
                f"{player['blizzard_username']} | "
                f"{player['tank_rank']} | {player['damage_rank']} | "
                f"{player['support_rank']} | {player['open_rank']}\n"
            )

        # Try to update previous leaderboard message
        async for message in channel.history(limit=100):
            if message.author == self.bot.user:
                try:
                    await message.edit(content=leaderboard_message)
                    print("Leaderboard message updated.")
                    return
                except Exception as e:
                    print(f"Error updating leaderboard message: {str(e)}")
                    raise RuntimeError("Failed to update leaderboard message")
        # If not found, send a new message
        await channel.send(content=leaderboard_message)

def setup(bot: discord.Bot):
    print("Loading Leaderboard Cog")
    bot.add_cog(Leaderboard(bot))
