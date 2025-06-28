from discord.ext import commands
from .youtube import Youtube


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Youtube(bot))