from discord.ext import commands
from .general import General

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))