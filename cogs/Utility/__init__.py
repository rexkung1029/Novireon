from discord.ext import commands
from .ping import PingCommands

class Utility(commands.Cog, PingCommands):
    def __init__(self, bot: commands.Bot):
        commands.Cog.__init__(self)
        PingCommands.__init__(self, bot)

async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
