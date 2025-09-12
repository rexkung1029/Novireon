from discord.ext import commands
from .core.music_main import Music
from .core.music_setup import MusicSetup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Music_Core")


async def setup(bot: commands.Bot) -> None:
    for vc in bot.voice_clients:
        try:
            await vc.disconnect(force=True)
            print("a")
        except Exception as e:
            logger.error(f"cleaning VC connect error: {e}")
    await bot.add_cog(Music(bot))
    await bot.add_cog(MusicSetup(bot))
