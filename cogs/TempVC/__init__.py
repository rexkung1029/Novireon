import logging
from .temp_vc_commands import TempVCCommands
from .setup import TempVCSetup

_log = logging.getLogger(__name__)

async def setup(bot):
    """
    為 Bot 載入 TempVC 功能的所有相關 Cog。
    """
    await bot.add_cog(TempVCCommands(bot))
    await bot.add_cog(TempVCSetup(bot))
    _log.info("TempVC module (both commands and setup) loaded successfully.")