from discord.ext import commands
from .ping import PingCommands
from .miq import MIQ


class Utility(commands.Cog, PingCommands, MIQ):
    def __init__(self, bot: commands.Bot):
        commands.Cog.__init__(self)
        MIQ.__init__(self, bot)
        PingCommands.__init__(self, bot)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
