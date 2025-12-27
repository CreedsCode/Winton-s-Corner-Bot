import discord
import os
from dotenv import load_dotenv
import mongo
import posthog_tracker

load_dotenv()

mongo.init(os.getenv('MONGO_URI', 'mongodb://mongo:27017/wintonbot'), 'winton_bot')
posthog_tracker.init()

bot = discord.Bot(debug_guilds=os.getenv('BOT_DEV_GUILDS', '1425571463192121354').split(';'))

# Store invites to track which one was used
server_invites = {}

# Target invite code to track
TARGET_INVITE_CODE = os.getenv('TARGET_INVITE_CODE', 'GbjrfMQey2')

COCKS = [
    "cogs.leaderboard"
]

for cock in COCKS:
    bot.load_extensions(cock)


@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")
    
    # Cache invites for all guilds
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            server_invites[guild.id] = {invite.code: invite.uses for invite in invites}
            print(f"Cached {len(invites)} invites for guild: {guild.name}")
        except discord.Forbidden:
            print(f"Missing permissions to fetch invites for guild: {guild.name}")
    
    # start leaderboard updates
    leaderboard_cog = bot.get_cog("Leaderboard")
    if leaderboard_cog:
        await leaderboard_cog.update_leaderboard()


CHANNEL_CREATE_CHANNEL_NAME = '[CREATE CHANNEL]'


@bot.event
async def on_member_join(member: discord.Member):
    """Track which invite was used when a member joins"""
    try:
        # Fetch current invites
        invites_after = await member.guild.invites()
        invites_before = server_invites.get(member.guild.id, {})
        
        # Find which invite was used by comparing usage counts
        used_invite = None
        for invite in invites_after:
            before_uses = invites_before.get(invite.code, 0)
            if invite.uses > before_uses:
                used_invite = invite
                break
        
        # Update cached invites
        server_invites[member.guild.id] = {invite.code: invite.uses for invite in invites_after}
        
        if used_invite:
            invite_code = used_invite.code
            print(f"Member {member.name} (ID: {member.id}) joined using invite: {invite_code}")
            
            # Store join event in MongoDB
            joins_collection = mongo.get_collection('invite_joins')
            join_data = {
                'user_id': str(member.id),
                'username': member.name,
                'discriminator': member.discriminator,
                'invite_code': invite_code,
                'guild_id': str(member.guild.id),
                'guild_name': member.guild.name,
                'joined_at': member.joined_at,
                'created_at': member.created_at,
                'is_bot': member.bot
            }
            joins_collection.insert_one(join_data)
            
            # Track conversion in PostHog if it matches target invite
            if invite_code == TARGET_INVITE_CODE:
                posthog_tracker.track_conversion(
                    user_id=str(member.id),
                    username=member.name,
                    invite_code=invite_code,
                    properties={
                        'guild_name': member.guild.name,
                        'account_age_days': (member.joined_at - member.created_at).days if member.joined_at and member.created_at else None,
                        'is_bot': member.bot
                    }
                )
        else:
            print(f"Could not determine invite used by {member.name}")
            
    except discord.Forbidden:
        print(f"Missing permissions to fetch invites in guild: {member.guild.name}")
    except Exception as e:
        print(f"Error tracking member join: {e}")


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


@bot.slash_command(name="invite_stats", description="View invite conversion statistics")
async def invite_stats(ctx: discord.ApplicationContext, invite_code: str = TARGET_INVITE_CODE):
    """Display statistics for a specific invite code"""
    try:
        joins_collection = mongo.get_collection('invite_joins')
        
        # Get all joins for this invite code
        joins = list(joins_collection.find({'invite_code': invite_code}))
        total_joins = len(joins)
        
        # Get unique users (excluding bots)
        unique_users = len([j for j in joins if not j.get('is_bot', False)])
        bots = total_joins - unique_users
        
        embed = discord.Embed(
            title=f"📊 Invite Statistics: {invite_code}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Total Joins", value=str(total_joins), inline=True)
        embed.add_field(name="Unique Users", value=str(unique_users), inline=True)
        embed.add_field(name="Bots", value=str(bots), inline=True)
        
        if joins:
            # Get most recent joins
            recent = sorted(joins, key=lambda x: x.get('joined_at', ''), reverse=True)[:5]
            recent_text = '\n'.join([f"• {j['username']} - <t:{int(j['joined_at'].timestamp())}:R>" for j in recent if j.get('joined_at')])
            if recent_text:
                embed.add_field(name="Recent Joins", value=recent_text, inline=False)
        
        await ctx.respond(embed=embed, ephemeral=True)
        
    except Exception as e:
        await ctx.respond(f"Error fetching stats: {str(e)}", ephemeral=True)


if __name__ == '__main__':
    try:
        bot.run(os.getenv('TOKEN'))
    finally:
        posthog_tracker.shutdown()
        mongo.close()
