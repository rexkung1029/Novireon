import discord
import logging

from discord.ext import commands

logger = logging.getLogger("discord_event_watcher.voice")
logger.setLevel(logging.INFO)


class VoiceWatcher:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        server_logger_cog = self.bot.get_cog("ServerLogger")
        if server_logger_cog:
            await server_logger_cog.voice_event(member=member, before=before, after=after)
