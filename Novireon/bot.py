import discord
import logging
import os

from discord.ext import commands
from pathlib import Path

from Novireon.cogs.Utility.role_giver import RoleGiverView

logger = logging.getLogger("Novireon")


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        self.add_view(RoleGiverView())

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return

        await super().on_command_error(ctx, error)


bot = Bot()


@bot.event
async def on_ready():
    await load_all_cogs(bot)
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    logger.info("syncing...")
    await bot.tree.sync()
    logging.info("已連接至以下伺服器")
    for guild in bot.guilds:
        logging.info(f" - {guild.name} (ID: {guild.id})")
    logger.info(">>Bot is online<<")


@bot.event
async def on_disconnect():
    logger.info("Bot disconnected.")


async def load_all_cogs(bot: commands.Bot):
    loaded_packages = []
    base_dirs = ["cogs", "src"]
    for base in base_dirs:
        for item_name in os.listdir(Path(__file__).parent / base):
            item_path = Path(__file__).parent / base / item_name
            if os.path.isdir(item_path) and "__init__.py" in os.listdir(item_path):
                module_path = f"Novireon.{base}.{item_name}"
                try:
                    await bot.load_extension(module_path)
                    loaded_packages.append(module_path)
                except Exception as e:
                    logger.error(f"無法載入{module_path}: {e}", exc_info=True)
    for package in loaded_packages:
        logger.info(f"已載入{package.split(".")[-1]}模組")
