import discord
import logging

from discord.ext import commands

logger = logging.getLogger("discord_event_watcher.member")
logger.setLevel(logging.INFO)


class MemberWatcher:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            event_type = "nick"
        elif before.roles != after.roles:
            event_type = "role"
        elif before.pending != after.pending:
            event_type = "pending"
        else:
            return
        server_logger_cog = self.bot.get_cog("ServerLogger")
        await server_logger_cog.member_event(before=before, after=after, event_type=event_type)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        if before.avatar.key != after.avatar.key:
            event_type = "avatar"
        elif before.global_name != after.global_name:
            event_type = "global_name"
        elif before.name != after.name:
            event_type = "username"
        elif before.discriminator != after.discriminator:
            event_type = "discriminator"
        else:
            return
        server_logger_cog = self.bot.get_cog("ServerLogger")
        await server_logger_cog.user_event(before=before, after=after, event_type=event_type)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        server_logger_cog = self.bot.get_cog("ServerLogger")
        if server_logger_cog:
            await server_logger_cog.join_leave_event(member=member, event_type="join")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        server_logger_cog = self.bot.get_cog("ServerLogger")
        if server_logger_cog:
            await server_logger_cog.join_leave_event(member=member, event_type="leave")
