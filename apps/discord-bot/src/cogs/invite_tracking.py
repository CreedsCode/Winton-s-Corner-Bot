import os

import discord
from discord.ext import commands

import posthog_tracker


TARGET_INVITE_CODE = os.getenv('TARGET_INVITE_CODE', 'GbjrfMQey2')


class InviteTracking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.server_invites = {}

    @commands.Cog.listener()
    async def on_ready(self):
        self.server_invites.clear()
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                self.server_invites[guild.id] = {invite.code: invite.uses for invite in invites}
                print(f"Cached {len(invites)} invites for guild: {guild.name}")
            except discord.Forbidden:
                print(f"Missing permissions to fetch invites for guild: {guild.name}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            invites_after = await member.guild.invites()
            invites_before = self.server_invites.get(member.guild.id, {})

            used_invite = None
            for invite in invites_after:
                before_uses = invites_before.get(invite.code, 0)
                if invite.uses > before_uses:
                    used_invite = invite
                    break

            self.server_invites[member.guild.id] = {invite.code: invite.uses for invite in invites_after}

            if used_invite:
                invite_code = used_invite.code
                print(f"Member {member.name} (ID: {member.id}) joined using invite: {invite_code}")

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


def setup(bot):
    bot.add_cog(InviteTracking(bot))
