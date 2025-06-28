import discord

from discord import app_commands
from discord.ext import commands


class General(commands.Cog):
    def __init__(self,bot:commands.Bot):
        self.bot = bot
    


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
